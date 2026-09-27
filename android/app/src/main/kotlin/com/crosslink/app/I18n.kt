package com.crosslink.app

import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import java.util.Locale

/**
 * 界面语言（中文 / English）。
 *
 * 做法和电脑端一样：界面文案以中文为源，切到英文时把已经渲染出来的文字
 * 按“中文原文 → English”查表替换，带数字的用正则规则。
 * 这样不用把几百处字面量全部改写成 key，也不会漏掉动态生成的状态行。
 */
object I18n {

    const val ZH = "zh"
    const val EN = "en"

    @Volatile
    var lang: String = ZH

    /** 跟随系统语言给一个默认值 */
    fun defaultLang(): String =
        if (Locale.getDefault().language.startsWith("zh")) ZH else EN

    private val DICT: Map<String, String> = mapOf(
        // —— 基本 ——
        "手机" to "Phone",
        "电脑" to "PC",
        "跨屏输入" to "TypeBridge",
        "手机当电脑的无线键盘" to "Use your phone as the PC keyboard",
        "启动出错，请把下面这段发给我：" to "Startup error - please send me this:",

        // —— 设备列表 ——
        "附近的电脑" to "Nearby computers",
        "正在搜索同一 Wi-Fi 下的电脑" to "Searching for computers on the same Wi-Fi",
        "正在搜索同一 Wi-Fi 下的电脑…" to "Searching for computers on the same Wi-Fi…",
        "没搜到 · 检查同一 Wi-Fi 和电脑端防火墙" to
            "Nothing found - check the same Wi-Fi and the PC firewall",
        "连接设置" to "Connection settings",
        "地址和配对码和电脑窗口上显示的一致；配对码只有电脑开了「需要配对码」时才要填。" to
            "Address and pairing code must match the PC window; the code is only needed " +
            "when the PC requires it.",
        "电脑地址，例如 192.168.1.146:8788" to "PC address, e.g. 192.168.1.146:8788",
        "配对码（电脑没开就留空）" to "Pairing code (leave empty if not required)",
        "连接电脑" to "Connect to PC",
        "发送后自动回车" to "Press Enter after sending",
        "立即搜索" to "Search now",
        "发送模式" to "Send mode",
        "即打即输" to "Live typing",
        "编辑后发送" to "Edit then send",
        "断开当前连接" to "Disconnect",
        "已断开连接" to "Disconnected",
        "需要配对码" to "Code required",
        "连接" to "Connect",
        "取消" to "Cancel",
        "关闭" to "Close",

        // —— 底部栏 ——
        "发送" to "Send",
        "记录" to "Logs",
        "设置" to "Settings",

        // —— 记录页 ——
        "打开应用，开始搜索" to "App opened, searching",
        "运行记录" to "Activity log",
        "连接、搜索、发送的动作都会记在这里，方便排查。" to
            "Connection, search and send actions are logged here.",
        "（空）" to "(empty)",

        // —— 输入页 ——
        "先在电脑上点一下要输入的窗口" to "Click the window you want to type into on the PC",
        "在这里打字…" to "Type here…",
        "输入" to "Enter",
        "删除" to "Delete",
        "恢复" to "Restore",
        "多按键" to "Keys",
        "点一个发一个，面板不会自动关" to "Each tap sends one key; the panel stays open",
        "还没有发送过内容" to "Nothing has been sent yet",
        "内容没变化" to "No change",
        "已清空手机输入框（电脑上的内容没动）" to
            "Phone input cleared (the PC keeps its text)",
        "已恢复上次发送的内容（正在同步到电脑）" to
            "Restored the last sent text (syncing to the PC)",
        "已敲回车，输入框已清空（可用「恢复」找回）" to
            "Enter sent, input cleared (use Restore to get it back)",
        "与电脑重连成功，已继续同步" to "Reconnected to the PC, syncing again",
        "电脑端已断开连接，返回设备列表" to "The PC disconnected; back to the device list",
        "已断开连接，返回设备列表" to "Disconnected; back to the device list",
        "连接失败" to "Connection failed",
        "进入输入页出错：" to "Failed to open the typing page: ",

        // —— 配对码弹窗 ——
        "配对码在电脑窗口上（输入页和设置页都显示）" to
            "The pairing code is shown in the PC window (input and settings page)",
        "请输入 4 位配对码" to "Enter the 4-digit pairing code",
        "电脑上：（空）" to "On PC: (empty)",
        "电脑上：" to "On PC: ",
        "焦点在 CrossLink 上，点一下目标程序" to
            "Focus is on TypeBridge - click your target program",

        // —— 功能键 ——
        "行首" to "Home",
        "行尾" to "End",
        "全选" to "Select all",
        "复制" to "Copy",
        "粘贴" to "Paste",
        "撤销" to "Undo",
        "保存" to "Save",
        "切窗口" to "Switch window"
    )

    private val RULES: List<Pair<Regex, (MatchResult) -> String>> = listOf(
        Regex("^移除 (\\d+) 台已断开的设备$") to
            { m: MatchResult -> "Removed ${m.groupValues[1]} disconnected device(s)" },
        Regex("^网段扫描找到 (\\d+) 台电脑$") to
            { m: MatchResult -> "Subnet scan found ${m.groupValues[1]} computer(s)" },
        Regex("^找到 (\\d+) 台电脑$") to
            { m: MatchResult -> "Found ${m.groupValues[1]} computer(s)" },
        Regex("^(\\d+) 字$") to
            { m: MatchResult -> "${m.groupValues[1]} chars" },
        Regex("^已就绪：(.*)$") to
            { m: MatchResult -> "Ready: ${m.groupValues[1]}" },
        Regex("^连不上：(.*)$") to
            { m: MatchResult -> "Cannot connect: ${m.groupValues[1]}" },
        Regex("^连接出错：(.*)$") to
            { m: MatchResult -> "Connection error: ${m.groupValues[1]}" },
        Regex("^v([\\d.]+) · .*$") to
            { m: MatchResult -> "v${m.groupValues[1]} · Live typing / Edit then send" }
    )

    fun t(text: String?): String? {
        if (lang != EN || text.isNullOrEmpty()) return text
        val s = text.trim()
        if (s.isEmpty()) return text
        DICT[s]?.let { return text.replace(s, it) }
        for ((re, fn) in RULES) {
            val m = re.matchEntire(s)
            if (m != null) {
                val out = fn(m)
                if (out != s) return text.replace(s, out)
            }
        }
        return text
    }

    /** 把一整棵视图树上的文字、提示、无障碍描述都翻译一遍 */
    fun localize(view: View?) {
        if (lang != EN || view == null) return
        when (view) {
            is TextView -> {
                t(view.text?.toString())?.let { if (it != view.text.toString()) view.text = it }
                val hint = view.hint?.toString()
                t(hint)?.let { if (it != hint) view.hint = it }
                view.contentDescription?.toString()?.let { cd ->
                    t(cd)?.let { if (it != cd) view.contentDescription = it }
                }
            }
            else -> view.contentDescription?.toString()?.let { cd ->
                t(cd)?.let { if (it != cd) view.contentDescription = it }
            }
        }
        if (view is Button) t(view.text?.toString())?.let { if (it != view.text.toString()) view.text = it }
        if (view is EditText) {
            val hint = view.hint?.toString()
            t(hint)?.let { if (it != hint) view.hint = it }
        }
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) localize(view.getChildAt(i))
        }
    }
}
