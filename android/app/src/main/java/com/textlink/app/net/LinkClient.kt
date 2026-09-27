package com.textlink.app.net

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** 连接到同一台电脑的其他设备（由电脑端下发）。 */
data class PeerInfo(val name: String, val ip: String, val chars: Int)

sealed class LinkEvent {
    data class Ready(val pcName: String, val version: String) : LinkEvent()
    data class Closed(val reason: String) : LinkEvent()
    data class Failed(val message: String) : LinkEvent()
    data class Rejected(val message: String) : LinkEvent()
    data class Peers(val devices: List<PeerInfo>) : LinkEvent()
    /** 一次心跳往返耗时（毫秒）。 */
    data class Latency(val millis: Long) : LinkEvent()
    /** 电脑上输入框的内容变了，手机端需要同步。 */
    data class Mirror(val text: String) : LinkEvent()
}

/** 与电脑端保持一条 WebSocket 长连接。 */
class LinkClient {

    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    private var socket: WebSocket? = null
    private var host: String = ""
    private var port: Int = Protocol.DEFAULT_PORT
    @Volatile private var pingSentAt = 0L

    private val _events = MutableSharedFlow<LinkEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<LinkEvent> = _events

    @Volatile var connected: Boolean = false
        private set

    val target: String get() = "$host:$port"

    fun connect(device: PcDevice, deviceName: String, pin: String) {
        disconnect()
        host = device.host
        port = device.port
        val request = Request.Builder().url("ws://${device.host}:${device.port}/ws").build()
        socket = http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(Protocol.hello(deviceName, pin))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val obj = try {
                    JSONObject(text)
                } catch (_: Exception) {
                    return
                }
                when (obj.optString("t")) {
                    "welcome" -> {
                        connected = true
                        _events.tryEmit(
                            LinkEvent.Ready(
                                obj.optString("name", "Windows 电脑"),
                                obj.optString("version", "")
                            )
                        )
                    }
                    "error" -> _events.tryEmit(
                        LinkEvent.Rejected(obj.optString("message", "配对失败"))
                    )
                    "peers" -> {
                        val array = obj.optJSONArray("devices")
                        val list = buildList {
                            if (array != null) {
                                for (i in 0 until array.length()) {
                                    val item = array.optJSONObject(i) ?: continue
                                    if (!item.optBoolean("authed", true)) continue
                                    add(
                                        PeerInfo(
                                            name = item.optString("name", "设备"),
                                            ip = item.optString("ip", ""),
                                            chars = item.optInt("chars", 0)
                                        )
                                    )
                                }
                            }
                        }
                        _events.tryEmit(LinkEvent.Peers(list))
                    }
                    "mirror" -> _events.tryEmit(LinkEvent.Mirror(obj.optString("text", "")))
                    "pong" -> {
                        val sentAt = pingSentAt
                        if (sentAt > 0) {
                            _events.tryEmit(LinkEvent.Latency(System.currentTimeMillis() - sentAt))
                        }
                    }
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                connected = false
                _events.tryEmit(LinkEvent.Failed(t.message ?: "无法连接到电脑"))
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                connected = false
                _events.tryEmit(LinkEvent.Closed(reason.ifBlank { "连接已断开" }))
            }
        })
    }

    fun sendEdit(delete: Int, insert: String) {
        socket?.send(Protocol.edit(delete, insert))
    }

    fun sendInsert(text: String) {
        socket?.send(Protocol.insert(text))
    }

    /** 手机上点「发送」：电脑端输入并发出去（按回车）。 */
    fun sendFromPhone(text: String, enter: Boolean) {
        socket?.send(Protocol.send(text, enter))
    }

    fun sendKey(name: String) {
        socket?.send(Protocol.key(name))
    }

    fun sendCombo(
        key: String,
        ctrl: Boolean = false,
        alt: Boolean = false,
        shift: Boolean = false,
        meta: Boolean = false
    ) {
        socket?.send(Protocol.combo(key, ctrl, alt, shift, meta))
    }

    fun sendPing() {
        pingSentAt = System.currentTimeMillis()
        socket?.send(Protocol.ping())
    }

    fun disconnect() {
        try {
            socket?.close(1000, "bye")
        } catch (_: Exception) {
        }
        socket = null
        connected = false
    }
}
