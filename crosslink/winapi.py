# -*- coding: utf-8 -*-
"""Windows 底层能力：键盘注入、剪贴板、前台窗口、DPI、防火墙、开机自启。

全部用 ctypes 直连系统 API，不依赖第三方库，方便打包成单文件 EXE。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from typing import Callable

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
else:   # 仅用于在非 Windows 平台跑单元测试
    user32 = kernel32 = shell32 = None

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


VK: dict[str, int] = {
    "ENTER": 0x0D, "RETURN": 0x0D, "TAB": 0x09, "ESC": 0x1B, "ESCAPE": 0x1B,
    "BACKSPACE": 0x08, "DELETE": 0x2E, "INSERT": 0x2D, "HOME": 0x24, "END": 0x23,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "SPACE": 0x20,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "CTRL": 0x11, "CONTROL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B,
}
for _i in range(1, 13):
    VK["F%d" % _i] = 0x6F + _i
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    VK.setdefault(_c, ord(_c))

EXTENDED = {"LEFT", "UP", "RIGHT", "DOWN", "HOME", "END", "DELETE", "INSERT",
            "PAGEUP", "PAGEDOWN", "WIN"}


def set_dpi_aware() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:   # noqa: BLE001
        try:
            user32.SetProcessDPIAware()
        except Exception:   # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# 键盘注入
# --------------------------------------------------------------------------

class InjectError(RuntimeError):
    pass


def _send(events: list[INPUT]) -> None:
    if not events or not IS_WINDOWS:
        return
    array = (INPUT * len(events))(*events)
    sent = user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
    if sent != len(events):
        err = ctypes.get_last_error()
        if sent == 0 and err in (0, 5):
            raise InjectError("当前桌面不接受模拟输入（可能锁屏，或被管理员权限的程序挡住）")
        raise InjectError("SendInput 只成功 %d/%d，错误码 %d" % (sent, len(events), err))


def _unicode_events(text: str) -> list[INPUT]:
    events: list[INPUT] = []
    for ch in text:
        units = ch.encode("utf-16-le")
        for i in range(0, len(units), 2):
            unit = int.from_bytes(units[i:i + 2], "little")
            events.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(
                ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, 0))))
            events.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(
                ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))))
    return events


def _key_events(name: str) -> list[INPUT]:
    key = name.strip().upper()
    if key not in VK:
        raise InjectError("不认识的按键：%s" % name)
    vk = VK[key]
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_EXTENDEDKEY if key in EXTENDED else 0
    return [
        INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(vk, scan, flags, 0, 0))),
        INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(
            ki=KEYBDINPUT(vk, scan, flags | KEYEVENTF_KEYUP, 0, 0))),
    ]


def type_text(text: str, delay_ms: int = 0) -> None:
    if not text:
        return
    step = max(0, min(int(delay_ms), 200)) / 1000.0
    for i in range(0, len(text), 200):
        _send(_unicode_events(text[i:i + 200]))
        if step:
            time.sleep(step)


def press_key(name: str, repeat: int = 1, delay_ms: int = 0) -> None:
    events = _key_events(name)
    batch: list[INPUT] = []
    for _ in range(max(1, int(repeat))):
        batch.extend(events)
        if len(batch) >= 40:
            _send(batch)
            batch = []
            if delay_ms:
                time.sleep(min(delay_ms, 200) / 1000.0)
    if batch:
        _send(batch)


def press_combo(name: str, ctrl: bool = False, alt: bool = False,
                shift: bool = False, meta: bool = False) -> None:
    mods = [k for flag, k in ((ctrl, "CTRL"), (alt, "ALT"),
                              (shift, "SHIFT"), (meta, "WIN")) if flag]
    events: list[INPUT] = []
    for mod in mods:
        events.append(_key_events(mod)[0])
    events.extend(_key_events(name))
    for mod in reversed(mods):
        events.append(_key_events(mod)[1])
    _send(events)


# --------------------------------------------------------------------------
# 剪贴板
# --------------------------------------------------------------------------

def clipboard_get_text() -> str | None:
    if not IS_WINDOWS:
        return None
    opened = False
    for _ in range(8):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.03)
    if not opened:
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def clipboard_set_text(text: str) -> bool:
    if not IS_WINDOWS:
        return False
    data = text.encode("utf-16-le") + b"\x00\x00"
    opened = False
    for _ in range(8):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.03)
    if not opened:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def paste_text(text: str, restore: bool = True) -> None:
    backup = clipboard_get_text() if restore else None
    if not clipboard_set_text(text):
        type_text(text)
        return
    time.sleep(0.03)
    press_combo("V", ctrl=True)
    time.sleep(0.06)
    if restore and backup is not None:
        clipboard_set_text(backup)


# --------------------------------------------------------------------------
# 前台窗口
# --------------------------------------------------------------------------

def _window_pid(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _process_name(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


def foreground_info() -> dict:
    if not IS_WINDOWS:
        return {"title": "", "app": "", "self": False}
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "", "app": "", "self": False}
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = _window_pid(hwnd)
    return {"title": buf.value, "app": _process_name(pid), "pid": pid,
            "self": pid == os.getpid()}


# --------------------------------------------------------------------------
# 注入线程：指令排队顺序执行，保证打字顺序不乱
# --------------------------------------------------------------------------

class Injector(threading.Thread):
    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        super().__init__(daemon=True, name="crosslink-injector")
        self.queue: queue.Queue[tuple] = queue.Queue()
        self.enabled = True
        self.method = "direct"
        self.delay_ms = 0
        self.restore_clipboard = True
        self.chars = 0
        self._last_len = 0          # 上一次写入的字符数（整段同步用）
        self.last_error = ""
        self.log = log or (lambda *_: None)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()
        self.queue.put(("noop",))

    def submit(self, *item) -> None:
        self.queue.put(item)

    def _text(self, text: str) -> None:
        if not text:
            return
        if self.method == "clipboard":
            paste_text(text, self.restore_clipboard)
        else:
            type_text(text, self.delay_ms)
        self.chars += len(text)

    def _dispatch(self, item: tuple) -> None:
        kind = item[0]
        if kind == "insert":
            self._text(str(item[1]))
        elif kind == "sync":
            self._apply_full(str(item[1]))
        elif kind == "edit":
            if int(item[1]):
                press_key("BACKSPACE", int(item[1]), self.delay_ms)
            self._text(str(item[2]))
        elif kind == "key":
            press_key(str(item[1]), int(item[2]) if len(item) > 2 else 1, self.delay_ms)
        elif kind == "combo":
            press_combo(str(item[1]), bool(item[2]), bool(item[3]),
                        bool(item[4]), bool(item[5]))
        elif kind == "noop":
            return
        else:
            raise InjectError("未知指令 %r" % (kind,))

    def _apply_full(self, text: str) -> None:
        """整段同步：让目标输入框的内容等于 text。

        做法：Ctrl+A 全选 → 直接用 Unicode 输入整段（**不碰剪贴板**）。
        之前的"全选 + 粘贴"会出现重复：粘贴后我们很快把剪贴板还原，
        目标程序还没来得及读剪贴板，于是粘到旧内容或没粘上，下一轮又补一遍。
        """
        if not text:
            try:
                press_combo("A", ctrl=True)
                press_key("DELETE")
            except Exception:   # noqa: BLE001
                pass
            self._last_len = 0
            return
        try:
            press_combo("A", ctrl=True)      # 全选，随后输入会整体替换
            time.sleep(0.03)
        except Exception:   # noqa: BLE001
            pass
        self._text(text)
        self._last_len = len(text)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self.queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if item[0] == "noop":
                continue
            if not self.enabled:
                continue
            try:
                self._dispatch(item)
            except Exception as exc:   # noqa: BLE001
                self.last_error = str(exc)
                self.log("⚠ 输入失败：%s" % exc)
                if os.environ.get("CROSSLINK_DEBUG"):
                    print(traceback.format_exc(), flush=True)


# --------------------------------------------------------------------------
# 防火墙 / 开机自启 / 网卡地址
# --------------------------------------------------------------------------

RULE_NAME = "CrossLink 跨屏输入"
RULE_NAME_TCP = RULE_NAME + " TCP"
RULE_NAME_UDP = RULE_NAME + " UDP"
# 放行端口段而不是单个端口：端口被占用时程序会自动往后找（8788 → 8789 …），
# 只放行一个端口的话，换了端口手机就搜不到了。
PORT_SPAN = 12

_FW_LAST: dict = {"ok": False, "msg": "还没执行过"}


def firewall_last_result() -> dict:
    """给界面用：上一次放行到底成没成，别在界面上瞎报喜。"""
    return dict(_FW_LAST)


def _fw_set(ok: bool, msg: str) -> bool:
    _FW_LAST["ok"] = bool(ok)
    _FW_LAST["msg"] = msg
    return bool(ok)


def _netsh_add(kind: str, port: int) -> int:
    code, _out = _run(["netsh", "advfirewall", "firewall", "add", "rule",
                       "name=%s %s" % (RULE_NAME, kind),
                       "dir=in", "action=allow", "protocol=" + kind,
                       "localport=%d-%d" % (int(port), int(port) + PORT_SPAN),
                       "profile=any"])
    return code


def firewall_apply_now(port: int) -> bool:
    """直接跑 netsh（只在当前进程已经提权时才有意义）。规则不绑程序路径。"""
    for name in (RULE_NAME, RULE_NAME_TCP, RULE_NAME_UDP):
        _run(["netsh", "advfirewall", "firewall", "delete", "rule",
              "name=" + name])
    return _netsh_add("TCP", port) == 0 and _netsh_add("UDP", port) == 0
_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def _run(cmd: list[str], timeout: float = 12.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              creationflags=_NO_WINDOW)
        out = (proc.stdout or b"").decode("gbk", "ignore") + \
              (proc.stderr or b"").decode("gbk", "ignore")
        return proc.returncode, out.strip()
    except Exception as exc:   # noqa: BLE001
        return -1, str(exc)


def firewall_rule_exists() -> bool:
    if not IS_WINDOWS:
        return True
    ok = True
    for name in (RULE_NAME_TCP, RULE_NAME_UDP):
        code, out = _run(["netsh", "advfirewall", "firewall", "show", "rule",
                          "name=" + name])
        if code != 0 or name not in out:
            ok = False
    return ok


def firewall_add_via_uac(exe: str | None, port: int) -> bool:
    """弹一次 UAC，放行入站端口段。

    以前这里有三个毛病，正是"点了没反应、也没弹管理员授权"的原因：
      1. 不看 ShellExecuteW 的返回值（≤32 就是没起来），照样往界面上报成功；
      2. 规则绑死了 exe 路径，打包换个目录这条规则就形同虚设（手机就搜不到）；
      3. 只放行单个端口，端口被占用往后挪一位就失效了。
    现在：端口段 + 不绑程序 + 弹完等规则真的出现才算成功，没成也如实说明。
    """
    if not IS_WINDOWS:
        return _fw_set(False, "只有 Windows 需要放行防火墙")
    if firewall_rule_exists():
        # 规则已经在（而且是按端口段、不绑程序路径的新规则），就别再弹一次 UAC 打扰人
        return _fw_set(True, "端口 %d-%d 早就放行过了，不用重复放行"
                       % (int(port), int(port) + PORT_SPAN))
    lo, hi = int(port), int(port) + PORT_SPAN
    bat = os.path.join(os.environ.get("TEMP", "."), "crosslink_fw.bat")
    lines = [
        "@echo off",
        'netsh advfirewall firewall delete rule name="%s" >nul 2>nul' % RULE_NAME,
        'netsh advfirewall firewall delete rule name="%s" >nul 2>nul' % RULE_NAME_TCP,
        'netsh advfirewall firewall delete rule name="%s" >nul 2>nul' % RULE_NAME_UDP,
        'netsh advfirewall firewall add rule name="%s" dir=in action=allow '
        'protocol=TCP localport=%d-%d profile=any' % (RULE_NAME_TCP, lo, hi),
        'netsh advfirewall firewall add rule name="%s" dir=in action=allow '
        'protocol=UDP localport=%d-%d profile=any' % (RULE_NAME_UDP, lo, hi),
    ]
    try:
        with open(bat, "w", encoding="gbk", errors="ignore") as fh:
            fh.write("\r\n".join(lines) + "\r\n")
    except OSError as exc:
        return _fw_set(False, "写临时脚本失败：%s" % exc)
    try:
        rc = int(shell32.ShellExecuteW(None, "runas", "cmd.exe",
                                       '/c "%s"' % bat, None, 0))
    except Exception as exc:   # noqa: BLE001
        return _fw_set(False, "调不起管理员确认：%s" % exc)
    if rc > 32:
        # 等用户点「是」、等 bat 跑完，以规则真的出现为准（最多 12 秒）
        for _ in range(24):
            time.sleep(0.5)
            if firewall_rule_exists():
                return _fw_set(True, "已放行入站端口 %d-%d（TCP + UDP）" % (lo, hi))
        return _fw_set(False, "管理员确认没点「是」，或者被安全软件拦下了")
    # rc ≤ 32：弹不出来。如果本来就已经是管理员，直接自己跑一遍也一样管用。
    if firewall_apply_now(port) or firewall_rule_exists():
        return _fw_set(True, "已放行入站端口 %d-%d（TCP + UDP）" % (lo, hi))
    return _fw_set(False, "管理员授权没成功（错误码 %d），规则没加上" % rc)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return '"%s" --tray' % os.path.abspath(sys.executable)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    return '"%s" "%s" --tray' % (exe, os.path.join(root, "main.py"))


def set_autostart(on: bool) -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, "CrossLink", 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, "CrossLink")
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def local_ipv4_list() -> list[str]:
    import socket
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip.startswith("169.254.") or ip in ips:
                continue
            ips.append(ip)
    except OSError:
        pass
    if not ips:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ips.append(sock.getsockname()[0])
            sock.close()
        except OSError:
            ips.append("127.0.0.1")
    ips.sort(key=lambda ip: (not ip.startswith("192.168."), not ip.startswith("10."), ip))
    return ips


def open_url(url: str) -> None:
    if IS_WINDOWS:
        try:
            os.startfile(url)   # noqa: S606
            return
        except OSError:
            pass
    import webbrowser
    webbrowser.open(url)
