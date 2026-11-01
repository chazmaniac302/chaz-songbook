"""Voice memo recording (mic -> 16-bit WAV), playback and a metronome click."""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from array import array
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal


def write_click_wav(path: Path, freq: float, ms: int = 45, volume: float = 0.8, rate: int = 44100) -> Path:
    n = int(rate * ms / 1000)
    frames = bytearray()
    for i in range(n):
        env = math.exp(-i / (n / 6.0))
        v = math.sin(2 * math.pi * freq * i / rate) * env * volume
        frames += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


def wav_duration(path: str | Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (OSError, wave.Error, EOFError):
        return 0.0


def _to_int16(data: bytes, sample_format) -> bytes:
    from PySide6.QtMultimedia import QAudioFormat
    if sample_format == QAudioFormat.SampleFormat.Int16:
        return data
    if sample_format == QAudioFormat.SampleFormat.Float:
        a = array("f")
        a.frombytes(data[: len(data) - len(data) % 4])
        return array("h", (int(max(-1.0, min(1.0, x)) * 32767) for x in a)).tobytes()
    if sample_format == QAudioFormat.SampleFormat.Int32:
        a = array("i")
        a.frombytes(data[: len(data) - len(data) % 4])
        return array("h", (x >> 16 for x in a)).tobytes()
    if sample_format == QAudioFormat.SampleFormat.UInt8:
        return array("h", ((b - 128) << 8 for b in data)).tobytes()
    return data


class Recorder(QObject):
    """Records the default microphone to a 16-bit PCM WAV file."""
    levelChanged = Signal(float)   # 0..1 peak
    elapsedChanged = Signal(float)  # seconds
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = None
        self._io = None
        self._wav = None
        self._fmt = None
        self._frames = 0
        self.path: Path | None = None

    @property
    def recording(self) -> bool:
        return self._source is not None

    def start(self, path: Path) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
        dev = QMediaDevices.defaultAudioInput()
        if dev.isNull():
            raise RuntimeError("No microphone found. Plug one in and check Windows Settings › Privacy › Microphone.")
        fmt = QAudioFormat()
        fmt.setSampleRate(44100)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt = dev.preferredFormat()
        self._fmt = fmt
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._wav = wave.open(str(path), "wb")
        self._wav.setnchannels(fmt.channelCount())
        self._wav.setsampwidth(2)
        self._wav.setframerate(fmt.sampleRate())
        self._frames = 0
        self._source = QAudioSource(dev, fmt, self)
        self._io = self._source.start()
        if self._io is None:
            self._cleanup()
            raise RuntimeError("Could not open the microphone (is another app using it?)")
        self._io.readyRead.connect(self._read)

    def _read(self) -> None:
        if not self._io or not self._wav:
            return
        raw = bytes(self._io.readAll().data())
        if not raw:
            return
        pcm = _to_int16(raw, self._fmt.sampleFormat())
        self._wav.writeframes(pcm)
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        if samples:
            self._frames += len(samples) // max(1, self._fmt.channelCount())
            peak = max(max(samples), -min(samples)) / 32768.0
            self.levelChanged.emit(min(1.0, peak))
            self.elapsedChanged.emit(self._frames / float(self._fmt.sampleRate()))

    def stop(self) -> Path | None:
        if not self._source:
            return None
        self._read()
        self._source.stop()
        path = self.path
        self._cleanup()
        return path

    def _cleanup(self) -> None:
        if self._wav:
            try:
                self._wav.close()
            except Exception:
                pass
        self._wav = None
        if self._source:
            self._source.deleteLater()
        self._source = None
        self._io = None
        self.levelChanged.emit(0.0)


class Player(QObject):
    stateChanged = Signal(bool)  # playing?

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._out = None

    def _ensure(self):
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._player = QMediaPlayer(self)
            self._out = QAudioOutput(self)
            self._player.setAudioOutput(self._out)
            self._player.playbackStateChanged.connect(
                lambda st: self.stateChanged.emit(st == QMediaPlayer.PlaybackState.PlayingState))
        return self._player

    def play(self, path: str | Path) -> None:
        p = self._ensure()
        p.setSource(QUrl.fromLocalFile(str(path)))
        p.play()

    def stop(self) -> None:
        if self._player:
            self._player.stop()


class Metronome(QObject):
    """Click at the song tempo; accent on beat 1."""
    beat = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._bpm = 120.0
        self._beats_per_bar = 4
        self._i = 0
        self._hi = self._lo = None

    def _ensure_sounds(self):
        if self._hi is not None:
            return
        from PySide6.QtMultimedia import QSoundEffect
        d = Path(tempfile.gettempdir()) / "ChazSongBook"
        d.mkdir(parents=True, exist_ok=True)
        hi = write_click_wav(d / "click_hi.wav", 1760)
        lo = write_click_wav(d / "click_lo.wav", 1175, volume=0.6)
        self._hi, self._lo = QSoundEffect(self), QSoundEffect(self)
        self._hi.setSource(QUrl.fromLocalFile(str(hi)))
        self._lo.setSource(QUrl.fromLocalFile(str(lo)))

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def set_tempo(self, bpm: float, beats_per_bar: int = 4) -> None:
        self._bpm = max(20.0, min(400.0, float(bpm or 120)))
        self._beats_per_bar = max(1, beats_per_bar)
        if self._timer.isActive():
            self._timer.setInterval(int(round(60000.0 / self._bpm)))

    def start(self) -> None:
        self._ensure_sounds()
        self._i = 0
        self._timer.start(int(round(60000.0 / self._bpm)))
        self._tick()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        n = self._i % self._beats_per_bar
        snd = self._hi if n == 0 else self._lo
        if snd is not None:
            snd.play()
        self.beat.emit(n)
        self._i += 1
