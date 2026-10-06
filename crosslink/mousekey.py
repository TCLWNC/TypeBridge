# -*- coding: utf-8 -*-
"""鼠标键当语音热键：全局低级鼠标钩子（WH_MOUSE_LL）。

为什么要另写一个模块：键盘热键用的是 RegisterHotKey，它**只认键盘**，
鼠标中键/侧键根本注册不了 —— 这就是"设定按键里选不了鼠标中键"的原因。
鼠标键得用 SetWindowsHookEx(WH_MOUSE_LL) 全局勾着看。

支持的写法：
    MouseMiddle   鼠标中键
    MouseX1       鼠标侧键 1（靠大拇指靠近自己的那个，一般是"后退"）
    MouseX2       鼠标侧键 2（"前进"）
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
import time

WH_MOUSE_LL = 14
WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
XBUTTON1, XBUTTON2 = 0x0001, 0x0002

MOUSE_SPECS = {
    "MOUSEMIDDLE": ("mbutton", "鼠标中键"),
    "MOUSEMID": ("mbutton", "鼠标中键"),
    "MIDDLE": ("mbutton", "鼠标中键"),
    "MOUSEX1": ("x1", "鼠标侧键 1"),
    "MOUSEX2": ("x2", "鼠标侧键 2"),
    "MOUSEBACK": ("x1", "鼠标侧键 1"),
    "MOUSEFORWARD": ("x2", "鼠标侧键 2"),
}

_VK_CONTROL, _VK_MENU, _VK_SHIFT = 0x11, 0x12, 0x10


def is_mouse_spec(spec: str) -> bool:
    return _split(spec)[1] in MOUSE_SPECS


def mouse_kind(spec: str) -> str:
    """返回 mbutton / x1 / x2，认不出来返回空串。"""
    hit = MOUSE_SPECS.get(_split(spec)[1])
    return hit[0] if hit else ""


def pretty(spec: str) -> str:
    """显示名：Ctrl+鼠标中键 这样。"""
    mods, key = _split(spec)
    hit = MOUSE_SPECS.get(key)
    if not hit:
        return spec or "（未设置）"
    return "+".join(mods + [hit[1]])


def _split(spec: str) -> tuple[list[str], str]:
    """把 "Ctrl+MouseMiddle" 拆成 (["Ctrl"], "MOUSEMIDDLE")。"""
    mods, key = [], ""
    for raw in str(spec or "").replace(" ", "").split("+"):
        part = raw.upper()
        if part in ("CTRL", "CONTROL"):
            mods.append("Ctrl")
        elif part == "ALT":
            mods.append("Alt")
        elif part == "SHIFT":
            mods.append("Shift")
        elif part in ("WIN", "META", "SUPER"):
            mods.append("Win")
        elif part:
            key = part
    return mods, key


class MouseHotkeyThread(threading.Thread):
    """勾住全局鼠标；按下/松开中键（或侧键）时回调。

    和键盘热键一样支持两种方式：hold 按住说话 / toggle 按一下开始。
    带修饰键的写法（Ctrl+鼠标中键）也认。
    """

    def __init__(self, spec: str, on_fire, log=None, mode: str = "hold",
                 on_release=None) -> None:
        super().__init__(daemon=True, name="crosslink-mousehotkey")
        self.spec = spec
        self.kind = mouse_kind(spec)
        self.mods, _ = _split(spec)
        self.on_fire = on_fire
        self.on_release = on_release
        self.mode = "hold" if mode == "hold" else "toggle"
        self.log = log or (lambda *_: None)
        self.ok = False
        self._stop = threading.Event()
        self._thread_id = 0
        self._proc = None          # 保住回调引用，别被回收
        self._hook = None

    def stop(self) -> None:
        self._stop.set()
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(wt.DWORD(self._thread_id), 0x0012, 0, 0)

    # -- 钩子 --------------------------------------------------------------
    def _mods_down(self) -> bool:
        user32 = ctypes.windll.user32
        want = {"Ctrl": _VK_CONTROL, "Alt": _VK_MENU, "Shift": _VK_SHIFT}
        for name in self.mods:
            vk = want.get(name)
            if vk and not (user32.GetAsyncKeyState(vk) & 0x8000):
                return False
        return True

    def _is_my_button(self, msg: int, info) -> bool:
        if self.kind == "mbutton":
            return msg in (WM_MBUTTONDOWN, WM_MBUTTONUP)
        if self.kind in ("x1", "x2"):
            if msg not in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                return False
            flag = XBUTTON1 if self.kind == "x1" else XBUTTON2
            return (int(info.mouseData) >> 16) == flag
        return False

    def run(self) -> None:
        if not self.kind:
            self.log("鼠标热键写法不对：%r" % self.spec)
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # 32 位/wintypes 的 LPARAM 在这里不够用：鼠标钩子传进来的 lparam
        # 是 64 位地址，不声明清楚就会 OverflowError（每次鼠标动一下都刷屏）。
        LRESULT = ctypes.c_ssize_t
        WPARAM = ctypes.c_size_t
        LPARAM = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
        user32.CallNextHookEx.restype = LRESULT
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM, LPARAM]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC,
                                             ctypes.c_void_p, wt.DWORD]
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), ctypes.c_void_p,
                                       wt.UINT, wt.UINT]
        self._thread_id = kernel32.GetCurrentThreadId()

        def _proc(code, wparam, lparam):
            try:
                if code >= 0:
                    info = ctypes.cast(ctypes.c_void_p(lparam),
                                       ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                    down = wparam in (WM_MBUTTONDOWN, WM_XBUTTONDOWN)
                    up = wparam in (WM_MBUTTONUP, WM_XBUTTONUP)
                    if (down or up) and self._is_my_button(wparam, info) and self._mods_down():
                        if self.mode == "toggle":
                            if down:
                                self.on_fire()
                        else:
                            if down:
                                self.on_fire()
                            elif up and self.on_release:
                                self.on_release()
                        # 不吞事件：中键该干嘛还干嘛（浏览器开新标签照旧）
            except Exception:                  # noqa: BLE001
                pass
            return user32.CallNextHookEx(None, code, WPARAM(wparam), LPARAM(lparam))

        self._proc = HOOKPROC(_proc)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        if not self._hook:
            self.log("鼠标钩子没挂上（错误码 %d）" % ctypes.get_last_error())
            return
        self.ok = True
        self.log("鼠标热键就绪：%s" % pretty(self.spec))
        msg = wt.MSG()
        while not self._stop.is_set():
            got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if got in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        try:
            user32.UnhookWindowsHookEx(self._hook)
        except Exception:                      # noqa: BLE001
            pass
        self.ok = False
        time.sleep(0.05)


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
