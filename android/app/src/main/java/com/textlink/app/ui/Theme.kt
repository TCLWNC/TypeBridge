package com.textlink.app.ui

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

/**
 * 蓝色主题（Material 3 色彩角色）。
 * 结构照搬 LocalSend 的做法：组件全部用 M3 角色取色，品牌色只体现在 primary 上。
 */
// 色值来自对 LocalSend 窗口的实测取样（纯黑底 + 近黑面板 + 淡蓝主色）
private val BluePrimaryDark = Color(0xFFB4C5FF)
private val BlueOnPrimaryDark = Color(0xFF0B2A5B)
private val BluePrimaryContainerDark = Color(0xFF26408B)
private val BlueOnPrimaryContainerDark = Color(0xFFDCE1FF)
private val BlueSecondaryContainerDark = Color(0xFF1B1E27)
private val BlueOnSecondaryContainerDark = Color(0xFFE2E2EA)

private val BluePrimaryLight = Color(0xFF415F91)
private val BlueOnPrimaryLight = Color(0xFFFFFFFF)
private val BluePrimaryContainerLight = Color(0xFFD8E2FF)
private val BlueOnPrimaryContainerLight = Color(0xFF001A41)
private val BlueSecondaryContainerLight = Color(0xFFDCE3F9)
private val BlueOnSecondaryContainerLight = Color(0xFF151B2C)

private val DarkScheme = darkColorScheme(
    primary = BluePrimaryDark,
    onPrimary = BlueOnPrimaryDark,
    primaryContainer = BluePrimaryContainerDark,
    onPrimaryContainer = BlueOnPrimaryContainerDark,
    secondary = Color(0xFFC5C6D0),
    onSecondary = Color(0xFF2E3036),
    secondaryContainer = BlueSecondaryContainerDark,
    onSecondaryContainer = BlueOnSecondaryContainerDark,
    tertiary = Color(0xFF00AEFA),
    onTertiary = Color(0xFF002F3D),
    background = Color(0xFF000000),
    onBackground = Color(0xFFFFFFFF),
    surface = Color(0xFF000000),
    onSurface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFF1C1D22),
    onSurfaceVariant = Color(0xFFC5C6D0),
    surfaceContainerLowest = Color(0xFF000000),
    surfaceContainerLow = Color(0xFF090A0D),
    surfaceContainer = Color(0xFF0E0F14),
    surfaceContainerHigh = Color(0xFF15171E),
    surfaceContainerHighest = Color(0xFF1C1E26),
    outline = Color(0xFF3A3E48),
    outlineVariant = Color(0xFF23252C),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
)

private val LightScheme = lightColorScheme(
    primary = BluePrimaryLight,
    onPrimary = BlueOnPrimaryLight,
    primaryContainer = BluePrimaryContainerLight,
    onPrimaryContainer = BlueOnPrimaryContainerLight,
    secondary = Color(0xFF4A5A75),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = BlueSecondaryContainerLight,
    onSecondaryContainer = BlueOnSecondaryContainerLight,
    tertiary = Color(0xFF2C5F8A),
    onTertiary = Color(0xFFFFFFFF),
    background = Color(0xFFF9F9FF),
    onBackground = Color(0xFF1A1B20),
    surface = Color(0xFFF9F9FF),
    onSurface = Color(0xFF1A1B20),
    surfaceVariant = Color(0xFFE1E2EC),
    onSurfaceVariant = Color(0xFF44474F),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF2F4FA),
    surfaceContainer = Color(0xFFECEEF5),
    surfaceContainerHigh = Color(0xFFE6E9F0),
    surfaceContainerHighest = Color(0xFFE0E4EB),
    outline = Color(0xFF74777F),
    outlineVariant = Color(0xFFC4C6D0),
    error = Color(0xFFBA1A1A),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
)

private val AppShapes = Shapes(
    extraSmall = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
    small = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
    medium = androidx.compose.foundation.shape.RoundedCornerShape(22.dp),
    large = androidx.compose.foundation.shape.RoundedCornerShape(28.dp),
    extraLarge = androidx.compose.foundation.shape.RoundedCornerShape(32.dp),
)

/** 品牌要求是蓝色，所以默认不使用 Material You 动态取色。 */
private const val USE_DYNAMIC_COLOR = false

@Composable
fun TextLinkTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    val scheme = when {
        USE_DYNAMIC_COLOR && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        darkTheme -> DarkScheme
        else -> LightScheme
    }
    MaterialTheme(colorScheme = scheme, shapes = AppShapes, content = content)
}

/** 界面里需要"强调蓝"的地方（图表、状态点）直接用这个。 */
val BrandBlue = Color(0xFFB4C5FF)
val BrandBlueDark = Color(0xFF00AEFA)
val SuccessGreen = Color(0xFF4CBB7F)
val WarnAmber = Color(0xFFD9A441)
