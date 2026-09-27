package com.textlink.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * 从 React Bits 源码移植过来的动效（原生 Compose 实现）：
 *   ShinyText     高光扫过文字（background-position 150% → -50%，扫完停一下）
 *   CountUp       数字弹簧滚动
 *   SpotlightCard 跟随指针的径向高光
 *   ClickSpark    点击处 8 条火花线（ease-out 外扩并缩短）
 *   BreathingDot  呼吸状态点
 */

@Composable
fun ShinyText(
    text: String,
    modifier: Modifier = Modifier,
    baseColor: Color = MaterialTheme.colorScheme.onSurface,
    shineColor: Color = Color.White,
    speedMillis: Int = 2600,
    holdMillis: Int = 1400,
    style: TextStyle = LocalTextStyle.current,
    fontWeight: FontWeight? = null,
    animated: Boolean = true
) {
    if (!animated) {
        // 静止版：保留渐变发光的观感，但不跑动画（手机端标题用，避免持续重绘）
        Text(
            text = text,
            modifier = modifier,
            style = style.copy(
                brush = Brush.linearGradient(
                    colors = listOf(baseColor, shineColor, baseColor),
                    start = Offset(0f, 0f),
                    end = Offset(180f, 180f)
                ),
                fontWeight = fontWeight ?: style.fontWeight
            )
        )
        return
    }
    val transition = rememberInfiniteTransition(label = "shiny")
    val cycle by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = speedMillis + holdMillis,
                easing = LinearEasing
            )
        ),
        label = "shinyCycle"
    )
    val progress = ((cycle * (speedMillis + holdMillis)) / speedMillis).coerceAtMost(1f)
    val start = 1.5f - progress * 2f

    Text(
        text = text,
        modifier = modifier,
        style = style.copy(
            brush = Brush.linearGradient(
                colors = listOf(baseColor, baseColor, shineColor, baseColor, baseColor),
                start = Offset(start * 200f, 0f),
                end = Offset((start + 1f) * 200f, 200f)
            ),
            fontWeight = fontWeight ?: style.fontWeight
        )
    )
}

@Composable
fun CountUp(
    value: Int,
    modifier: Modifier = Modifier,
    suffix: String = "",
    prefix: String = "",
    style: TextStyle = LocalTextStyle.current,
    color: Color = Color.Unspecified
) {
    val animated = remember { Animatable(0f) }
    var previous by remember { mutableIntStateOf(value) }

    LaunchedEffect(value) {
        animated.snapTo(0f)
        animated.animateTo(
            targetValue = 1f,
            animationSpec = spring(
                dampingRatio = Spring.DampingRatioNoBouncy,
                stiffness = Spring.StiffnessLow
            )
        )
        previous = value
    }

    val shown = (previous + (value - previous) * animated.value).roundToInt()
    Text(text = "$prefix$shown$suffix", modifier = modifier, style = style, color = color)
}

/**
 * SpotlightCard：卡片内跟随指针的柔光。
 * 用 rememberSpotlightModifier() 拿到 Modifier，再 .then() 到卡片上。
 */
@Composable
fun rememberSpotlightModifier(
    enabled: Boolean = true,
    glow: Color = Color.White.copy(alpha = 0.10f)
): Modifier {
    var position by remember { mutableStateOf(Offset.Zero) }
    var visible by remember { mutableStateOf(false) }
    val alpha by animateFloatAsState(
        targetValue = if (visible && enabled) 1f else 0f,
        animationSpec = tween(durationMillis = 400),
        label = "spotlightAlpha"
    )

    return Modifier
        .pointerInput(enabled) {
            if (!enabled) return@pointerInput
            awaitPointerEventScope {
                while (true) {
                    val event = awaitPointerEvent()
                    val change = event.changes.firstOrNull() ?: continue
                    when (event.type) {
                        PointerEventType.Move,
                        PointerEventType.Enter,
                        PointerEventType.Press -> {
                            position = change.position
                            visible = true
                        }
                        PointerEventType.Exit -> visible = false
                        else -> Unit
                    }
                }
            }
        }
        .drawWithContent {
            drawContent()
            if (alpha > 0.01f) {
                val radius = size.maxDimension * 0.8f
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(glow, Color.Transparent),
                        center = position,
                        radius = radius
                    ),
                    radius = radius,
                    center = position,
                    alpha = alpha
                )
            }
        }
}

class SparkState {
    internal val bursts = mutableStateListOf<SparkBurst>()

    fun launch(origin: Offset) {
        bursts.add(SparkBurst(origin, System.nanoTime()))
        if (bursts.size > 6) bursts.removeAt(0)
    }
}

internal class SparkBurst(val origin: Offset, val startedAt: Long)

/**
 * 按下时轻微缩一下再弹回来（弹簧），所有可点击组件都能用。
 * 配合 Material 的水波纹一起，点击反馈就很明确。
 */
@Composable
fun Modifier.pressScale(
    interactionSource: MutableInteractionSource,
    pressedScale: Float = 0.96f
): Modifier {
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) pressedScale else 1f,
        animationSpec = spring(
            dampingRatio = 0.5f,
            stiffness = Spring.StiffnessMedium
        ),
        label = "pressScale"
    )
    return this.graphicsLayer {
        scaleX = scale
        scaleY = scale
    }
}

/**
 * 点击反馈：先盖一层白，再淡出落回原样（和 LocalSend 按钮的手感一致）。
 * 用圆角矩形裁剪，保证圆润组件上不会出现方角白块。
 */
@Composable
fun Modifier.pressFlash(
    interactionSource: MutableInteractionSource,
    corner: Dp = 28.dp,
    maxAlpha: Float = 0.26f,
    durationMillis: Int = 260
): Modifier {
    val pressed by interactionSource.collectIsPressedAsState()
    val alpha = remember { Animatable(0f) }
    LaunchedEffect(pressed) {
        if (pressed) {
            alpha.snapTo(maxAlpha)
            alpha.animateTo(
                targetValue = 0f,
                animationSpec = tween(durationMillis = durationMillis, easing = LinearEasing)
            )
        }
    }
    return this.drawWithContent {
        drawContent()
        if (alpha.value > 0.01f) {
            drawRoundRect(
                color = Color.White.copy(alpha = alpha.value),
                cornerRadius = CornerRadius(corner.toPx(), corner.toPx())
            )
        }
    }
}

/** ClickSpark：包住内容即可，点击处会散出火花，不会拦截子元素点击。 */
@Composable
fun SparkHost(
    state: SparkState,
    color: Color,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    var frame by remember { mutableStateOf(0L) }

    LaunchedEffect(state.bursts.size) {
        while (state.bursts.isNotEmpty()) {
            withFrameMillis { frame = it }
            val now = System.nanoTime()
            state.bursts.removeAll { (now - it.startedAt) / 1_000_000 > 400 }
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        if (event.type == PointerEventType.Press) {
                            event.changes.firstOrNull()?.let { state.launch(it.position) }
                        }
                    }
                }
            }
            .drawWithContent {
                drawContent()
                frame              // 每帧重绘的触发点
                val now = System.nanoTime()
                state.bursts.forEach { burst ->
                    val elapsed = (now - burst.startedAt) / 1_000_000f
                    val progress = (elapsed / 400f).coerceIn(0f, 1f)
                    val eased = progress * (2 - progress)     // ease-out，与源码一致
                    val distance = eased * 46f
                    val lineLength = 18f * (1 - eased)
                    repeat(8) { index ->
                        val angle = 2.0 * PI * index / 8.0
                        val cx = cos(angle).toFloat()
                        val cy = sin(angle).toFloat()
                        drawLine(
                            color = color.copy(alpha = 1f - progress),
                            start = Offset(
                                burst.origin.x + distance * cx,
                                burst.origin.y + distance * cy
                            ),
                            end = Offset(
                                burst.origin.x + (distance + lineLength) * cx,
                                burst.origin.y + (distance + lineLength) * cy
                            ),
                            strokeWidth = 2.dp.toPx()
                        )
                    }
                }
            }
    ) {
        content()
    }
}

/** 呼吸状态点（正弦，和电脑端一致）。 */
@Composable
fun BreathingDot(color: Color, size: Dp = 9.dp) {
    val transition = rememberInfiniteTransition(label = "breath")
    val scale by transition.animateFloat(
        initialValue = 0.82f,
        targetValue = 1.12f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breathScale"
    )
    Box(
        modifier = Modifier
            .size(size)
            .scale(scale)
            .background(color, CircleShape)
    )
}
