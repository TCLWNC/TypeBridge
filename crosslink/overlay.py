# -*- coding: utf-8 -*-
"""收音时屏幕上的声纹 —— 效果照 Handy 搬过来。

Handy（github.com/cjpais/Handy，同样是离线语音输入）的声纹参数，这里是原样抄的：
  .swave        flex、居中、gap 3px、高 18px
  .swave i      width 4px、min 3px、max 18px、border-radius 2px、颜色 = 强调色
  高度公式       max(3, min(18, 3 + v^0.7 * 15))，值来自 FFT 频段（见 asr.Spectrum）
  待命动画      scaleY 0.55~1.5、900ms 循环、每根条延迟 0/75/150/225/300ms（中间最晚）
  配色          浅色主题 #FAA2CA，深色主题 #F28CBB（Handy 的 --color-logo-primary）

窗口本身**背景透明**（Win32 分层窗口 + 色键），所以屏幕上只剩那几根粉色的条，
不会挡到后面的东西；窗口置顶且不抢焦点。
"""

from __future__ import annotations

import ctypes
import math
import threading
import time
import tkinter as tk

# ---- Handy 的尺寸（逻辑像素，最后按 DPI 缩放） ----
BARS = 9
BAR_W = 4
BAR_GAP = 3
BAR_MIN, BAR_MAX = 3.0, 18.0
BAR_RADIUS = 2
WINDOW_W, WINDOW_H = 184, 40
BOTTOM_OFFSET = 120
ARM_MS = 900.0                 # 待命动画周期
ARM_DELAYS = [0, 75, 150, 225, 300, 225, 150, 75, 0]
ARM_BASE = 6.0                 # .swave.arming i { height: 6px }
ARM_SCALE_MIN, ARM_SCALE_MAX = 0.55, 1.5

KEY = "#000000"                # 色键：这个颜色会被挖成透明（所以画笔别用它）


def _scale() -> float:
    """DPI 缩放：96dpi 记 1.0。"""
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:                     # noqa: BLE001
        return 1.0


def _colors() -> tuple[str, str]:
    """竖条配色：(工作时, 待命时)。

    Handy 原本是粉色的（浅色主题 #FAA2CA / 深色 #F28CBB），这里按用户要求改成白色；
    待命动画用暗一点的灰，跟活动状态区分开。
    """
    return ("#FFFFFF", "#9A9A9A")


def _make_colorkey(win: tk.Toplevel) -> None:
    """用分层窗口把 KEY 颜色挖透明；只设色键不设 alpha，所以条本身是不透明的。"""
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    LWA_COLORKEY = 0x00000001
    user32 = ctypes.windll.user32
    win.update_idletasks()
    hwnd = int(win.winfo_id())
    style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
    user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(ctypes.c_void_p(hwnd),
                                      ctypes.c_uint32(0x000000),
                                      ctypes.c_ubyte(255), LWA_COLORKEY)


class WaveOverlay(threading.Thread):
    """bars() 返回 16 个 0..1 的频段值；show()/hide() 控制显示。"""

    def __init__(self, bars, log=None) -> None:
        super().__init__(daemon=True, name="crosslink-overlay")
        self.bars = bars
        self.log = log or (lambda *_: None)
        self._show = threading.Event()
        self._hide = threading.Event()
        self._ready = threading.Event()
        self._root = None

    # -- 外部接口 ----------------------------------------------------------
    def show(self) -> None:
        self._hide.clear()
        self._show.set()

    def hide(self) -> None:
        self._show.clear()
        self._hide.set()

    def stop(self) -> None:
        self._hide.set()

    # -- 画窗口 ------------------------------------------------------------
    def run(self) -> None:
        try:
            k = _scale()
            accent, muted = _colors()
            w, h = int(WINDOW_W * k), int(WINDOW_H * k)
            gap, bw = int(BAR_GAP * k), int(BAR_W * k)
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
            mid = h // 2
            bars_items = []
            for i in range(BARS):
                bx = x0 + i * (bw + gap)
                # 竖条就是长方形（不要圆角）
                rect = canvas.create_rectangle(
                    bx, mid - int(BAR_MIN * k), bx + bw, mid + int(BAR_MIN * k),
                    fill=accent, outline="")
                bars_items.append((bx, rect))

            win.deiconify()
            self._root = root
            self._ready.set()
            try:
                _make_colorkey(win)
            except Exception:                 # noqa: BLE001
                pass

            shown = True
            smooth = [0.0] * BARS
            opened = time.time()

            def place(i: int, height: float, fill: str) -> None:
                bx, rect = bars_items[i]
                half = max(height / 2.0, 1.0)
                canvas.coords(rect, bx, mid - half, bx + bw, mid + half)
                if canvas.itemcget(rect, "fill") != fill:
                    canvas.itemconfigure(rect, fill=fill)

            def tick() -> None:
                nonlocal shown, opened
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
                        opened = time.time()      # 重新开始待命动画
                    try:
                        values = list(self.bars())[:BARS]
                    except Exception:             # noqa: BLE001
                        values = []
                    arming = (time.time() - opened) * 1000.0 < 600.0
                    now_ms = time.time() * 1000.0
                    for i in range(BARS):
                        if arming:
                            # Handy 的待命：6px 基准 × 0.55~1.5 的呼吸，每根条错开
                            phase = ((now_ms - ARM_DELAYS[i]) % ARM_MS) / ARM_MS
                            wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
                            scale = ARM_SCALE_MIN + (ARM_SCALE_MAX - ARM_SCALE_MIN) * wave
                            place(i, ARM_BASE * scale * k, muted)
                            continue
                        target = float(values[i]) if i < len(values) else 0.0
                        # Handy 的指数平滑（0.7 / 0.3），再套它的高度公式
                        smooth[i] = smooth[i] * 0.7 + target * 0.3
                        tall = max(BAR_MIN,
                                   min(BAR_MAX, BAR_MIN + (smooth[i] ** 0.7) * 15.0))
                        place(i, tall * k, accent)
                root.after(50, tick)

            root.after(50, tick)
            root.mainloop()
        except Exception as exc:                # noqa: BLE001
            self.log("声纹窗口起不来：%s" % exc)
        finally:
            self._ready.set()
            try:
                if self._root is not None:
                    self._root.destroy()
            except Exception:                   # noqa: BLE001
                pass
