package com.textlink.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.Keyboard
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.textlink.app.Level
import com.textlink.app.LinkViewModel
import com.textlink.app.net.PcDevice
import com.textlink.app.net.PeerInfo
import kotlinx.coroutines.delay

@Composable
fun DeviceScreen(vm: LinkViewModel, modifier: Modifier = Modifier) {
    val devices by vm.devices.collectAsState()
    val status by vm.status.collectAsState()
    val level by vm.level.collectAsState()
    val pinTarget by vm.pinTarget.collectAsState()
    val manual by vm.manualPrompt.collectAsState()
    val busy by vm.busy.collectAsState()
    val pinError by vm.pinError.collectAsState()
    val help by vm.help.collectAsState()
    val peers by vm.peers.collectAsState()

    var waited by remember { mutableStateOf(0) }
    LaunchedEffect(devices.isEmpty()) {
        waited = 0
        while (devices.isEmpty()) {
            delay(1000)
            waited += 1
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp)
    ) {
        // 顶部品牌区（LocalSend 首页也是"大 logo + 名称 + 一句话"）
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 20.dp, bottom = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            AppLogo(size = 72.dp, color = MaterialTheme.colorScheme.primary)
            Text(
                text = "TextLink",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(top = 12.dp)
            )
            Text(
                text = "手机变成电脑的无线键盘",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp)
            )
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            if (busy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.primary
                )
            } else {
                BreathingDot(levelColor(level), 9.dp)
            }
            Text(
                text = status,
                style = MaterialTheme.typography.bodyMedium,
                color = if (level == Level.Bad) MaterialTheme.colorScheme.error
                else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 8.dp)
            )
        }

        Spacer(Modifier.height(20.dp))

        AnimatedVisibility(
            visible = help != null,
            enter = fadeIn(tween(220)) + expandVertically(tween(220)),
            exit = fadeOut(tween(140)) + shrinkVertically(tween(140))
        ) {
            Column {
                InfoBanner(
                    text = help.orEmpty(),
                    container = MaterialTheme.colorScheme.errorContainer,
                    content = MaterialTheme.colorScheme.onErrorContainer
                )
                Spacer(Modifier.height(16.dp))
            }
        }

        // 新增：设备列表 —— 电脑端会把它上面连着的设备发过来
        if (peers.isNotEmpty()) {
            DeviceListCard(peers)
            Spacer(Modifier.height(16.dp))
        }

        if (devices.isEmpty() && waited >= 6 && help == null) {
            InfoBanner(
                text = "搜不到电脑？确认三件事：电脑上 TextLink-PC.exe 正在运行；" +
                    "手机和电脑连同一个 Wi-Fi；电脑窗口里如果出现黄色提示条，点「一键放行防火墙」。",
                icon = Icons.Outlined.Wifi
            )
            Spacer(Modifier.height(16.dp))
        }

        if (devices.isEmpty()) {
            EmptyState(
                title = "正在搜索电脑…",
                detail = "保持 TextLink-PC.exe 运行，手机和电脑连同一个 Wi-Fi 即可",
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                icon = Icons.Outlined.Computer
            )
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                items(devices, key = { it.key }) { device ->
                    DeviceCard(device, enabled = !busy) { vm.askPin(device) }
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 20.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Button(
                onClick = { vm.refresh() },
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Outlined.Search, contentDescription = null, Modifier.size(18.dp))
                Text("重新搜索", Modifier.padding(start = 8.dp))
            }
            OutlinedButton(
                onClick = { vm.showManual(true) },
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Outlined.Keyboard, contentDescription = null, Modifier.size(18.dp))
                Text("手动输入 IP", Modifier.padding(start = 8.dp))
            }
        }
    }

    pinTarget?.let { device ->
        PinDialog(
            device = device,
            error = pinError,
            busy = busy,
            onDismiss = { vm.dismissPin() },
            onConfirm = { pin -> vm.connect(device, pin) }
        )
    }

    if (manual) {
        ManualDialog(
            preset = vm.lastHost,
            onDismiss = { vm.showManual(false) },
            onConfirm = { host, port, pin -> vm.connectManual(host, port, pin) }
        )
    }
}

internal fun levelColor(level: Level) = when (level) {
    Level.Ok -> SuccessGreen
    Level.Warn -> WarnAmber
    Level.Bad -> androidx.compose.ui.graphics.Color(0xFFFF6B6B)
    Level.Idle -> androidx.compose.ui.graphics.Color(0xFF7C8AA0)
}

@Composable
private fun DeviceCard(device: PcDevice, enabled: Boolean, onClick: () -> Unit) {
    val spotlight = rememberSpotlightModifier(
        glow = MaterialTheme.colorScheme.primary.copy(alpha = 0.16f)
    )
    val interaction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    Surface(
        onClick = onClick,
        enabled = enabled,
        interactionSource = interaction,
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainer,
        modifier = Modifier
            .fillMaxWidth()
            .then(spotlight)
            .pressScale(interaction)
            .pressFlash(interaction, corner = 28.dp)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            RoundIcon(
                icon = Icons.Outlined.Computer,
                size = 48.dp,
                container = MaterialTheme.colorScheme.primaryContainer,
                tint = MaterialTheme.colorScheme.onPrimaryContainer
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 14.dp)
            ) {
                Text(
                    text = device.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 3.dp)
                ) {
                    StatusDot(SuccessGreen, 7.dp)
                    Text(
                        text = "${device.host}:${device.port}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 6.dp)
                    )
                }
            }
            Icon(
                imageVector = Icons.Outlined.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

/**
 * 新增：设备列表 —— 显示当前连在这台电脑上的所有设备。
 * 每行都带圆形头像、圆角标签，并且逐个错峰淡入。
 */
@Composable
private fun DeviceListCard(peers: List<PeerInfo>) {
    Surface(
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainer,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "设备列表",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(Modifier.weight(1f))
                Surface(
                    shape = MaterialTheme.shapes.extraSmall,
                    color = MaterialTheme.colorScheme.primaryContainer
                ) {
                    Text(
                        text = "${peers.size} 台在线",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }
            }
            peers.forEachIndexed { index, peer ->
                var visible by remember(peer.name, peer.ip) { mutableStateOf(false) }
                LaunchedEffect(peer.name, peer.ip) {
                    kotlinx.coroutines.delay(index * 60L)
                    visible = true
                }
                AnimatedVisibility(
                    visible = visible,
                    enter = fadeIn(tween(240)) + expandVertically(tween(240))
                ) {
                    PeerRow(peer)
                }
            }
        }
    }
}

@Composable
private fun PeerRow(peer: PeerInfo) {
    val interaction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    Surface(
        onClick = {},
        interactionSource = interaction,
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceContainerHigh,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 10.dp)
            .pressScale(interaction)
            .pressFlash(interaction, corner = 22.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            RoundIcon(
                icon = Icons.Outlined.PhoneAndroid,
                size = 40.dp,
                container = MaterialTheme.colorScheme.secondaryContainer,
                tint = MaterialTheme.colorScheme.onSecondaryContainer
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 12.dp)
            ) {
                Text(
                    text = peer.name,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1
                )
                Text(
                    text = peer.ip.ifBlank { "同机连接" },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            CountUp(
                value = peer.chars,
                suffix = " 字",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun PinDialog(
    device: PcDevice,
    error: String?,
    busy: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var pin by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("输入配对码") },
        text = {
            Column {
                Text(
                    text = if (device.needsPin)
                        "电脑端 TextLink-PC.exe 窗口顶部显示的四位数字"
                    else
                        "这台电脑没有开启配对码，直接连接即可",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = pin,
                    onValueChange = { input -> pin = input.filter { it.isDigit() }.take(8) },
                    singleLine = true,
                    label = { Text("配对码") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.fillMaxWidth()
                )
                if (error != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                if (busy) {
                    Spacer(Modifier.height(10.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(14.dp),
                            strokeWidth = 2.dp
                        )
                        Text(
                            text = "正在连接…",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 8.dp)
                        )
                    }
                }
            }
        },
        confirmButton = {
            val ready = (pin.length >= 4 || !device.needsPin) && !busy
            TextButton(onClick = { onConfirm(pin) }, enabled = ready) { Text("连接") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@Composable
private fun ManualDialog(
    preset: String,
    onDismiss: () -> Unit,
    onConfirm: (String, Int, String) -> Unit
) {
    var host by remember { mutableStateOf(preset) }
    var port by remember { mutableStateOf("8765") }
    var pin by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("手动连接电脑") },
        text = {
            Column {
                Text(
                    text = "电脑端窗口顶部会显示本机地址，例如 192.168.1.8",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    singleLine = true,
                    label = { Text("电脑 IP") },
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = port,
                    onValueChange = { port = it.filter { ch -> ch.isDigit() }.take(5) },
                    singleLine = true,
                    label = { Text("端口") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = pin,
                    onValueChange = { pin = it.filter { ch -> ch.isDigit() }.take(8) },
                    singleLine = true,
                    label = { Text("配对码（没开启就留空）") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(host, port.toIntOrNull() ?: 8765, pin) },
                enabled = host.isNotBlank()
            ) { Text("连接") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}
