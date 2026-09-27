# -*- coding: utf-8 -*-
"""网页服务 + 实时事件通道。

电脑端界面和手机端界面都由这里提供；手机通过 HTTP 提交指令，
两端都用 SSE（Server-Sent Events）接收实时状态，任何一端改动另一端立刻看到。
"""

from __future__ import annotations

import io
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

from . import VERSION
from . import asr
from .config import resource_path

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Hub:
    """全局状态：在线设备、输入记录、设置，以及所有订阅者。"""

    def __init__(self, cfg: dict[str, Any], injector, on_change: Callable | None = None) -> None:
        self.cfg = cfg
        self.injector = injector
        self.on_change = on_change or (lambda: None)
        self.mobile_url: list[str] = []
        self.on_quit: Callable | None = None
        self.phones: dict[str, dict] = {}
        self.streams: set[str] = set()
        self.logs: deque[dict] = deque(maxlen=120)
        self.target = {"title": "", "app": "", "self": False}
        # 电脑端本地语音输入（离线 SenseVoice）
        self.voice = asr.VoiceSession(log=lambda text: self.log("电脑", text, "system"))
        self.overlay = None          # 收音时的声纹浮层，第一次用时才创建
        self.server: ThreadingHTTPServer | None = None
        self.started_at = time.time()
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    # -- 设置 --------------------------------------------------------------
    def apply_settings(self, changed: dict) -> None:
        cfg = self.cfg
        for key, value in changed.items():
            if key == "inject":
                self.injector.enabled = bool(value)
            elif key == "method":
                self.injector.method = "clipboard" if value == "clipboard" else "direct"
            elif key == "delay_ms":
                try:
                    self.injector.delay_ms = max(0, min(int(value), 200))
                except (TypeError, ValueError):
                    pass
            elif key == "restore_clipboard":
                self.injector.restore_clipboard = bool(value)
            elif key in cfg:
                cfg[key] = bool(value) if isinstance(cfg[key], bool) else value
        self.save()
        if "autostart" in changed:
            from . import winapi
            winapi.set_autostart(bool(cfg["autostart"]))
        self.on_change()
        self.broadcast({"type": "settings", "state": self.state(self.mobile_url)})

    def save(self) -> None:
        from .config import save as save_cfg
        save_cfg(self.cfg)

    def quit_app(self) -> None:
        if self.on_quit:
            self.on_quit()

    # -- 设备 --------------------------------------------------------------
    def add_phone(self, name: str, addr: str, device_id: str = "") -> dict:
        # 按唯一 ID 认设备：同一台手机重连时先清掉旧记录，
        # 避免列表里出现同一台手机两条、或旧会话残留。
        if device_id:
            with self._lock:
                dup = [sid for sid, info in self.phones.items()
                       if info.get("device_id") == device_id]
            for sid in dup:
                self.drop_phone(sid, "同一台手机重新连接")
        sid = secrets.token_hex(8)
        info = {"sid": sid, "name": (name or "手机").strip()[:40], "addr": addr,
                 "device_id": device_id,
                 "chars": 0, "since": time.time(), "last": "", "last_at": time.time()}
        with self._lock:
            self.phones[sid] = info
        self.push_phones()
        self.log(info["name"], "已连接", "system")
        return info

    def drop_phone(self, sid: str, reason: str = "已断开") -> None:
        with self._lock:
            info = self.phones.pop(sid, None)
        # 顺手把注入器里这台手机的同步基线清掉：否则它下次连上，
        # 第一次同步会把上一次留着的文字当"我打过的"退格退掉
        try:
            self.injector.forget_session(sid)
        except Exception:   # noqa: BLE001
            pass
        if not info:
            return
        self.push_phones()
        self.log(info["name"], reason, "system")

    def touch_phone(self, sid: str, chars: int = 0, last: str = "") -> dict | None:
        with self._lock:
            info = self.phones.get(sid)
            if not info:
                return None
            info["chars"] += chars
            info["last_at"] = time.time()
            if last:
                info["last"] = last[:120]
        self.push_phones()
        return info

    # -- 记录 --------------------------------------------------------------
    def log(self, who: str, text: str, kind: str = "text") -> None:
        entry = {"t": time.strftime("%H:%M:%S"), "who": who, "text": text[:200],
                 "kind": kind, "id": secrets.token_hex(4)}
        self.logs.appendleft(entry)
        self.broadcast({"type": "log", "entry": entry})

    def clear_logs(self) -> None:
        self.logs.clear()
        self.broadcast({"type": "logs", "logs": []})

    # -- 订阅 --------------------------------------------------------------
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def broadcast(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def push_phones(self) -> None:
        self.broadcast({"type": "phones", "phones": self.phone_list()})

    def mark_stream(self, sid: str, on: bool) -> None:
        """记录手机会话的实时连接是否还在。

        注意：**不要**在这里立刻移除设备——手机的实时连接会因为网络抖动断开，
        那样会导致"打一个字就被踢下线"。真正的下线由心跳超时（12 秒）判定。
        """
        if not sid:
            return
        with self._lock:
            if on:
                self.streams.add(sid)
            else:
                self.streams.discard(sid)

    def phone_list(self) -> list[dict]:
        with self._lock:
            items = list(self.phones.values())
        return [{k: v for k, v in p.items() if k != "sid"} | {"sid": p["sid"]}
                for p in sorted(items, key=lambda p: p["since"])]

    # -- 快照 --------------------------------------------------------------
    # -- 语音输入（电脑本地离线识别）----------------------------------------
    def voice_overlay(self):
        """收音时屏幕上的声纹浮层；第一次用到才建窗口。"""
        if self.overlay is None:
            from .overlay import WaveOverlay
            # 传频谱（16 段）给声纹，画出来才是"跟着说话起伏"的波形
            self.overlay = WaveOverlay(bars=lambda: self.voice.bars,
                                       log=lambda t: self.log("电脑", t, "warn"))
            self.overlay.start()
        return self.overlay

    def voice_start(self) -> bool:
        if self.voice.recording:
            return False
        self.voice.start()
        try:
            self.voice_overlay().show()
        except Exception:                  # noqa: BLE001
            pass
        self.broadcast({"type": "voice", "state": "listening"})
        return True

    def voice_stop(self) -> str:
        """停止录音 → 识别 → 文字打进当前窗口。"""
        try:
            text = self.voice.stop()
        finally:
            if self.overlay is not None:
                self.overlay.hide()
        self.deliver_voice(text)
        return text

    def voice_toggle(self) -> None:
        """热键用：正在录就停，否则开始。"""
        if self.voice.recording:
            try:
                self.voice_stop()
            except Exception as exc:        # noqa: BLE001
                self.log("电脑", "语音识别失败：%s" % exc, "warn")
                self.broadcast({"type": "voice", "state": "idle"})
        else:
            self.voice_start()

    def deliver_voice(self, text: str) -> None:
        """识别结果：直接打进电脑当前窗口 + 记一条运行记录 + 同步给各个界面。"""
        text = (text or "").strip()
        if not text:
            self.broadcast({"type": "voice", "state": "idle", "text": ""})
            return
        self.injector.submit("insert", text)
        self.log("电脑", "🎤 " + text[:60], "text")
        self.broadcast({"type": "voice", "state": "done", "text": text})

    def state(self, urls: list[str]) -> dict:
        return {
            "type": "state",
            "app": {"version": VERSION, "name": self.cfg["name"], "port": self.cfg["port"]},
            "urls": urls,
            "pin": self.cfg["pin"],
            "require_pin": self.cfg["require_pin"],
            # 界面语言："zh" / "en" / ""（跟随浏览器）。前端 i18n.js 用它切换文案。
            "lang": self.cfg.get("lang", ""),
            # 语音输入的状态：模型在不在、热键是什么、当前是否在收音
            "voice": {"ready": asr.model_ready(),
                      "hotkey": self.cfg.get("voice_hotkey", ""),
                      "listening": bool(self.voice.recording)},
            "settings": {
                "inject": self.injector.enabled,
                "method": self.injector.method,
                "delay_ms": self.injector.delay_ms,
                "restore_clipboard": self.injector.restore_clipboard,
                "topmost": self.cfg["topmost"],
                "tray": self.cfg["tray"],
                "autostart": self.cfg["autostart"],
                "enter_after_send": self.cfg["enter_after_send"],
            },
            "phones": self.phone_list(),
            "logs": list(self.logs),
            "target": self.target,
            "chars": self.injector.chars,
            "focused": bool(self.phones),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "CrossLink/" + VERSION
    protocol_version = "HTTP/1.1"
    hub: Hub = None            # type: ignore[assignment]

    # -- 工具 --------------------------------------------------------------
    def log_message(self, fmt, *args):   # 静音：不要往控制台刷日志
        if os.environ.get("CROSSLINK_DEBUG"):
            super().log_message(fmt, *args)

    def log_error(self, fmt, *args):
        """打包成无控制台程序时 sys.stderr 是 None，这里必须兜住，
        否则异常处理本身会再抛一次，客户端只能看到连接被断开。"""
        try:
            if os.environ.get("CROSSLINK_DEBUG") and sys.stderr is not None:
                super().log_error(fmt, *args)
        except Exception:   # noqa: BLE001
            pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except Exception:   # noqa: BLE001
            self.close_connection = True

    @property
    def is_local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1", "localhost")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0 or length > 4 * 1024 * 1024:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _static(self, name: str) -> None:
        # 界面文件在 crosslink/web/，图标在 crosslink/assets/，两边都要找。
        # 之前只找了 web/，导致 icon.png 一直是 404 —— 界面左上角那个 logo
        # 就显示成了浏览器默认的“图片加载失败”占位图标。
        from .config import asset_path
        path = resource_path(name)
        if not os.path.exists(path):
            path = asset_path(name)
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(name)[1].lower()
        self._send(200, body, MIME.get(ext, "application/octet-stream"))

    # -- GET ---------------------------------------------------------------
    def do_HEAD(self):   # noqa: N802
        self.do_GET()

    def do_GET(self):   # noqa: N802
        try:
            self._do_get()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:   # noqa: BLE001
            self._fail(exc)

    def _do_get(self) -> None:
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)

        if path in ("/", "/index.html"):
            self._static("index.html")
        elif path in ("/m", "/m/", "/mobile"):
            self._static("mobile.html")
        elif path.startswith("/assets/"):
            self._static(os.path.basename(path))
        elif path == "/api/events":
            self._sse()
        elif path == "/api/state":
            self._json(self.hub.state(self.hub.mobile_url))
        elif path == "/api/qr.png":
            self._qr(query.get("u", [None])[0])
        elif path == "/favicon.ico":
            self._static("icon.png")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    # -- POST --------------------------------------------------------------
    def do_POST(self):   # noqa: N802
        try:
            self._do_post()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:   # noqa: BLE001
            self._fail(exc)

    def _fail(self, exc: Exception) -> None:
        try:
            self.hub.log("电脑", "接口出错：%s: %s" % (type(exc).__name__, exc), "warn")
        except Exception:   # noqa: BLE001
            pass
        try:
            self._json({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, 500)
        except Exception:   # noqa: BLE001
            self.close_connection = True

    def _do_post(self) -> None:
        path = urlparse(self.path).path
        # 手机语音走原始字节（WAV），不能按 JSON 解析，所以放在最前面
        if path == "/api/voice/audio":
            self._voice_audio()
            return
        data = self._body()

        if path == "/api/hello":
            self._hello(data)
        elif path == "/api/op":
            self._op(data)
        elif path == "/api/leave":
            self.hub.drop_phone(str(data.get("sid", "")), "手机已离开")
            self._json({"ok": True})
        elif path.startswith("/api/pc/"):
            if not self.is_local:
                self._json({"ok": False, "error": "只允许本机操作"}, 403)
                return
            self._pc(path, data)
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    # -- 各接口 ------------------------------------------------------------
    def _hello(self, data: dict) -> None:
        hub = self.hub
        if hub.cfg["require_pin"]:
            if str(data.get("pin", "")).strip() != str(hub.cfg["pin"]):
                hub.log("手机", "配对码不正确，已拒绝", "warn")
                self._json({"ok": False, "error": "配对码不正确"}, 403)
                return
        info = hub.add_phone(str(data.get("name", "手机")), self.client_address[0],
                             str(data.get("device_id", ""))[:64])
        self._json({"ok": True, "sid": info["sid"], "pc": hub.cfg["name"],
                    "version": VERSION,
                    "lang": hub.cfg.get("lang", ""),
                    "settings": {"enter_after_send": hub.cfg["enter_after_send"]}})

    def _op(self, data: dict) -> None:
        hub = self.hub
        sid = str(data.get("sid", ""))
        if sid not in hub.phones:
            self._json({"ok": False, "error": "会话已失效，请重新连接"}, 409)
            return
        ops = data.get("ops")
        if not isinstance(ops, list):
            self._json({"ok": False, "error": "指令格式不对"}, 400)
            return
        name = hub.phones[sid]["name"]
        typed = 0
        for op in ops[:40]:
            if not isinstance(op, dict):
                continue
            kind = op.get("k")
            try:
                if kind == "edit":
                    dele = max(0, min(int(op.get("del", 0)), 500))
                    ins = str(op.get("ins", ""))[:4000]
                    if not dele and not ins:
                        continue
                    hub.injector.submit("edit", dele, ins)
                    typed += len(ins)
                    if dele:
                        hub.log(name, "⌫ 退格 %d 次" % dele, "key")
                    if ins:
                        if "\n" not in ins and len(ins) <= 60:
                            hub.log(name, ins, "text")
                        else:
                            hub.log(name, ins[:60].replace("\n", "⏎") + "…", "text")
                elif kind == "insert":
                    text = str(op.get("text", ""))[:4000]
                    hub.injector.submit("insert", text)
                    typed += len(text)
                    hub.log(name, text[:60].replace("\n", "⏎"), "text")
                elif kind == "sync":
                    # 手机端把整段文字交过来，电脑端负责让目标窗口变成这段文字
                    text = str(op.get("text", ""))[:4000]
                    # 带上会话 id：注入器按手机分别记"上次同步的文字"，
                    # 这样多台手机不会互相把对方打的字退掉
                    hub.injector.submit("sync", text, sid)
                    typed += len(text)
                    if text:
                        hub.log(name, text[:60].replace("\n", "⏎"), "text")
                elif kind == "key":
                    key = str(op.get("key", "")).upper()[:16]
                    repeat = max(1, min(int(op.get("repeat", 1)), 100))
                    hub.injector.submit("key", key, repeat)
                    hub.log(name, "⏎ %s%s" % (key, " ×%d" % repeat if repeat > 1 else ""), "key")
                elif kind == "combo":
                    hub.injector.submit("combo", str(op.get("key", ""))[:16],
                                        bool(op.get("ctrl")), bool(op.get("alt")),
                                        bool(op.get("shift")), bool(op.get("meta")))
                    mods = "".join(s for f, s in ((op.get("ctrl"), "Ctrl+"),
                                                  (op.get("alt"), "Alt+"),
                                                  (op.get("shift"), "Shift+"),
                                                  (op.get("meta"), "Win+")) if f)
                    hub.log(name, "%s%s" % (mods, op.get("key", "")), "key")
                elif kind == "note":
                    hub.log(name, str(op.get("text", ""))[:60], "note")
                elif kind == "ping":
                    pass          # 心跳：什么都不做，下面统一 touch_phone 记录时间
                elif kind == "bye":
                    # 手机主动告别（退出输入页 / 从后台划掉）：立刻从设备列表里去掉，
                    # 不用等心跳超时。以前没有这条，划掉 App 之后电脑端还会挂 20 多秒。
                    hub.drop_phone(sid, "手机已退出")
                    self._json({"ok": True})
                    return
            except (TypeError, ValueError):
                continue
        hub.touch_phone(sid, typed)
        self._json({"ok": True, "chars": hub.phones[sid]["chars"]})

    def _pc(self, path: str, data: dict) -> None:
        hub = self.hub
        action = path.rsplit("/", 1)[-1]
        cfg = hub.cfg
        if action == "settings":
            changed = {}
            for key, value in data.items():
                if key in ("inject", "method", "delay_ms", "restore_clipboard",
                           "topmost", "tray", "autostart", "enter_after_send",
                           "require_pin", "name", "lang", "voice_hotkey"):
                    changed[key] = value
            hub.apply_settings(changed)
            self._json({"ok": True, "state": hub.state(hub.mobile_url)})
        elif action == "clear":
            hub.clear_logs()
            self._json({"ok": True})
        elif action == "pin":
            cfg["pin"] = "%04d" % secrets.randbelow(10000)
            hub.save()
            hub.broadcast({"type": "pin", "pin": cfg["pin"]})
            hub.log("电脑", "已更换配对码", "system")
            self._json({"ok": True, "pin": cfg["pin"]})
        elif action == "kick":
            hub.drop_phone(str(data.get("sid", "")), "电脑主动断开")
            self._json({"ok": True})
        elif action == "firewall":
            from . import winapi
            ok = winapi.firewall_add_via_uac(None, cfg["port"])
            detail = str(winapi.firewall_last_result().get("msg", ""))
            hub.log("电脑", "放行防火墙：%s" % detail, "system")
            self._json({"ok": bool(ok), "detail": detail})
        elif action == "voice":
            self._voice(data)
        elif action == "quit":
            self._json({"ok": True})
            hub.broadcast({"type": "quit"})
            threading.Timer(0.35, hub.quit_app).start()
        else:
            self._json({"ok": False, "error": "未知操作"}, 404)

    # -- SSE ---------------------------------------------------------------
    # -- 语音输入 ----------------------------------------------------------
    def _voice(self, data: dict) -> None:
        """本地离线听写。

        start = 开始收音（说完自动停） / stop = 停止并识别 / cancel = 放弃
        file  = 直接识别一个音频文件（也是给自动化测试用的入口）
        """
        hub = self.hub
        action = str(data.get("action", "start"))

        if action == "status":
            self._json({"ok": True, "ready": asr.model_ready(),
                        "state": asr.model_status(), "dir": str(asr.model_dir()),
                        "url": asr.MODEL_URL})
            return
        if action == "file":
            try:
                text = asr.transcribe_file(str(data.get("path", "")))
            except Exception as exc:                    # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 500)
                return
            hub.deliver_voice(text)
            self._json({"ok": True, "text": text})
            return
        if action == "start":
            if not asr.model_ready():
                self._json({"ok": False, "error": "语音模型还没下载",
                            "dir": str(asr.model_dir()), "url": asr.MODEL_URL}, 409)
                return
            hub.voice_start()
            self._json({"ok": True, "listening": True})
            return
        if action == "stop":
            try:
                text = hub.voice_stop()
            except Exception as exc:                    # noqa: BLE001
                hub.broadcast({"type": "voice", "state": "idle"})
                self._json({"ok": False, "error": str(exc)}, 500)
                return
            self._json({"ok": True, "text": text})
            return
        if action == "cancel":
            hub.voice.cancel()
            if hub.overlay is not None:
                hub.overlay.hide()
            hub.broadcast({"type": "voice", "state": "idle"})
            self._json({"ok": True})
            return
        self._json({"ok": False, "error": "未知语音动作"}, 404)

    def _voice_audio(self) -> None:
        """手机录好一段 WAV 直接 POST 过来 → 用电脑上的离线模型识别 → 文字回给手机。

        手机不装识别模型也能用语音：手机只当麦克风，识别在电脑上做。
        """
        hub = self.hub
        query = parse_qs(urlparse(self.path).query)
        sid = (query.get("sid") or [""])[0]
        name = (hub.phones.get(sid) or {}).get("name", "手机")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 8 * 1024 * 1024:
            self._json({"ok": False, "error": "音频长度不对"}, 400)
            return
        raw = self.rfile.read(length)
        started = time.time()
        try:
            text = asr.transcribe_wav_bytes(raw)
        except Exception as exc:                    # noqa: BLE001
            self._json({"ok": False, "error": "识别失败：%s" % exc}, 500)
            return
        took = round(time.time() - started, 2)
        hub.log(name, "🎤 " + ((text or "（没听清）")[:60]), "text")
        hub.broadcast({"type": "voice", "state": "done", "text": text, "from": name})
        self._json({"ok": True, "text": text, "took": took})

    def _sse(self) -> None:
        hub = self.hub
        # 手机订阅时带 ?sid=xxx；连接一断就说明手机退出/断网了
        sid = (parse_qs(urlparse(self.path).query).get("sid") or [""])[0]
        hub.mark_stream(sid, True)
        q = hub.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self._sse_send(hub.state(hub.mobile_url))
            last_ping = time.time()
            while True:
                try:
                    event = q.get(timeout=1.0)
                except queue.Empty:
                    if time.time() - last_ping > 12:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
                    continue
                self._sse_send(event)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hub.unsubscribe(q)
            hub.mark_stream(sid, False)
            self.close_connection = True

    def _sse_send(self, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        self.wfile.write(("data: %s\n\n" % payload).encode("utf-8"))
        self.wfile.flush()

    # -- 二维码 -------------------------------------------------------------
    def _qr(self, url: str | None) -> None:
        hub = self.hub
        target = url or (hub.mobile_url[0] if hub.mobile_url else "http://127.0.0.1")
        try:
            import qrcode
            img = qrcode.make(target)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            self._send(200, buf.getvalue(), "image/png")
        except Exception:   # noqa: BLE001
            self._send(500, b"qr failed", "text/plain; charset=utf-8")


def create_server(hub: Hub, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"hub": hub, "mobile_url": []})
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    httpd.daemon_threads = True
    hub.server = httpd
    return httpd


def local_urls(port: int) -> list[str]:
    from .winapi import local_ipv4_list
    return ["http://%s:%d/m" % (ip, port) for ip in local_ipv4_list()]


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
