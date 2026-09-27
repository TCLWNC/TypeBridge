package com.textlink.app

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.Keyboard
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Keyboard
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.textlink.app.ui.AppLogo
import com.textlink.app.ui.DeviceScreen
import com.textlink.app.ui.SettingsScreen
import com.textlink.app.ui.ShinyText
import com.textlink.app.ui.SparkHost
import com.textlink.app.ui.SparkState
import com.textlink.app.ui.TextLinkTheme
import com.textlink.app.ui.TypeScreen
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        setContent {
            TextLinkTheme {
                AppShell()
            }
        }
    }
}

private data class Destination(
    val label: String,
    val selectedIcon: ImageVector,
    val icon: ImageVector
)

private val destinations = listOf(
    Destination("设备", Icons.Filled.Devices, Icons.Outlined.Devices),
    Destination("输入", Icons.Filled.Keyboard, Icons.Outlined.Keyboard),
    Destination("设置", Icons.Filled.Settings, Icons.Outlined.Settings)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppShell() {
    val vm: LinkViewModel = viewModel()
    val screen by vm.screen.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var tab by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(screen) {
        if (screen == Screen.Typing) tab = 1
    }

    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        // 手机（窄屏）用底部导航；平板/大屏才用左侧导航栏
        val wideLayout = maxWidth >= 600.dp

        Row(modifier = Modifier.fillMaxSize()) {
            if (wideLayout) {
                NavigationRail(containerColor = MaterialTheme.colorScheme.surfaceContainer) {
                    AppLogo(
                        size = 30.dp,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(top = 16.dp, bottom = 24.dp)
                    )
                    destinations.forEachIndexed { index, item ->
                        NavigationRailItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = {
                                Icon(
                                    if (tab == index) item.selectedIcon else item.icon,
                                    contentDescription = item.label
                                )
                            },
                            label = { Text(item.label) }
                        )
                    }
                }
            }

            Scaffold(
                modifier = Modifier.weight(1f),
                topBar = {
                    CenterAlignedTopAppBar(
                        title = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (!wideLayout) {
                                    AppLogo(
                                        size = 26.dp,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                                ShinyText(
                                    text = "TextLink",
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.titleLarge,
                                    animated = false,
                                    modifier = Modifier.padding(start = if (wideLayout) 0.dp else 8.dp)
                                )
                            }
                        },
                        colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                            containerColor = MaterialTheme.colorScheme.surface
                        )
                    )
                },
                bottomBar = {
                    if (!wideLayout) {
                        NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainer) {
                            destinations.forEachIndexed { index, item ->
                                NavigationBarItem(
                                    selected = tab == index,
                                    onClick = { tab = index },
                                    icon = {
                                        Icon(
                                            if (tab == index) item.selectedIcon else item.icon,
                                            contentDescription = item.label
                                        )
                                    },
                                    label = { Text(item.label) }
                                )
                            }
                        }
                    }
                },
                snackbarHost = { SnackbarHost(snackbarHostState) },
                containerColor = MaterialTheme.colorScheme.background
            ) { inner ->
                val sparkState = remember { SparkState() }
                SparkHost(
                    state = sparkState,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(inner)
                ) {
                    AnimatedContent(
                        targetState = tab,
                        transitionSpec = {
                            val forward = targetState > initialState
                            // 进场减速、退场加速，短距离滑动 + 淡入淡出
                            (
                                fadeIn(tween(durationMillis = 220)) +
                                    slideInHorizontally(tween(260)) {
                                        if (forward) it / 10 else -it / 10
                                    }
                                ) togetherWith
                                (
                                    fadeOut(tween(durationMillis = 140)) +
                                        slideOutHorizontally(tween(140)) {
                                            if (forward) -it / 14 else it / 14
                                        }
                                    )
                        },
                        label = "tab"
                    ) { current ->
                        when (current) {
                            0 -> DeviceScreen(vm)
                            1 -> TypeScreen(
                                vm = vm,
                                onSent = {
                                    scope.launch { snackbarHostState.showSnackbar("已发送到电脑") }
                                }
                            )
                            else -> SettingsScreen(vm)
                        }
                    }
                }
            }
        }
    }
}
