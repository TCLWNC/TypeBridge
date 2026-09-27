package com.textlink.app.net

import org.json.JSONObject

/**
 * 与电脑端 textlink_pc.py 完全一致的通信协议。
 *
 * 手机 -> 电脑：
 *   {"t":"hello","device":"Pixel 8","pin":"1234","v":1}
 *   {"t":"edit","del":2,"ins":"你好"}     先按 2 次退格，再输入"你好"
 *   {"t":"insert","text":"整段文字"}      直接在光标处插入
 *   {"t":"key","key":"ENTER"}            按下某个功能键
 *   {"t":"combo","key":"V","ctrl":true}  组合键
 *
 * 电脑 -> 手机：
 *   {"t":"welcome","name":"DESKTOP-XX","version":"1.0.0",...}
 *   {"t":"peers","count":1,...}
 *   {"t":"error","message":"配对码不正确"}
 */
object Protocol {
    const val APP_ID = "textlink"
    const val DEFAULT_PORT = 8765
    const val UDP_PORT = 8766
    const val VERSION = 1

    fun hello(device: String, pin: String): String = JSONObject()
        .put("t", "hello")
        .put("device", device)
        .put("pin", pin)
        .put("v", VERSION)
        .toString()

    fun edit(delete: Int, insert: String): String = JSONObject()
        .put("t", "edit")
        .put("del", delete)
        .put("ins", insert)
        .toString()

    fun insert(text: String): String = JSONObject()
        .put("t", "insert")
        .put("text", text)
        .toString()

    /** 手机上点「发送」：电脑端先输入这段文字，再按一次回车。 */
    fun send(text: String, enter: Boolean = true): String = JSONObject()
        .put("t", "send")
        .put("text", text)
        .put("enter", enter)
        .toString()

    fun key(name: String): String = JSONObject()
        .put("t", "key")
        .put("key", name)
        .toString()

    fun combo(
        key: String,
        ctrl: Boolean = false,
        alt: Boolean = false,
        shift: Boolean = false,
        meta: Boolean = false
    ): String = JSONObject()
        .put("t", "combo")
        .put("key", key)
        .put("ctrl", ctrl)
        .put("alt", alt)
        .put("shift", shift)
        .put("meta", meta)
        .toString()

    fun probe(): ByteArray = JSONObject()
        .put("app", APP_ID)
        .put("t", "probe")
        .put("v", VERSION)
        .toString()
        .toByteArray()

    /** 心跳：电脑端回 {"t":"pong"}，用来测延迟和保活。 */
    fun ping(): String = JSONObject()
        .put("t", "ping")
        .toString()
}

/** 自动搜索到的一台电脑。 */
data class PcDevice(
    val name: String,
    val host: String,
    val port: Int,
    val needsPin: Boolean,
    val lastSeen: Long = System.currentTimeMillis()
) {
    val key: String get() = "$host:$port"
}
