package com.textlink.app

import android.app.Application
import android.os.Build
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.TextRange
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.textlink.app.net.Discovery
import com.textlink.app.net.LinkClient
import com.textlink.app.net.LinkEvent
import com.textlink.app.net.PcDevice
import com.textlink.app.net.PeerInfo
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class Screen { Devices, Typing }
enum class Level { Idle, Ok, Warn, Bad }
enum class SendMode { Live, Batch }

class LinkViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("textlink", 0)
    private val client = LinkClient()
    private val discovery = Discovery(app.applicationContext, viewModelScope)

    private val _devices = MutableStateFlow<List<PcDevice>>(emptyList())
    val devices: StateFlow<List<PcDevice>> = _devices.asStateFlow()

    private val _screen = MutableStateFlow(Screen.Devices)
    val screen: StateFlow<Screen> = _screen.asStateFlow()

    private val _status = MutableStateFlow("正在搜索同一 Wi-Fi 下的电脑…")
    val status: StateFlow<String> = _status.asStateFlow()

    private val _level = MutableStateFlow(Level.Warn)
    val level: StateFlow<Level> = _level.asStateFlow()

    private val _pcName = MutableStateFlow<String?>(null)
    val pcName: StateFlow<String?> = _pcName.asStateFlow()

    private val _target = MutableStateFlow("")
    val target: StateFlow<String> = _target.asStateFlow()

    private val _mode = MutableStateFlow(SendMode.Live)
    val mode: StateFlow<SendMode> = _mode.asStateFlow()

    private val _sentChars = MutableStateFlow(0)
    val sentChars: StateFlow<Int> = _sentChars.asStateFlow()

    private val _field = MutableStateFlow(TextFieldValue(""))
    val field: StateFlow<TextFieldValue> = _field.asStateFlow()

    private val _pinTarget = MutableStateFlow<PcDevice?>(null)
    val pinTarget: StateFlow<PcDevice?> = _pinTarget.asStateFlow()

    private val _manualPrompt = MutableStateFlow(false)
    val manualPrompt: StateFlow<Boolean> = _manualPrompt.asStateFlow()

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    /** 配对码输错时的提示，会显示在配对弹窗里。 */
    private val _pinError = MutableStateFlow<String?>(null)
    val pinError: StateFlow<String?> = _pinError.asStateFlow()

    /** 连不上时给出的排查建议。 */
    private val _help = MutableStateFlow<String?>(null)
    val help: StateFlow<String?> = _help.asStateFlow()

    /** 与电脑的心跳延迟（毫秒），-1 表示还没测出来。 */
    private val _latency = MutableStateFlow(-1L)
    val latency: StateFlow<Long> = _latency.asStateFlow()

    /** 已发出、还可以"还原"回输入框的消息（最新的在最后）。 */
    private val _history = MutableStateFlow<List<String>>(emptyList())
    val history: StateFlow<List<String>> = _history.asStateFlow()

    private val _sendWithEnter = MutableStateFlow(prefs.getBoolean("sendEnter", true))
    val sendWithEnter: StateFlow<Boolean> = _sendWithEnter.asStateFlow()

    private val _sendCount = MutableStateFlow(prefs.getInt("sendCount", 0))
    val sendCount: StateFlow<Int> = _sendCount.asStateFlow()

    private val _lastMirror = MutableStateFlow("")
    val lastMirror: StateFlow<String> = _lastMirror.asStateFlow()

    /** 电脑端下发的设备列表（连在同一台电脑上的设备）。 */
    private val _peers = MutableStateFlow<List<PeerInfo>>(emptyList())
    val peers: StateFlow<List<PeerInfo>> = _peers.asStateFlow()

    /** 是否接收电脑端输入框的变化（反向同步）。 */
    private val _mirrorEnabled = MutableStateFlow(prefs.getBoolean("mirror", true))
    val mirrorEnabled: StateFlow<Boolean> = _mirrorEnabled.asStateFlow()

    val lastHost: String get() = prefs.getString("host", "") ?: ""

    private var lastCommitted = ""
    private var lastDevice: PcDevice? = null
    private var lastPin = ""
    private var retryJob: Job? = null
    private var pingJob: Job? = null
    /** 刚发出去的内容：用来识别"电脑端把这段文字同步回来"的回声，避免看起来像重复发送。 */
    private var lastSentText = ""
    private var mirrorMuteUntil = 0L

    val deviceName: String = "${Build.MANUFACTURER} ${Build.MODEL}".trim().ifBlank { "Android 手机" }

    init {
        viewModelScope.launch {
            discovery.devices.collect { list ->
                _devices.value = list
                if (_screen.value == Screen.Devices && list.isEmpty()) {
                    _level.value = Level.Warn
                    _status.value = "正在搜索同一 Wi-Fi 下的电脑…"
                }
            }
        }
        viewModelScope.launch {
            client.events.collect { event ->
                when (event) {
                    is LinkEvent.Ready -> {
                        _busy.value = false
                        _pinTarget.value = null
                        _pinError.value = null
                        _help.value = null
                        _pcName.value = event.pcName
                        _target.value = client.target
                        _level.value = Level.Ok
                        _status.value = "已连接"
                        _screen.value = Screen.Typing
                        startPingLoop()
                        prefs.edit()
                            .putString("host", lastDevice?.host ?: "")
                            .putInt("port", lastDevice?.port ?: 8765)
                            .putString("name", event.pcName)
                            .apply()
                    }
                    is LinkEvent.Rejected -> {
                        _busy.value = false
                        _level.value = Level.Bad
                        _status.value = event.message
                        _pinError.value = event.message
                        _help.value = "配对码在电脑端 TextLink-PC.exe 窗口顶部显示，点「换一个」可以换新的。"
                        client.disconnect()
                    }
                    is LinkEvent.Failed -> {
                        _busy.value = false
                        _level.value = Level.Bad
                        _status.value = "连不上 ${client.target}"
                        _pinError.value = null
                        _help.value =
                            "手机能找到电脑，说明网络是通的。连不上通常是 Windows 防火墙拦住了：" +
                                "回到电脑上点绿色提示条里的「一键放行防火墙」，或在电脑命令行运行 " +
                                "TextLink-PC.exe --selftest 看看防火墙那一行。"
                        if (_screen.value == Screen.Typing) scheduleReconnect()
                    }
                    is LinkEvent.Closed -> {
                        if (_screen.value == Screen.Typing) {
                            _level.value = Level.Warn
                            _status.value = "连接已断开，正在重连…"
                            scheduleReconnect()
                        }
                    }
                    is LinkEvent.Peers -> _peers.value = event.devices
                    is LinkEvent.Latency -> _latency.value = event.millis
                    is LinkEvent.Mirror -> applyMirror(event.text)
                }
            }
        }
        discovery.start()
    }

    // -- 设备与连接 ------------------------------------------------------
    fun refresh() {
        discovery.clear()
        discovery.stop()
        discovery.start()
        _status.value = "正在搜索同一 Wi-Fi 下的电脑…"
        _level.value = Level.Warn
    }

    fun askPin(device: PcDevice) {
        _pinTarget.value = device
    }

    fun dismissPin() {
        _pinTarget.value = null
        _pinError.value = null
        _busy.value = false
    }

    fun showManual(show: Boolean) {
        _manualPrompt.value = show
    }

    fun connect(device: PcDevice, pin: String) {
        // 配对弹窗先不关：配对码错了可以直接重输
        _pinError.value = null
        _help.value = null
        _busy.value = true
        _level.value = Level.Warn
        _status.value = "正在连接 ${device.name}…"
        lastDevice = device
        lastPin = pin
        retryJob?.cancel()
        client.connect(device, deviceName, pin)
    }

    fun connectManual(host: String, port: Int, pin: String) {
        val clean = host.trim()
        if (clean.isEmpty()) return
        _manualPrompt.value = false
        connect(PcDevice(clean, clean, port, pin.isNotEmpty()), pin)
    }

    fun disconnect() {
        retryJob?.cancel()
        pingJob?.cancel()
        _latency.value = -1L
        _peers.value = emptyList()
        client.disconnect()
        _screen.value = Screen.Devices
        _pcName.value = null
        _level.value = Level.Warn
        _status.value = "正在搜索同一 Wi-Fi 下的电脑…"
        discovery.start()
    }

    private fun scheduleReconnect() {
        retryJob?.cancel()
        val device = lastDevice ?: return
        retryJob = viewModelScope.launch {
            delay(1500)
            if (_screen.value == Screen.Typing) {
                _level.value = Level.Warn
                _status.value = "正在重连 ${device.name}…"
                client.connect(device, deviceName, lastPin)
            }
        }
    }

    /** 每 3 秒一次心跳：既保活，也顺便测出到电脑的延迟显示在界面上。 */
    private fun startPingLoop() {
        pingJob?.cancel()
        pingJob = viewModelScope.launch {
            while (true) {
                client.sendPing()
                delay(3000)
            }
        }
    }

    // -- 输入同步 --------------------------------------------------------
    fun setMode(mode: SendMode) {
        _mode.value = mode
        lastCommitted = committedPart(_field.value)
    }

    fun onTextChange(value: TextFieldValue) {
        _field.value = value
        if (_mode.value != SendMode.Live) return
        val committed = committedPart(value)
        if (committed == lastCommitted) return
        val (deletes, insert) = diffText(lastCommitted, committed)
        if (deletes > 0 || insert.isNotEmpty()) {
            client.sendEdit(deletes, insert)
            if (insert.isNotEmpty()) _sentChars.value += insert.length
        }
        lastCommitted = committed
    }

    fun sendBuffer() {
        val text = _field.value.text
        if (text.isEmpty()) return
        client.sendInsert(text)
        _sentChars.value += text.length
        _field.value = TextFieldValue("")
        lastCommitted = ""
    }

    /** 手机上点「发送」：电脑端输入这段文字再按回车，等于在电脑上点了发送。 */
    fun sendFromPhone() {
        val text = _field.value.text
        if (text.isEmpty()) {
            if (_sendWithEnter.value) client.sendKey("ENTER")
            return
        }
        // 即打即输模式下文字已经在电脑输入框里了，这里只需要按回车，
        // 否则会把同一段文字再输入一遍（就是你看到的"重复一遍"）。
        val alreadyTyped = _mode.value == SendMode.Live
        if (alreadyTyped) {
            if (_sendWithEnter.value) client.sendKey("ENTER")
        } else {
            client.sendFromPhone(text, _sendWithEnter.value)
        }
        lastSentText = text
        mirrorMuteUntil = System.currentTimeMillis() + 2500
        _sentChars.value += text.length
        _sendCount.value += 1
        prefs.edit().putInt("sendCount", _sendCount.value).apply()
        _history.value = (_history.value + text).takeLast(20)
        _field.value = TextFieldValue("")
        lastCommitted = ""
    }

    /** 点「还原」：把最近发出的一条放回输入框，可以连续还原更早的。 */
    fun restoreLast() {
        val list = _history.value
        if (list.isEmpty()) return
        val text = list.last()
        _history.value = list.dropLast(1)
        _field.value = TextFieldValue(text, selection = TextRange(text.length))
        lastCommitted = text
    }

    fun clearHistory() {
        _history.value = emptyList()
    }

    fun setSendWithEnter(enabled: Boolean) {
        _sendWithEnter.value = enabled
        prefs.edit().putBoolean("sendEnter", enabled).apply()
    }

    fun setMirrorEnabled(enabled: Boolean) {
        _mirrorEnabled.value = enabled
        prefs.edit().putBoolean("mirror", enabled).apply()
    }

    /** 电脑上输入框内容变了 → 同步到手机输入框（不回传，避免两边打架）。 */
    private fun applyMirror(text: String) {
        if (!_mirrorEnabled.value) return
        // 刚发完的 2.5 秒内不接收镜像：否则电脑输入框没被清空时，
       val current = _field.value.text
        if (System.currentTimeMillis() < mirrorMuteUntil) return
        // 电脑把"我刚发出去的那段"同步回来时忽略掉，避免看起来像重复了一遍
        if (lastSentText.isNotEmpty() && text.trim() == lastSentText.trim()) return
        if (current.isNotEmpty() && current != _lastMirror.value) {
            return      // 用户正在手机上编辑，不覆盖
        }
        _lastMirror.value = text
        if (current == text) return
        _field.value = TextFieldValue(text, selection = TextRange(text.length))
        lastCommitted = text
    }

    fun clearField() {
        _field.value = TextFieldValue("")
        lastCommitted = ""
    }

    fun pressKey(name: String) {
        client.sendKey(name)
    }

    fun pressCombo(
        key: String,
        ctrl: Boolean = false,
        alt: Boolean = false,
        shift: Boolean = false,
        meta: Boolean = false
    ) {
        client.sendCombo(key, ctrl, alt, shift, meta)
    }

    /** 取"已经确认输入"的部分：正在拼写（拼音候选）的那段不算。 */
    private fun committedPart(value: TextFieldValue): String {
        val composition = value.composition
        if (composition == null || composition.collapsed) return value.text
        val start = composition.start.coerceIn(0, value.text.length)
        val end = composition.end.coerceIn(start, value.text.length)
        return value.text.substring(0, start) + value.text.substring(end)
    }

    /** 对比新旧文字，算出要按几次退格、再补什么。 */
    private fun diffText(old: String, new: String): Pair<Int, String> {
        var common = 0
        while (common < old.length && common < new.length && old[common] == new[common]) {
            common++
        }
        val deletes = (old.length - common).coerceAtMost(MAX_DELETE)
        return Pair(deletes, new.substring(common))
    }

    override fun onCleared() {
        retryJob?.cancel()
        pingJob?.cancel()
        discovery.stop()
        client.disconnect()
        super.onCleared()
    }

    companion object {
        /** 一次最多补发多少次退格，防止误操作在电脑上删掉大段内容。 */
        const val MAX_DELETE = 500
    }
}
