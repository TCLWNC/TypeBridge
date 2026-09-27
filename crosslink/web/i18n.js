/* TypeBridge - runtime translation (中文 -> English).
 *
 * The UI is written in Chinese as the source language. This file translates the
 * rendered text instead of forcing every literal to be rewritten: it walks text
 * nodes and a few attributes, looks up an exact match in DICT, and falls back to
 * RULES for strings with numbers in them. A MutationObserver keeps it applied to
 * content that is generated later (toasts, dialogs, log lines).
 *
 * Why: the server also emits Chinese status lines ("已连接", "手机已退出"); with
 * this approach those get translated on screen too, without touching the server.
 */
(function () {
  "use strict";

  const DICT = {
    /* ---- window / brand ---- */
    "跨屏输入": "TypeBridge",
    "跨屏输入 · ": "TypeBridge · ",
    "退出 CrossLink": "Quit TypeBridge",
    "退出 CrossLink？": "Quit TypeBridge?",
    "CrossLink 自己": "TypeBridge itself",

    /* ---- nav ---- */
    "输入": "Input",
    "设备": "Devices",
    "设置": "Settings",

    /* ---- status ---- */
    "等待手机连接": "Waiting for a phone",
    "正在获取地址…": "Getting address…",
    "正在启动…": "Starting…",
    "与电脑端失联，正在重连…": "Lost the PC, reconnecting…",
    "手机连不上时点这里": "Click here if the phone cannot connect",
    "放行防火墙": "Allow firewall",
    "扫码连接": "QR code to connect",
    "手机扫码即可用": "Scan the code to start typing",
    "不用装 App，和电脑连着同一个 Wi-Fi 就能打字。": "No app needed - same Wi-Fi as this PC is enough.",
    "复制链接": "Copy link",
    "链接已复制，发到手机上打开就行": "Link copied - open it on your phone",
    "复制失败，请手动选中地址复制": "Copy failed - select the address manually",
    /* ---- voice input ---- */
    "语音输入": "Voice input",
    "本地离线语音输入：点一下开始说话，说完自动停":
      "Local offline dictation: click, speak, it stops by itself",
    "正在听…（点一下结束）": "Listening… (click to stop)",
    "正在听…说完会自动停": "Listening… it stops when you finish",
    "语音不可用：": "Voice input unavailable: ",
    "识别：": "Recognized: ",
    "识别失败：": "Recognition failed: ",
    "没听到说话": "No speech detected",
    "语音已输入：": "Voice text inserted: ",
    "语音模型还没下载": "The speech model has not been downloaded yet",
    "可用": "Ready",
    "正在收音": "Listening",
    "缺少模型": "Model missing",
    "离线识别": "Offline recognition",
    "说一句话，文字直接打进当前窗口，不联网":
      "Say something - the text goes straight into the focused window, offline",
    "试一下": "Try it",
    "结束收音": "Stop listening",
    "触发热键": "Hotkey",
    "在任何程序里按这个键，开始收音；再按一下结束并输入":
      "Press it anywhere to start listening; press again to stop and type it",
    "未设置": "not set",
    "按下新键": "Set key",
    "按你要的键…": "Press a key…",
    "现在按一下想用的键（Esc 取消）": "Press the key you want now (Esc cancels)",
    "已取消": "Cancelled",
    "字母和数字要配 Ctrl 或 Alt，避免和打字冲突":
      "Letters and digits need Ctrl or Alt so they do not clash with typing",
    "热键已设为 ": "Hotkey set to ",
    "还差语音模型：先运行 Get-Voice-Model.bat（约 228MB）":
      "The speech model is missing: run Get-Voice-Model.bat first (about 228 MB)",
    "正在收音时": "While listening",
    "屏幕下方会出现一条声纹，跟着你说话起伏":
      "A waveform appears at the bottom of the screen and follows your voice",

    /* ---- pairing code ---- */
    "配对码": "Pairing code",
    "换一个": "New code",
    "免配对码": "No code needed",
    "需要配对码": "Code required",
    "新手机需要输入配对码": "New phones must enter the pairing code",
    "已允许同网段直接连接": "Direct connection on this network allowed",
    "当前配对码": "Current pairing code",
    "手机上要输入这 4 位数字（就在输入页也显示着）":
      "Phones type these 4 digits (also shown on the input page)",
    "打开后，新手机必须输入 4 位配对码才能连上":
      "New phones must enter the 4-digit code before connecting",

    /* ---- input target ---- */
    "输入目标": "Input target",
    "检测中": "Checking",
    "等待选中窗口": "Waiting for a window",
    "先在电脑上点一下要输入的窗口": "Click the window you want to type into on the PC",
    "现在焦点在本程序，点一下你要输入的程序":
      "This app has focus - click the program you want to type into",
    "就绪 · 可以打字": "Ready · you can type",
    "未就绪": "Not ready",
    "⚠ 本程序窗口": "⚠ This app's own window",
    "已输入字数": "Characters typed",
    "在线手机": "Phones online",
    "已连接设备": "Connected devices",
    "还没有手机连接，扫左边二维码试试":
      "No phone connected yet - scan the QR code on the left",
    "在线": "online",
    "断开": "Disconnect",
    "已断开该设备": "Device disconnected",

    /* ---- activity ---- */
    "输入记录": "Activity",
    "清空记录": "Clear",
    "还没有输入记录": "No activity yet",
    "记录已清空": "Activity cleared",
    "界面": "UI",
    "电脑": "PC",
    "我的电脑": "My PC",
    "界面语言": "Language",
    "显示窗口": "Show window",
    "复制手机链接": "Copy phone link",
    "键盘注入（托盘）": "Keyboard injection",
    "退出（托盘）": "Quit",
    "电脑端已退出": "The PC app has quit",

    /* ---- settings: injection ---- */
    "键盘注入": "Keyboard injection",
    "关掉后手机照样能连，但电脑不会接收输入":
      "Phones can still connect, but nothing will be typed",
    "键盘注入已开启": "Keyboard injection on",
    "键盘注入已关闭": "Keyboard injection off",
    "输入方式": "Injection method",
    "个别程序不吃 Unicode 注入时改用剪贴板粘贴":
      "Switch to clipboard paste for apps that ignore Unicode input",
    "直接输入": "Direct",
    "剪贴板粘贴": "Clipboard paste",
    "剪贴板": "Clipboard",
    "字间延迟": "Keystroke delay",
    "老程序吞字时调到 5～20 毫秒": "Raise to 5-20 ms for old programs that drop keys",
    "粘贴后还原剪贴板": "Restore clipboard after paste",
    "剪贴板方式下，用完把原来的内容还回去":
      "Put the previous clipboard content back after pasting",
    "发送后自动回车": "Press Enter after sending",
    "手机点「发送到电脑」以后自动敲一次回车":
      "Send an Enter keystroke after the phone sends text",

    /* ---- settings: window ---- */
    "窗口与启动": "Window & startup",
    "窗口置顶": "Keep window on top",
    "让这个小窗口一直看得见": "Keep this window above other windows",
    "关闭时最小化到托盘": "Minimize to tray on close",
    "点右上角 × 不退出，留在托盘继续用":
      "Keep running in the tray instead of quitting",
    "开机自动启动": "Start at login",
    "开机后自动在托盘常驻": "Launch into the tray when Windows starts",
    "已设置开机自启": "Will start at login",
    "已取消开机自启": "Autostart disabled",

    /* ---- settings: security ---- */
    "安全": "Security",
    "本机名称": "Computer name",
    "手机上显示的名字": "The name phones see",
    "电脑端完全关闭，手机将断开": "Closes the PC app; phones will disconnect",
    "退出": "Quit",
    "再想想": "Not now",
    "取消": "Cancel",
    "设置没保存成功：": "Could not save the setting: ",
    "服务端无响应": "no response from the app",

    /* ---- firewall dialog ---- */
    "手机连不上电脑？": "Phone cannot reach the PC?",
    "多半是 Windows 防火墙把手机拦住了。\n点下面的按钮会弹出一次管理员确认（UAC），点「是」，等它把 8788-8800 这段端口放行。":
      "Windows Firewall is the usual reason.\nThe button below triggers one administrator prompt (UAC): click Yes and let it open ports 8788-8800.",
    "已弹出管理员确认，请在弹窗里点「是」…":
      "Administrator prompt shown - please click Yes…",
    "防火墙已放行：": "Firewall opened: ",
    "没放行成功：": "Not opened: ",
    "规则已生效": "rule is active",
    "请在弹窗里点「是」": "click Yes in the prompt",

    /* ---- phone web UI (mobile.html / mobile.js) ---- */
    "电脑": "PC",
    "我的手机": "My phone",
    "已连接 · 电脑端在线": "Connected · PC online",
    "连接中断，正在重连…": "Disconnected, reconnecting…",
    "这台电脑需要 4 位配对码（电脑窗口上有）":
      "This PC needs the 4-digit pairing code (shown in its window)",
    "连接失败，稍后重试…": "Connection failed, retrying…",
    "请输入 4 位配对码": "Enter the 4-digit pairing code",
    "配对码不正确": "Wrong pairing code",
    "电脑焦点在 CrossLink 自己身上，点一下目标程序":
      "The PC is focused on TypeBridge itself - click your target program",
    "电脑已就绪：": "PC ready: ",
    "发送到电脑": "Send to PC",
    "敲回车": "Enter",
    "编辑好以后点「发送到电脑」": "Edit your text, then tap “Send to PC”",
    "即打即输：打的字立刻出现在电脑上":
      "Live mode: every character appears on the PC immediately",
    "先写点字再发送": "Type something first",
    "已发送到电脑": "Sent to the PC",
    "已清空手机输入框（电脑上的内容没动）":
      "Phone input cleared (the PC keeps its text)",
    "还没有发送过内容": "Nothing has been sent yet",
    "已还原上次发送的内容": "Last sent text restored",
    "清空输入框": "Clear the input box",
    "还原上次发送的内容": "Restore the last sent text",
    "行首": "Home",
    "行尾": "End",
    "全选": "Select all",
    "复制": "Copy",
    "粘贴": "Paste",
    "撤销": "Undo",
    "保存": "Save",
    "切窗口": "Switch window",
    "功能键": "Function keys",
    "剪切": "Cut",
    "即打即输": "Live typing",
    "编辑后发送": "Edit then send",
    "更多": "More",
    "发送后自动回车": "Press Enter after sending",
    "发完自动敲一次回车": "Send an Enter keystroke right after",
    "重新连接": "Reconnect",
    "换网络或断开后点这里": "Click here after switching network or dropping out",
    "重连": "Reconnect",
    "电脑地址": "PC address",
    "正在连接电脑…": "Connecting to the PC…",
    "正在连接电脑": "Connecting to the PC",
    "正在和电脑握手…": "Handshaking with the PC…",
    "已连接同一 Wi-Fi": "Same Wi-Fi",
    "在这里打字…": "Type here…",
    "连接": "Connect",

    /* ---- server status lines (shown in the activity list) ---- */
    "已连接": "connected",
    "已断开（超时未响应）": "disconnected (no heartbeat)",
    "手机已退出": "phone left",
    "手机已退出/断网": "phone left or lost the network",
    "电脑主动断开": "disconnected by the PC",
    "已更换配对码": "pairing code rolled",
    "同一台手机重新连接": "the same phone reconnected",
    "与电脑重连成功，已继续同步": "reconnected to the PC, syncing again",
    "电脑端已断开连接，返回设备列表": "the PC disconnected; back to the device list",
    "已断开连接，返回设备列表": "Disconnected, back to the device list",
    "已清空手机输入框（电脑上的内容没动）":
      "Phone input cleared (the PC keeps its text)",
    "已敲回车，输入框已清空（可用「恢复」找回）":
      "Enter sent, phone input cleared (use Restore to get it back)",
    "已恢复上次发送的内容（正在同步到电脑）":
      "Restored the last sent text (syncing to the PC)"
  };

  /* Strings that contain numbers/names are handled by rules. */
  const RULES = [
    [/^已连接 (\d+) 台 · (.*)$/, (m) => `Connected: ${m[1]} · ${m[2]}`],
    [/^(\d+) 台$/, (m) => `${m[1]} phones`],
    [/^已输入 (\d+) 字$/, (m) => `${m[1]} characters typed`],
    [/^已输入 (\d+) 字 · (刚刚连接|\d+ 分钟前连接)$/, (m) => `${m[1]} characters · ${m[2]}`],
    [/^(\d+) 分钟前连接$/, (m) => `connected ${m[1]} min ago`],
    [/^刚刚连接$/, () => "connected just now"],
    [/^(\d+) 字$/, (m) => `${m[1]} chars`],
    [/^0 字$/, () => "0 chars"],
    [/^(\d+) 毫秒$/, (m) => `${m[1]} ms`],
    [/^延迟 (\d+)ms$/, (m) => `Delay ${m[1]}ms`],
    [/^已更换配对码：(\d+)$/, (m) => `New pairing code: ${m[1]}`],
    [/^已改名为 (.*)$/, (m) => `Renamed to ${m[1]}`],
    [/^启动完成 · 最差一帧 (\d+) 毫秒（>34 就可能感到卡）$/,
      (m) => `Started · worst frame ${m[1]} ms (above 34 ms feels laggy)`],
    [/^跨屏输入 v(.*) 已就绪$/, (m) => `TypeBridge v${m[1]} ready`],
    [/^跨屏输入 · (.*)$/, (m) => `TypeBridge · ${DICT[m[1]] || m[1]}`],
    [/^已就绪：(.*)$/, (m) => `Ready: ${m[1]}`],
    [/^电脑已就绪：(.*)$/, (m) => `PC ready: ${m[1]}`]
  ];

  let LANG = "zh";
  let busy = false;

  function translate(text) {
    if (!text) return null;
    const raw = text;
    const s = raw.trim();
    if (!s) return null;
    if (DICT[s]) return raw.replace(s, DICT[s]);
    for (const pair of RULES) {
      const m = s.match(pair[0]);
      if (m) {
        const out = pair[1](m);
        if (out !== s) return raw.replace(s, out);
      }
    }
    return null;
  }

  const ATTRS = ["placeholder", "title", "alt", "aria-label"];

  function applyTo(root) {
    if (!root) return;
    // 中文原文必须留住：翻译是把文字就地改掉的，不存一份就再也切不回中文了
    // （之前就踩了这个坑：切到英文后切不回中文，界面一直英文）。
    // 标题比较特殊：app.js 会在状态到达后改写它，所以不能死记第一次的值。
    // 规则：如果当前标题还是我们上次处理过的那条，就按语言来回切；
    // 否则说明是程序新设的标题，重新记一份原文。
    const cached = document.__zhTitle;
    const seen = cached !== undefined
      && (document.title === cached || document.title === (translate(cached) || cached));
    if (!seen) {
      document.__zhTitle = document.title;
      if (LANG === "en") {
        const t = translate(document.title);
        if (t) document.title = t;
      }
    } else {
      const wantTitle = LANG === "zh" ? cached : (translate(cached) || cached);
      if (document.title !== wantTitle) document.title = wantTitle;
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      if (node.__zh === undefined) node.__zh = node.nodeValue;
      const src = node.__zh;
      const want = LANG === "zh" ? src : (translate(src) || src);
      if (node.nodeValue !== want) node.nodeValue = want;
    }
    const els = root.querySelectorAll ? root.querySelectorAll("[placeholder],[title],[alt],[aria-label]") : [];
    for (const el of els) {
      for (const attr of ATTRS) {
        const cur = el.getAttribute(attr);
        if (cur === null) continue;
        const key = "__zh_" + attr;
        if (el[key] === undefined) el[key] = cur;
        const src = el[key];
        const want = LANG === "zh" ? src : (translate(src) || src);
        if (cur !== want) el.setAttribute(attr, want);
      }
    }
  }

  function watch() {
    const mo = new MutationObserver(() => {
      if (busy) return;
      busy = true;
      queueMicrotask(() => {
        busy = false;
        applyTo(document.body);
      });
    });
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  window.I18N = {
    set(lang) {
      const want = lang === "zh" || lang === "en"
        ? lang
        : (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
      const changed = want !== LANG;
      LANG = want;
      document.documentElement.lang = want === "zh" ? "zh-CN" : "en";
      if (changed) applyTo(document.body);
      return LANG;
    },
    get lang() { return LANG; },
    apply: applyTo,
    t(text) { return translate(text) || text; }
  };

  if (document.body) watch();
  else document.addEventListener("DOMContentLoaded", watch);
})();
