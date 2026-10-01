# -*- coding: utf-8 -*-
"""收音时屏幕上的声纹 —— 效果照 Handy 搬过来。

Handy（github.com/cjpais/Handy，同样是离线语音输入）的声纹参数，这里原样抄：
  .swave        flex、居中、gap 3px、高 18px
  .swave i      width 4px、min 3px、max 18px、颜色 = 强调色
  高度公式       max(3, min(18, 3 + v^0.7 * 15))，值来自 FFT 频段（见 asr.Spectrum）
  待命动画      scaleY 0.55~1.5、900ms 循环、每根条延迟 0/75/150/225/300ms（中间最晚）
  配色          这里按用户要求改成白色，待命态用灰的区分

窗口本身是**真透明**的，屏幕上只剩那几根白色竖条和它们背后的黑色柔光：
  · 首选：自己建一个 32 位分层窗口（UpdateLayeredWindow），用 PIL 画
          白条 + 高斯模糊的黑色柔光 —— 每像素 alpha，任意背景都好看。
  · 兜底：如果分层窗口起不来，退回 tk 画布 + 色键抠图（+ 硬边阴影）。

注意：**不能**拿 tkinter 的 winfo_id() 去 UpdateLayeredWindow —— 那是 Tk 的
子窗口，Windows 不支持给子窗口贴分层位图（贴了也看不见，只会静静失败）。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math
import threading
import time
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAS_PIL = True
except Exception:                      # noqa: BLE001
    HAS_PIL = False

# ---- Handy 的尺寸（逻辑像素，最后按 DPI 缩放） ----
BARS = 9
BAR_W = 4
BAR_GAP = 3
BAR_MIN, BAR_MAX = 3.0, 18.0
BAR_RADIUS = 2
WINDOW_W, WINDOW_H = 184, 58
BAR_CENTER_Y = 22              # 竖条的竖中位置
LABEL_Y = 46                   # 「正在识别」这行字的位置
RECOG_PERIOD_MS = 900.0        # 识别期走波一圈的时间
BOTTOM_OFFSET = 120
ARM_MS = 900.0                 # 待命动画周期
ARM_DELAYS = [0, 75, 150, 225, 300, 225, 150, 75, 0]
ARM_BASE = 6.0
ARM_SCALE_MIN, ARM_SCALE_MAX = 0.55, 1.5

KEY = "#000000"                # 兜底画法的色键：这个颜色会被挖成透明

# 白色条后面的**黑色柔光**：中间浓、往外淡（高斯模糊做出来的）
GLOW_BLUR = 3.2                # 模糊半径（逻辑像素）
GLOW_ALPHA = 0.62              # 最浓处的不透明度
GLOW_SPREAD = 1.0              # 先把条子往外胖一圈再模糊，光晕才裹得住

# 兜底画法用的硬阴影（不能是纯黑，纯黑会被色键挖掉）
SHADOW_COLOR = "#2A2A2A"
SHADOW_PAD = 1.5
SHADOW_DX, SHADOW_DY = 0.6, 0.6

LABEL_TEXT = "正在识别"
FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc",
                   r"C:\Windows\Fonts\msyhl.ttc",
                   r"C:\Windows\Fonts\simhei.ttf")

WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
ULW_ALPHA = 2

_WNDPROC = None                # 必须留引用，否则回调被回收会崩


def _scale() -> float:
    """DPI 缩放：96dpi 记 1.0。"""
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:                     # noqa: BLE001
        return 1.0


def _colors() -> tuple[str, str]:
    """竖条配色：(工作时, 待命时)。"""
    return ("#FFFFFF", "#9A9A9A")


# --------------------------------------------------------------------------
# Win32：一个真正的 32 位分层窗口
# --------------------------------------------------------------------------

class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class _WNDCLASS(ctypes.Structure):
    # 句柄一律按 void_p 走：ctypes.wintypes 里 HCURSOR/HBRUSH 不一定有
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


def create_overlay_window(x: int, y: int, w: int, h: int) -> int:
    """建一个不抢焦点、不进任务栏的分层弹窗；返回窗口句柄。"""
    global _WNDPROC
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    LONG_PTR = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LONG_PTR, wt.HWND, wt.UINT,
                                 ctypes.c_size_t, LONG_PTR)
    user32.DefWindowProcW.restype = LONG_PTR
    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, ctypes.c_size_t, LONG_PTR]

    def _proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _WNDPROC = WNDPROC(_proc)
    hinst = kernel32.GetModuleHandleW(None)
    cls = _WNDCLASS()
    cls.lpfnWndProc = ctypes.cast(_WNDPROC, ctypes.c_void_p)
    cls.hInstance = hinst
    cls.lpszClassName = "TypeBridgeWaveOverlay"
    user32.RegisterClassW(ctypes.byref(cls))       # 已经注册过就忽略
    hwnd = user32.CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        cls.lpszClassName, "", WS_POPUP, x, y, w, h, None, None, hinst, None)
    if not hwnd:
        raise OSError("分层窗口没建起来（错误码 %d）" % ctypes.get_last_error())
    return int(hwnd)


def show_window(hwnd: int, on: bool) -> None:
    user32 = ctypes.windll.user32
    SW_SHOWNOACTIVATE, SW_HIDE = 4, 0
    if on:
        # 重新置顶 + 不激活地显示（点别的地方不会被它抢焦点）
        user32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(-1), 0, 0, 0, 0,
                            0x0001 | 0x0002 | 0x0010)      # NOSIZE|NOMOVE|NOACTIVATE
        user32.ShowWindow(ctypes.c_void_p(hwnd), SW_SHOWNOACTIVATE)
    else:
        user32.ShowWindow(ctypes.c_void_p(hwnd), SW_HIDE)


def destroy_window(hwnd: int) -> None:
    try:
        ctypes.windll.user32.DestroyWindow(ctypes.c_void_p(hwnd))
    except Exception:                     # noqa: BLE001
        pass


def push_layered(hwnd: int, img) -> bool:
    """把一张 RGBA 图整张推成分层窗口的内容（真·每像素透明）。"""
    import numpy as np

    gdi = ctypes.windll.gdi32
    user32 = ctypes.windll.user32
    image = img.convert("RGBA")
    cw, ch = image.size
    arr = np.asarray(image, dtype=np.uint8)
    alpha = arr[:, :, 3:4].astype(np.uint16)
    # 分层窗口要"预乘 alpha"的 BGRA
    rgb = (arr[:, :, :3].astype(np.uint16) * alpha // 255).astype(np.uint8)
    bgra = np.ascontiguousarray(
        np.dstack([rgb[:, :, 2], rgb[:, :, 1], rgb[:, :, 0], arr[:, :, 3]]))

    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi.CreateCompatibleDC(hdc_screen)
    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = cw
    bmi.bmiHeader.biHeight = -ch           # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0        # BI_RGB
    bits = ctypes.c_void_p()
    hbmp = gdi.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0,
                                ctypes.byref(bits), None, 0)
    old = None
    try:
        if not hbmp or not bits:
            return False
        ctypes.memmove(bits, bgra.tobytes(), cw * ch * 4)
        old = gdi.SelectObject(hdc_mem, hbmp)
        rect = wt.RECT()
        user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
        dst = wt.POINT(rect.left, rect.top)
        size = wt.SIZE(cw, ch)
        src = wt.POINT(0, 0)
        blend = _BLENDFUNCTION(0, 0, 255, 1)      # AC_SRC_OVER + AC_SRC_ALPHA
        ok = user32.UpdateLayeredWindow(
            ctypes.c_void_p(hwnd), hdc_screen, ctypes.byref(dst),
            ctypes.byref(size), hdc_mem, ctypes.byref(src), 0,
            ctypes.byref(blend), ULW_ALPHA)
        return bool(ok)
    finally:
        if old:
            gdi.SelectObject(hdc_mem, old)
        if hbmp:
            gdi.DeleteObject(hbmp)
        gdi.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)


def load_font(size: int):
    """「正在识别」那行字的字体；找不到就返回 None（那就只走波不写字）。"""
    if not HAS_PIL:
        return None
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:                 # noqa: BLE001
            continue
    return None


# --------------------------------------------------------------------------
# 兜底画法：tk 画布 + 色键
# --------------------------------------------------------------------------

def _make_colorkey(win: tk.Toplevel) -> None:
    GWL_EXSTYLE = -20
    LWA_COLORKEY = 0x00000001
    user32 = ctypes.windll.user32
    win.update_idletasks()
    hwnd = int(win.winfo_id())
    style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
    user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(ctypes.c_void_p(hwnd),
                                      ctypes.c_uint32(0x000000),
                                      ctypes.c_ubyte(255), LWA_COLORKEY)


def _rgba(name: str) -> tuple:
    return (int(name[1:3], 16), int(name[3:5], 16), int(name[5:7], 16), 255)


class WaveOverlay(threading.Thread):
    """bars() 返回频段值；state() 返回 idle/listening/recognizing；show()/hide() 控制显示。"""

    def __init__(self, bars, log=None, state=None) -> None:
        super().__init__(daemon=True, name="crosslink-overlay")
        self.bars = bars
        self.state = state or (lambda: "listening")
        self.log = log or (lambda *_: None)
        self._show = threading.Event()
        self._hide = threading.Event()
        self._ready = threading.Event()
        self._root = None
        self.hwnd = 0
        # 自查用：画了多少帧、上一帧每根条多高、每根条光晕的范围、上一帧的图
        self.frames = 0
        self.last_heights = [0.0] * BARS
        self.last_shadows: list[tuple] = [()] * BARS
        self.last_image = None
        self.last_push_ok = None       # 上一帧有没有真的推到屏幕上（自查用）

    # -- 外部接口 ----------------------------------------------------------
    def show(self) -> None:
        self._hide.clear()
        self._show.set()

    def hide(self) -> None:
        self._show.clear()
        self._hide.set()

    def stop(self) -> None:
        self._hide.set()

    # -- 运动学（两条画法共用） --------------------------------------------
    def _motion(self, now_ms: float, opened: float, values: list,
                smooth: list) -> tuple[list, list, bool]:
        """算出这一帧每根条的高度和颜色，以及要不要写「正在识别」。"""
        accent, muted = _colors()
        try:
            phase_state = str(self.state())
        except Exception:                 # noqa: BLE001
            phase_state = "listening"
        arming = (now_ms - opened) < 600.0
        label_on = (phase_state == "recognizing" and not arming)
        heights, fills = [], []
        for i in range(BARS):
            if label_on:
                # 一条匀速横穿的波：一段高一段低地走过去，
                # 一眼就能看出"还在干活"，而不是冻在最后一帧
                phase = ((now_ms % RECOG_PERIOD_MS) / RECOG_PERIOD_MS + i * 0.11) % 1.0
                wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
                tall = BAR_MIN + (BAR_MAX - BAR_MIN) * 0.8 * wave
                fills.append(accent)
            elif arming:
                # Handy 的待命：6px 基准 × 0.55~1.5 的呼吸，每根条错开
                phase = ((now_ms - ARM_DELAYS[i]) % ARM_MS) / ARM_MS
                wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
                tall = ARM_BASE * (ARM_SCALE_MIN
                                   + (ARM_SCALE_MAX - ARM_SCALE_MIN) * wave)
                fills.append(muted)
            else:
                target = float(values[i]) if i < len(values) else 0.0
                # Handy 的指数平滑（0.7 / 0.3），再套它的高度公式
                smooth[i] = smooth[i] * 0.7 + target * 0.3
                tall = max(BAR_MIN, min(BAR_MAX, BAR_MIN + (smooth[i] ** 0.7) * 15.0))
                fills.append(accent)
            heights.append(tall)
        return heights, fills, label_on

    def _values(self) -> list:
        try:
            return list(self.bars())[:BARS]
        except Exception:                 # noqa: BLE001
            return []

    # -- 主入口 ------------------------------------------------------------
    def run(self) -> None:
        try:
            if HAS_PIL:
                try:
                    self._run_layered()
                    return
                except Exception as exc:          # noqa: BLE001
                    self.log("柔光浮层没起来（%s），改用兜底画法" % exc)
            self._run_canvas()
        except Exception as exc:                  # noqa: BLE001
            self.log("声纹窗口起不来：%s" % exc)
        finally:
            self._ready.set()
            try:
                if self._root is not None:
                    self._root.destroy()
            except Exception:                     # noqa: BLE001
                pass
            if self.hwnd:
                destroy_window(self.hwnd)

    # -- 首选：32 位分层窗口 + 柔光 ----------------------------------------
    def _run_layered(self) -> None:
        import numpy  # noqa: F401   （push_layered 里要用，先在这里探一次）

        k = _scale()
        w, h = int(WINDOW_W * k), int(WINDOW_H * k)
        root = tk.Tk()
        root.withdraw()                    # 只用它跑消息循环和定时器
        self._root = root
        user32 = ctypes.windll.user32
        x = (user32.GetSystemMetrics(0) - w) // 2
        y = user32.GetSystemMetrics(1) - h - int(BOTTOM_OFFSET * k)
        hwnd = create_overlay_window(x, y, w, h)
        self.hwnd = hwnd
        gap, bw = max(1, int(BAR_GAP * k)), max(2, int(BAR_W * k))
        total = BARS * bw + (BARS - 1) * gap
        x0 = (w - total) // 2
        mid = int(BAR_CENTER_Y * k)
        label_y = int(LABEL_Y * k)
        font = load_font(max(9, int(12 * k)))

        def draw(heights: list, fills: list, label_on: bool) -> None:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            glow = Image.new("L", (w, h), 0)
            gd = ImageDraw.Draw(glow)
            spread = GLOW_SPREAD * k
            for i, tall in enumerate(heights):
                bx = x0 + i * (bw + gap)
                half = max(tall * k / 2.0, 1.0)
                gd.rectangle([bx - spread, mid - half - spread,
                              bx + bw + spread, mid + half + spread], fill=255)
                self.last_shadows[i] = (bx - spread, mid - half - spread,
                                        bx + bw + spread, mid + half + spread)
            glow = glow.filter(ImageFilter.GaussianBlur(max(1.0, GLOW_BLUR * k)))
            shadow = Image.new("RGBA", (w, h), (0, 0, 0, 255))
            shadow.putalpha(glow.point(lambda v: int(v * GLOW_ALPHA)))
            img = Image.alpha_composite(img, shadow)

            # 条子和文字单独一层再叠上去，边界才干净
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            for i, tall in enumerate(heights):
                bx = x0 + i * (bw + gap)
                half = max(tall * k / 2.0, 1.0)
                d.rectangle([bx, mid - half, bx + bw, mid + half],
                            fill=_rgba(fills[i]))
            if label_on and font is not None:
                try:
                    d.text((w / 2.0, label_y), LABEL_TEXT, font=font,
                           fill=(255, 255, 255, 255), anchor="mm",
                           stroke_width=max(1, int(k)), stroke_fill=(0, 0, 0, 230))
                except Exception:             # noqa: BLE001
                    d.text((w / 2.0, label_y), LABEL_TEXT, font=font,
                           fill=(255, 255, 255, 255))
            img = Image.alpha_composite(img, layer)
            self.last_image = img
            self.last_push_ok = push_layered(hwnd, img)

        shown = False
        smooth = [0.0] * BARS
        opened = time.time()

        def tick() -> None:
            nonlocal shown, opened
            if self._hide.is_set():
                self._hide.clear()
                if shown:
                    show_window(hwnd, False)
                    shown = False
            if self._show.is_set():
                if not shown:
                    show_window(hwnd, True)
                    shown = True
                    opened = time.time() * 1000.0     # 重新开始待命动画
                now_ms = time.time() * 1000.0
                heights, fills, label_on = self._motion(now_ms, opened,
                                                        self._values(), smooth)
                try:
                    draw(heights, fills, label_on)
                except Exception as exc:              # noqa: BLE001
                    self.log("柔光绘制失败：%s" % exc)
                self.last_heights = heights
                self.frames += 1
            root.after(50, tick)

        show_window(hwnd, True)
        shown = True
        opened = time.time() * 1000.0
        root.after(50, tick)
        self._ready.set()
        root.mainloop()

    # -- 兜底：tk 画布 + 色键 + 硬阴影 -------------------------------------
    def _run_canvas(self) -> None:
        k = _scale()
        accent, muted = _colors()
        w, h = int(WINDOW_W * k), int(WINDOW_H * k)
        gap, bw = max(1, int(BAR_GAP * k)), max(2, int(BAR_W * k))
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        x = (win.winfo_screenwidth() - w) // 2
        y = win.winfo_screenheight() - h - int(BOTTOM_OFFSET * k)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        canvas = tk.Canvas(win, width=w, height=h, highlightthickness=0, bg=KEY)
        canvas.pack()
        total = BARS * bw + (BARS - 1) * gap
        x0 = (w - total) // 2
        mid = int(BAR_CENTER_Y * k)
        shadow_items, bars_items = [], []
        for i in range(BARS):
            bx = x0 + i * (bw + gap)
            shadow = canvas.create_rectangle(
                bx, mid - int(BAR_MIN * k), bx + bw, mid + int(BAR_MIN * k),
                fill=SHADOW_COLOR, outline="")
            rect = canvas.create_rectangle(
                bx, mid - int(BAR_MIN * k), bx + bw, mid + int(BAR_MIN * k),
                fill=accent, outline="")
            shadow_items.append(shadow)
            bars_items.append((bx, rect))
        canvas_font = ("Microsoft YaHei UI", max(8, int(11 * k)))
        label_shadow = canvas.create_text(
            w // 2 + max(1, int(1.2 * k)), int(LABEL_Y * k) + max(1, int(1.2 * k)),
            text=LABEL_TEXT, fill=SHADOW_COLOR, font=canvas_font, state="hidden")
        label = canvas.create_text(
            w // 2, int(LABEL_Y * k), text=LABEL_TEXT,
            fill=accent, font=canvas_font, state="hidden")
        win.deiconify()
        self._root = root
        try:
            _make_colorkey(win)
        except Exception:                 # noqa: BLE001
            pass

        shown = True
        smooth = [0.0] * BARS
        opened = time.time() * 1000.0
        labelling = False

        def tick() -> None:
            nonlocal shown, opened, labelling
            if self._hide.is_set():
                self._hide.clear()
                if shown:
                    win.withdraw()
                    shown = False
            if self._show.is_set():
                if not shown:
                    win.deiconify()
                    win.attributes("-topmost", True)
                    shown = True
                    opened = time.time() * 1000.0
                now_ms = time.time() * 1000.0
                heights, fills, label_on = self._motion(now_ms, opened,
                                                        self._values(), smooth)
                if label_on != labelling:
                    labelling = label_on
                    state = "normal" if label_on else "hidden"
                    canvas.itemconfigure(label_shadow, state=state)
                    canvas.itemconfigure(label, state=state)
                for i in range(BARS):
                    bx, rect = bars_items[i]
                    tall = heights[i] * k
                    half = max(tall / 2.0, 1.0)
                    canvas.coords(rect, bx, mid - half, bx + bw, mid + half)
                    pad = SHADOW_PAD * k
                    shadow = (bx - pad + SHADOW_DX * k,
                              mid - half - pad + SHADOW_DY * k,
                              bx + bw + pad + SHADOW_DX * k,
                              mid + half + pad + SHADOW_DY * k)
                    canvas.coords(shadow_items[i], *shadow)
                    self.last_shadows[i] = shadow
                    if canvas.itemcget(rect, "fill") != fills[i]:
                        canvas.itemconfigure(rect, fill=fills[i])
                self.last_heights = list(heights)
                self.frames += 1
            root.after(50, tick)

        root.after(50, tick)
        self._ready.set()
        root.mainloop()
