# -*- coding: utf-8 -*-
"""读取当前焦点输入框里的文字（UI Automation，纯 ctypes）。

移植自上一版 TextLink 的 UiaTextReader（已验证可用）：
优先用 ValuePattern.Value，其次 TextPattern.DocumentRange.GetText()，
都拿不到时退回 WM_GETTEXT。用法：在同一个线程里创建并调用。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import sys

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
else:
    user32 = None

UIA_ValuePatternId = 10002
UIA_TextPatternId = 10014
UIA_CLSID = "{FF48DBA4-60EF-4201-AA87-54103EEF594E}"
UIA_IID = "{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}"


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> "_GUID":
        guid = cls()
        try:
            ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
        except Exception:   # noqa: BLE001
            pass
        return guid


def _com_call(ptr, index: int, restype, *argtypes):
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])


def _com_release(ptr) -> None:
    if ptr:
        try:
            _com_call(ptr, 2, ctypes.c_ulong)(ptr)
        except Exception:   # noqa: BLE001
            pass


def focused_control_hwnd():
    """当前线程所属前台窗口里、拥有键盘焦点的那个控件句柄。"""
    if not IS_WINDOWS:
        return None

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                    ("rcCaret", wintypes.RECT)]

    front = user32.GetForegroundWindow()
    if not front:
        return None
    tid = user32.GetWindowThreadProcessId(front, None)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    try:
        if user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
            return info.hwndFocus or front
    except Exception:   # noqa: BLE001
        pass
    return front


class UiaTextReader:
    """读当前焦点控件的文字；必须在创建它的线程里使用。"""

    def __init__(self) -> None:
        self.available = False
        self.error = ""
        self._uia = None
        if not IS_WINDOWS:
            self.error = "非 Windows"
            return
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0x2)
            uia = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(_GUID.parse(UIA_CLSID)), None, 1,
                ctypes.byref(_GUID.parse(UIA_IID)), ctypes.byref(uia))
            if hr != 0 or not uia:
                self.error = "CoCreateInstance hr=%s" % hr
                return
            self._uia = uia
            self.available = True
        except Exception as exc:   # noqa: BLE001
            self.error = repr(exc)

    def close(self) -> None:
        _com_release(self._uia)
        self._uia = None
        self.available = False
        if IS_WINDOWS:
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:   # noqa: BLE001
                pass

    def _element_text(self, element) -> str | None:
        if not element:
            return None
        for pattern_id, index in ((UIA_ValuePatternId, 4), (UIA_TextPatternId, 7)):
            pattern = ctypes.c_void_p()
            try:
                hr = _com_call(element, 16, ctypes.c_long, ctypes.c_int,
                               ctypes.POINTER(ctypes.c_void_p))(
                    element, pattern_id, ctypes.byref(pattern))
            except Exception:   # noqa: BLE001
                continue
            if hr != 0 or not pattern:
                continue
            try:
                if pattern_id == UIA_ValuePatternId:
                    bstr = ctypes.c_void_p()
                    if _com_call(pattern, index, ctypes.c_long,
                                 ctypes.POINTER(ctypes.c_void_p))(
                            pattern, ctypes.byref(bstr)) == 0 and bstr.value:
                        return ctypes.wstring_at(bstr.value)
                else:
                    rng = ctypes.c_void_p()
                    if _com_call(pattern, index, ctypes.c_long,
                                 ctypes.POINTER(ctypes.c_void_p))(
                            pattern, ctypes.byref(rng)) == 0 and rng:
                        bstr = ctypes.c_void_p()
                        ok = _com_call(rng, 12, ctypes.c_long, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_void_p))(
                            rng, -1, ctypes.byref(bstr))
                        _com_release(rng)
                        if ok == 0 and bstr.value:
                            return ctypes.wstring_at(bstr.value)
            finally:
                _com_release(pattern)
        return None

    def _fallback(self) -> str | None:
        hwnd = focused_control_hwnd()
        if not hwnd:
            return None
        try:
            buf = ctypes.create_unicode_buffer(4096)
            user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 4096)
            return buf.value
        except Exception:   # noqa: BLE001
            return None

    def read_focused(self) -> str | None:
        if not self.available:
            return self._fallback()
        element = ctypes.c_void_p()
        try:
            hr = _com_call(self._uia, 8, ctypes.c_long,
                           ctypes.POINTER(ctypes.c_void_p))(
                self._uia, ctypes.byref(element))
        except Exception:   # noqa: BLE001
            return self._fallback()
        if hr != 0 or not element:
            return self._fallback()
        try:
            text = self._element_text(element)
            return text if text is not None else self._fallback()
        finally:
            _com_release(element)
