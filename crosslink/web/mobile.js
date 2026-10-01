/* CrossLink 手机端：即打即输 / 编辑后发送 / 功能键 */
(() => {
  const $ = (id) => document.getElementById(id);
  let sid = null;
  let sent = "";              // 已经镜像到电脑的文字（即打即输的基线）
  let acked = "";             // 电脑端确认收到的文字（兜底重发用）
  let lastSent = "";          // 最近一次完整发送，供「还原」用
  let mode = "live";
  let timer = null;
  // 这个开关是“这台手机自己的发送习惯”，存本地，重开页面仍然有效
  let settings = {
    enter_after_send: (() => {
      try { return localStorage.getItem('crosslink.enter') === '1'; } catch (e) { return false; }
    })(),
  };

  const post = async (path, data) => {
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      return await res.json();
    } catch (err) {
      console.warn(err);
      return { ok: false };
    }
  };

  const toast = (text, ms = 1800) => {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = text;
    $("toasts").appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      setTimeout(() => el.remove(), 240);
    }, ms);
  };

  /** 输入页底下那行提示（和 App 的 notice 一样） */
  const say = (text, warn = false) => {
    const el = $("notice");
    if (!el) return;
    el.textContent = text || "";
    el.className = warn ? "notice warn" : "notice";
  };

  /* ---------------- 涟漪 ---------------- */
  document.addEventListener("pointerdown", (e) => {
    const el = e.target.closest(".fx, .key, .send, .round");
    if (!el) return;
    el.classList.add("fx", "pressing");
    const r = el.getBoundingClientRect();
    el.style.setProperty("--rx", `${e.clientX - r.left}px`);
    el.style.setProperty("--ry", `${e.clientY - r.top}px`);
    el.style.setProperty("--rs", (Math.max(r.width, r.height) / 8 * 2.4).toFixed(1));
    const done = () => {
      el.classList.remove("pressing");
      el.classList.add("rippling");
      setTimeout(() => el.classList.remove("rippling"), 520);
      window.removeEventListener("pointerup", done);
      window.removeEventListener("pointercancel", done);
    };
    window.addEventListener("pointerup", done);
    window.addEventListener("pointercancel", done);
  });

  /* ---------------- 连接 ---------------- */
  const deviceName = (() => {
    const ua = navigator.userAgent;
    if (/iPhone/.test(ua)) return "iPhone";
    if (/iPad/.test(ua)) return "iPad";
    if (/Android/.test(ua)) {
      const m = ua.match(/Android[^;]*;\s*([^;)]+)/);
      return m ? m[1].trim().split(" ")[0] : "安卓手机";
    }
    if (/Macintosh/.test(ua)) return "Mac";
    if (/Windows/.test(ua)) return "Windows";
    return "手机";
  })();

  async function hello(pin) {
    const res = await post("/api/hello", { name: deviceName, pin: pin || "" });
    if (res.ok) {
      sid = res.sid;
      settings = Object.assign(settings, res.settings || {});
      // 语言：电脑端设了就跟随电脑端，没设就按手机浏览器的语言
      let savedLang = null;
      try { savedLang = localStorage.getItem("crosslink.lang"); } catch (e) { /* 忽略 */ }
      if (window.I18N) window.I18N.set(savedLang || res.lang);
      $("pc-name").textContent = res.pc || "电脑";
      // 会话过期重新握手时这个连接页早就不在了，得判空，
      // 不然这里抛异常，整条"重连并补发"的路都会断掉（字就同步不上去了）
      const gate = $("gate");
      if (gate) {
        gate.classList.add("hide");
        setTimeout(() => gate.remove(), 420);
      }
      subscribe();
      return true;
    }
    if (res.error && res.error.indexOf("配对码") >= 0) {
      $("gate-text").textContent = "这台电脑需要 4 位配对码（电脑窗口上有）";
      $("pin-box").style.display = "flex";
      $("pin-input").focus();
      return false;
    }
    $("gate-text").textContent = "连接失败，稍后重试…";
    return false;
  }

  $("pin-go").onclick = async () => {
    const pin = $("pin-input").value.trim();
    if (pin.length < 4) return toast("请输入 4 位配对码");
    if (!(await hello(pin))) toast("配对码不正确");
  };
  $("pin-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("pin-go").click();
  });

  /* ---------------- 事件流 ---------------- */
  let es = null;

  function subscribe() {
    // 重新握手时会再调一次：先把上一条连接关掉，不然页面里会挂两条流
    if (es) { try { es.close(); } catch (e) { /* 忽略 */ } }
    es = new EventSource("/api/events");
    es.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "state" || msg.type === "settings") {
        const state = msg.type === "state" ? msg : msg.state;
        if (state && window.I18N) window.I18N.set(state.lang);
        if (state && state.settings) {
          const local = settings.enter_after_send;
          settings = Object.assign(settings, state.settings);
          try {
            if (localStorage.getItem('crosslink.enter') !== null) {
              settings.enter_after_send = local;
            }
          } catch (e) { /* 忽略 */ }
        }
        if (state && state.app) $("pc-name").textContent = state.app.name;
        if (state && state.urls && state.urls[0]) $("addr").textContent = state.urls[0];
        if (state && state.target) renderTarget(state.target);
        if (state && state.logs) renderLogs(state.logs);
        if (state && state.app && $("about-ver")) {
          $("about-ver").textContent = "v" + state.app.version;
        }
        if (state && state.update) paintUpdate(state.update);
        $("sw-enter").classList.toggle("on", !!settings.enter_after_send);
      } else if (msg.type === "target") {
        renderTarget(msg.target);
      } else if (msg.type === "update") {
        paintUpdate(msg.update);
      } else if (msg.type === "urls" && msg.urls[0]) {
        $("addr").textContent = msg.urls[0];
      }
    };
    es.onerror = () => {
      // 和 App 一样：连不上只在状态行提示一句，页面别的地方不动
      const s = $("status");
      if (s) { s.textContent = "连接中断，正在重连…"; s.className = "status warn"; }
    };
    es.onopen = () => {
      const s = $("status");
      if (s) { s.textContent = ""; s.className = "status"; }
    };
  }

  function renderTarget(target) {
    const bar = $("target-bar");
    const dot = $("target-dot");
    if (!target || !target.app) {
      bar.className = "target";
      dot.className = "dot";
      $("target-text").textContent = "先在电脑上点一下要输入的窗口";
      return;
    }
    if (target.self) {
      bar.className = "target";
      dot.className = "dot";
      $("target-text").textContent = "电脑焦点在 CrossLink 自己身上，点一下目标程序";
      return;
    }
    bar.className = "target ok";
    dot.className = "dot ok";
    $("target-text").textContent = "电脑已就绪：" + (target.title || target.app);
  }

  /** 电脑端那边查到的版本情况，照实显示（查不到就说查不到） */
  function paintUpdate(info) {
    const el = $("upd-text");
    if (!el || !info) return;
    if (!info.checked_at) el.textContent = "还没检查过";
    else if (!info.ok) el.textContent = info.error || "检查失败";
    else if (info.newer) el.textContent = "电脑端有新版本 v" + info.latest + "（当前 v" + info.current + "）";
    else el.textContent = "已是最新版本 v" + info.current;
  }

  /* ---------------- 发送 ----------------
     一条指令一条指令按顺序发：以前打完字就发一条，两条请求会同时在路上，
     电脑端先收到后发的那条、后收到先发的那条，最后那段字就少一截。
     现在所有指令串成一条链，前一条发完才发下一条。 */
  let chain = Promise.resolve();

  function send(ops) {
    chain = chain.then(() => sendOnce(ops)).catch(() => {});
    return chain;
  }

  async function sendOnce(ops) {
    if (!sid) return;
    for (let attempt = 0; attempt < 3; attempt++) {
      const res = await post("/api/op", { sid, ops });
      if (res && res.ok) {
        ops.forEach((op) => {
          if (op.k === "sync") acked = op.text;
          if (op.k === "reset") acked = "";
        });
        return;
      }
      // 会话过期（电脑端重启过 / 断过网）：重新握手，再重发这一条
      if (res && String(res.error || "").indexOf("会话") >= 0) {
        if (await hello(($("pin-input") || {}).value || "")) continue;
      }
      // 网络抖了一下：等一下再试，别把这段字直接丢掉
      await new Promise((r) => setTimeout(r, 120 * (attempt + 1)));
    }
    say("这段没同步上，正在重试…", true);
  }

  function flushLive() {
    const value = $("input").value;
    if (value === sent) return;
    sent = value;
    if (value) lastSent = value;
    // 和 App 完全一样：整段交给电脑端，由电脑端自己算该退几个字、补哪些字。
    // 以前在手机端算差量，删超过 200 字会被截断，越打越对不上。
    send([{ k: "sync", text: value }]);
  }

  $("input").addEventListener("input", () => {
    const len = $("input").value.length;
    $("counter").textContent = `${len} 字`;
    $("counter").animate(
      [{ transform: "scale(1.12)" }, { transform: "scale(1)" }],
      { duration: 180, easing: "cubic-bezier(.2,0,0,1)" }
    );
    if (mode !== "live") return;
    clearTimeout(timer);
    timer = setTimeout(flushLive, 90);
  });

  /* ---------------- 模式 ---------------- */
  const seg = $("mode");
  seg.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      seg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      mode = b.dataset.v;
      if (mode === "batch") {
        sent = $("input").value;
        $("btn-send").textContent = "发送";
        say("编辑好以后点「发送」");
      } else {
        sent = $("input").value;
        $("btn-send").textContent = "输入";
        say("即打即输：打的字立刻出现在电脑上");
      }
    };
  });

  /* ---------------- 底部按钮 ---------------- */
  $("btn-send").onclick = async () => {
    const value = $("input").value;
    if (mode === "batch") {
      if (!value) return say("先写点字再发送", true);
      await send([{ k: "insert", text: value }, ...(settings.enter_after_send ? [{ k: "key", key: "ENTER" }] : [])]);
      lastSent = value;
      say("已发送到电脑");
    } else {
      // 和 App 一样：这个键就是敲一次回车（文字由输入框实时同步）
      await send([{ k: "key", key: "ENTER" }, { k: "reset" }]);
      lastSent = value;
      $("input").value = "";
      sent = "";
      acked = "";
      $("counter").textContent = "0 字";
      say("已敲回车，输入框已清空（可用「恢复」找回）");
    }
    if (navigator.vibrate) navigator.vibrate(12);
  };

  $("btn-clear").onclick = () => {
    $("input").value = "";
    sent = "";
    // 电脑端的同步基线一起归零，下一段字不会把电脑上已有的内容退掉
    send([{ k: "reset" }]);
    $("counter").textContent = "0 字";
    say("已清空手机输入框（电脑上的内容没动）");
  };

  $("btn-restore").onclick = () => {
    const text = lastSent || "";
    if (!text) return say("还没有发送过内容", true);
    $("input").value = text;
    $("counter").textContent = `${text.length} 字`;
    // 故意不把 sent 设成 text：设了就等于"内容没变化"，电脑端不会有任何反应，
    // 用户点了「恢复」却什么都没发生（以前就是这个"纯空壳"）。
    if (mode === "live") flushLive();
    say("已还原上次发送的内容（正在同步到电脑）");
  };

  /* 兜底同步：手机上的文字和电脑端确认收到的对不上就自动补发一次。
     网络抖一下、会话过期重连，这条路上丢掉的字都能自己找回来。 */
  setInterval(() => {
    if (!sid || mode !== "live") return;
    const value = $("input").value;
    if (value !== acked) send([{ k: "sync", text: value }]);
  }, 1200);

  /* ---------------- 底部三栏（发送 / 记录 / 设置） ---------------- */
  document.querySelectorAll(".tab[data-page]").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab[data-page]").forEach((t) => {
        t.classList.toggle("on", t === tab);
      });
      document.querySelectorAll(".page").forEach((p) => {
        p.classList.toggle("active", p.id === "page-" + tab.dataset.page);
      });
    };
  });

  /* ---------------- 记录 ---------------- */
  function renderLogs(list) {
    const box = $("logs");
    if (!box) return;
    if (!list || !list.length) {
      box.innerHTML = '<div class="empty">（空）</div>';
      return;
    }
    box.innerHTML = list.slice(0, 40).map((e) =>
      `<div class="logline"><span>${e.t}</span>${escapeHtml(e.who)}　${escapeHtml(e.text)}</div>`
    ).join("");
  }
  const escapeHtml = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  /* ---------------- 设置里的开关和语言 ---------------- */
  $("sw-enter").onclick = () => {
    settings.enter_after_send = !settings.enter_after_send;
    $("sw-enter").classList.toggle("on", settings.enter_after_send);
    try { localStorage.setItem('crosslink.enter', settings.enter_after_send ? '1' : '0'); } catch (e) { /* 忽略 */ }
    toast(settings.enter_after_send ? "发送后会自动回车" : "已关闭自动回车");
  };
  $("btn-reconnect").onclick = () => location.reload();
  $("addr").textContent = location.origin;
  $("set-device").textContent = deviceName;

  /* 界面语言：网页这边存本地（电脑端的语言设置只有本机能改） */
  const segLang = $("seg-lang");
  function paintLang(lang) {
    segLang.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("active", b.dataset.v === lang);
    });
  }
  segLang.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      const lang = b.dataset.v;
      paintLang(lang);
      if (window.I18N) window.I18N.set(lang);
      try { localStorage.setItem("crosslink.lang", lang); } catch (e) { /* 忽略 */ }
    };
  });
  try {
    const saved = localStorage.getItem("crosslink.lang");
    if (saved) paintLang(saved);
  } catch (e) { /* 忽略 */ }

  /* ---------------- 启动 ---------------- */
  hello("");
  window.addEventListener("pagehide", () => {
    if (sid) navigator.sendBeacon("/api/leave", new Blob([JSON.stringify({ sid })],
      { type: "application/json" }));
  });
})();
