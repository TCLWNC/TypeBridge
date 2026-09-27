package com.crosslink.app

import android.app.Activity
import android.app.Dialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.graphics.drawable.ColorDrawable
import android.os.Build
import android.os.Bundle
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.view.animation.OvershootInterpolator
import android.view.animation.DecelerateInterpolator
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import java.io.File
import org.json.JSONObject
import kotlin.concurrent.thread

/* 配色取自 LocalSend 源码 app/lib/config/theme.dart：
   ColorScheme.fromSeed(seedColor: Colors.teal) + ColorMode.oled(surface: Colors.black)；
   圆角取自同文件 _borderRadius = BorderRadius.circular(5)。 */
private const val C_BG = 0xFF000000.toInt()       // OLED：纯黑
private const val C_CARD = 0xFF1A1B21.toInt()     // M3 dark surfaceContainer
private const val C_INPUT = 0xFF101116.toInt()
private const val C_LINE = 0x22FFFFFF
private const val C_TEXT = 0xFFFFFFFF.toInt()
private const val C_DIM = 0xFFC7C9D4.toInt()
private const val C_MUTED = 0xFF8B8E9D.toInt()
private const val C_PRIMARY = 0xFFB4C5FF.toInt()  // M3 dark primary（teal 种子）
private const val C_ON_PRIMARY = 0xFF0B2A5B.toInt()
private const val C_OK = 0xFF4CD07D.toInt()
private const val C_BRAND = 0xFF00AEFA.toInt()
private const val C_BAD = 0xFFFF6B6B.toInt()
private const val C_CHIP_ON = 0x2AB4C5FF

class MainActivity : Activity() {

    private lateinit var client: Client
    private var sid = ""
    private var sent = ""
    private var lastSent = ""
    private var liveMode = true
    private var enterAfter = false
    private val device: String = (Build.MODEL ?: "手机").ifBlank { "手机" }

    private lateinit var root: LinearLayout
    private lateinit var input: EditText
    private lateinit var counter: TextView
    private var lblMirror: TextView? = null
    private lateinit var notice: TextView
    private lateinit var targetText: TextView
    private lateinit var pcName: TextView
    private lateinit var sendBtn: Button
    private lateinit var liveBtn: TextView
    private lateinit var batchBtn: TextView
    private var addrField: EditText? = null
    private var pinField: EditText? = null
    private var deviceList: LinearLayout? = null
    private var statusLine: TextView? = null
    private var manualBox: LinearLayout? = null
    private var refreshBar: ProgressBar? = null
    private var emptyHint: TextView? = null
    // 语音输入：手机只当麦克风，录好的 WAV 发给电脑识别
    private var recorder: android.media.AudioRecord? = null
    @Volatile private var recording = false
    // 长按「输入」转语音：按住 0.5 秒开始，松手结束
    private val holdHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private var holdRunnable: Runnable? = null
    private var holdArmed = false
    private var pendingHold = false
    private val HOLD_MS = 500L
    private val found = LinkedHashMap<String, Discovery.Found>()
    private val lastSeen = HashMap<String, Long>()
    private val logs = mutableListOf<String>()
    private var tabSend: View? = null
    private var tabLogs: View? = null
    private var tabCfg: View? = null
    private var tabButtons = mutableMapOf<String, Button>()
    private var tabItems = mutableMapOf<String, Triple<View, TextView, View>>()
    private var lastSignature = ""
    private val REQ_MIC = 1001
    @Volatile private var discovering = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 崩溃自查：把所有未捕获异常写到文件，并在屏幕上显示原因，
        // 这样即使我没有真机，下一次也能拿到确切错误而不是靠猜。
        Thread.setDefaultUncaughtExceptionHandler { _, e ->
            runCatching {
                File(filesDir, "crash.txt").appendText(
                    "\n==== ${java.util.Date()} ====\n" + android.util.Log.getStackTraceString(e))
            }
        }
        window.statusBarColor = C_BG
        window.navigationBarColor = C_BG
        // 界面语言：设置里选过就按选的，没选过就跟随系统
        I18n.lang = runCatching {
            getSharedPreferences("crosslink", MODE_PRIVATE).getString("lang", null)
        }.getOrNull() ?: I18n.defaultLang()
        try {
            buildShell()
        } catch (e: Throwable) {
            showCrash(e)
        }
    }

    private fun buildShell() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(C_BG)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        setContentView(root)
        showDevices()
        // 文案是"渲染后再翻译"，状态行这类动态文字靠定时器兜住
        i18nHandler.postDelayed(i18nTick, 600)
    }

    private val i18nHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val i18nTick = object : Runnable {
        override fun run() {
            if (this@MainActivity::root.isInitialized) runCatching { I18n.localize(root) }
            i18nHandler.postDelayed(this, 600)
        }
    }

    /** 切换界面语言：记到本地，然后重画一次让文字立刻变过来。 */
    private fun setLang(value: String) {
        I18n.lang = value
        runCatching {
            getSharedPreferences("crosslink", MODE_PRIVATE).edit()
                .putString("lang", value).apply()
        }
        showDevices()
    }

    /** 出问题时不闪退，把原因显示出来（可滚动）。 */
    private fun showCrash(e: Throwable) {
        val text = android.util.Log.getStackTraceString(e)
        runCatching {
            File(filesDir, "crash.txt").appendText("\n==== ${java.util.Date()} ====\n$text")
        }
        val tv = TextView(this).apply {
            this.text = "启动出错，请把下面这段发给我：\n\n$text"
            textSize = 12.5f
            setTextColor(C_BAD)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        setContentView(ScrollView(this).apply { addView(tv) })
    }

    override fun onResume() {
        super.onResume()
        if (!connectedOnce) startDiscovery()
    }

    override fun onPause() {
        super.onPause()
        discovering = false
    }

    private var connectedOnce = false

    /** 打开就在搜，并且一直刷新——这才叫设备列表。 */
    private fun startDiscovery() {
        if (discovering) return
        discovering = true
        thread {
            var lastScanAt = 0L
            while (discovering) {
                val list = runCatching { Discovery.search(port = 8788, timeoutMs = 1500) }
                    .getOrDefault(emptyList())
                // 兜底扫 /24 很贵（254 × 若干端口），所以：
                // 只在「一直搜不到」且距上次扫描超过 15 秒时才扫，避免手机发热、掉电
                val now = System.currentTimeMillis()
                val scanned = if (list.isEmpty() && found.isEmpty() && now - lastScanAt > 15_000) {
                    lastScanAt = now
                    runCatching { Discovery.scanSubnet(port = 8788) }.getOrDefault(emptyList())
                } else emptyList()
                runOnUiThread {
                    if (!discovering) return@runOnUiThread
                    (list + scanned).forEach { found["${it.host}:${it.port}"] = it }
                    val nowMs = System.currentTimeMillis()
                    found.keys.forEach { lastSeen[it] = nowMs }
                    // 超过 12 秒没再出现的设备要从列表里清掉（之前断了也一直挂着）
                    val stale = lastSeen.filterValues { nowMs - it > 12_000 }.keys.toList()
                    if (stale.isNotEmpty()) {
                        stale.forEach { found.remove(it); lastSeen.remove(it) }
                        logs.add("移除 ${stale.size} 台已断开的设备")
                        lastSignature = ""
                    }
                    if (scanned.isNotEmpty()) {
                        logs.add("网段扫描找到 ${scanned.size} 台电脑")
                    }
                    renderDevices()
                }
                runCatching { Thread.sleep(1200) }
            }
        }
    }

    private fun renderDevices() {
        val box = deviceList ?: return
        val st = statusLine ?: return
        val keys = found.keys.sorted()
        // 签名里必须带上「是否需要配对码」：否则电脑上关掉配对码后，
        // 手机列表因为签名没变而不重绘，仍按旧状态弹配对码。
        val sig = keys.joinToString("|") { "$it:${found[it]?.needPin}" }
        refreshBar?.visibility = if (discovering && found.isEmpty()) View.VISIBLE else View.GONE

        // 列表没变化就直接返回：不重建、不重放动画，整片列表保持静止
        if (sig == lastSignature) return
        val previous = lastSignature.split("|").filter { it.isNotEmpty() }.toSet()
        lastSignature = sig

        box.removeAllViews()
        val text = if (found.isEmpty()) "正在搜索同一 Wi-Fi 下的电脑" else "找到 ${found.size} 台电脑"
        if (st.text.toString() != text) {
            st.text = text
            st.alpha = 0.4f
            st.animate().alpha(1f).setDuration(220L).start()
        }
        emptyHint?.visibility = if (found.isEmpty()) View.VISIBLE else View.GONE
        if (found.isEmpty()) {
            return
        }
        keys.forEachIndexed { index, key ->
            val dev = found[key] ?: return@forEachIndexed
            val row = deviceRow(dev) { connectTo("${dev.host}:${dev.port}", dev.needPin) }
            box.addView(row, lp(top = 8, matchWidth = true))
            // 只有这一轮新出现的设备才做入场动画；已存在的行直接显示
            if (key !in previous) enter(row, delayMs = index * 40L)
        }
    }

    private fun showDevices() {
        root.removeAllViews()
        root.gravity = Gravity.TOP
        found.clear()

        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 0, 0, dp(8))
        }
        page.addView(label("跨屏输入", 22f, C_TEXT, true))
        page.addView(label("手机当电脑的无线键盘", 12.5f, C_MUTED))

        /* ---- 卡片一：附近的电脑 ---- */
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(C_CARD, 16f)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        head.addView(label("附近的电脑", 13f, C_MUTED, true))
        head.addView(LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }, LinearLayout.LayoutParams(0, 1, 1f))
        refreshBar = ProgressBar(this).apply {
            visibility = View.VISIBLE
            layoutParams = LinearLayout.LayoutParams(dp(22), dp(22))
        }
        head.addView(refreshBar)
        card.addView(head)

        statusLine = label("正在搜索同一 Wi-Fi 下的电脑…", 12.5f, C_BRAND)
        card.addView(statusLine, lp(top = 8, matchWidth = true))

        // 只剩一句提示：列表本身才是主角，不要把首页堆成说明书
        emptyHint = label("没搜到 · 检查同一 Wi-Fi 和电脑端防火墙", 12f, C_MUTED)
        card.addView(emptyHint, lp(top = 8, matchWidth = true))

        deviceList = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        card.addView(deviceList, lp(top = 8, matchWidth = true))
        renderDevices()
        page.addView(card, lp(top = 16, matchWidth = true))

        /* ---- 卡片二：连接设置（一直显示，不折叠）---- */
        val cfg = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(C_CARD, 16f)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        cfg.addView(label("连接设置", 13f, C_MUTED, true))
        cfg.addView(label("地址和配对码和电脑窗口上显示的一致；配对码只有电脑开了「需要配对码」时才要填。",
            12f, C_MUTED), lp(top = 8, matchWidth = true))

        val addr = EditText(this).apply {
            hint = "电脑地址，例如 192.168.1.146:8788"
            setText("192.168.1.146:8788")
            setTextColor(C_TEXT); setHintTextColor(C_MUTED)
            background = pressable(C_INPUT, 14f, C_LINE)
            setPadding(dp(14), dp(12), dp(14), dp(12))
            inputType = InputType.TYPE_TEXT_VARIATION_URI
        }
        val pin = EditText(this).apply {
            hint = "配对码（电脑没开就留空）"
            setTextColor(C_TEXT); setHintTextColor(C_MUTED)
            background = pressable(C_INPUT, 14f, C_LINE)
            setPadding(dp(14), dp(12), dp(14), dp(12))
            inputType = InputType.TYPE_CLASS_NUMBER
        }
        val go = Button(this).apply {
            text = "连接电脑"
            setTextColor(C_ON_PRIMARY)
            textSize = 14f
            background = pressable(C_PRIMARY, 999f)
            setOnClickListener {
                connectTo(addr.text.toString().trim(), pin.text.toString().trim().isNotEmpty())
            }
        }
        // 这里必须先创建容器再往里放控件：上一版把创建那几行删了，
        // 却留着 manualBox!!，启动就 NPE（MainActivity.kt:244）。
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        manualBox = box
        box.addView(addr, lp(top = 8, matchWidth = true))
        box.addView(pin, lp(top = 8, matchWidth = true))
        cfg.addView(box, lp(top = 8, matchWidth = true))

        val opt = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val swAuto = Switch(this).apply {
            isChecked = enterAfter
            setOnCheckedChangeListener { _, v -> enterAfter = v }
        }
        opt.addView(swAuto)
        // 英文文案更长，给它一个上限并允许省略号，别把右边的「立即搜索」挤出屏幕
        opt.addView(label("发送后自动回车", 13f, C_DIM).apply {
            maxWidth = dp(150)
            ellipsize = android.text.TextUtils.TruncateAt.END
            maxLines = 1
        })
        opt.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        opt.addView(chip("立即搜索") {
            found.clear()
            lastSignature = ""
            renderDevices()
            startDiscovery()
        })
        cfg.addView(opt, lp(top = 8, matchWidth = true))
        cfg.addView(go, lp(top = 8, h = 46, matchWidth = true))
        // 版本号从安装包里读，别写死（写死过一次，界面显示的还是旧版本号）
        val verName = runCatching {
            packageManager.getPackageInfo(packageName, 0).versionName
        }.getOrNull().orEmpty()
        cfg.addView(label("v$verName · 即打即输 / 编辑后发送 / 16 个功能键", 11.5f, C_MUTED),
            lp(top = 8, matchWidth = true))
        // 「发送后自动回车」和「断开」放进设置页（输入页保持干净）
        val setRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = dp(48)
        }
        setRow.addView(Switch(this).apply {
            isChecked = enterAfter
            setOnCheckedChangeListener { _, v -> enterAfter = v }
        })
        setRow.addView(label("发送后自动回车", 14f, C_DIM))
        setRow.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        cfg.addView(setRow, lp(top = 8, matchWidth = true))
        // 发送模式挪到设置页：即打即输 / 编辑后发送
        val modeRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = dp(48)
        }
        modeRow.addView(label("发送模式", 14f, C_DIM))
        modeRow.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        liveBtn = tabButton("即打即输")
        batchBtn = tabButton("编辑后发送")
        liveBtn.setOnClickListener { liveMode = true; syncMode() }
        batchBtn.setOnClickListener { liveMode = false; syncMode() }
        // 英文（Live typing / Edit then send）比中文长，写死宽度会把字挤出去，
        // 这里改成按比例分剩余空间，两边都拿得到位置
        modeRow.addView(liveBtn, LinearLayout.LayoutParams(0, dp(40), 1f))
        modeRow.addView(batchBtn, LinearLayout.LayoutParams(0, dp(40), 1f).apply { leftMargin = dp(8) })
        cfg.addView(modeRow, lp(top = 8, matchWidth = true))

        // 界面语言：中文 / English（电脑端界面里也有同一个开关）
        val langRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = dp(48)
        }
        langRow.addView(label("界面语言", 14f, C_DIM))
        langRow.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        val zhBtn = tabButton("中文")
        val enBtn = tabButton("English")
        zhBtn.setOnClickListener { setLang(I18n.ZH) }
        enBtn.setOnClickListener { setLang(I18n.EN) }
        zhBtn.setTextColor(if (I18n.lang == I18n.ZH) C_PRIMARY else C_MUTED)
        enBtn.setTextColor(if (I18n.lang == I18n.EN) C_PRIMARY else C_MUTED)
        langRow.addView(zhBtn, LinearLayout.LayoutParams(0, dp(40), 1f))
        langRow.addView(enBtn, LinearLayout.LayoutParams(0, dp(40), 1f).apply { leftMargin = dp(8) })
        cfg.addView(langRow, lp(top = 8, matchWidth = true))
        cfg.addView(TextView(this).apply {
            text = "断开当前连接"
            textSize = 14f
            gravity = Gravity.CENTER
            setTextColor(C_BAD)
            background = pressable(C_INPUT, 12f, C_LINE)
            isClickable = true
            setOnClickListener {
                runCatching { client.close() }
                connectedOnce = false
                logs.add("已断开连接")
                showDevices()
            }
        }, lp(top = 8, h = 48, matchWidth = true))
        page.addView(cfg, lp(top = 16, matchWidth = true))

        addrField = addr
        pinField = pin

        val err = label("", 13f, C_BAD)
        page.addView(err, lp(top = 8, matchWidth = true))
        this.errLabel = err

        val scroll = ScrollView(this).apply { addView(page) }
        root.addView(scroll, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        /* ---- 底部栏（对应 LocalSend 手机端的 NavigationBar：发送 / 记录 / 设置）---- */
        tabSend = card
        tabCfg = cfg
        tabLogs = buildLogCard()
        page.addView(tabLogs, lp(top = 16, matchWidth = true))
        tabLogs?.visibility = View.GONE

        // 底部栏：只用「图标 + 文字 + 一条 3dp 下划线」表示选中，
        // 不再给按钮加整块圆角背景（那就是你说的"斜着的长方形"）。
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setBackgroundColor(C_INPUT)
            setPadding(0, dp(8), 0, dp(10))
        }
        listOf(
            Triple("send", "发送", 0),
            Triple("logs", "记录", 0),
            Triple("cfg", "设置", 0),
        ).forEach { (key, label, icon) ->
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                isClickable = true
                setOnClickListener { switchTab(key) }
            }
            // 三个图标用同一套自绘矢量（同 24 视口 / 同线宽），并强制 24×24dp —— 尺寸必然一致
            val iconView = android.widget.ImageView(this).apply {
                setImageResource(
                    when (key) {
                        "send" -> R.drawable.ic_tab_send
                        "logs" -> R.drawable.ic_tab_logs
                        else -> R.drawable.ic_tab_settings
                    })
                layoutParams = LinearLayout.LayoutParams(dp(24), dp(24))
                alpha = if (key == "send") 1f else 0.6f
            }
            val labelView = TextView(this).apply {
                text = label
                textSize = 11f
                gravity = Gravity.CENTER
                includeFontPadding = false     // 去掉字体自带留白，图标和文字才会对齐
                setTextColor(if (key == "send") C_PRIMARY else C_MUTED)
            }
            val underline = View(this).apply {
                setBackgroundColor(if (key == "send") C_PRIMARY else 0x00000000)
                layoutParams = LinearLayout.LayoutParams(dp(18), dp(3))
                    .apply { topMargin = dp(3) }
            }
            item.addView(iconView)
            item.addView(labelView)
            item.addView(underline)
            item.layoutParams = LinearLayout.LayoutParams(0, dp(56), 1f)
            item.tag = underline
            bar.addView(item, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            tabButtons[key] = Button(this)   // 占位，保持下面的逻辑不改
            tabItems[key] = Triple(iconView, labelView, underline)
        }
        root.addView(bar, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        logs.add("打开应用，开始搜索")
        // 关键：初始化时只显示「发送」页的内容。
        // 之前漏了这一步，导致「连接设置」卡片默认堆在发送页上，
        // 「设置」Tab 里反而看到同样的东西。
        switchTab("send")
        enter(page, 0L)
        startDiscovery()
    }

    /** 底部栏切换：发送（设备列表）/ 记录 / 设置 */
    private fun switchTab(key: String) {
        if (key == "logs") renderLogCard()
        val target = when (key) {
            "send" -> tabSend
            "logs" -> tabLogs
            else -> tabCfg
        }
        listOf(tabSend, tabLogs, tabCfg).forEach { panel ->
            if (panel !== target) panel?.visibility = View.GONE
        }
        // 切换时淡入 + 上移 10dp，220ms 减速；不是"啪"地一下换掉
        target?.visibility = View.VISIBLE
        enter(target, 0L)
        tabButtons.forEach { (k, b) ->
            tabItems[k]?.let { (iconView, labelView, underline) ->
                val on = k == key
                labelView.setTextColor(if (on) C_PRIMARY else C_MUTED)
                underline.setBackgroundColor(if (on) C_PRIMARY else 0x00000000)
                iconView.alpha = if (on) 1f else 0.65f
            }
        }
    }

    private var logText: TextView? = null

    private fun buildLogCard(): LinearLayout {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(C_CARD, 16f)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        card.addView(label("运行记录", 13f, C_MUTED, true))
        card.addView(label("连接、搜索、发送的动作都会记在这里，方便排查。", 12f, C_MUTED),
            lp(top = 8, matchWidth = true))
        logText = label("", 12f, C_DIM)
        card.addView(logText, lp(top = 8, matchWidth = true))
        return card
    }

    private fun renderLogCard() {
        logText?.text = if (logs.isEmpty()) "（空）"
        else logs.takeLast(40).reversed().joinToString("\n") { "· $it" }
    }

    private var errLabel: TextView? = null

    private fun connectTo(rawAddr: String, needPin: Boolean) {
        val addr = if (rawAddr.startsWith("http")) rawAddr else "http://$rawAddr"
        val pin = pinField?.text?.toString()?.trim().orEmpty()
        if (needPin && pin.isEmpty()) {
            askPin(rawAddr)      // 需要配对码就直接弹输入框，不再只给一行小字提示
            return
        }
        errLabel?.text = ""
        discovering = false
        thread {
            runCatching {
                client = Client(addr.trimEnd('/'))
                val res = client.hello(device, pin, androidId())
                if (res.optBoolean("ok")) {
                    sid = res.optString("sid")
                    connectedOnce = true
                    runOnUiThread {
                        try {
                            window.setSoftInputMode(
                                android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
                            // 连上先给一个过场动画，再进输入页（不然是"啪"地一下换界面）
                            val pc = res.optString("pc", "电脑")
                            playConnectedAnim(pc) { showInput(pc) }
                        } catch (e: Throwable) {
                            // 进输入页时出问题也别闪退，把原因留在屏幕上
                            val msg = "进入输入页出错：" + e
                            logs.add(msg)
                            errLabel?.text = msg
                        }
                    }
                    client.listen(sid) { ev -> onEvent(ev) }
                    // 心跳：每 5 秒告诉电脑端"我还在"，这样手机关掉/断网后
                    // 电脑端 12 秒内就会把设备移除（不依赖 SSE 是否带 sid）
                    thread {
                        while (connectedOnce) {
                            runCatching {
                                client.op(sid, listOf(JSONObject().put("k", "ping")))
                            }
                            runCatching { Thread.sleep(5000) }
                        }
                    }
                } else {
                    runOnUiThread { errLabel?.text = res.optString("error", "连接失败"); startDiscovery() }
                }
            }.onFailure {
                runOnUiThread { errLabel?.text = "连不上：${it.message}"; startDiscovery() }
            }
        }
    }

    /** 连上电脑的过场：整屏压暗 → 「已连接 · 电脑名」卡片弹出来 → 再让位给输入页。 */
    private fun playConnectedAnim(pc: String, then: () -> Unit) {
        val host = (root.parent as? ViewGroup) ?: root
        val cover = FrameLayout(this).apply { setBackgroundColor(0xE0000000.toInt()) }
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            background = rounded(C_CARD, 16f)
            setPadding(dp(24), dp(28), dp(24), dp(28))
        }
        card.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_check)
            layoutParams = LinearLayout.LayoutParams(dp(48), dp(48))
        })
        card.addView(label("已连接", 22f, C_TEXT, true).apply { gravity = Gravity.CENTER },
            lp(top = 16, matchWidth = true))
        card.addView(label(pc, 12.5f, C_MUTED).apply { gravity = Gravity.CENTER },
            lp(top = 8, matchWidth = true))
        cover.addView(card, FrameLayout.LayoutParams(dp(220), ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { gravity = Gravity.CENTER })
        cover.alpha = 0f
        host.addView(cover, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        card.alpha = 0f
        card.scaleX = 0.9f
        card.scaleY = 0.9f
        cover.animate().alpha(1f).setDuration(160L).start()
        card.animate().alpha(1f).scaleX(1f).scaleY(1f)
            .setStartDelay(60L).setDuration(260L)
            .setInterpolator(OvershootInterpolator(1.15f)).start()
        cover.postDelayed({
            card.animate().alpha(0f).scaleX(1.06f).scaleY(1.06f).setDuration(160L).start()
            cover.animate().alpha(0f).setStartDelay(60L).setDuration(220L)
                .withEndAction {
                    runCatching { host.removeView(cover) }
                    then()
                }.start()
        }, 900L)
    }

    private fun showInput(pc: String) {
        root.removeAllViews()
        root.gravity = Gravity.TOP

        pcName = label(pc, 18f, C_TEXT, true)
        targetText = label("先在电脑上点一下要输入的窗口", 12f, C_MUTED)
        val head = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        head.addView(pcName)
        head.addView(targetText)
        root.addView(head)
        enter(head, 0L)

        input = EditText(this).apply {
            hint = "在这里打字…"
            setTextColor(C_TEXT); setHintTextColor(C_MUTED)
            textSize = 17f
            gravity = Gravity.TOP
            background = rounded(C_CARD, 12f, C_LINE)
            setPadding(dp(16), dp(16), dp(16), dp(16))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            minimumHeight = dp(96)   // 键盘弹出时输入框要能被压缩，否则下面按钮会被挤出屏幕
        }
        root.addView(input, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f).apply { topMargin = dp(12) })
        enter(input, 60L)

        counter = label("0 字", 12f, C_MUTED)
        root.addView(counter, lp(top = 8, matchWidth = true))
        enter(counter, 120L)

        // 功能键收成一个按钮，点开是一个面板（不再占着屏幕一排）
        // 功能键只留一个入口按钮，点开是面板（屏幕上不再排一长条按键）
        val keyBar = TextView(this).apply {
            setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_keys, 0, 0, 0)
            compoundDrawablePadding = dp(10)
            text = "多按键"
            textSize = 14f
            gravity = Gravity.CENTER
            setTextColor(C_DIM)
            background = pressable(C_CARD, 12f, C_LINE)
            setPadding(dp(14), 0, dp(14), 0)
            isClickable = true
            setOnClickListener { showKeysDialog() }
        }
        // 一行四格：删除 | 恢复（略宽） | 输入（撑满中间） | 多按键
        val clearBtn = iconButton(R.drawable.ic_delete_trash, "删除") {
            input.setText(""); sent = ""; counter.text = "0 字"
            if (this@MainActivity::notice.isInitialized) notice.text = "已清空手机输入框（电脑上的内容没动）"
        }
        val restoreBtn = iconButton(R.drawable.ic_restore_undo, "恢复") {
            // 注意花括号：以前写成 "if (空) if (提示已初始化) … else {恢复}"，
            // else 会绑到内层 if 上，导致恢复永远不执行（用户反馈的"恢复没用"）。
            if (lastSent.isEmpty()) {
                if (this@MainActivity::notice.isInitialized) notice.text = "还没有发送过内容"
            } else {
                // 注意：这里不能把 sent 也设成 lastSent，否则同步逻辑会认为
                // "内容没变化"而不往电脑发，用户就会觉得"恢复键没用"。
                input.setText(lastSent)
                input.setSelection(input.text.length)
                if (this@MainActivity::notice.isInitialized) notice.text = "已恢复上次发送的内容（正在同步到电脑）"
            }
        }
        sendBtn = Button(this).apply {
            text = "发送"
            textSize = 14f
            setTextColor(C_ON_PRIMARY)
            background = pressable(C_PRIMARY, 12f)
            // 麦克风图标直接并进这个键：短按敲回车，按住 0.5 秒变语音，松手即止
            setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_mic, 0, 0, 0)
            compoundDrawablePadding = dp(8)
            compoundDrawableTintList = ColorStateList.valueOf(C_ON_PRIMARY)
        }
        // 短按 = 敲一次回车；按住 0.5 秒 = 转成语音输入，一直按着一直听，松手立刻结束并识别
        fun doEnter() {
            send(listOf(JSONObject().put("k", "key").put("key", "ENTER")))
            // 点完之后清空手机输入框——注意要把"已同步基线"也清成空，
            // 否则清空这个动作会被当成一次文本变化同步过去，把电脑上的内容也删掉。
            lastSent = input.text.toString()
            input.setText("")
            sent = ""
            counter.text = "0 字"
            if (this@MainActivity::notice.isInitialized) {
                notice.text = "已敲回车，输入框已清空（可用「恢复」找回）"
            }
        }
        sendBtn.setOnTouchListener { view, ev ->
            when (ev.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    view.isPressed = true
                    holdArmed = true
                    val run = Runnable {
                        if (holdArmed && !recording) {
                            holdArmed = false
                            startRecording(holdMode = true)
                        }
                    }
                    holdRunnable = run
                    holdHandler.postDelayed(run, HOLD_MS)
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    holdArmed = false
                    holdRunnable?.let { holdHandler.removeCallbacks(it) }
                    holdRunnable = null
                    view.isPressed = false
                    if (recording) {
                        recording = false          // 松手即止：录音线程收尾并上传识别
                        paintMic()
                    } else {
                        doEnter()                  // 短按：还是敲回车
                    }
                    true
                }
                else -> false
            }
        }
        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        actions.addView(clearBtn, LinearLayout.LayoutParams(dp(48), dp(48)))
        actions.addView(restoreBtn, LinearLayout.LayoutParams(dp(64), dp(48)).apply { leftMargin = dp(8) })
        // 多按键已取消：中间只留「发送」（敲回车），左边删除、恢复
        actions.addView(sendBtn, LinearLayout.LayoutParams(0, dp(48), 1f).apply { leftMargin = dp(8) })
        root.addView(actions, lp(top = 8, matchWidth = true))
        enter(actions, 180L)

        // 一句状态提示：清空、恢复、敲回车之后有反馈，不然用户不知道刚才那下有没有生效
        notice = label("", 12f, C_MUTED)
        root.addView(notice, lp(top = 8, matchWidth = true))
        enter(notice, 240L)
        input.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                counter.text = "${s?.length ?: 0} 字"
                if (liveMode) flush()
            }
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
        })
        syncMode()
    }

    private fun syncMode() {
        liveBtn.background = pressable(if (liveMode) C_CHIP_ON else 0x00000000, 12f)
        batchBtn.background = pressable(if (!liveMode) C_CHIP_ON else 0x00000000, 12f)
        liveBtn.setTextColor(if (liveMode) C_PRIMARY else C_MUTED)
        batchBtn.setTextColor(if (!liveMode) C_PRIMARY else C_MUTED)
        // 安全调用：设置页的「发送模式」在未连接时也能点，那时 sendBtn 还没创建，
        // 直接写属性会空指针闪退（你反馈的切换输入方式闪退就是这个）。
        if (this::sendBtn.isInitialized) sendBtn.text = "输入"
    }

    /** 功能键面板：点一个发一个，面板留着方便连点，右上角关闭。 */
    private fun showKeysDialog() {
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(8))
        }
        col.addView(label("多按键", 15f, C_TEXT, true))
        col.addView(label("点一个发一个，面板不会自动关", 12f, C_MUTED), lp(top = 8, matchWidth = true))
        val grid = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        KEYS.chunked(4).forEach { rowKeys ->
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            rowKeys.forEach { (name, op) ->
                row.addView(chip(name) { send(listOf(op)) },
                    LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
                        .apply { rightMargin = dp(6); topMargin = dp(6) })
            }
            while (row.childCount < 4) {
                row.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
            }
            grid.addView(row)
        }
        col.addView(grid, lp(top = 8, matchWidth = true))
        val dialog = android.app.AlertDialog.Builder(this)
            .setView(ScrollView(this).apply { addView(col) })
            .setPositiveButton("关闭", null)
            .create()
        dialog.show()
    }

    /** 搜索结果里的一行：点一下就连过去 */
    /** 设备行：照 LocalSend 的 device_list_tile.dart 排——左边 46 的设备图标、
     *  20px 名字、下面一排徽章（HTTP / 地址:端口 / 需要配对码）、右边详情按钮；
     *  整行点一下就是连接。 */
    private fun deviceRow(dev: Discovery.Found, onClick: () -> Unit): LinearLayout {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = pressable(C_INPUT, 12f, C_LINE)
            setPadding(dp(16), dp(12), dp(16), dp(12))
            minimumHeight = dp(64)
            isClickable = true
            setOnClickListener {
                // 兜底：点设备→连接这条路上任何异常都显示出来，不要直接闪退
                try {
                    onClick()
                } catch (e: Throwable) {
                    val msg = "连接出错：" + e
                    logs.add(msg)
                    notice?.text = msg
                    errLabel?.text = msg
                }
            }
        }
        // 左：设备图标 46
        row.addView(TextView(this).apply {
            setCompoundDrawablesWithIntrinsicBounds(0, R.drawable.ic_computer, 0, 0)
            text = ""
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(dp(40), dp(40))
        })
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, 0, 0)
        }
        col.addView(label(dev.name, 17f, C_TEXT, true))
        // 副标题只留一行地址（超长省略号），保持简约整齐
        col.addView(TextView(this).apply {
            text = "${dev.host}:${dev.port}"
            textSize = 12.5f
            setTextColor(C_MUTED)
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            setPadding(0, dp(8), 0, 0)
        })
        row.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        // 需要配对码时，右侧出现一个小标签；不需要就什么都不显示（更整洁）
        if (dev.needPin) {
            row.addView(TextView(this).apply {
                text = "需要配对码"
                textSize = 11f
                setTextColor(C_PRIMARY)
                background = rounded(C_CHIP_ON, 6f)
                setPadding(dp(8), dp(8), dp(8), dp(8))
                gravity = Gravity.CENTER
            })
        }
        return row
    }

    /** 徽章：底色用主色低透明 + 描边，和 LocalSend 的 DeviceBadge 一个意思。 */
    private fun badge(text: String, high: Boolean = false): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 11f
            setTextColor(if (high) C_PRIMARY else C_DIM)
            background = rounded(if (high) C_CHIP_ON else 0x1AFFFFFF.toInt(), 6f, C_LINE)
            setPadding(dp(8), dp(8), dp(8), dp(8))
            (layoutParams as? LinearLayout.LayoutParams)?.rightMargin = dp(6)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { rightMargin = dp(6) }
        }

    private fun showDeviceInfo(dev: Discovery.Found) {
        android.app.AlertDialog.Builder(this)
            .setTitle(dev.name)
            .setMessage(
                "地址：${dev.host}\n端口：${dev.port}\n" +
                    "配对码：${if (dev.needPin) "需要（在电脑窗口上）" else "不需要"}"
            )
            .setPositiveButton("连接") { _, _ -> connectTo("${dev.host}:${dev.port}", dev.needPin) }
            .setNegativeButton("关闭", null)
            .show()
    }

    /**
     * 需要配对码时弹一个自绘弹窗：圆角卡片 + 4 个数字格 + 弹入动画，
     * 填满 4 位自动连；不够 4 位时抖一下并就地提示，不再是系统那个灰框。
     */
    private fun askPin(rawAddr: String) {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(C_CARD, 16f)
            setPadding(dp(20), dp(20), dp(20), dp(20))
        }
        card.addView(label("需要配对码", 17f, C_TEXT, true))
        card.addView(label("配对码在电脑窗口上（输入页和设置页都显示）", 12f, C_MUTED),
            lp(top = 8, matchWidth = true))

        // 4 个数字格负责"好看"，真正的输入交给盖在上面的透明 EditText
        val boxes = ArrayList<TextView>()
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        repeat(4) { i ->
            val cell = TextView(this).apply {
                textSize = 22f
                setTextColor(C_TEXT)
                gravity = Gravity.CENTER
                background = rounded(C_INPUT, 12f, C_LINE)
            }
            boxes.add(cell)
            val p = LinearLayout.LayoutParams(0, dp(56), 1f)
            if (i > 0) p.leftMargin = dp(8)
            row.addView(cell, p)
        }
        val field = FrameLayout(this)
        field.addView(row, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(56)))
        val hidden = EditText(this).apply {
            background = null
            setTextColor(Color.TRANSPARENT)
            isCursorVisible = false
            inputType = InputType.TYPE_CLASS_NUMBER
            filters = arrayOf(android.text.InputFilter.LengthFilter(4))
        }
        field.addView(hidden, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(56)))
        card.addView(field, lp(top = 16, matchWidth = true))

        val err = label("", 12f, C_BAD)
        card.addView(err, lp(top = 8, matchWidth = true))

        val cancel = Button(this).apply {
            text = "取消"
            textSize = 14f
            setTextColor(C_DIM)
            background = pressable(C_INPUT, 12f, C_LINE)
        }
        val ok = Button(this).apply {
            text = "连接"
            textSize = 14f
            setTextColor(C_ON_PRIMARY)
            background = pressable(C_PRIMARY, 12f)
        }
        val acts = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        acts.addView(cancel, LinearLayout.LayoutParams(0, dp(48), 1f))
        acts.addView(ok, LinearLayout.LayoutParams(0, dp(48), 1f).apply { leftMargin = dp(8) })
        card.addView(acts, lp(top = 16, matchWidth = true))

        val dlg = Dialog(this)
        dlg.requestWindowFeature(Window.FEATURE_NO_TITLE)
        dlg.setContentView(card, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        dlg.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
            setLayout(dp(320), ViewGroup.LayoutParams.WRAP_CONTENT)
            setDimAmount(0.62f)
            setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE)
        }

        fun paint() {
            val s = hidden.text.toString()
            boxes.forEachIndexed { i, cell ->
                cell.text = if (i < s.length) s[i].toString() else ""
                val active = i == s.length
                cell.background = rounded(if (active) C_CHIP_ON else C_INPUT, 12f,
                    if (active) C_PRIMARY else C_LINE)
            }
        }

        fun submit() {
            val code = hidden.text.toString().trim()
            if (code.length < 4) {
                err.text = "请输入 4 位配对码"
                android.animation.ObjectAnimator.ofFloat(field, "translationX",
                    0f, dp(7).toFloat(), -dp(7).toFloat(), dp(4).toFloat(), 0f)
                    .setDuration(240L).start()
                return
            }
            pinField?.setText(code)
            dlg.dismiss()
            connectTo(rawAddr, false)   // 配对码已写进输入框，直接连
        }

        hidden.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                err.text = ""
                paint()
                if ((s?.length ?: 0) == 4) hidden.postDelayed({ submit() }, 130L)
            }
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
        })
        cancel.setOnClickListener { dlg.dismiss() }
        ok.setOnClickListener { submit() }
        dlg.setOnShowListener {
            paint()
            I18n.localize(card)
            hidden.requestFocus()
            card.alpha = 0f
            card.scaleX = 0.92f
            card.scaleY = 0.92f
            card.animate().alpha(1f).scaleX(1f).scaleY(1f)
                .setDuration(220L).setInterpolator(OvershootInterpolator(1.1f)).start()
        }
        dlg.show()
    }

    private fun onEvent(ev: JSONObject) {
        val type = ev.optString("type")
        if (type == "state" || type == "settings") {
            val s = if (type == "settings") ev.optJSONObject("state") else ev
            val name = s?.optJSONObject("app")?.optString("name").orEmpty()
            if (name.isNotEmpty()) runOnUiThread { if (::pcName.isInitialized) pcName.text = name }
        }
        val target = when (type) {
            "mirror" -> {
            val txt = ev.optString("text")
            runOnUiThread { lblMirror?.text = if (txt.isEmpty()) "电脑上：（空）" else "电脑上：" + txt.takeLast(60) }
            null
        }
            "target" -> ev.optJSONObject("target")
            "state" -> ev.optJSONObject("target")
            "settings" -> ev.optJSONObject("state")?.optJSONObject("target")
            else -> null
        } ?: return
        val app = target.optString("app")
        val title = target.optString("title")
        val ready = app.isNotEmpty() && !target.optBoolean("self")
        runOnUiThread {
            if (!::targetText.isInitialized) return@runOnUiThread
            targetText.text = when {
                app.isEmpty() -> "先在电脑上点一下要输入的窗口"
                target.optBoolean("self") -> "焦点在 CrossLink 上，点一下目标程序"
                else -> "已就绪：${title.ifEmpty { app }}"
            }
            targetText.setTextColor(if (ready) C_OK else C_MUTED)
        }
    }

    private fun send(ops: List<JSONObject>) {
        thread {
            val res = runCatching { client.op(sid, ops) }.getOrNull()
            val err = res?.optString("error").orEmpty()
            if (res != null && !res.optBoolean("ok", true) && err.contains("会话")) {
                // 会话失效（通常是电脑端重启或网络抖动）：自动重新握手并重发，
                // 不再把用户踢回设备列表（那样会出现"打一下断一下"）。
                val again = runCatching {
                    val h = client.hello(device, pinField?.text?.toString()?.trim().orEmpty(),
                        androidId())
                    if (h.optBoolean("ok")) {
                        sid = h.optString("sid")
                        client.op(sid, ops)
                        true
                    } else false
                }.getOrDefault(false)
                if (again) {
                    runOnUiThread { logs.add("与电脑重连成功，已继续同步") }
                } else {
                    runOnUiThread {
                        logs.add("电脑端已断开连接，返回设备列表")
                        connectedOnce = false
                        runCatching { client.close() }
                        showDevices()
                    }
                }
            }
        }
    }

    /** 安卓返回键：在输入页时退回设备列表，而不是直接退出应用 */
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (connectedOnce) {
            connectedOnce = false
            logs.add("已断开连接，返回设备列表")
            // 先跟电脑端说一声，让它立刻把设备从列表里去掉，再关连接
            thread {
                sayBye()
                runCatching { client.close() }
            }
            showDevices()
        } else {
            @Suppress("DEPRECATION")
            super.onBackPressed()
        }
    }

    /**
     * 从后台划掉应用 / 被系统回收时，主动告诉电脑端"我走了"。
     * 不这么做的话，电脑端要等心跳超时才知道，设备列表里会挂着一条已经不在线的手机。
     */
    override fun onDestroy() {
        if (connectedOnce) {
            connectedOnce = false
            runCatching { thread { sayBye() } }
        }
        super.onDestroy()
    }

    /** 发一条"告别"指令给电脑端（电脑端收到就立刻把这台设备移出列表）。 */
    private fun sayBye() {
        val s = sid
        if (s.isEmpty() || !this::client.isInitialized) return
        runCatching { client.op(s, listOf(JSONObject().put("k", "bye"))) }
    }

    /* ---------------- 语音输入：手机当无线麦克风 ----------------
     * 手机上不装识别模型：按住麦克风录音（16k 单声道 PCM），录完把整段 WAV
     * 发给电脑，电脑用它本地的 SenseVoice 识别，再把文字回给手机填进输入框，
     * 之后照常走同步打进电脑当前窗口。
     */
    /** 检查麦克风权限再开录（第一次长按会弹一次授权） */
    private fun ensureMic(holdMode: Boolean = false) {
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
            != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            pendingHold = holdMode
            requestPermissions(arrayOf(android.Manifest.permission.RECORD_AUDIO), REQ_MIC)
            return
        }
        startRecording(holdMode)
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<out String>,
                                            granted: IntArray) {
        super.onRequestPermissionsResult(code, perms, granted)
        if (code != REQ_MIC) return
        if (granted.isNotEmpty() &&
            granted[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            startRecording(pendingHold)
        } else if (this::notice.isInitialized) {
            notice.text = "没有麦克风权限，语音输入用不了"
        }
    }

    private fun paintMic() {
        if (this::sendBtn.isInitialized) {
            if (recording) {
                // 录音时中间那个键直接变成"松开结束"，一眼能看出在收音
                sendBtn.text = "松开结束"
                sendBtn.background = pressable(C_BAD, 12f)
                sendBtn.setTextColor(C_TEXT)
                sendBtn.compoundDrawableTintList = ColorStateList.valueOf(C_TEXT)
            } else {
                sendBtn.text = "输入"
                sendBtn.background = pressable(C_PRIMARY, 12f)
                sendBtn.setTextColor(C_ON_PRIMARY)
                sendBtn.compoundDrawableTintList = ColorStateList.valueOf(C_ON_PRIMARY)
            }
        }
        if (recording && this::notice.isInitialized) {
            notice.text = "正在听…松手结束（也可以点上面的麦克风）"
        }
    }

    private fun startRecording(holdMode: Boolean = false) {
        val sr = 16000
        val minBuf = android.media.AudioRecord.getMinBufferSize(
            sr, android.media.AudioFormat.CHANNEL_IN_MONO,
            android.media.AudioFormat.ENCODING_PCM_16BIT)
        if (minBuf <= 0) {
            if (this::notice.isInitialized) notice.text = "这台手机不支持录音"
            return
        }
        val rec = runCatching {
            android.media.AudioRecord(
                android.media.MediaRecorder.AudioSource.MIC, sr,
                android.media.AudioFormat.CHANNEL_IN_MONO,
                android.media.AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, sr * 2))
        }.getOrNull()
        if (rec == null) {
            if (this::notice.isInitialized) notice.text = "录音启动失败"
            return
        }
        recorder = rec
        recording = true
        paintMic()
        if (holdMode && this::notice.isInitialized) notice.text = "正在听…松手结束"
        val bufSize = maxOf(minBuf, sr / 10)
        thread {
            val out = java.io.ByteArrayOutputStream()
            var peak = 0.0
            try {
                rec.startRecording()
                val buf = ByteArray(bufSize)
                while (recording) {
                    val n = rec.read(buf, 0, buf.size)
                    if (n <= 0) continue
                    out.write(buf, 0, n)
                    var i = 0
                    while (i + 1 < n) {
                        val v = (((buf[i + 1].toInt() and 0xFF) shl 8) or
                            (buf[i].toInt() and 0xFF)).toShort() / 32768.0
                        if (Math.abs(v) > peak) peak = Math.abs(v)
                        i += 2
                    }
                }
            } catch (e: Throwable) {
                logs.add("录音出错：$e")
            } finally {
                runCatching { rec.stop() }
                runCatching { rec.release() }
                recorder = null
                recording = false
            }
            val pcm = out.toByteArray()
            if (pcm.size < sr / 2) {                 // 不到 0.5 秒，等于没说话
                runOnUiThread {
                    paintMic()
                    if (this@MainActivity::notice.isInitialized) notice.text = "说话时间太短"
                }
                return@thread
            }
            runOnUiThread {
                if (this@MainActivity::notice.isInitialized) notice.text = "正在识别…"
            }
            val res = runCatching { client.transcribe(sid, wav(pcm, sr)) }.getOrNull()
            val text = res?.optString("text").orEmpty()
            runOnUiThread {
                paintMic()
                if (res != null && res.optBoolean("ok") && text.isNotEmpty()) {
                    val cur = input.text.toString()
                    input.setText(cur + text)
                    input.setSelection(input.text.length)
                    if (this@MainActivity::notice.isInitialized) notice.text = "语音已识别：$text"
                } else if (peak < 0.02) {
                    if (this@MainActivity::notice.isInitialized) notice.text = "没听到声音，靠近点再说"
                } else {
                    val err = res?.optString("error").orEmpty()
                    if (this@MainActivity::notice.isInitialized) {
                        notice.text = if (err.isNotEmpty()) err else "没听清，再说一次"
                    }
                }
            }
        }
    }

    /** 给 PCM 套一个 44 字节的 WAV 头，电脑端直接当 WAV 读。 */
    private fun wav(pcm: ByteArray, sampleRate: Int): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        fun le32(v: Int) = byteArrayOf((v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte(),
            ((v shr 16) and 0xFF).toByte(), ((v shr 24) and 0xFF).toByte())
        fun le16(v: Int) = byteArrayOf((v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte())
        out.write("RIFF".toByteArray()); out.write(le32(36 + pcm.size)); out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray()); out.write(le32(16)); out.write(le16(1)); out.write(le16(1))
        out.write(le32(sampleRate)); out.write(le32(sampleRate * 2))
        out.write(le16(2)); out.write(le16(16))
        out.write("data".toByteArray()); out.write(le32(pcm.size)); out.write(pcm)
        return out.toByteArray()
    }

    private fun flush() {
        // 250ms 防抖：连续打字时不逐字发，停手后才同步一次，
        // 否则电脑端会一直"全选→粘贴"，看起来就是在反复重刷。
        syncHandler.removeCallbacks(syncTask)
        syncHandler.postDelayed(syncTask, 250)
    }

    private val syncHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val syncTask = Runnable { flushNow() }

    private fun flushNow() {
        // 整段同步：不再算差量（差量会因电脑端光标位置而串位），
        // 直接把手机上输入框的完整内容交给电脑端，由电脑端负责变成这段文字。
        val now = input.text.toString()
        if (now == sent) return
        sent = now
        // 记录"上一次发到电脑的内容"，供「恢复」使用。
        // 之前只有发送键会写入它，而发送键早就改成只敲回车了，
        // 于是「恢复」永远是空的（用户反馈的"纯空壳"就是这个原因）。
        if (now.isNotEmpty()) lastSent = now
        send(listOf(JSONObject().put("k", "sync").put("text", now)))
    }

    private fun label(text: String, size: Float, color: Int, bold: Boolean = false): TextView =
        TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    private fun chip(text: String, onClick: () -> Unit): Button =
        Button(this).apply {
            this.text = text
            textSize = 14f
            setTextColor(C_DIM)
            background = pressable(C_CARD, 999f, C_LINE)
            minWidth = 0
            minimumWidth = 0
            setPadding(dp(16), dp(8), dp(16), dp(8))
            setOnClickListener { onClick() }
        }

    /** 纯图标按钮（清空 / 还原这些） */
    /** 顶部页签（即打即输 / 编辑后发送）：选中 = 主色文字 + 底部 16×3 下划线 */
    private fun tabButton(text: String): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 14f
            gravity = Gravity.CENTER
            setTextColor(C_MUTED)
            background = pressable(0x00000000, 12f)
            isClickable = true
        }

    private fun iconButton(iconRes: Int, desc: String, onClick: () -> Unit): ImageButton =
        ImageButton(this).apply {
            // 用 ImageButton + scaleType=centerInside：图标严格居容器中心，
            // 不会像 TextView 的 compoundDrawable 那样受字体留白影响而"偏"。
            setImageResource(iconRes)
            scaleType = android.widget.ImageView.ScaleType.CENTER_INSIDE
            contentDescription = desc
            background = pressable(C_CARD, 12f, C_LINE)
            layoutParams = LinearLayout.LayoutParams(dp(48), dp(48))
                .apply { leftMargin = dp(8); rightMargin = 0 }
            setPadding(dp(12), dp(12), dp(12), dp(12))
            setOnClickListener { onClick() }
        }

    private fun rounded(color: Int, radiusDp: Float, stroke: Int = 0): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            setColor(color)
            cornerRadius = radiusDp * resources.displayMetrics.density
            if (stroke != 0) setStroke(1, stroke)
        }

    /** 按压反馈：底色不变，按下时浮出一层白色涟漪（就是你要的「点击显白」）。 */
    private fun pressable(color: Int, radiusDp: Float, stroke: Int = 0): RippleDrawable =
        RippleDrawable(ColorStateList.valueOf(0x40FFFFFF),
            rounded(color, radiusDp, stroke), null)

    /** 内容入场：淡入 + 轻微上移，220ms 减速曲线。 */
    private fun enter(view: View?, delayMs: Long = 0L) {
        view ?: return
        view.alpha = 0f
        view.translationY = dp(10).toFloat()
        view.animate().alpha(1f).translationY(0f)
            .setStartDelay(delayMs).setDuration(220L)
            .setInterpolator(DecelerateInterpolator()).start()
    }

    private fun lp(top: Int = 0, h: Int = 0, matchWidth: Boolean = false): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            if (matchWidth) ViewGroup.LayoutParams.MATCH_PARENT
            else ViewGroup.LayoutParams.WRAP_CONTENT,
            if (h > 0) dp(h) else ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(top) }

    /** 本机唯一标识：用系统 ANDROID_ID，电脑端据此认出是同一台手机 */
    private fun androidId(): String = runCatching {
        android.provider.Settings.Secure.getString(contentResolver,
            android.provider.Settings.Secure.ANDROID_ID)
    }.getOrNull().orEmpty()

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    companion object {
        private val KEYS: List<Pair<String, JSONObject>> = listOf(
            "⌫" to JSONObject().put("k", "key").put("key", "BACKSPACE"),
            "⏎" to JSONObject().put("k", "key").put("key", "ENTER"),
            "Tab" to JSONObject().put("k", "key").put("key", "TAB"),
            "Esc" to JSONObject().put("k", "key").put("key", "ESC"),
            "←" to JSONObject().put("k", "key").put("key", "LEFT"),
            "↑" to JSONObject().put("k", "key").put("key", "UP"),
            "↓" to JSONObject().put("k", "key").put("key", "DOWN"),
            "→" to JSONObject().put("k", "key").put("key", "RIGHT"),
            "行首" to JSONObject().put("k", "key").put("key", "HOME"),
            "行尾" to JSONObject().put("k", "key").put("key", "END"),
            "全选" to JSONObject().put("k", "combo").put("key", "A").put("ctrl", true),
            "复制" to JSONObject().put("k", "combo").put("key", "C").put("ctrl", true),
            "粘贴" to JSONObject().put("k", "combo").put("key", "V").put("ctrl", true),
            "撤销" to JSONObject().put("k", "combo").put("key", "Z").put("ctrl", true),
            "保存" to JSONObject().put("k", "combo").put("key", "S").put("ctrl", true),
            "切窗口" to JSONObject().put("k", "combo").put("key", "TAB").put("alt", true),
        )
    }
}
