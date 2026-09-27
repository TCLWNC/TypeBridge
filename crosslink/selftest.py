# -*- coding: utf-8 -*-
"""自检：把环境、依赖、端口、防火墙、注入能力写成一份报告。

打包成 EXE 以后没有控制台，这个报告就是排查问题的第一现场：
    CrossLink.exe --selftest
报告文件：%APPDATA%\\CrossLink\\自检报告.txt
"""

from __future__ import annotations

import io
import os
import socket
import sys
import traceback

from . import APP_TITLE, VERSION
from . import config as config_mod
from . import winapi


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def run() -> tuple[bool, str]:
    lines: list[str] = []
    ok = True

    def add(label: str, good: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and good
        lines.append("%s %s%s" % ("✔" if good else "✘", label, ("  → " + detail) if detail else ""))

    lines.append("%s v%s 自检报告" % (APP_TITLE, VERSION))
    lines.append("时间：%s" % __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("Python：%s" % sys.version.split()[0])
    lines.append("打包运行：%s" % bool(getattr(sys, "frozen", False)))
    lines.append("程序路径：%s" % sys.executable)
    lines.append("配置目录：%s" % config_mod.config_dir())
    lines.append("")

    cfg = config_mod.load()
    add("配置文件可读写", os.path.exists(config_mod.config_path()),
        config_mod.config_path())
    add("电脑名", bool(cfg["name"]), cfg["name"])
    add("配对码", bool(cfg["pin"]), cfg["pin"] if cfg["require_pin"] else "（未启用）")

    for name in ("index.html", "mobile.html", "base.css", "app.js", "mobile.js"):
        path = config_mod.resource_path(name)
        add("界面资源 " + name, os.path.exists(path), path)
    for name in ("icon.png", "icon.ico"):
        path = config_mod.asset_path(name)
        add("图标 " + name, os.path.exists(path), path)

    port = int(cfg["port"])
    add("端口 %d 可用" % port, _port_free(port))

    if sys.platform == "win32":
        add("防火墙规则已放行", winapi.firewall_rule_exists(),
            "没放行的话手机连不上，界面上点「放行防火墙」")
    add("本机地址", bool(winapi.local_ipv4_list()), ", ".join(winapi.local_ipv4_list()))

    try:
        import qrcode
        img = qrcode.make("http://example.com")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        add("二维码生成", buf.tell() > 100, "%d 字节" % buf.tell())
    except Exception as exc:   # noqa: BLE001
        add("二维码生成", False, "%s: %s" % (type(exc).__name__, exc))

    try:
        import PIL
        add("Pillow（托盘图标）", True, PIL.__version__)
    except Exception as exc:   # noqa: BLE001
        add("Pillow（托盘图标）", False, str(exc))

    try:
        import pystray
        add("托盘组件", True, getattr(pystray, "__version__", "ok"))
    except Exception as exc:   # noqa: BLE001
        add("托盘组件", False, str(exc))

    try:
        import webview
        add("窗口组件（pywebview）", True, str(getattr(webview, "__version__", "ok")))
    except Exception as exc:   # noqa: BLE001
        add("窗口组件（pywebview）", False, str(exc))

    if sys.platform == "win32":
        try:
            before = winapi.clipboard_get_text()
            add("剪贴板读取", True, ("%d 字" % len(before)) if before else "（空）")
        except Exception as exc:   # noqa: BLE001
            add("剪贴板读取", False, str(exc))
        try:
            info = winapi.foreground_info()
            add("前台窗口识别", True, "%s / %s" % (info.get("app", ""), info.get("title", "")[:30]))
        except Exception as exc:   # noqa: BLE001
            add("前台窗口识别", False, str(exc))
        try:
            winapi.type_text("")   # 空串不发事件，只验证结构体可用
            add("键盘注入模块", True, "SendInput 结构体就绪")
        except Exception as exc:   # noqa: BLE001
            add("键盘注入模块", False, str(exc))

    lines.append("")
    lines.append("结论：" + ("一切正常 ✅" if ok else "有项目未通过，按上面的 ✘ 排查"))
    report = "\n".join(lines)
    try:
        path = os.path.join(config_mod.config_dir(), "自检报告.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        report += "\n\n报告已保存：%s" % path
    except OSError:
        pass
    return ok, report


def main() -> int:
    try:
        ok, report = run()
    except Exception:   # noqa: BLE001
        ok, report = False, traceback.format_exc()
    try:
        print(report)
    except Exception:   # noqa: BLE001
        pass
    # 双击运行时没有控制台，直接把报告用记事本打开（不阻塞）
    if getattr(sys, "frozen", False):
        try:
            path = os.path.join(config_mod.config_dir(), "自检报告.txt")
            os.startfile(path)   # noqa: S606
        except Exception:   # noqa: BLE001
            pass
    return 0 if ok else 1
