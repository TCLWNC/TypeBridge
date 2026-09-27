# -*- coding: utf-8 -*-
"""收音时屏幕上的声纹。

样式照 Handy（github.com/cjpais/Handy，同样是离线语音输入）来：
一个小的深色圆角"药丸"，中间 9 根短竖条，跟着麦克风频谱起伏。
参数也照抄它的：9 根条、每根高 3~18px、取频谱前 9 段、指数平滑 0.7/0.3；
频谱本身是 1024 点 FFT + 对数分频 + dB 映射（见 asr.Spectrum）。

用 tkinter 画，不依赖额外库；窗口无边框、置顶、不抢焦点。
"""

from __future__ import annotations

import ctypes
import threading
import tkinter as tk

BARS = 9                     # Handy 的 WAVE_BARS
BAR_W = 3
BAR_GAP = 3
BAR_MIN, BAR_MAX = 3, 18     # Handy 的 Math.max(3, Math.min(18, 3 + v^0.7 * 15))
PILL_W, PILL_H = 184, 40     # Handy 的胶囊尺寸
RADIUS = 12
BOTTOM_OFFSET = 120

BG = "#1C1C1E"
LINE = "#3A3A3C"
BAR = "#E8E8EE"


def _scale() -> float:
    """DPI 缩放：96dpi 记 1.0，免得高分屏上画出来太小。"""
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:                     # noqa: BLE001
        return 1.0


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

    def show(self) -> None:
        self._hide.clear()
        self._show.set()

    def hide(self) -> None:
        self._show.clear()
        self._hide.set()

    def stop(self) -> None:
        self._hide.set()

    def run(self) -> None:
        try:
            k = _scale()
            w, h = int(PILL_W * k), int(PILL_H * k)
            gap, bw = int(BAR_GAP * k), int(BAR_W * k)
            root = tk.Tk()
            root.withdraw()
            win = tk.Toplevel(root)
            win.overrideredirect(True)          # 无边框
            win.attributes("-topmost", True)    # 置顶
            try:
                win.attributes("-alpha", 0.94)
            except tk.TclError:
                pass
            x = (win.winfo_screenwidth() - w) // 2
            y = win.winfo_screenheight() - h - int(BOTTOM_OFFSET * k)
            win.geometry("%dx%d+%d+%d" % (w, h, x, y))
            canvas = tk.Canvas(win, width=w, height=h, highlightthickness=0,
                               bg="#000000")
            canvas.pack()
            r = int(RADIUS * k)
            canvas.create_polygon(
                r, 0, w - r, 0, w, r, w, h - r, w - r, h, r, h, 0, h - r, 0, r,
                smooth=True, splinesteps=24, fill=BG, outline=LINE,
                width=max(1, int(k)))
            total = BARS * bw + (BARS - 1) * gap
            x0 = (w - total) // 2
            mid = h // 2
            rects = []
            for i in range(BARS):
                bx = x0 + i * (bw + gap)
                rects.append(canvas.create_rectangle(
                    bx, mid - int(BAR_MIN * k), bx + bw, mid + int(BAR_MIN * k),
                    fill=BAR, outline=""))
            win.deiconify()
            self._root = root
            self._ready.set()

            shown = True
            smooth = [0.0] * BARS

            def tick() -> None:
                nonlocal shown
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
                    try:
                        values = list(self.bars())[:BARS]
                    except Exception:           # noqa: BLE001
                        values = []
                    for i in range(BARS):
                        target = float(values[i]) if i < len(values) else 0.0
                        # 照 Handy：指数平滑 prev*0.7 + target*0.3
                        smooth[i] = smooth[i] * 0.7 + target * 0.3
                        tall = BAR_MIN + (smooth[i] ** 0.7) * (BAR_MAX - BAR_MIN)
                        tall = max(BAR_MIN, min(BAR_MAX, tall))
                        half = int(tall * k)
                        bx = x0 + i * (bw + gap)
                        canvas.coords(rects[i], bx, mid - half, bx + bw, mid + half)
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
