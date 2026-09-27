# -*- coding: utf-8 -*-
"""程序主控：起服务、开窗口、挂托盘、盯着前台窗口。"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

from . import APP_TITLE, VERSION
from . import config as config_mod
from . import winapi
from .server import Hub, create_server, local_urls, port_available

WINDOW_MIN = (1000, 660)

# 启动画面：内联 HTML（不读文件、不发请求），WebView2 一能绘制就显示，
# 主界面（本地服务）就绪后再切过去，避免开局几秒是一片空白。
SPLASH_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#000;color:#fff;
  font-family:"Microsoft YaHei UI",system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;overflow:hidden}
.box{text-align:center}
.ring{width:72px;height:72px;margin:0 auto 18px}
h1{margin:0;font-size:22px;font-weight:600;letter-spacing:.5px}
p{margin:8px 0 0;font-size:12.5px;color:#8B8E9D}
.dots{margin-top:14px;display:flex;gap:6px;justify-content:center}
.dots i{width:6px;height:6px;border-radius:50%;background:#B4C5FF;opacity:.3;
  animation:b 1.2s ease-in-out infinite}
.dots i:nth-child(2){animation-delay:.15s}
.dots i:nth-child(3){animation-delay:.3s}
@keyframes b{0%,100%{opacity:.25;transform:translateY(0)}50%{opacity:1;transform:translateY(-3px)}}
</style></head><body><div class="box">
<svg class="ring" viewBox="0 0 108 108"><path fill="#B4C5FF" fill-rule="evenodd"
 d="M54,24 L84,54 L54,84 L24,54 Z M54,28.5 L79.5,54 L54,79.5 L28.5,54 Z"/>
 <path fill="#B4C5FF" d="M54,38 L70,54 L54,70 L38,54 Z"/></svg>
<h1>跨屏输入</h1><p>正在启动…</p>
<div class="dots"><i></i><i></i><i></i></div>
</div></body></html>"""


class WebApi:
    """暴露给界面的原生能力：剪贴板等（浏览器里被拦的操作走这里，保证真的执行）。"""

    def __init__(self, app: "CrossLinkApp") -> None:
        # 注意：千万不要写成 self.app = app。
        # pywebview 会把 js_api 对象的属性递归展开给 JS，于是它会顺着
        # app.window → window.native → .AccessibilityObject.Bounds.Empty.Empty.Empty…
        # 一路展开到递归爆栈。日志里刷满 "[pywebview] Error while processing
        # app.window.native...Empty...: maximum recursion depth exceeded"，
        # CPU 和 GIL 全被这些异常吃掉 —— 表现出来就是「界面一打开就卡、
        # 连服务都不响应」。这里改成一个闭包变量，实例上就没有可展开的引用。
        def copy(text: str) -> bool:
            ok = False
            try:
                ok = winapi.clipboard_set_text(str(text))
            except Exception:   # noqa: BLE001
                ok = False
            if ok:
                app.hub.log("电脑", "链接已复制到剪贴板", "system")
                return True
            return False

        def open_url(url: str) -> bool:
            try:
                winapi.open_url(str(url))
                return True
            except Exception:   # noqa: BLE001
                return False

        self.copy = copy
        self.open_url = open_url


class CrossLinkApp:
    def __init__(self, cfg: dict[str, Any] | None = None, headless: bool = False) -> None:
        self.cfg = cfg or config_mod.load()
        self.headless = headless
        self.log_lines: list[str] = []
        self.injector = winapi.Injector(log=self._log)
        self.injector.enabled = bool(self.cfg["inject"])
        self.injector.method = self.cfg["method"]
        self.injector.delay_ms = int(self.cfg["delay_ms"])
        self.injector.restore_clipboard = bool(self.cfg["restore_clipboard"])
        self.hub = Hub(self.cfg, self.injector, on_change=self._on_change)
        self.hub.on_quit = self.quit
        self.httpd = None
        # 必须在开托盘之前就先有这个属性：托盘菜单回调会读它，
        # 之前没有提前定义 → 回调抛异常 → 整个托盘菜单静默失效。
        self.window = None
        self.native = None
        self.qt = None
        self.window = None
        self.tray = None
        self.app_url = ""
        self._stop = threading.Event()
        self._target_cache = {"title": "", "app": "", "self": False}

    # -- 基础 --------------------------------------------------------------
    def window_title(self) -> str:
        """窗口标题：英文界面用 TypeBridge，中文界面用 跨屏输入。"""
        if self.cfg.get("lang") == "en":
            return "TypeBridge v%s · %s" % (VERSION, self.cfg["name"])
        return "%s v%s · %s" % (APP_TITLE, VERSION, self.cfg["name"])

    def _log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_lines.append("%s  %s" % (stamp, text))
        if os.environ.get("CROSSLINK_DEBUG"):
            print(self.log_lines[-1], flush=True)

    def _on_change(self) -> None:
        """设置变更后同步到托盘等外部状态。"""
        if self.window is not None:
            try:
                # 不要写 self.window.on_top：那是从 HTTP 线程去动 WinForms 窗口，
                # 跨线程同步等待会把界面消息循环卡成「(未响应)」。用 Win32 置顶即可。
                hwnd = self._find_hwnd(self.window_title())
                if hwnd:
                    import ctypes
                    HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
                    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010
                    ctypes.windll.user32.SetWindowPos(
                        ctypes.c_void_p(hwnd),
                        ctypes.c_void_p(HWND_TOPMOST if self.cfg.get("topmost")
                                        else HWND_NOTOPMOST),
                        0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            except Exception:   # noqa: BLE001
                pass
        if self.tray is not None:
            try:
                self.tray.refresh()
            except Exception:   # noqa: BLE001
                pass

    # -- 服务 --------------------------------------------------------------
    def start_server(self) -> str:
        port = int(self.cfg["port"])
        for offset in range(20):
            if port_available(port + offset):
                port = port + offset
                break
        else:
            raise RuntimeError("端口 %d 附近都被占用了" % port)
        self.cfg["port"] = port
        self.httpd = create_server(self.hub, port)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True,
                                  name="crosslink-http")
        thread.start()
        self.hub.mobile_url = local_urls(port)
        self.hub.save()
        self._log("✔ 服务已启动，端口 %d" % port)
        for url in self.hub.mobile_url:
            self._log("手机访问：%s" % url)
        return "http://127.0.0.1:%d" % port

    def start_watchers(self) -> None:
        from .discovery import Discovery
        self.discovery = Discovery(self.cfg, log=self._log)
        self.discovery.start()
        threading.Thread(target=self._watch_foreground, daemon=True,
                         name="crosslink-fg").start()
        threading.Thread(target=self._watch_mirror, daemon=True,
                         name="crosslink-mirror").start()
        threading.Thread(target=self._watch_network, daemon=True,
                         name="crosslink-net").start()

    def _watch_foreground(self) -> None:
        while not self._stop.is_set():
            info = winapi.foreground_info()
            if info != self._target_cache:
                self._target_cache = info
                self.hub.target = info
                self.hub.broadcast({"type": "target", "target": info})
            self._stop.wait(0.7)

    def _watch_network(self) -> None:
        while not self._stop.is_set():
            urls = local_urls(int(self.cfg["port"]))
            if urls != self.hub.mobile_url:
                self.hub.mobile_url = urls
                self.hub.broadcast({"type": "urls", "urls": urls})
            # 电脑端的在线设备列表也要清理：手机退出/断网后不能一直挂着
            now = time.time()
            # 手机每 5 秒发一次心跳，分两种宽限：
            #   长连接还挂着       → 12 秒（网络抖动不至于把人踢了）
            #   长连接已经断了     → 6 秒（手机被划掉/杀掉，进程一死连接就断，
            #                              这里要立刻把它从列表里去掉）
            # 以前只有 12 秒一种、而且每 10 秒才检查一次，所以划掉 App 之后
            # 电脑端能挂着 20 多秒，看着就像"下线了还显示在线"。
            streams = set(self.hub.streams)
            gone = []
            for sid, info in list(self.hub.phones.items()):
                age = now - float(info.get("last_at") or info.get("since", now))
                if age > (12.0 if sid in streams else 6.0):
                    gone.append((sid, "已断开（超时未响应）" if sid in streams
                                 else "手机已退出/断网"))
            for sid, why in gone:
                self.hub.drop_phone(sid, why)
            self._stop.wait(2.0)

    def _watch_mirror(self) -> None:
        """镜像：读电脑当前输入框的文字，推给手机显示（手机端"电脑上：…"）。

        - 注入刚发生时跳过（回声抑制），否则手机上会看到自己刚打的字被"回灌"；
        - 只在文字变化时推送，700ms 一次，硬超时由 UIA 自己决定。
        """
        try:
            from .uia import UiaTextReader
            reader = UiaTextReader()
        except Exception as exc:   # noqa: BLE001
            self._log("镜像读取不可用：%s" % exc)
            return
        last = None
        while not self._stop.is_set():
            try:
                if self.injector.chars != getattr(self, "_mirror_chars", None):
                    # 刚刚注入过 → 这一轮不推（避免回声）
                    self._mirror_chars = self.injector.chars
                    self._stop.wait(0.7)
                    continue
                text = reader.read_focused() or ""
                text = text[:2000]
                if text != last:
                    last = text
                    self.hub.broadcast({"type": "mirror", "text": text,
                                        "len": len(text)})
            except Exception:   # noqa: BLE001
                pass
            self._stop.wait(0.7)

    # -- 窗口 --------------------------------------------------------------
    def run(self) -> int:
        winapi.set_dpi_aware()
        # 无 GPU 的机器（比如虚拟机）上，WebView2 的硬件合成路径会非常卡。
        # 这两个开关让 Chromium 走低端/软件渲染并对齐降载策略，界面会明显跟手。
        os.environ.setdefault(
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
            "--enable-low-end-device-mode --disable-gpu-compositing "
            "--disable-features=CalculateNativeWinOcclusion",
        )
        url = self.start_server()
        # app_url 必须在这里就定下来：浏览器模式、托盘「显示窗口」都要用它，
        # 以前只在创建内嵌窗口那个分支里赋值，于是"浏览器模式"打开时
        # self.app_url 还不存在，AttributeError 被 except 吞掉，浏览器根本没弹。
        self.app_url = url
        self.injector.start()
        self.start_watchers()
        self.hub.log("电脑", "%s v%s 已就绪" % (APP_TITLE, VERSION), "system")

        if not winapi.firewall_rule_exists():
            self.hub.log("电脑", "防火墙还没有放行，手机连不上时点一下「放行防火墙」", "warn")
        else:
            self._log("防火墙规则已存在")

        if self.headless or self.cfg.get("headless"):
            self._log("headless 模式，仅运行服务")
            try:
                while not self._stop.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return 0

        # 无窗口模式：完全不创建 WebView2（没有 GPU 的机器上最流畅），只常驻托盘
        if self.cfg.get("no_window"):
            self._log("无窗口模式：界面用手机端，电脑端只在托盘常驻")
            self.start_tray(None)
            try:
                while not self._stop.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return 0

        # 浏览器模式：不加载内嵌 WebView2，界面用系统默认浏览器打开。
        # 这是"换内核"的做法——同样的页面，交给浏览器渲染（对没有 GPU 的机器友好得多）。
        if self.cfg.get("browser"):
            self._log("浏览器模式：界面已在你的默认浏览器中打开（不使用内嵌内核）")
            self.start_tray(None)
            try:
                winapi.open_url(self.app_url + "/")
            except Exception:   # noqa: BLE001
                pass
            try:
                while not self._stop.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return 0

        # 原生界面（默认推荐）：tkinter 真·本地界面，不加载任何网页内核
        if self.cfg.get("native"):
            self._log("使用原生界面（tkinter），不加载 WebView2")
            from .native import NativeUI
            self.native = NativeUI(self)
            self.native.run()
            return 0

        # Qt 原生界面（把网页那套 UI 换算成原生控件；不加载任何网页内核）
        if self.cfg.get("qt", False):
            try:
                from .qtui import QtUI
                self._log("使用 Qt 原生界面（无网页内核）")
                self.qt = QtUI(self)
                self.qt.run()
                return 0
            except Exception as exc:   # noqa: BLE001
                self._log("Qt 界面不可用（%s），改用内嵌网页界面" % exc)

        try:
            import webview
        except ImportError:
            self._log("没有安装 pywebview，改用默认浏览器打开界面")
            winapi.open_url("http://127.0.0.1:%d" % self.cfg["port"])
            try:
                while not self._stop.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return 0

        self.start_tray(webview)
        width, height = self.cfg.get("window") or [1120, 740]
        self.app_url = url
        self.window = webview.create_window(
            self.window_title(),
            url,                       # 直接加载主界面：加启动画面那版实测会卡死，已回退
            width=int(width), height=int(height), min_size=WINDOW_MIN,
            background_color="#000000", text_select=False,
            confirm_close=False, easy_drag=False,
            js_api=WebApi(self),
        )
        self.window.events.closing += self._on_closing
        self.window.events.closed += self._on_closed
        # 窗口装饰必须在这个窗口自己的线程里做：
        # 之前另开线程调用 SendMessageW/SetClassLongPtrW，跟 WinForms 消息循环
        # 跨线程同步等待，直接把界面卡成「(未响应)」。
        self.window.events.shown += self._decorate
        self.window.events.loaded += self._decorate
        threading.Thread(target=self._keep_titlebar_dark, daemon=True,
                         name="crosslink-titlebar").start()
        if self.cfg.get("start_hidden"):
            def hide_soon() -> None:
                time.sleep(1.2)
                try:
                    self.window.hide()
                except Exception:   # noqa: BLE001
                    pass
            threading.Thread(target=hide_soon, daemon=True).start()
        webview.start(debug=bool(os.environ.get("CROSSLINK_DEBUG")), private_mode=False)
        return 0

    def _on_closing(self) -> bool | None:
        """点了系统关闭按钮：默认缩到托盘，行为可配置。"""
        if self.cfg.get("tray", True) and not self._stop.is_set():
            try:
                self.window.hide()
            except Exception:   # noqa: BLE001
                pass
            self.hub.log("电脑", "已最小化到托盘，右键托盘图标可退出", "system")
            return False
        return None

    def _on_closed(self) -> None:
        self.quit()

    def _goto_app_once(self) -> None:
        """启动画面加载完成后，隔一小会儿切到真正的主界面（只做一次）。"""
        if getattr(self, "_app_loaded", False):
            return
        self._app_loaded = True

        def go() -> None:
            time.sleep(0.6)
            try:
                self.window.load_url(self.app_url)
            except Exception as exc:   # noqa: BLE001
                self._log("切到主界面失败，改用浏览器打开：%s" % exc)
                winapi.open_url(self.app_url)

        threading.Thread(target=go, daemon=True, name="crosslink-splash").start()

    def _decorate(self) -> None:
        """窗口显示后做一次装饰（标题栏配色 + 图标），只在界面线程执行。"""
        if getattr(self, "_decorated", False):
            return
        # 注意：shown 可能早于窗口标题就绪，那一次会找不到窗口；
        # 只有两步都成功才算完成，否则留给 loaded 事件重试。
        icon_ok = self.apply_icon()
        self.fix_titlebar()
        if icon_ok:
            self._decorated = True
        # 窗口刚起来这会儿，pywebview/系统还会再刷一次非客户区，把刚设好的
        # 标题栏样式冲掉。所以这里补几次。
        if not getattr(self, "_title_retry", False):
            self._title_retry = True
            for delay in (0.6, 1.5, 3.0):
                threading.Timer(delay, self.fix_titlebar).start()

    # -- 标题栏 ------------------------------------------------------------
    def fix_titlebar(self) -> bool:
        """标题栏保持浅色（用户要的白色）。

        这里只做一件事：确保标题栏是浅色的。Win11 上顺手把标题栏底色、
        字色、边框线都设成"白底黑字 + 无边框"。

        走过的弯路记一下，别再试：
          · 开沉浸式深色（attr 20）→ 标题栏变深灰，跟纯黑界面连成一片，
            但用户明确要的是"标题栏白"，所以关掉。
          · Win10 上 DwmExtendFrameIntoClientArea(1,1,1,1) 想拿掉外沿
            1px 的亮线 → 副作用是整个非客户区变成玻璃混合，标题栏跟着
            背景一起变暗（实测从 249 掉到 44），得不偿失，已去掉。
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            dwm = ctypes.windll.dwmapi
            title = self.window_title()
            hwnd = self._find_hwnd(title, visible_only=False)
            if not hwnd:
                return False
            off = ctypes.c_int(0)
            # 20/19 是新旧两个版本的 DWMWA_USE_IMMERSIVE_DARK_MODE。
            # 关掉它 = 浅色（白色）标题栏，这是用户要的。
            hr = dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(off),
                                           ctypes.sizeof(off))
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(off),
                                      ctypes.sizeof(off))
            build = getattr(sys, "getwindowsversion", lambda: (0,))().build
            if build >= 22000:      # Win11：标题栏白底黑字 + 不要边框
                caption = ctypes.c_int(0x00FFFFFF)
                text = ctypes.c_int(0x00000000)
                none = ctypes.c_int(0xFFFFFFFE)
                dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption),
                                          ctypes.sizeof(caption))
                dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text),
                                          ctypes.sizeof(text))
                dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(none),
                                          ctypes.sizeof(none))
            # 设完要让系统重画一次窗口边框，否则屏幕上还是旧的那圈白边
            user32 = ctypes.windll.user32
            SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 1, 2, 4, 16
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER
                                | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            RDW_FRAME, RDW_INVALIDATE, RDW_UPDATENOW = 0x0400, 0x0001, 0x0100
            user32.RedrawWindow(ctypes.c_void_p(hwnd), None, None,
                                RDW_FRAME | RDW_INVALIDATE | RDW_UPDATENOW)
            # 常驻补设，日志只记第一次，别把记录刷满
            if not getattr(self, "_titlebar_logged", False):
                self._titlebar_logged = True
                self._log("标题栏已设为浅色（hr=%s，build=%s）" % (hr, build))
            return True
        except Exception as exc:   # noqa: BLE001
            self._log("标题栏设置跳过：%s" % exc)
            return False

    def _keep_titlebar_dark(self) -> None:
        """常驻盯着窗口边框/标题栏样式。

        实测：pywebview 初始化完、窗口最小化再恢复、系统换主题，都会把
        非客户区重刷一遍，之前设的样式会被冲掉。所以这里不是"设一次就完"，
        而是先立刻设一遍，然后一直盯着补。
        """
        if sys.platform != "win32":
            return
        self.fix_titlebar()
        while not self._stop.is_set():
            time.sleep(2.5)
            self.fix_titlebar()

    def apply_icon(self) -> bool:
        """把窗口 / 任务栏图标真正设成我们自己的 .ico。

        之前没调用任何设图标的 API，标题栏显示的是系统兜底图标（灰阶轮廓），
        所以左上角看到的是一个单色菱形，而不是蓝底 logo。
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            path = config_mod.asset_path("icon.ico")
            if not os.path.exists(path):
                self._log("图标文件缺失：%s" % path)
                return False
            IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
            user32.LoadImageW.restype = ctypes.c_void_p
            user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                          ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_uint]
            big = user32.LoadImageW(None, path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            small = user32.LoadImageW(None, path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE) or big
            if not big and not small:
                self._log("图标加载失败：%s" % path)
                return False
            hwnd = self._find_hwnd(self.window_title())
            if not hwnd:
                return False
            # 必须用 PostMessage（异步投递）：SendMessage / SetClassLongPtr 是从别的
            # 线程同步调用窗口过程，会把 pywebview 的 WinForms 消息循环堵死，
            # 系统就会把窗口标成「(未响应)」。异步投递只是排队，不会阻塞。
            user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0080, 0, ctypes.c_void_p(small))
            user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0080, 1, ctypes.c_void_p(big))
            self._log("窗口图标已设置（%s）" % os.path.basename(path))
            return True
        except Exception as exc:   # noqa: BLE001
            self._log("设置图标失败：%s" % exc)
            return False

    def _find_hwnd(self, title: str, visible_only: bool = True) -> int | None:
        """"--tray" 启动时窗口是被 hide() 藏起来的，只看可见窗口就永远找不到，
        托盘上的「显示窗口」自然没反应。所以这里允许把隐藏窗口也找出来。"""
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        found: list[int] = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(hwnd, _lp):
            if visible_only and not user32.IsWindowVisible(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if not n:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title:
                found.append(hwnd)
            return True

        user32.EnumWindows(EnumProc(cb), None)
        return found[0] if found else None

    # -- 托盘 --------------------------------------------------------------
    def start_tray(self, webview_mod) -> None:
        if os.environ.get("CROSSLINK_NO_TRAY"):
            self._log("（诊断）已按环境变量跳过托盘")
            return
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return
        icon_path = config_mod.asset_path("icon.png")
        try:
            image = Image.open(icon_path)
        except OSError:
            return

        def show(_icon=None, _item=None):
            try:
                # 1) 有 pywebview 窗口：用 Win32 唤出（不要在托盘线程里调 window.show()）。
                #    连隐藏的窗口也找——"--tray" 启动时它就是藏起来的。
                hwnd = self._find_hwnd(self.window_title(), visible_only=False)
                if hwnd:
                    import ctypes
                    user32 = ctypes.windll.user32
                    user32.ShowWindow(ctypes.c_void_p(hwnd), 5)   # SW_SHOW
                    user32.ShowWindow(ctypes.c_void_p(hwnd), 9)   # SW_RESTORE
                    user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
                    return
                # 2) Qt / tkinter 原生界面：把窗口抬起来
                for ui in (self.qt, self.native):
                    win = getattr(ui, "win", None) or getattr(ui, "root", None)
                    if win is not None:
                        win.deiconify()
                        win.lift()
                        win.focus_force()
                        return
                # 3) 浏览器模式：重新打开页面
                if getattr(self, "app_url", ""):
                    winapi.open_url(self.app_url + "/")
            except Exception:   # noqa: BLE001
                self._log("托盘「显示窗口」失败：%s" % sys.exc_info()[1])

        def toggle_inject(icon=None, _item=None):
            self.hub.apply_settings({"inject": not self.injector.enabled})
            if icon is not None:
                icon.update_menu()

        def copy_link(icon=None, _item=None):
            target = self.hub.mobile_url[0] if self.hub.mobile_url else ""
            if target:
                winapi.clipboard_set_text(target)
                self.hub.log("电脑", "手机链接已复制：%s" % target, "system")

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", show, default=True),
            pystray.MenuItem("复制手机链接", copy_link),
            pystray.MenuItem(
                lambda _: ("✔ " if self.injector.enabled else "") + "键盘注入",
                toggle_inject),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda: self.quit()),
        )
        self.tray = pystray.Icon("TypeBridge", image, self.window_title(), menu)
        threading.Thread(target=self.tray.run, daemon=True, name="crosslink-tray").start()

    # -- 收尾 --------------------------------------------------------------
    def quit(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        self._log("正在退出…")
        try:
            self.discovery.stop()
        except Exception:   # noqa: BLE001
            pass
        try:
            self.cfg["window"] = [int(self.window.width), int(self.window.height)]
        except Exception:   # noqa: BLE001
            pass
        self.hub.save()
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:   # noqa: BLE001
                pass
        self.injector.stop()
        if self.httpd is not None:
            threading.Thread(target=self.httpd.shutdown, daemon=True).start()
        try:
            if self.window is not None:
                self.window.destroy()
        except Exception:   # noqa: BLE001
            pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # 诊断开关：CROSSLINK_TRACE=1 时每 10 秒把所有线程的 Python 调用栈写进文件，
    # 用来定位「窗口被系统判未响应」时到底是哪个调用堵住了。
    if os.environ.get("CROSSLINK_TRACE"):
        try:
            import faulthandler
            trace_path = os.path.join(config_mod.config_dir(), "运行栈.txt")
            handle = open(trace_path, "w", encoding="utf-8", buffering=1)
            faulthandler.enable(file=handle, all_threads=True)
            faulthandler.dump_traceback_later(10, repeat=True, file=handle)
            print("诊断已开启：", trace_path, flush=True)
        except Exception as exc:   # noqa: BLE001
            print("诊断开启失败：", exc, flush=True)
    # 打包成窗口程序后 stdout/stderr 是 None，任何 print 都会炸，这里先兜底
    if sys.stdout is None or sys.stderr is None:
        try:
            sink = open(os.path.join(os.environ.get("TEMP", "."), "crosslink-console.log"),
                        "a", encoding="utf-8", errors="ignore")
        except OSError:
            sink = open(os.devnull, "w")
        sys.stdout = sys.stdout or sink
        sys.stderr = sys.stderr or sink
    cfg = config_mod.load()
    headless = False
    tray_start = False
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--headless":
            headless = True
        elif item == "--no-window":
            cfg["no_window"] = True
        elif item == "--tray":
            tray_start = True
        elif item == "--web":
            cfg["native"] = False
        elif item == "--native":
            cfg["native"] = True
        elif item == "--qt":
            cfg["qt"] = True
        elif item == "--browser":
            cfg["browser"] = True
            index += 1
            try:
                cfg["port"] = int(argv[index])
            except ValueError:
                pass
        elif item == "--name" and index + 1 < len(argv):
            index += 1
            cfg["name"] = argv[index]
        elif item == "--pin" and index + 1 < len(argv):
            index += 1
            cfg["pin"] = argv[index]
        elif item == "--no-pin":
            cfg["require_pin"] = False
        elif item == "--no-inject":
            cfg["inject"] = False
        elif item in ("--version", "-v"):
            print("%s %s" % (APP_TITLE, VERSION))
            return 0
        elif item == "--selftest":
            from .selftest import main as selftest_main
            return selftest_main()
        index += 1

    app = CrossLinkApp(cfg, headless=headless)
    if tray_start:
        # 托盘常驻：窗口照样创建，只是先藏着。这样点托盘「显示窗口」出来的
        # 是本程序自己的窗口，而不是甩给浏览器。
        # （以前"打开就卡"不是窗口的错，是 js_api 属性被递归展开刷爆 GIL，已修。）
        cfg["start_hidden"] = True
    return app.run()
