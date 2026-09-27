package com.textlink.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowForward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.Backspace
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.KeyboardReturn
import androidx.compose.material.icons.outlined.Send
import androidx.compose.material.icons.outlined.Undo
import androidx.compose.material.icons.outlined.VerticalAlignBottom
import androidx.compose.material.icons.outlined.VerticalAlignTop
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.textlink.app.Level
import com.textlink.app.LinkViewModel
import com.textlink.app.SendMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TypeScreen(
    vm: LinkViewModel,
    modifier: Modifier = Modifier,
    onSent: () -> Unit
) {
    val pcName by vm.pcName.collectAsState()
    val status by vm.status.collectAsState()
    val level by vm.level.collectAsState()
    val mode by vm.mode.collectAsState()
    val field by vm.field.collectAsState()
    val sent by vm.sentChars.collectAsState()
    val latency by vm.latency.collectAsState()
    val history by vm.history.collectAsState()
    val sendCount by vm.sendCount.collectAsState()

    val sendInteraction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val restoreInteraction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }

    // 字数变化时用弹簧轻轻弹一下，作为"送出去了"的反馈
    var pulse by remember { mutableStateOf(false) }
    LaunchedEffect(sent) {
        if (sent > 0) {
            pulse = true
            kotlinx.coroutines.delay(160)
            pulse = false
        }
    }
    val counterScale by animateFloatAsState(
        targetValue = if (pulse) 1.07f else 1f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "counterScale"
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
    ) {
        Spacer(Modifier.height(16.dp))

        // 连接状态
        Row(verticalAlignment = Alignment.CenterVertically) {
            RoundIcon(
                icon = Icons.Outlined.Computer,
                size = 36.dp,
                container = MaterialTheme.colorScheme.primaryContainer,
                tint = MaterialTheme.colorScheme.onPrimaryContainer
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 10.dp)
            ) {
                Text(
                    text = pcName ?: "电脑",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusDot(levelColor(level), 7.dp)
                    Text(
                        text = "  $status · ${latencyText(latency)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1
                    )
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                // 这个数字每敲一个字就变，用弹簧动画会一直重排导致卡顿，所以静态显示
                Text(
                    text = "已输入 $sent 字",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
                if (sendCount > 0) {
                    CountUp(
                        value = sendCount,
                        prefix = "已发送 ",
                        suffix = " 条",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        Spacer(Modifier.height(20.dp))

        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            SegmentedButton(
                selected = mode == SendMode.Live,
                onClick = { vm.setMode(SendMode.Live) },
                shape = SegmentedButtonDefaults.itemShape(index = 0, count = 2)
            ) { Text("即打即输") }
            SegmentedButton(
                selected = mode == SendMode.Batch,
                onClick = { vm.setMode(SendMode.Batch) },
                shape = SegmentedButtonDefaults.itemShape(index = 1, count = 2)
            ) { Text("编辑后发送") }
        }

        Spacer(Modifier.height(16.dp))

        OutlinedTextField(
            value = field,
            onValueChange = { vm.onTextChange(it) },
            modifier = Modifier
                .fillMaxWidth()
                // 给一个最小高度：键盘弹出时不会被上面的固定内容挤没
                .heightIn(min = 148.dp, max = 300.dp),
            placeholder = {
                Text(
                    text = if (mode == SendMode.Live)
                        "在这里打字，文字会直接出现在电脑光标处"
                    else
                        "先在这里写好，点「发送」一次性输入并按回车",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 15.sp
                )
            },
            textStyle = MaterialTheme.typography.bodyLarge,
            shape = MaterialTheme.shapes.large
        )

        Spacer(Modifier.height(12.dp))

        AnimatedContent(
            targetState = level,
            transitionSpec = { fadeIn(tween(200)) togetherWith fadeOut(tween(120)) },
            label = "hint"
        ) { current ->
            Text(
                text = when (current) {
                    Level.Ok -> "先在电脑上点一下要输入的程序，再在这里打字"
                    Level.Warn -> "正在重连电脑，这期间打的字可能不会送过去"
                    Level.Bad -> "连接已断开，回到「设备」页重新连接"
                    Level.Idle -> ""
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (current == Level.Bad) MaterialTheme.colorScheme.error
                else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Spacer(Modifier.height(14.dp))

        // 功能键
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            KeyButton("退格", Icons.Outlined.Backspace) { vm.pressKey("BACKSPACE") }
            KeyButton("回车", Icons.Outlined.KeyboardReturn) { vm.pressKey("ENTER") }
            KeyButton("Tab") { vm.pressKey("TAB") }
            KeyButton("Esc") { vm.pressKey("ESCAPE") }
            KeyButton(icon = Icons.Outlined.ArrowBack) { vm.pressKey("ARROWLEFT") }
            KeyButton(icon = Icons.Outlined.ArrowUpward) { vm.pressKey("ARROWUP") }
            KeyButton(icon = Icons.Outlined.ArrowDownward) { vm.pressKey("ARROWDOWN") }
            KeyButton(icon = Icons.Outlined.ArrowForward) { vm.pressKey("ARROWRIGHT") }
            KeyButton(icon = Icons.Outlined.VerticalAlignTop) { vm.pressKey("HOME") }
            KeyButton(icon = Icons.Outlined.VerticalAlignBottom) { vm.pressKey("END") }
            KeyButton("全选") { vm.pressCombo("A", ctrl = true) }
            KeyButton("复制") { vm.pressCombo("C", ctrl = true) }
            KeyButton("粘贴") { vm.pressCombo("V", ctrl = true) }
            KeyButton("撤销") { vm.pressCombo("Z", ctrl = true) }
            KeyButton("切换窗口") { vm.pressCombo("TAB", alt = true) }
        }

        Spacer(Modifier.height(16.dp))

        // 发送 / 还原 / 清空
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    vm.sendFromPhone()
                    onSent()
                },
                interactionSource = sendInteraction,
                modifier = Modifier
                    .weight(1f)
                    .pressScale(sendInteraction)
                    .pressFlash(sendInteraction, corner = 20.dp)
            ) {
                Icon(Icons.Outlined.Send, contentDescription = null, Modifier.size(18.dp))
                Text("发送", Modifier.padding(start = 8.dp), fontWeight = FontWeight.SemiBold)
            }
            OutlinedButton(
                onClick = { vm.restoreLast() },
                enabled = history.isNotEmpty(),
                interactionSource = restoreInteraction,
                modifier = Modifier
                    .pressScale(restoreInteraction)
                    .pressFlash(restoreInteraction, corner = 20.dp)
            ) {
                Icon(Icons.Outlined.Undo, contentDescription = null, Modifier.size(18.dp))
                Text(
                    text = if (history.isEmpty()) "还原" else "还原 ${history.size}",
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
            TextButton(onClick = { vm.clearField() }) { Text("清空") }
        }
    }
}

@Composable
private fun KeyButton(
    text: String? = null,
    icon: ImageVector? = null,
    onClick: () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    val interaction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    FilledTonalButton(
        onClick = {
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
            onClick()
        },
        interactionSource = interaction,
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 0.dp),
        modifier = Modifier
            .height(40.dp)
            .pressScale(interaction, pressedScale = 0.94f)
            .pressFlash(interaction, corner = 20.dp, maxAlpha = 0.30f)
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = text, modifier = Modifier.size(18.dp))
        }
        if (text != null) {
            Text(
                text = text,
                fontSize = 13.sp,
                modifier = Modifier.padding(start = if (icon != null) 6.dp else 0.dp)
            )
        }
    }
}

private fun latencyText(ms: Long): String = if (ms < 0) "测延迟…" else "${ms}ms"
