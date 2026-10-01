# -*- coding: utf-8 -*-
"""检查有没有新版本。

只做一件事：问一下 GitHub 发布页上最新的 tag 是多少，和本机 VERSION 比大小。
不下载、不安装、不改任何东西 —— 有新版本就告诉界面一声，装不装由用户决定。

网络不通 / 被墙 / 限流都会如实报出来（ok=False + error），界面照实显示，
不会假装"已是最新"。
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request

from . import VERSION

REPO = "TCLWNC/TypeBridge"
API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
API_LIST = "https://api.github.com/repos/%s/releases" % REPO
RELEASES_PAGE = "https://github.com/%s/releases" % REPO


def parse_ver(text: str) -> tuple[int, ...]:
    """把 "v1.2.3" / "1.2" 变成 (1, 2, 3)，认不出来的部分当 0。"""
    nums = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_ver(latest), parse_ver(current)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def _fetch(url: str, timeout: float) -> object:
    req = urllib.request.Request(url, headers={
        "User-Agent": "TypeBridge/%s" % VERSION,
        "Accept": "application/vnd.github+json",
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as res:
        return json.loads(res.read().decode("utf-8", "ignore"))


def check(current: str = VERSION, timeout: float = 6.0) -> dict:
    """返回一份界面能直接用的结果。永不抛异常。"""
    out = {
        "ok": False,
        "current": current,
        "latest": "",
        "newer": False,
        "url": RELEASES_PAGE,
        "name": "",
        "checked_at": time.time(),
        "error": "",
    }
    try:
        data = _fetch(API_LATEST, timeout)
    except urllib.error.HTTPError as exc:
        # 发布页一个正式版都没有时 GitHub 会回 404，退回去读列表
        if exc.code == 404:
            try:
                items = _fetch(API_LIST, timeout)
                data = items[0] if isinstance(items, list) and items else {}
            except Exception as inner:      # noqa: BLE001
                out["error"] = "检查失败：%s" % inner
                return out
        elif exc.code == 403:
            out["error"] = "检查太频繁，GitHub 暂时不让问，等会儿再试"
            return out
        else:
            out["error"] = "检查失败：HTTP %d" % exc.code
            return out
    except Exception as exc:                # noqa: BLE001
        out["error"] = "连不上 GitHub：%s" % exc
        return out

    if not isinstance(data, dict) or not data.get("tag_name"):
        out["error"] = "发布页上没有可用版本"
        return out

    out["ok"] = True
    out["latest"] = str(data.get("tag_name", "")).lstrip("vV")
    out["name"] = str(data.get("name") or "")
    out["url"] = str(data.get("html_url") or RELEASES_PAGE)
    out["newer"] = is_newer(out["latest"], current)
    return out
