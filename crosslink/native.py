# -*- coding: utf-8 -*-
"""原生 Windows 界面（tkinter）——真正的本地 EXE，不用 WebView2、不用浏览器。

在没 GPU 的机器上这是最流畅的方案：界面是系统原生控件，几乎不占资源。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from . import APP_TITLE, VERSION
from . import winapi

BG = "#000000"
CARD = "#1A1B21"
ROW = "#111216"
LINE = "#25262C"
TEXT = "#FFFFFF"
DIM = "#C7C9D4"
MUTED = "#8B8E9D"
PRIMARY = "#B4C5FF"
ON_PRIMARY = "#0B2A5B"
OK = "#4CD07D"
BAD = "#FF6B6B"


class NativeUI:
    def __init__(self, app) -> None:
        self.app = app
        self.hub = app.hub
        self.cfg = app.cfg
        self.root = tk.Tk()
        self.root.title("%s v%s · %s" % (APP_TITLE, VERSION, self.cfg["name"]))
        self.root.configure(bg=BG)
        self.root.geometry("880x620")
        self.root.minsize(780, 560)
        try:
            icon = tk.PhotoImage(file=__import__("crosslink.config", fromlist=["x"]).asset_path("icon.png"))
            self.root.iconphoto(True, icon)
            self._icon = icon
        except Exception:   # noqa: BLE001
            pass
        self._build()
        self.root.after(400, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 布局 ----------------
    def _build(self) -> None:
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(family="Microsoft YaHei UI", size=10)

        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text=APP_TITLE, bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        self.lbl_state = tk.Label(head, text="● 等待手机连接", bg=BG, fg=MUTED,
                                  font=("Microsoft YaHei UI", 10))
        self.lbl_state.pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=8)
        body.columnconfigure(0, weight=0, minsize=280)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # 左：连接信息 + 设置
        left = tk.Frame(body, bg=CARD)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._card_title(left, "连接信息")
        self.lbl_addr = self._kv(left, "本机地址", "-")
        self.lbl_pin = self._kv(left, "配对码", self.cfg["pin"])
        btns = tk.Frame(left, bg=CARD)
        btns.pack(fill="x", padx=14, pady=(6, 12))
        self._button(btns, "复制地址", self._copy_addr).pack(side="left")
        self._button(btns, "换配对码", self._new_pin).pack(side="left", padx=8)

        self._card_title(left, "输入设置")
        self.var_inject = tk.BooleanVar(value=bool(self.cfg["inject"]))
        self._check(left, "键盘注入（关闭后不接收输入）", self.var_inject, self._apply)
        self.var_pin = tk.BooleanVar(value=bool(self.cfg["require_pin"]))
        self._check(left, "需要配对码", self.var_pin, self._apply)
        self.var_top = tk.BooleanVar(value=bool(self.cfg["topmost"]))
        self._check(left, "窗口置顶", self.var_top, self._apply)

        row = tk.Frame(left, bg=CARD)
        row.pack(fill="x", padx=14, pady=(8, 4))
        tk.Label(row, text="输入方式", bg=CARD, fg=DIM).pack(side="left")
        self.var_method = tk.StringVar(value=self.cfg["method"])
        tk.OptionMenu(row, self.var_method, "direct", "clipboard",
                      command=lambda _=None: self._apply()).pack(side="right")
        row2 = tk.Frame(left, bg=CARD)
        row2.pack(fill="x", padx=14, pady=(4, 12))
        tk.Label(row2, text="字间延迟", bg=CARD, fg=DIM).pack(side="left")
        self.var_delay = tk.IntVar(value=int(self.cfg["delay_ms"]))
        tk.Spinbox(row2, from_=0, to=200, increment=5, width=5,
                   textvariable=self.var_delay, command=self._apply).pack(side="right")

        # 右：设备 + 记录
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        dev = tk.Frame(right, bg=CARD)
        dev.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._card_title(dev, "在线设备")
        self.dev_box = tk.Frame(dev, bg=CARD)
        self.dev_box.pack(fill="x", padx=14, pady=(0, 12))

        logs = tk.Frame(right, bg=CARD)
        logs.grid(row=1, column=0, sticky="nsew")
        top = tk.Frame(logs, bg=CARD)
        top.pack(fill="x")
        self._card_title(top, "输入记录", side="left")
        self._button(top, "清空", self._clear_logs).pack(side="right", padx=14, pady=(10, 6))
        self.log = tk.Text(logs, bg=CARD, fg=DIM, bd=0, highlightthickness=0,
                           font=("Microsoft YaHei UI", 10), wrap="word")
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.log.configure(state="disabled")

        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(foot, text="手机：同一 Wi-Fi 打开 App，点设备即连",
                 bg=BG, fg=MUTED).pack(side="left")
        self._button(foot, "退出程序", self._quit).pack(side="right")

    def _card_title(self, parent, text, side="top"):
        tk.Label(parent, text=text, bg=parent["bg"], fg=MUTED,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(
            side=side, anchor="w", padx=14, pady=(12, 6))

    def _kv(self, parent, key, value):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=14, pady=2)
        tk.Label(row, text=key, bg=CARD, fg=MUTED).pack(side="left")
        lbl = tk.Label(row, text=value, bg=CARD, fg=TEXT)
        lbl.pack(side="right")
        return lbl

    def _check(self, parent, text, var, cmd):
        tk.Checkbutton(parent, text=text, variable=var, command=cmd,
                       bg=CARD, fg=DIM, selectcolor=ROW, activebackground=CARD,
                       activeforeground=TEXT, bd=0, highlightthickness=0,
                       anchor="w").pack(fill="x", padx=14, pady=2)

    def _button(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=ROW, fg=DIM,
                         activebackground=CARD, activeforeground=TEXT,
                         bd=0, highlightthickness=0, padx=12, pady=6)

    # ---------------- 行为 ----------------
    def _apply(self) -> None:
        self.hub.apply_settings({
            "inject": bool(self.var_inject.get()),
            "require_pin": bool(self.var_pin.get()),
            "topmost": bool(self.var_top.get()),
            "method": self.var_method.get(),
            "delay_ms": int(self.var_delay.get()),
        })

    def _copy_addr(self) -> None:
        url = self.hub.mobile_url[0] if self.hub.mobile_url else ""
        if url:
            winapi.clipboard_set_text(url)
            self.hub.log("电脑", "手机链接已复制：%s" % url, "system")

    def _new_pin(self) -> None:
        from .config import new_pin
        self.cfg["pin"] = new_pin()
        self.hub.save()
        self.lbl_pin.configure(text=self.cfg["pin"])
        self.hub.log("电脑", "已更换配对码：%s" % self.cfg["pin"], "system")

    def _clear_logs(self) -> None:
        self.hub.clear_logs()

    def _quit(self) -> None:
        self.app.quit()

    def _on_close(self) -> None:
        if self.cfg.get("tray", True):
            self.root.withdraw()
            self.hub.log("电脑", "已最小化（从托盘可再打开）", "system")
        else:
            self.app.quit()

    # ---------------- 刷新 ----------------
    def _tick(self) -> None:
        try:
            urls = self.hub.mobile_url or ["-"]
            self.lbl_addr.configure(text=urls[0])
            phones = self.hub.phone_list()
            if phones:
                names = "、".join(p["name"] for p in phones)
                self.lbl_state.configure(text="● 已连接 %d 台 · %s" % (len(phones), names), fg=OK)
            else:
                self.lbl_state.configure(text="● 等待手机连接", fg=MUTED)
            for child in self.dev_box.winfo_children():
                child.destroy()
            if not phones:
                tk.Label(self.dev_box, text="还没有手机连接（手机打开 App 会自动出现）",
                         bg=CARD, fg=MUTED).pack(anchor="w")
            for p in phones:
                row = tk.Frame(self.dev_box, bg=ROW)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=p["name"], bg=ROW, fg=TEXT).pack(side="left", padx=10, pady=8)
                tk.Label(row, text="%s · %d 字" % (p["addr"], p["chars"]),
                         bg=ROW, fg=MUTED).pack(side="left")
                self._button(row, "断开", lambda sid=p["sid"]: self.hub.drop_phone(sid, "电脑主动断开")
                             ).pack(side="right", padx=8, pady=4)
            lines = ["%s  %s  %s" % (e["t"], e["who"], e["text"]) for e in list(self.hub.logs)[:80]]
            text = "\n".join(lines) if lines else "（还没有记录）"
            if self.log.get("1.0", "end-1c") != text:
                self.log.configure(state="normal")
                self.log.delete("1.0", "end")
                self.log.insert("1.0", text)
                self.log.configure(state="disabled")
        except Exception as exc:   # noqa: BLE001
            print("原生界面刷新出错:", exc, flush=True)
        self.root.after(700, self._tick)

    def run(self) -> None:
        self.root.mainloop()
