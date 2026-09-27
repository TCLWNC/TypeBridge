/* CrossLink 电脑端界面逻辑：状态同步、动效、设置 */
(() => {
  const $ = (id) => document.getElementById(id);

  /* ---------------- 启动画面 ---------------- */
  let bootHidden = false;
  let gotState = false;
  let worstFrame = 0;      // 最差一帧耗时，用来判断"卡不卡"
  let goodStreak = 0;      // 连续顺滑帧数
  let lastFrame = performance.now();

  function qrReady() {
    const img = $("qr");
    return !!img && img.complete && img.naturalWidth > 0;
  }

  function hideBoot() {
    if (bootHidden) return;
    bootHidden = true;
    const b = $("boot");
    if (!b) return;
    b.classList.add("hide");
    setTimeout(() => { b.style.display = "none"; }, 420);
  }

  /** 启动画面什么时候撤：状态到了 + 二维码画完 + 连续 15 帧顺滑（约 250ms） */
  function maybeHideBoot() {
    if (bootHidden || !gotState) return;
    if (!qrReady()) return;
    hideBoot();
  }

  // 帧耗时采样：一直跑，最差帧会写进「输入记录」，卡不卡有据可查
  let probeUntil = performance.now() + 3000;   // 只采样启动后的 3 秒，然后必须停
  function frameTick(t) {
    const dt = t - lastFrame;
    lastFrame = t;
    if (dt > 1 && dt < 1000) {
      if (dt > worstFrame) worstFrame = dt;
      goodStreak = dt < 34 ? goodStreak + 1 : 0;   // 30fps 以上算顺滑
    }
    maybeHideBoot();
    // 关键：采样窗口结束后立刻停止 rAF。
    // 一直跑会逼着 WebView2 持续重绘，在没有 GPU 的机器上就是"加载完就开始卡"。
    if (t < probeUntil) requestAnimationFrame(frameTick);
  }
  requestAnimationFrame(frameTick);
  setTimeout(() => { hideBoot(); }, 6000);   // 兜底：最多 10 秒也必须露出界面
  setTimeout(() => {
    prependLog({
      t: new Date().toTimeString().slice(0, 8), who: "界面", kind: "system",
      text: "启动完成 · 最差一帧 " + Math.round(worstFrame) + " 毫秒（>34 就可能感到卡）",
    });
  }, 3000);
  const api = async (path, data) => {
    try {
      const res = await fetch(path, {
        method: data === undefined ? "GET" : "POST",
        headers: { "Content-Type": "application/json" },
        body: data === undefined ? undefined : JSON.stringify(data),
      });
      return await res.json();
    } catch (err) {
      console.warn("请求失败", path, err);
      return { ok: false };
    }
  };

  /* ---------------- 涟漪 / 按压反馈（对齐 LocalSend 手感） ---------------- */
  document.addEventListener("pointerdown", (e) => {
    const el = e.target.closest(".fx");
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--rx", `${e.clientX - r.left}px`);
    el.style.setProperty("--ry", `${e.clientY - r.top}px`);
    const span = Math.max(r.width, r.height) / 8 * 2.4;
    el.style.setProperty("--rs", span.toFixed(1));
    el.classList.add("pressing");
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

  /* ---------------- 提示条 ---------------- */
  function toast(text, ms = 2200) {
    const wrap = $("toasts");
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = text;
    wrap.appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      setTimeout(() => el.remove(), 240);
    }, ms);
  }

  /* ---------------- 弹窗 ---------------- */
  function dialog({ title, body, actions }) {
    const box = $("dialog");
    box.innerHTML = "";
    const h = document.createElement("div");
    h.style.cssText = "font-size:17px;font-weight:700;margin-bottom:10px";
    h.textContent = title;
    const p = document.createElement("div");
    p.className = "muted";
    p.style.cssText = "font-size:13px;line-height:1.6;white-space:pre-wrap";
    p.textContent = body;
    const row = document.createElement("div");
    row.style.cssText = "display:flex;gap:10px;justify-content:flex-end;margin-top:18px";
    (actions || []).forEach((a) => {
      const b = document.createElement("button");
      b.className = "btn fx " + (a.style || "");
      b.textContent = a.label;
      b.onclick = () => {
        close();
        a.onClick && a.onClick();
      };
      row.appendChild(b);
    });
    box.append(h, p, row);
    $("backdrop").classList.add("show");
  }
  const close = () => $("backdrop").classList.remove("show");
  $("backdrop").addEventListener("click", (e) => {
    if (e.target === $("backdrop")) close();
  });

  /* ---------------- 页面切换 ---------------- */
  document.querySelectorAll(".nav[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav[data-page]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const target = "page-" + btn.dataset.page;
      document.querySelectorAll(".page").forEach((p) => {
        p.classList.remove("active");
        if (p.id === target) {
          void p.offsetWidth;          // 重启动画
          p.classList.add("active");
        }
      });
    });
  });

  /* ---------------- 数字滚动 ---------------- */
  const counters = new Map();
  let lastPhonesSig = "";
  function countUp(el, value) {
    const from = Number(el.dataset.v || 0);
    const to = Number(value || 0);
    if (from === to) return;
    el.dataset.v = String(to);
    const start = performance.now();
    const dur = 420;
    const step = (now) => {
      const k = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(from + (to - from) * eased).toLocaleString();
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* ---------------- 分段控件 ---------------- */
  function initSegmented(seg) {
    const thumb = seg.querySelector(".thumb");
    const buttons = [...seg.querySelectorAll("button")];
    const move = () => {
      const active = seg.querySelector("button.active") || buttons[0];
      thumb.style.width = `${active.offsetWidth}px`;
      thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
    };
    buttons.forEach((b) => {
      b.addEventListener("click", () => {
        buttons.forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        move();
        if (!seg.dataset.silent) setSetting({ method: b.dataset.v });
        syncMethod(b.dataset.v);
      });
    });
    requestAnimationFrame(move);
    window.addEventListener("resize", move);
    return move;
  }
  const segs = [...document.querySelectorAll(".segmented")];
  // #seg-lang 是语言切换，不是"输入方式"，别让通用分段控件把方法也一起改了
  segs.filter((s) => s.id !== "seg-lang").forEach(initSegmented);

  /* ---------------- 界面语言 ---------------- */
  const segLang = $("seg-lang");
  if (segLang) {
    const buttons = [...segLang.querySelectorAll("button")];
    const paint = (lang) => {
      buttons.forEach((b) => b.classList.toggle("active", b.dataset.v === lang));
      const active = segLang.querySelector("button.active") || buttons[0];
      const thumb = segLang.querySelector(".thumb");
      if (active && thumb) {
        thumb.style.width = `${active.offsetWidth}px`;
        thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
      }
    };
    buttons.forEach((b) => {
      b.addEventListener("click", () => {
        const lang = b.dataset.v;
        paint(lang);
        window.I18N && window.I18N.set(lang);
        setSetting({ lang });
      });
    });
    window.__paintLang = paint;
  }
  function syncMethod(value) {
    segs.forEach((seg) => {
      seg.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("active", b.dataset.v === value);
      });
      const active = seg.querySelector("button.active");
      const thumb = seg.querySelector(".thumb");
      if (active && thumb) {
        thumb.style.width = `${active.offsetWidth}px`;
        thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
      }
    });
  }

  /* ---------------- 开关 ---------------- */
  function bindSwitch(id, key, after) {
    const el = $(id);
    el.addEventListener("click", () => {
      const on = !el.classList.contains("on");
      el.classList.toggle("on", on);
      setSetting({ [key]: on });
      after && after(on);
    });
  }
  const setSetting = (data) => api("/api/pc/settings", data);

  bindSwitch("sw-inject", "inject", (on) => toast(on ? "键盘注入已开启" : "键盘注入已关闭"));
  bindSwitch("sw-restore", "restore_clipboard");
  bindSwitch("sw-enter", "enter_after_send");
  bindSwitch("sw-top", "topmost");
  bindSwitch("sw-tray", "tray");
  bindSwitch("sw-auto", "autostart", (on) => toast(on ? "已设置开机自启" : "已取消开机自启"));
  // 「需要配对码」单独处理：以服务端返回的状态为准，失败必须明确提示，
  // 否则开关会"看着点不动"（本地翻转后被状态回灌覆盖，用户不知道发生了什么）。
  $("sw-pin").addEventListener("click", async () => {
    const want = !$("sw-pin").classList.contains("on");
    $("sw-pin").classList.toggle("on", want);          // 先给即时反馈
    const res = await api("/api/pc/settings", { require_pin: want });
    if (!res || res.ok === false) {
      $("sw-pin").classList.toggle("on", !want);       // 失败回滚
      toast("设置没保存成功：" + ((res && res.error) || "服务端无响应"));
      return;
    }
    if (res.state && res.state.settings) applySettings(res.state.settings);
    if (res.state) applyPinState(res.state.require_pin, res.state.pin);
    toast(want ? "新手机需要输入配对码" : "已允许同网段直接连接");
  });
  $("pin-mode").addEventListener("click", () => $("sw-pin").click());

  /* ---------------- 延迟步进 ---------------- */
  let delay = 0;
  const renderDelay = () => {
    $("dl-val").textContent = `${delay} 毫秒`;
    $("delay-label").textContent = `延迟 ${delay}ms`;
  };
  const bump = (delta) => {
    delay = Math.max(0, Math.min(200, delay + delta));
    renderDelay();
    setSetting({ delay_ms: delay });
  };
  $("dl-minus").onclick = () => bump(-5);
  $("dl-plus").onclick = () => bump(5);

  /* ---------------- 配对码 ---------------- */
  function renderPin(pin, animate) {
    // 输入页和设置页都要显示同一个配对码（用户在设置页也要看得到）
    ["pin", "pin2"].forEach((id) => {
      const box = $(id);
      if (!box || box.dataset.pin === pin) return;
      box.dataset.pin = pin;
      box.innerHTML = "";
      String(pin)
        .split("")
        .forEach((d, i) => {
          const b = document.createElement("b");
          b.textContent = d;
          box.appendChild(b);
          if (animate) {
            b.classList.add("flip");
            setTimeout(() => b.classList.remove("flip"), 260 + i * 40);
          }
        });
    });
  }
  $("btn-pin").onclick = async () => {
    const res = await api("/api/pc/pin", {});
    if (res.pin) {
      renderPin(res.pin, true);
      toast("已更换配对码：" + res.pin);
    }
  };
  $("btn-pin2").onclick = () => $("btn-pin").click();

  /* ---------------- 记录 ---------------- */
  function logNode(entry) {
    const el = document.createElement("div");
    el.className = "log " + (entry.kind || "text");
    const t = document.createElement("time");
    t.textContent = entry.t;
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = entry.who;
    const txt = document.createElement("span");
    txt.className = "txt";
    txt.textContent = entry.text;
    el.append(t, who, txt);
    return el;
  }
  function renderLogs(logs) {
    const box = $("logs");
    box.innerHTML = "";
    if (!logs || !logs.length) {
      box.innerHTML = '<div class="empty">还没有输入记录</div>';
      return;
    }
    logs.slice(0, 120).forEach((entry) => box.appendChild(logNode(entry)));
  }
  function prependLog(entry) {
    const box = $("logs");
    const empty = box.querySelector(".empty");
    if (empty) empty.remove();
    box.prepend(logNode(entry));
    while (box.childElementCount > 120) box.lastElementChild.remove();
  }
  $("btn-clear-log").onclick = async () => {
    await api("/api/pc/clear", {});
    renderLogs([]);
    toast("记录已清空");
  };

  /* ---------------- 设备 ---------------- */
  function renderPhones(phones) {
    // 手机每敲一个字都会推一次「设备」事件；内容没变就不要再重绘、
    // 更不要重放入场动画，否则实时打字时电脑端会一直在重绘（卡顿的来源）。
    const sig = (phones || []).map((p) => p.sid + ":" + p.name).join("|");   // 不带 chars，否则每敲一个字都会重绘
    if (sig === lastPhonesSig) return;
    lastPhonesSig = sig;
    const badge = $("nav-badge");
    badge.textContent = String(phones.length);
    badge.classList.toggle("on", phones.length > 0);
    $("dev-count").textContent = `${phones.length} 台`;
    countUp($("stat-phones"), phones.length);
    const box = $("devices");
    box.innerHTML = "";
    if (!phones.length) {
      box.innerHTML = '<div class="empty">还没有手机连接，扫左边二维码试试</div>';
      $("status-dot").className = "dot";
      $("bar-dot").className = "dot";
      $("status-text").textContent = "等待手机连接";
      $("bar-text").textContent = "等待手机连接";
      return;
    }
    $("status-dot").className = "dot live";
    $("bar-dot").className = "dot live";
    const names = phones.map((p) => p.name).join("、");
    $("status-text").textContent = `已连接 ${phones.length} 台 · ${names}`;
    $("bar-text").textContent = `已连接 ${phones.length} 台 · ${names}`;
    phones.forEach((p, i) => {
      const row = document.createElement("div");
      row.className = "device enter";
      row.style.animationDelay = `${i * 45}ms`;
      const initial = (p.name || "手")[0];
      const age = Math.max(0, Math.round((Date.now() / 1000 - p.since) / 60));
      row.innerHTML = `
        <div class="avatar">${initial}</div>
        <div class="grow">
          <div class="name">${escapeHtml(p.name)}<span class="chip ok"><i class="dot ok"></i>在线</span></div>
          <div class="sub">${p.addr} · 已输入 ${p.chars} 字 · ${age < 1 ? "刚刚连接" : age + " 分钟前连接"}</div>
        </div>
        <button class="btn sm outline fx" data-kick="${p.sid}">断开</button>`;
      box.appendChild(row);
    });
    box.querySelectorAll("[data-kick]").forEach((b) => {
      b.onclick = async () => {
        await api("/api/pc/kick", { sid: b.dataset.kick });
        toast("已断开该设备");
      };
    });
  }
  const escapeHtml = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------------- 输入目标 ---------------- */
  function renderTarget(target) {
    const chip = $("target-chip");
    if (!target || !target.app) {
      $("target-app").textContent = "等待选中窗口";
      $("target-title").textContent = "先在电脑上点一下要输入的窗口";
      chip.className = "chip";
      chip.textContent = "未就绪";
      return;
    }
    if (target.self) {
      $("target-app").textContent = "CrossLink 自己";
      $("target-title").textContent = "现在焦点在本程序，点一下你要输入的程序";
      chip.className = "chip warn";
      chip.textContent = "⚠ 本程序窗口";
      return;
    }
    $("target-app").textContent = target.title || target.app;
    $("target-title").textContent = target.app;
    chip.className = "chip ok";
    chip.textContent = "就绪 · 可以打字";
  }

  /* ---------------- 整包状态 ---------------- */
  let lastUrl = "";
  function applyState(state) {
    if (!state) return;
    gotState = true;
    maybeHideBoot();
    // 界面语言：设置里选了就按选的，没选（""）就跟随浏览器语言
    if (window.I18N) {
      const lang = window.I18N.set(state.lang);
      if (window.__paintLang) window.__paintLang(lang);
    }
    if (state.voice) {
      window.__voiceState = state.voice;
      if (typeof state.voice.listening === "boolean") voiceListening = state.voice.listening;
      paintVoice(state.voice);
    }
    if (state.app) {
      $("pc-name").textContent = state.app.name || "我的电脑";
      $("ver").textContent = "v" + state.app.version;
      document.title = `跨屏输入 · ${state.app.name}`;
      const nameInput = $("in-name");
      if (document.activeElement !== nameInput) nameInput.value = state.app.name || "";
    }
    if (state.urls && state.urls.length) {
      const url = state.urls[0];
      $("url").textContent = url;
      if (url !== lastUrl) {
        lastUrl = url;
        $("qr").src = "/api/qr.png?u=" + encodeURIComponent(url);
        $("qr").onload = () => maybeHideBoot();   // 二维码画完再考虑撤启动画面
        const qr = document.querySelector(".qr-box");
        qr.style.transform = "scale(.9)";
        requestAnimationFrame(() => (qr.style.transform = "none"));
      }
    }
    if (state.pin) renderPin(state.pin, false);
    applyPinState(state.require_pin, state.pin);
    if (state.settings) applySettings(state.settings);
    renderPhones(state.phones || []);
    if (state.logs) renderLogs(state.logs);
    if (state.target) renderTarget(state.target);
    if (typeof state.chars === "number") countUp($("stat-chars"), state.chars);
  }

  function applySettings(s) {
    $("sw-inject").classList.toggle("on", !!s.inject);
    $("sw-restore").classList.toggle("on", !!s.restore_clipboard);
    $("sw-enter").classList.toggle("on", !!s.enter_after_send);
    $("sw-top").classList.toggle("on", !!s.topmost);
    $("sw-tray").classList.toggle("on", !!s.tray);
    $("sw-auto").classList.toggle("on", !!s.autostart);
    // 注意：require_pin 不在 settings 子对象里，它是 state 的顶层字段，
    // 以前在 applySettings 里读它永远是 undefined，于是开关被强行渲染成"关闭"
    // —— 这就是「点了打不开」的真正原因。这里只负责开关以外的设置项。
    delay = Number(s.delay_ms || 0);
    renderDelay();
    if (s.method) syncMethod(s.method);
  }

  /** 配对码相关的界面（开关 + 两处数字 + 文案），只吃顶层 require_pin / pin */
  function applyPinState(requirePin, pin) {
    if (typeof requirePin === "boolean") {
      $("sw-pin").classList.toggle("on", requirePin);
      $("chk-pin").checked = requirePin;
      $("pin-mode-text").textContent = requirePin ? "需要配对码" : "免配对码";
      // 关掉配对码时，设置页那行「当前配对码」不该继续挂在那里让人以为还要配对
      const row = $("pin2-row");
      if (row) row.style.display = requirePin ? "" : "none";
      // 输入页的配对码数字 + 「换一个」也一起藏掉，只留「免配对码 / 需要配对码」这个标记
      ["pin", "pin-label", "btn-pin"].forEach((id) => {
        const el = $(id);
        if (el) el.style.display = requirePin ? "" : "none";
      });
    }
    if (pin) renderPin(pin, false);
  }

  /* ---------------- 事件流 ---------------- */
  function connect() {
    const es = new EventSource("/api/events");
    es.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "log") prependLog(msg.entry);
      else if (msg.type === "logs") renderLogs(msg.logs);
      else if (msg.type === "phones") renderPhones(msg.phones);
      else if (msg.type === "target") renderTarget(msg.target);
      else if (msg.type === "settings") applyState(msg.state);
      else if (msg.type === "pin") renderPin(msg.pin, true);
      else if (msg.type === "urls") applyState({ urls: msg.urls });
      else if (msg.type === "voice") onVoiceEvent(msg);
      else if (msg.type === "hotkey") {
        if (voiceCard.hotkey) voiceCard.hotkey.textContent = msg.spec || "未设置";
      }
      else if (msg.type === "state") applyState(msg);
      else if (msg.type === "quit") {
        toast("电脑端已退出");
        setTimeout(() => window.close(), 400);
      }
    };
    es.onerror = () => {
      $("status-text").textContent = "与电脑端失联，正在重连…";
      $("bar-text").textContent = "与电脑端失联，正在重连…";
      $("status-dot").className = "dot";
      $("bar-dot").className = "dot";
    };
  }
  connect();

  /* ---------------- 按钮 ---------------- */
  $("btn-copy").onclick = async () => {
    const text = $("url").textContent;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast("链接已复制，发到手机上打开就行");
      return;
    } catch {
      /* 浏览器不给权限，就走原生剪贴板 */
    }
    try {
      const ok = await window.pywebview.api.copy(text);
      toast(ok ? "链接已复制，发到手机上打开就行" : "复制失败，请手动选中地址复制");
    } catch (err) {
      toast("复制失败，请手动选中地址复制");
    }
  };
  /* ---------------- 语音输入（设置里的那一项 + 全局热键） ---------------- */
  let voiceListening = false;
  let capturingHotkey = false;
  const voiceCard = {
    state: $("voice-state"),
    hint: $("voice-hint"),
    test: $("btn-voice-test"),
    hotkey: $("hotkey-show"),
    setKey: $("btn-hotkey-set"),
  };

  function paintVoice(v) {
    if (voiceCard.state) {
      voiceCard.state.textContent = voiceListening
        ? "正在收音" : (v && v.ready ? "可用" : "缺少模型");
      voiceCard.state.className = "chip " +
        (voiceListening ? "ok" : (v && v.ready ? "brand" : "warn"));
    }
    if (voiceCard.test) voiceCard.test.textContent = voiceListening ? "结束收音" : "试一下";
    if (voiceCard.hotkey && v && typeof v.hotkey === "string") {
      voiceCard.hotkey.textContent = v.hotkey || "未设置";
    }
    if (voiceCard.hint && v && !v.ready) {
      voiceCard.hint.textContent = "还差语音模型：先运行 Get-Voice-Model.bat（约 228MB）";
    }
  }

  function onVoiceEvent(msg) {
    voiceListening = msg.state === "listening";
    paintVoice(window.__voiceState);
    if (msg.state === "done" && msg.text) toast("语音已输入：" + msg.text.slice(0, 40));
  }

  if (voiceCard.test) {
    voiceCard.test.onclick = async () => {
      if (!voiceListening) {
        const r = await api("/api/pc/voice", { action: "start" });
        if (r && r.ok) {
          toast("正在听…说完会自动停");
        } else {
          toast("语音不可用：" + ((r && r.error) || "未知原因"));
        }
      } else {
        const r = await api("/api/pc/voice", { action: "stop" });
        if (r && r.ok) toast(r.text ? ("识别：" + r.text) : "没听到说话");
        else toast("识别失败：" + ((r && r.error) || ""));
      }
    };
  }

  /* 热键：点「按下新键」之后，按什么键就绑什么键 */
  const KEY_ALIAS = {
    " ": "Space", ArrowUp: "Up", ArrowDown: "Down", ArrowLeft: "Left",
    ArrowRight: "Right", Control: null, Alt: null, Shift: null, Meta: null,
  };
  function hotkeySpec(ev) {
    if (KEY_ALIAS[ev.key] === null) return null;      // 光按修饰键不算
    if (ev.key === "Escape") return "";
    const parts = [];
    if (ev.ctrlKey) parts.push("Ctrl");
    if (ev.altKey) parts.push("Alt");
    if (ev.shiftKey) parts.push("Shift");
    if (ev.metaKey) parts.push("Win");
    let k = KEY_ALIAS[ev.key] !== undefined ? KEY_ALIAS[ev.key] : ev.key;
    if (k === null) return null;
    k = k.length === 1 ? k.toUpperCase() : k.toUpperCase();
    parts.push(k);
    return parts.join("+");
  }
  if (voiceCard.setKey) {
    voiceCard.setKey.onclick = () => {
      capturingHotkey = true;
      voiceCard.setKey.textContent = "按你要的键…";
      toast("现在按一下想用的键（Esc 取消）");
    };
  }
  document.addEventListener("keydown", (ev) => {
    if (!capturingHotkey) return;
    const spec = hotkeySpec(ev);
    if (spec === null) return;                        // 还在按修饰键
    ev.preventDefault();
    capturingHotkey = false;
    voiceCard.setKey.textContent = "按下新键";
    if (spec === "") {
      toast("已取消");
      return;
    }
    if (!/[+]|^F\d+$/.test(spec)) {
      toast("字母和数字要配 Ctrl 或 Alt，避免和打字冲突");
      return;
    }
    setSetting({ voice_hotkey: spec });
    toast("热键已设为 " + spec);
  });

  $("btn-firewall").onclick = () => {
    dialog({
      title: "手机连不上电脑？",
      body: "多半是 Windows 防火墙把手机拦住了。\n点下面的按钮会弹出一次管理员确认（UAC），点「是」，等它把 8788-8800 这段端口放行。",
      actions: [
        { label: "取消", style: "outline" },
        {
          label: "放行防火墙",
          style: "filled",
          onClick: async () => {
            toast("已弹出管理员确认，请在弹窗里点「是」…");
            const r = await api("/api/pc/firewall", {});
            // 结果按电脑端真正执行的结果来报，不再"点了就报成功"
            toast(r && r.ok
              ? ("防火墙已放行：" + ((r && r.detail) || "规则已生效"))
              : ("没放行成功：" + ((r && r.detail) || "请在弹窗里点「是」")));
          },
        },
      ],
    });
  };
  $("btn-quit").onclick = () => {
    dialog({
      title: "退出 CrossLink？",
      body: "退出后手机将断开连接，需要重新启动才能继续使用。",
      actions: [
        { label: "再想想", style: "outline" },
        { label: "退出", style: "filled", onClick: () => api("/api/pc/quit", {}) },
      ],
    });
  };

  /* 名称输入（失焦保存） */
  const nameInput = $("in-name");
  nameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") nameInput.blur();
  });
  nameInput.addEventListener("blur", async () => {
    const value = nameInput.value.trim();
    if (!value || value === $("pc-name").textContent) return;
    await api("/api/pc/settings", { name: value });
    toast("已改名为 " + value);
  });

  window.addEventListener("resize", () => segs.forEach((s) => {
    const active = s.querySelector("button.active");
    const thumb = s.querySelector(".thumb");
    if (active && thumb) {
      thumb.style.width = `${active.offsetWidth}px`;
      thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
    }
  }));
})();
