# -*- coding: utf-8 -*-
"""电脑端本地语音输入：麦克风 → 离线识别 → 文字打进当前窗口。

用的是 sherpa-onnx 里的 SenseVoice-Small（Apache-2.0）：
中文/英文/日文/韩文/粤语都能识别，int8 模型约 228 MB，CPU 上比实时快 8 倍左右
（实测 5.6 秒音频 0.73 秒出结果）。模型不进 exe，放在配置目录里，第一次用的时候下。

为什么不用讯飞输入法里那套：那是它的私有格式 + 私有运行时代码，拆出来既跑不起来
也不是许可允许的用法；这里用的是公开授权的权重，可以合法随程序分发。
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from . import config as config_mod

# 模型文件（两个都要在）
MODEL_FILE = "model.int8.onnx"
TOKENS_FILE = "tokens.txt"

# 供界面显示的模型下载地址（模型太大，不塞进安装包）
MODEL_URL = ("https://hf-mirror.com/csukuangfj/"
             "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/")

SAMPLE_RATE = 16000


def model_dir() -> Path:
    """模型放哪：优先环境变量，其次配置目录（正常情况），最后程序自己的 asr 子目录。"""
    env = os.environ.get("CROSSLINK_ASR_DIR")
    if env:
        return Path(env)
    return Path(config_mod.config_dir()) / "asr" / "sense-voice"


def model_ready() -> bool:
    d = model_dir()
    return (d / MODEL_FILE).exists() and (d / TOKENS_FILE).exists()


def model_status() -> str:
    d = model_dir()
    if model_ready():
        return "ok"
    if not d.exists():
        return "missing"
    return "partial"


_recognizer = None
_recognizer_lock = threading.Lock()


class Spectrum:
    """麦克风频谱：给"声纹"用，对齐 Handy 的做法。

    把音频切成 1024 点的窗，做 FFT，按**对数间隔**分成 16 个频段，
    每个频段取平均功率 → 转 dB → 映射到 0..1，再做一次跨频段平滑。
    dB 区间是照 Handy 校准过的那组（-68 ~ -30 dB，增益 1.3，曲线 0.7），
    这样说话时波形起伏明显，房间本底噪声又不会让波形乱抖。
    """

    WINDOW = 1024
    BUCKETS = 16
    F_MIN = 60.0
    F_MAX = 7600.0
    DB_MIN = -68.0
    DB_MAX = -30.0
    GAIN = 1.3
    CURVE = 0.7

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        import numpy as np

        self.np = np
        self.sample_rate = sample_rate
        self.buffer = np.zeros(0, dtype="float32")
        self.hann = 0.5 - 0.5 * np.cos(
            2.0 * np.pi * np.arange(self.WINDOW) / self.WINDOW)
        nyquist = sample_rate / 2.0
        f_max = min(self.F_MAX, nyquist)
        ranges = []
        for b in range(self.BUCKETS):
            start = (b / self.BUCKETS) ** 2          # 对数分频
            end = ((b + 1) / self.BUCKETS) ** 2
            f0 = self.F_MIN + (f_max - self.F_MIN) * start
            f1 = self.F_MIN + (f_max - self.F_MIN) * end
            i0 = int(f0 * self.WINDOW / sample_rate)
            i1 = int(f1 * self.WINDOW / sample_rate)
            if i1 <= i0:
                i1 = i0 + 1
            half = self.WINDOW // 2
            ranges.append((min(i0, half), min(i1, half)))
        self.ranges = ranges
        self.values = [0.0] * self.BUCKETS

    def feed(self, samples) -> list[float] | None:
        np = self.np
        self.buffer = np.concatenate([self.buffer, samples])
        if self.buffer.size < self.WINDOW:
            return None
        chunk = self.buffer[:self.WINDOW]
        self.buffer = self.buffer[self.WINDOW:]
        chunk = (chunk - float(chunk.mean())) * self.hann
        mag = np.abs(np.fft.rfft(chunk))
        out = []
        half = self.WINDOW // 2
        for (i0, i1) in self.ranges:
            if i0 >= half or i1 <= i0:
                out.append(0.0)
                continue
            power = float(np.mean(mag[i0:i1] ** 2))
            db = 20.0 * np.log10(np.sqrt(power) / self.WINDOW) if power > 1e-12 else -80.0
            norm = min(max((db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN), 0.0), 1.0)
            out.append(min((norm * self.GAIN) ** self.CURVE, 1.0))
        smoothed = list(out)
        for i in range(1, len(out) - 1):
            smoothed[i] = out[i] * 0.7 + out[i - 1] * 0.15 + out[i + 1] * 0.15
        self.values = smoothed
        return smoothed


def recognizer():
    """第一次调用时加载模型（约 2 秒），之后复用。"""
    global _recognizer
    with _recognizer_lock:
        if _recognizer is not None:
            return _recognizer
        import sherpa_onnx          # 延迟导入：没装语音模块时其它功能照常

        d = model_dir()
        _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(d / MODEL_FILE),
            tokens=str(d / TOKENS_FILE),
            use_itn=True,           # 打开数字/标点规整："九点" → "9点"
            language="zh",
            num_threads=max(2, min(4, (os.cpu_count() or 4))),
            debug=False,
        )
        return _recognizer


def transcribe(samples, sample_rate: int = SAMPLE_RATE) -> str:
    """把一段 float32 单声道音频转成文字。"""
    rec = recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(sample_rate, samples)
    rec.decode_stream(stream)
    text = (stream.result.text or "").strip()
    # SenseVoice 会在句首带一个语言/情绪标记，切掉
    for tag in ("<|zh|>", "<|en|>", "<|ja|>", "<|ko|>", "<|yue|>"):
        text = text.replace(tag, "")
    return text.strip()


def transcribe_file(path: str) -> str:
    import wave

    import numpy as np

    with wave.open(path, "rb") as fh:
        rate = fh.getframerate()
        channels = fh.getnchannels()
        raw = fh.readframes(fh.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return transcribe(audio, rate)


def transcribe_wav_bytes(data: bytes) -> str:
    """手机录好一段 WAV 直接发过来时用这个（不进磁盘）。"""
    import io
    import wave

    import numpy as np

    with wave.open(io.BytesIO(data), "rb") as fh:
        rate = fh.getframerate()
        channels = fh.getnchannels()
        width = fh.getsampwidth()
        raw = fh.readframes(fh.getnframes())
    if width != 2:
        raise ValueError("只支持 16 位 PCM WAV")
    audio = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return transcribe(audio, rate)


class VoiceSession:
    """一次"按住说话"：开一个线程录音，边说边判静音，说完自动停。"""

    def __init__(self, log=None) -> None:
        self.log = log or (lambda *_: None)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._text = ""
        self._error = ""
        self.recording = False
        # 是否"说完自动停"。按住说的模式下要关掉：什么时候停由松手决定，
        # 否则说话中间停顿超过 1.4 秒就被掐断（用户反馈的"按久一点就强制中断"）。
        self._auto_stop = True
        # 实时音量（0..1），声纹窗口用它画波形
        self.level = 0.0
        # 实时频谱（16 段），声纹画的就是这个
        self.bars = [0.0] * Spectrum.BUCKETS
        # 声纹浮层照这个决定画什么：
        #   "idle"        没在收
        #   "listening"   正在收音 —— 画跟着说话起伏的频谱
        #   "recognizing" 松手了、模型还在认字 —— 画"正在识别"的走波
        # （以前没有这个状态，松手后频谱没人更新，条子就冻在最后一帧）
        self.state = "idle"

    # -- 对外 --------------------------------------------------------------
    def start(self, auto_stop: bool = True) -> None:
        if self.recording:
            return
        self._stop.clear()
        self._auto_stop = bool(auto_stop)
        self._text = ""
        self._error = ""
        self.recording = True
        self.state = "listening"
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="crosslink-voice")
        self._thread.start()

    def stop(self, timeout: float = 25.0) -> str:
        """停止录音并等识别结果返回。"""
        if not self.recording and self._thread is None:
            return ""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        self.recording = False
        self._thread = None
        if self._error:
            raise RuntimeError(self._error)
        return self._text

    def cancel(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(6.0)
        self.recording = False
        self._thread = None
        self._text = ""
        self.state = "idle"

    # -- 内部 --------------------------------------------------------------
    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd

            block = 0.1
            chunks = []
            silence = 0.0
            voiced = 0.0
            started = time.time()
            spectrum = Spectrum(SAMPLE_RATE)
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                blocksize=int(SAMPLE_RATE * block)) as stream:
                self.log("🎤 开始收音…")
                while not self._stop.is_set():
                    data, _overflow = stream.read(int(SAMPLE_RATE * block))
                    mono = data[:, 0]
                    chunks.append(mono.copy())
                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    self.level = min(1.0, rms * 12.0)     # 给声纹用，顺手做个放大
                    bars = spectrum.feed(mono)
                    if bars is not None:
                        self.bars = bars
                    if rms > 0.012:
                        voiced += block
                        silence = 0.0
                    else:
                        silence += block
                    # 说完了（说过话之后静了 1.4 秒）自己停 —— 只在自动停模式下生效
                    if self._auto_stop and voiced > 0.25 and silence >= 1.4:
                        break
                    # 按住模式给足时间（说话中间可以停顿），自动停模式 60 秒足够
                    if time.time() - started > (150.0 if not self._auto_stop else 60.0):
                        break
                if self._stop.is_set():
                    self.log("🎤 手动停止")
            if not chunks:
                self._error = "没有录到声音"
                return
            audio = np.concatenate(chunks)
            self.level = 0.0
            if voiced < 0.2:
                self.log("🎤 没听到说话")
                self._error = "没有听到说话"
                return
            # 到这里就不录音了，接下来是模型认字：让声纹切成"正在识别"
            self.state = "recognizing"
            t0 = time.time()
            self._text = transcribe(audio, SAMPLE_RATE)
            self.log("🎤 识别完成 %.1fs：%s" % (time.time() - t0, self._text[:60]))
        except Exception as exc:      # noqa: BLE001
            self._error = "语音识别失败：%s" % exc
            self.log("🎤 " + self._error)
        finally:
            self.recording = False
            self.state = "idle"
