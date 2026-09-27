package com.crosslink.app

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** 电脑端 HTTP 接口客户端：握手、发指令、订阅事件流（SSE）。 */
class Client(private val base: String) {

    private val http = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)      // SSE 要长连接
        .build()

    private val json = "application/json; charset=utf-8".toMediaType()

    fun hello(name: String, pin: String, deviceId: String = ""): JSONObject {
        val body = JSONObject().put("name", name).put("pin", pin)
            .put("device_id", deviceId).toString()
        return post("/api/hello", body)
    }

    fun op(sid: String, ops: List<JSONObject>): JSONObject {
        val arr = JSONArray()
        ops.forEach { arr.put(it) }
        val body = JSONObject().put("sid", sid).put("ops", arr).toString()
        return post("/api/op", body)
    }

    /**
     * 手机当无线麦克风：把录好的 WAV 整段发给电脑，让电脑用它本地的模型识别。
     * 手机上不需要装任何识别模型。
     */
    fun transcribe(sid: String, wav: ByteArray): JSONObject {
        val body = wav.toRequestBody("audio/wav".toMediaType())
        val req = Request.Builder()
            .url("$base/api/voice/audio?sid=$sid")
            .post(body)
            .build()
        // 识别可能要几秒，单独给这个请求设超时（SSE 那条连接是无限等待的）
        val shortClient = http.newBuilder()
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
        shortClient.newCall(req).execute().use { res ->
            val text = res.body?.string().orEmpty()
            return if (text.isBlank()) JSONObject().put("ok", false)
            else JSONObject(text)
        }
    }

    private fun post(path: String, body: String): JSONObject {
        val req = Request.Builder().url(base + path)
            .post(body.toRequestBody(json)).build()
        http.newCall(req).execute().use { res ->
            val text = res.body?.string().orEmpty()
            return if (text.isBlank()) JSONObject().put("ok", false)
            else JSONObject(text)
        }
    }

    /** 订阅事件流；回调在后台线程，调用方自己切主线程。 */
    fun listen(sid: String = "", onEvent: (JSONObject) -> Unit) {
        // 带上会话 id：手机关掉时连接断开，电脑端据此立刻把设备从列表移除
        val path = if (sid.isEmpty()) "/api/events" else "/api/events?sid=$sid"
        val req = Request.Builder().url(base + path)
            .header("Accept", "text/event-stream").build()
        try {
            http.newCall(req).execute().use { res ->
                val source = res.body?.source() ?: return
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue
                    val payload = line.removePrefix("data:").trim()
                    if (payload.isEmpty()) continue
                    runCatching { onEvent(JSONObject(payload)) }
                }
            }
        } catch (_: Exception) {
            // 断线就安静退出，界面靠重连按钮
        }
    }

    fun close() {
        runCatching { http.dispatcher.executorService.shutdown() }
    }
}
