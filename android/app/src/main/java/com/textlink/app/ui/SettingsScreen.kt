package com.textlink.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.textlink.app.LinkViewModel

@Composable
fun SettingsScreen(vm: LinkViewModel, modifier: Modifier = Modifier) {
    val sendWithEnter by vm.sendWithEnter.collectAsState()
    val mirror by vm.mirrorEnabled.collectAsState()
    val pcName by vm.pcName.collectAsState()
    val status by vm.status.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
    ) {
        Spacer(Modifier.height(16.dp))

        SectionTitle("发送")
        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surfaceContainer,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(vertical = 4.dp)) {
                SwitchRow(
                    title = "发送后按回车",
                    detail = "点「发送」时，电脑端输入完文字再按一次回车（等于在电脑上点了发送）",
                    checked = sendWithEnter,
                    onCheckedChange = { vm.setSendWithEnter(it) }
                )
                HorizontalDivider(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    color = MaterialTheme.colorScheme.outlineVariant
                )
                SwitchRow(
                    title = "同步电脑上的改动",
                    detail = "电脑输入框的内容变化时，自动同步到手机输入框（手机正在编辑时不会覆盖）",
                    checked = mirror,
                    onCheckedChange = { vm.setMirrorEnabled(it) }
                )
            }
        }

        Spacer(Modifier.height(28.dp))
        SectionTitle("本机")
        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surfaceContainer,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(16.dp)) {
                InfoRow("设备名称", vm.deviceName)
                Spacer(Modifier.height(10.dp))
                InfoRow("电脑", pcName ?: "未连接")
                Spacer(Modifier.height(10.dp))
                InfoRow("状态", status)
            }
        }

        Spacer(Modifier.height(28.dp))
        SectionTitle("关于")
        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surfaceContainer,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(16.dp)) {
                InfoRow("版本", "1.3.2")
                Spacer(Modifier.height(10.dp))
                InfoRow("连接方式", "局域网 WebSocket + UDP 自动发现")
                Spacer(Modifier.height(10.dp))
                InfoRow("电脑端要求", "Windows，TextLink-PC.exe 1.2.0")
            }
        }

        Spacer(Modifier.height(32.dp))
    }
}

@Composable
private fun SwitchRow(
    title: String,
    detail: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Medium
            )
            Text(
                text = detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}
