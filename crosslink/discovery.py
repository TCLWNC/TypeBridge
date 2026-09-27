# -*- coding: utf-8 -*-
"""UDP 设备发现：手机广播一句探测，电脑回一句身份信息。

协议（明文，同网段）：
    手机 → 广播  "CROSSLINK?"           （也接受 {"t":"probe"}）
    电脑 → 单播  {"t":"crosslink","v":1,"name":"我的电脑","port":8788,
                  "pin":false,"id":"xxxx"}
用到和网页服务同一个端口号（TCP/UDP 独立，防火墙规则里本来就同时放行了两者）。
"""

from __future__ import annotations

import json
import socket
import threading

from . import VERSION

PROBE = b"CROSSLINK?"


class Discovery(threading.Thread):
    def __init__(self, cfg: dict, log=None) -> None:
        super().__init__(daemon=True, name="crosslink-discovery")
        self.cfg = cfg
        self.log = log or (lambda *_: None)
        self.probes = 0
        self._stop = threading.Event()
        self._sock: socket.socket | None = None

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass

    def payload(self) -> bytes:
        return json.dumps({
            "t": "crosslink",
            "v": 1,
            "name": self.cfg["name"],
            "port": int(self.cfg["port"]),
            "pin": bool(self.cfg["require_pin"]),
            "version": VERSION,
            "id": self.cfg["device_id"],
        }, ensure_ascii=False).encode("utf-8")

    def run(self) -> None:
        port = int(self.cfg["port"])
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(0.6)
            self._sock = sock
        except OSError as exc:
            self.log("⚠ 设备发现没起来（UDP %d）：%s" % (port, exc))
            return
        self.log("✔ 设备发现已监听 UDP %d（手机点「搜索电脑」就能找到）" % port)
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() not in (PROBE, b'{"t":"probe"}'):
                continue
            self.probes += 1
            if self.probes == 1:
                self.log("收到手机探测（来自 %s），已回应" % addr[0])
            try:
                sock.sendto(self.payload(), addr)
            except OSError:
                pass
