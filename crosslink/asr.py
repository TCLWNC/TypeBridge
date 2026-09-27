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


class VoiceSession:
    """一次"按住说话"：开一个线程录音，边说边判静音，说完自动停。"""

    def __init__(self, log=None) -> None:
        self.log = log or (lambda *_: None)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._text = ""
        self._error = ""
        self.recording = False

    # -- 对外 --------------------------------------------------------------
    def start(self) -> None:
        if self.recording:
            return
        self._stop.clear()
        self._text = ""
        self._error = ""
        self.recording = True
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
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                blocksize=int(SAMPLE_RATE * block)) as stream:
                self.log("🎤 开始收音…")
                while not self._stop.is_set():
                    data, _overflow = stream.read(int(SAMPLE_RATE * block))
                    mono = data[:, 0]
                    chunks.append(mono.copy())
                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    if rms > 0.012:
                        voiced += block
                        silence = 0.0
                    else:
                        silence += block
                    # 说完了（说过话之后静了 1.4 秒）自己停
                    if voiced > 0.25 and silence >= 1.4:
                        break
                    if time.time() - started > 60.0:
                        break
                if self._stop.is_set():
                    self.log("🎤 手动停止")
            if not chunks:
                self._error = "没有录到声音"
                return
            audio = np.concatenate(chunks)
            if voiced < 0.2:
                self.log("🎤 没听到说话")
                self._error = "没有听到说话"
                return
            t0 = time.time()
            self._text = transcribe(audio, SAMPLE_RATE)
            self.log("🎤 识别完成 %.1fs：%s" % (time.time() - t0, self._text[:60]))
        except Exception as exc:      # noqa: BLE001
            self._error = "语音识别失败：%s" % exc
            self.log("🎤 " + self._error)
        finally:
            self.recording = False
