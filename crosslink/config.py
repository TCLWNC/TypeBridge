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
    # 语音输入热键（全局生效）："F9" / "Ctrl+Alt+Space" 这样，空字符串表示不设
    "voice_hotkey": "F9",
    # 语音热键的触发方式："hold" 按住说话（松开即停） / "toggle" 按一下开始、再按一下结束
    "voice_hotkey_mode": "hold",
    # 启动时自动去 GitHub 看一眼有没有新版本（只查、不下、不装）
    "check_updates": True,
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


def save(cfg: dict[str, Any], keys: list[str] | None = None) -> None:
    """写配置。

    keys 给了就做"只改这几个键"的合并写：先读盘上现在的值，再把本次改的键盖上去。
    这样即使有第二个实例（或上一个没关干净的进程）内存里是旧值，
    它退出时也不会把别人刚改好的设置覆盖回去 ——
    "设置每次重启都得重设一遍"就是这么来的。
    """
    data = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    if keys:
        try:
            with open(config_path(), "r", encoding="utf-8") as fh:
                disk = json.load(fh)
            if isinstance(disk, dict):
                for k, v in disk.items():
                    if k in DEFAULTS and k not in keys:
                        data[k] = v
        except (OSError, ValueError):
            pass
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
