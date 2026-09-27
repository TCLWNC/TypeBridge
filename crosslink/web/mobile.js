/* CrossLink 手机端：即打即输 / 编辑后发送 / 功能键 */
(() => {
  const $ = (id) => document.getElementById(id);
  let sid = null;
  let sent = "";              // 已经镜像到电脑的文字（即打即输的基线）
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
      $("pc-name").textContent = res.pc || "电脑";
      $("gate").classList.add("hide");
      setTimeout(() => $("gate").remove(), 420);
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
  function subscribe() {
    const es = new EventSource("/api/events");
    es.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "state" || msg.type === "settings") {
        const state = msg.type === "state" ? msg : msg.state;
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
        $("sw-enter").classList.toggle("on", !!settings.enter_after_send);
      } else if (msg.type === "target") {
        renderTarget(msg.target);
      } else if (msg.type === "urls" && msg.urls[0]) {
        $("addr").textContent = msg.urls[0];
      }
    };
    es.onerror = () => {
      $("status").textContent = "连接中断，正在重连…";
      $("dot").className = "dot";
    };
    es.onopen = () => {
      $("status").textContent = "已连接 · 电脑端在线";
      $("dot").className = "dot live";
    };
  }

  function renderTarget(target) {
    const bar = $("target-bar");
    const dot = $("target-dot");
    if (!target || !target.app) {
      bar.className = "target-bar";
      dot.className = "dot";
      $("target-text").textContent = "先在电脑上点一下要输入的窗口";
      return;
    }
    if (target.self) {
      bar.className = "target-bar warn";
      dot.className = "dot";
      $("target-text").textContent = "电脑焦点在 CrossLink 自己身上，点一下目标程序";
      return;
    }
    bar.className = "target-bar ready";
    dot.className = "dot ok";
    $("target-text").textContent = "电脑已就绪：" + (target.title || target.app);
  }

  /* ---------------- 发送 ---------------- */
  async function send(ops) {
    if (!sid) return;
    const res = await post("/api/op", { sid, ops });
    if (res.ok === false && res.error) {
      toast(res.error);
      if (String(res.error).indexOf("会话") >= 0) location.reload();
    }
  }

  const diff = (a, b) => {
    let i = 0;
    const max = Math.min(a.length, b.length);
    while (i < max && a[i] === b[i]) i++;
    let j = 0;
    while (j < max - i && a[a.length - 1 - j] === b[b.length - 1 - j]) j++;
    return { del: a.length - i - j, ins: b.slice(i, b.length - j) };
  };

  function flushLive() {
    const value = $("input").value;
    if (value === sent) return;
    const { del, ins } = diff(sent, value);
    sent = value;
    if (del === 0 && !ins) return;
    send([{ k: "edit", del: Math.min(del, 200), ins }]);
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
  const thumb = seg.querySelector(".thumb");
  const moveThumb = () => {
    const active = seg.querySelector("button.active");
    thumb.style.width = `${active.offsetWidth}px`;
    thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
  };
  seg.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      seg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      moveThumb();
      mode = b.dataset.v;
      if (mode === "batch") {
        sent = $("input").value;
        $("btn-send").innerHTML = sendIcon + "发送到电脑";
        toast("编辑好以后点「发送到电脑」");
      } else {
        sent = $("input").value;
        $("btn-send").innerHTML = enterIcon + "敲回车";
        toast("即打即输：打的字立刻出现在电脑上");
      }
    };
  });
  requestAnimationFrame(moveThumb);
  window.addEventListener("resize", moveThumb);
  const sendIcon = $("btn-send").innerHTML;
  const enterIcon = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M9 10v6h10"/><path d="M19 16V8a2 2 0 0 0-2-2h-3"/><path d="M14 9l3-3-3-3"/></svg>`;

  /* ---------------- 底部按钮 ---------------- */
  $("btn-send").onclick = async () => {
    const value = $("input").value;
    if (mode === "batch") {
      if (!value) return toast("先写点字再发送");
      await send([{ k: "insert", text: value }, ...(settings.enter_after_send ? [{ k: "key", key: "ENTER" }] : [])]);
      lastSent = value;
      toast("已发送到电脑");
    } else {
      await send([{ k: "key", key: "ENTER" }]);
    }
    if (navigator.vibrate) navigator.vibrate(12);
  };

  $("btn-clear").onclick = () => {
    $("input").value = "";
    sent = "";
    $("counter").textContent = "0 字";
    toast("已清空手机输入框（电脑上的内容没动）");
  };

  $("btn-restore").onclick = () => {
    const text = lastSent || "";
    if (!text) return toast("还没有发送过内容");
    $("input").value = text;
    $("counter").textContent = `${text.length} 字`;
    if (mode === "live") sent = text;
    toast("已还原上次发送的内容");
  };

  /* ---------------- 功能键 ---------------- */
  const KEYS = [
    { label: "⌫", op: { k: "key", key: "BACKSPACE" } },
    { label: "⏎", op: { k: "key", key: "ENTER" } },
    { label: "Tab", op: { k: "key", key: "TAB" } },
    { label: "Esc", op: { k: "key", key: "ESC" } },
    { label: "←", op: { k: "key", key: "LEFT" } },
    { label: "↑", op: { k: "key", key: "UP" } },
    { label: "↓", op: { k: "key", key: "DOWN" } },
    { label: "→", op: { k: "key", key: "RIGHT" } },
    { label: "行首", op: { k: "key", key: "HOME" } },
    { label: "行尾", op: { k: "key", key: "END" } },
    { label: "全选", op: { k: "combo", key: "A", ctrl: true } },
    { label: "复制", op: { k: "combo", key: "C", ctrl: true } },
    { label: "粘贴", op: { k: "combo", key: "V", ctrl: true } },
    { label: "剪切", op: { k: "combo", key: "X", ctrl: true } },
    { label: "撤销", op: { k: "combo", key: "Z", ctrl: true } },
    { label: "保存", op: { k: "combo", key: "S", ctrl: true } },
    { label: "切窗口", op: { k: "combo", key: "TAB", alt: true } },
  ];
  const keysBox = $("keys");
  KEYS.forEach((item) => {
    const b = document.createElement("button");
    b.className = "key";
    b.textContent = item.label;
    b.addEventListener("pointerdown", (e) => e.preventDefault());
    b.onclick = () => send([item.op]);
    keysBox.appendChild(b);
  });

  /* ---------------- 更多面板 ---------------- */
  const sheet = $("sheet");
  $("btn-more").onclick = () => sheet.classList.toggle("show");
  $("backdrop").onclick = () => sheet.classList.remove("show");
  $("sw-enter").onclick = () => {
    settings.enter_after_send = !settings.enter_after_send;
    $("sw-enter").classList.toggle("on", settings.enter_after_send);
    try { localStorage.setItem('crosslink.enter', settings.enter_after_send ? '1' : '0'); } catch (e) { /* 忽略 */ }
    toast(settings.enter_after_send ? "发送后会自动回车" : "已关闭自动回车");
  };
  $("btn-reconnect").onclick = () => location.reload();
  $("addr").textContent = location.origin;

  /* ---------------- 启动 ---------------- */
  hello("");
  window.addEventListener("pagehide", () => {
    if (sid) navigator.sendBeacon("/api/leave", new Blob([JSON.stringify({ sid })],
      { type: "application/json" }));
  });
})();
