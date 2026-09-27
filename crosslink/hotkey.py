# -*- coding: utf-8 -*-
"""全局热键：在电脑的任何地方按一下设定的键，就开始/结束语音输入。

用 Win32 的 RegisterHotKey + 一个自己的消息循环线程实现（不装任何额外库）。
热键写法："F9" / "Ctrl+Alt+Space" / "Alt+Q" / "Ctrl+Shift+F2" 这样。
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

_VK_NAMES = {
    "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "END": 0x23, "HOME": 0x24,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "INSERT": 0x2D, "DELETE": 0x2E,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}
for _i in range(1, 25):                       # F1..F24
    _VK_NAMES["F%d" % _i] = 0x6F + _i
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    _VK_NAMES[_c] = ord(_c)


def parse(spec: str) -> tuple[int, int] | None:
    """把 "Ctrl+Alt+Space" 解析成 (修饰键, 虚拟键码)；解析不了返回 None。"""
    if not spec:
        return None
    mods = 0
    vk = None
    for raw in spec.replace(" ", "").split("+"):
        part = raw.upper()
        if part in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif part == "ALT":
            mods |= MOD_ALT
        elif part == "SHIFT":
            mods |= MOD_SHIFT
        elif part in ("WIN", "META", "SUPER"):
            mods |= MOD_WIN
        elif part in _VK_NAMES:
            vk = _VK_NAMES[part]
    if vk is None:
        return None
    return mods, vk


def pretty(spec: str) -> str:
    """显示用的写法：把用户抓到的按键统一成 Ctrl+Alt+X 这种顺序。"""
    parsed = parse(spec)
    if not parsed:
        return spec or "（未设置）"
    mods, _vk = parsed
    names = []
    if mods & MOD_CONTROL:
        names.append("Ctrl")
    if mods & MOD_ALT:
        names.append("Alt")
    if mods & MOD_SHIFT:
        names.append("Shift")
    if mods & MOD_WIN:
        names.append("Win")
    tail = [k for k, v in _VK_NAMES.items() if v == parsed[1]]
    names.append(tail[-1] if tail else "?")
    return "+".join(names)


class HotkeyThread(threading.Thread):
    """注册一个全局热键；按下时回调 on_fire()。换热键就停掉重开一个。"""

    _counter = 0

    def __init__(self, spec: str, on_fire, log=None) -> None:
        super().__init__(daemon=True, name="crosslink-hotkey")
        self.spec = spec
        self.on_fire = on_fire
        self.log = log or (lambda *_: None)
        self.ok = False
        self._stop = threading.Event()
        HotkeyThread._counter += 1
        self._id = 0xB000 + HotkeyThread._counter
        self._thread_id = 0

    def stop(self) -> None:
        self._stop.set()
        if self._thread_id:
            # 往那个线程的消息队列塞一条 WM_QUIT，让它退出循环
            ctypes.windll.user32.PostThreadMessageW(
                wintypes.DWORD(self._thread_id), 0x0012, 0, 0)

    def run(self) -> None:
        parsed = parse(self.spec)
        if not parsed:
            self.log("热键没设置或写得不对：%r" % self.spec)
            return
        mods, vk = parsed
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, self._id, mods | MOD_NOREPEAT, vk):
            self.log("热键 %s 被别的程序占用了，换个键试试" % pretty(self.spec))
            return
        self.ok = True
        self.log("语音热键已就绪：%s" % pretty(self.spec))
        msg = wintypes.MSG()
        try:
            while not self._stop.is_set():
                got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if got in (0, -1):
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._id:
                    try:
                        self.on_fire()
                    except Exception as exc:      # noqa: BLE001
                        self.log("热键回调出错：%s" % exc)
        finally:
            user32.UnregisterHotKey(None, self._id)
            self.ok = False
