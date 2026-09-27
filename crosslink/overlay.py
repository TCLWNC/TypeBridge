# -*- coding: utf-8 -*-
"""收音时屏幕上的声纹指示器。

一个无边框、置顶的小窗口，里面是一排随麦克风音量起伏的竖条 —— 表示"正在读语音"。
用 tkinter 画，不依赖任何额外库；窗口不会抢焦点（点它也不会把焦点从目标程序拿走）。
"""

from __future__ import annotations

import threading
import tkinter as tk

BAR_COUNT = 21
WIDTH, HEIGHT = 320, 104


class WaveOverlay(threading.Thread):
    """level() 返回 0..1 的当前音量；show()/hide() 控制显示。"""

    def __init__(self, level, log=None) -> None:
        super().__init__(daemon=True, name="crosslink-overlay")
        self.level = level
        self.log = log or (lambda *_: None)
        self._want_show = threading.Event()
        self._want_hide = threading.Event()
        self._ready = threading.Event()
        self._root = None
        self._canvas = None
        self._win = None

    # 外部接口（可从任意线程调用）
    def show(self) -> None:
        self._want_hide.clear()
        self._want_show.set()

    def hide(self) -> None:
        self._want_show.clear()
        self._want_hide.set()

    def stop(self) -> None:
        self._want_hide.set()

    # 线程主体
    def run(self) -> None:
        try:
            root = tk.Tk()
            root.withdraw()
            win = tk.Toplevel(root)
            win.overrideredirect(True)          # 没有标题栏/边框
            win.attributes("-topmost", True)    # 永远在最上层
            try:
                win.attributes("-alpha", 0.92)
            except tk.TclError:
                pass
            win.configure(bg="#14161C")
            win.geometry("%dx%d+%d+%d" % (
                WIDTH, HEIGHT,
                (win.winfo_screenwidth() - WIDTH) // 2,
                win.winfo_screenheight() - HEIGHT - 120))
            canvas = tk.Canvas(win, width=WIDTH, height=HEIGHT, bg="#14161C",
                               highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            canvas.create_text(WIDTH // 2, 18, text="正在听…", fill="#B4C5FF",
                               font=("Microsoft YaHei UI", 11))
            bars = []
            gap = 4
            bw = max(3, (WIDTH - 40 - (BAR_COUNT - 1) * gap) // BAR_COUNT)
            x0 = (WIDTH - (BAR_COUNT * bw + (BAR_COUNT - 1) * gap)) // 2
            for i in range(BAR_COUNT):
                x = x0 + i * (bw + gap)
                bars.append(canvas.create_rectangle(x, 70, x + bw, 72,
                                                    fill="#4C7DFF", outline=""))
            win.withdraw()
            self._root, self._win, self._canvas = root, win, canvas
            self._ready.set()

            history = [0.0] * BAR_COUNT

            def tick() -> None:
                if self._want_hide.is_set():
                    self._want_hide.clear()
                    win.withdraw()
                if self._want_show.is_set():
                    if win.state() == "withdrawn":
                        win.deiconify()
                        win.attributes("-topmost", True)
                    lv = 0.0
                    try:
                        lv = max(0.0, min(1.0, float(self.level())))
                    except Exception:           # noqa: BLE001
                        lv = 0.0
                    history.pop(0)
                    history.append(lv)
                    mid = 70
                    for rect, val in zip(bars, history):
                        h = 4 + val * 48
                        x1, _y1, x2, _y2 = canvas.coords(rect)
                        canvas.coords(rect, x1, mid - h, x2, mid + h)
                        canvas.itemconfigure(
                            rect, fill="#B4C5FF" if val > 0.08 else "#3A4570")
                root.after(60, tick)

            root.after(60, tick)
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
