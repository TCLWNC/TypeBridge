# -*- coding: utf-8 -*-
"""配置读写：全部设置落在 %APPDATA%\\CrossLink\\config.json。"""

from __future__ import annotations

import json
import os
import random
import sys
from typing import Any

DEFAULTS: dict[str, Any] = {
    "name": "",                 # 电脑名（手机上显示）
    "device_id": "",
    "pin": "",                  # 配对码，require_pin 打开时才校验
    "require_pin": False,       # 默认像 LocalSend 一样，同网段免配对
    "inject": True,             # 键盘注入总开关
    "method": "direct",         # direct=Unicode 注入 / clipboard=剪贴板粘贴
    "delay_ms": 0,              # 字间延迟
    "restore_clipboard": True,  # 剪贴板方式下用完还原剪贴板
    "topmost": False,           # 窗口置顶
    "tray": True,               # 关闭时最小化到托盘
    "autostart": False,         # 开机自启
    "enter_after_send": False,  # 发送后自动回车
    "port": 8788,
    # 界面模式：browser = 用系统默认浏览器打开（好看 + 弱机上也顺）
    #           native  = tkinter 原生窗口（最省资源，但外观朴素，可用 --native 切换）
    #           web     = 内嵌 WebView2 窗口（最好看，但没 GPU 的机器会卡，可用 --web 切换）
    "native": False,
    "browser": False,        # 默认：界面开在 exe 自己的窗口里（内嵌内核）
    "qt": False,             # True 时改用 Qt 原生界面（--qt 切换）；默认仍用网页那套 UI
    "window": [1120, 740],
    # 界面语言："zh" 中文 / "en" English / "" 跟随系统
    "lang": "",
}


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(name: str) -> str:
    """打包后（PyInstaller）与源码运行都能找到的静态资源路径。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "web", name),
                 os.path.join(getattr(sys, "_MEIPASS", here), "crosslink", "web", name),
                 os.path.join(_base_dir(), name)):
        if os.path.exists(cand):
            return cand
    return os.path.join(here, "web", name)


def asset_path(name: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "assets", name),
                 os.path.join(getattr(sys, "_MEIPASS", here), "crosslink", "assets", name),
                 os.path.join(_base_dir(), name)):
        if os.path.exists(cand):
            return cand
    return os.path.join(here, "assets", name)


def config_dir() -> str:
    # 自检/测试脚本可以设 CROSSLINK_CONFIG_DIR 指到临时目录，
    # 免得把自己的实验配置（端口、配对码开关）写回用户真正的配置里。
    override = os.environ.get("CROSSLINK_CONFIG_DIR")
    if override:
        try:
            os.makedirs(override, exist_ok=True)
            return override
        except OSError:
            pass
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        fallback = os.path.join(_base_dir(), "data")
        os.makedirs(fallback, exist_ok=True)
        return fallback


APP_DIR_NAME = "CrossLink"


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    if not cfg["device_id"]:
        cfg["device_id"] = "%012x" % random.getrandbits(48)
    if not cfg["pin"]:
        cfg["pin"] = new_pin()
    if not cfg["name"]:
        cfg["name"] = default_name()
    return cfg


def save(cfg: dict[str, Any]) -> None:
    data = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    try:
        with open(config_path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def new_pin() -> str:
    return "%04d" % random.randint(0, 9999)


def default_name() -> str:
    if sys.platform == "win32":
        name = os.environ.get("COMPUTERNAME") or "我的电脑"
        # DESKTOP-XXXX 这类名字在手机上不好认，转得友好一点
        if name.upper().startswith("DESKTOP-"):
            return "我的电脑"
        return name
    return os.uname().nodename if hasattr(os, "uname") else "我的电脑"
