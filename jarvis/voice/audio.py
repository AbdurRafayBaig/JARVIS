"""Audio Capture and Playback

Handles microphone capture and speaker playback.

PyAudio's read/write calls block, so every one of them runs on a worker
thread. Doing it inline would freeze the asyncio loop that drives the agent,
the UI and the wake-word detector for as long as the microphone is open.
"""

import array
import asyncio
import io
import threading
import wave
from typing import Optional
from pathlib import Path
from loguru import logger

from jarvis.core.config import get_settings

try:  # audioop was removed from the stdlib in Python 3.13
    import audioop
except ImportError:  # pragma: no cover - depends on interpreter version
    audioop = None

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM
CHUNK_SIZE = 1024

# RMS below which a chunk counts as silence. 16-bit samples run to 32767, and
# room tone typically sits well under 500.
SILENCE_RMS_THRESHOLD = 500


class AudioCapture:
    """Captures audio from the microphone."""

    def __init__(self):
        self._settings = get_settings()
        self._device_index = self._settings.voice.microphone_device_index
        self._sample_rate = SAMPLE_RATE
        self._channels = CHANNELS
        self._chunk_size = CHUNK_SIZE
        self._is_recording = False
        self._frames: list[bytes] = []
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _capture_loop(self) -> None:
        """Blocking capture loop; runs on a worker thread."""
        stream = None
        pa = None
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=self._chunk_size,
            )
            logger.info("Audio recording started")

            while self._is_recording:
                try:
                    data = stream.read(self._chunk_size, exception_on_overflow=False)
                except Exception as e:
                    logger.error(f"Recording error: {e}")
                    break
                with self._lock:
                    self._frames.append(data)

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
        finally:
            self._is_recording = False
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if pa is not None:
                try:
                    pa.terminate()
                except Exception:
                    pass

    async def start_recording(self) -> None:
        """Start recording in the background and return immediately."""
        if self._is_recording:
            return

        with self._lock:
            self._frames = []
        self._is_recording = True

        self._thread = threading.Thread(
            target=self._capture_loop, name="jarvis-audio-capture", daemon=True
        )
        self._thread.start()

    async def stop_recording(self) -> bytes:
        """Stop recording and return the captured audio as WAV bytes."""
        if not self._is_recording and self._thread is None:
            return self._get_wav_bytes()

        self._is_recording = False

        thread, self._thread = self._thread, None
        if thread is not None:
            await asyncio.get_running_loop().run_in_executor(None, thread.join, 5.0)

        audio_data = self._get_wav_bytes()
        logger.info(f"Audio recording stopped: {len(audio_data)} bytes")
        return audio_data

    def _get_wav_bytes(self) -> bytes:
        """Convert recorded frames to WAV bytes."""
        buffer = io.BytesIO()
        with self._lock:
            frames = b"".join(self._frames)

        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(self._sample_rate)
            wf.writeframes(frames)

        return buffer.getvalue()

    def _tail_rms(self, window_seconds: float) -> int:
        """Loudness of the most recent audio, used for silence detection."""
        chunks_needed = max(1, int(window_seconds * self._sample_rate / self._chunk_size))
        with self._lock:
            tail = self._frames[-chunks_needed:]
        if not tail:
            return 0
        payload = b"".join(tail)
        try:
            if audioop is not None:
                return audioop.rms(payload, SAMPLE_WIDTH)
            samples = array.array("h")
            samples.frombytes(payload[: len(payload) - len(payload) % SAMPLE_WIDTH])
            if not samples:
                return 0
            return int((sum(s * s for s in samples) / len(samples)) ** 0.5)
        except Exception:
            return 0

    @property
    def duration_seconds(self) -> float:
        """Length of the audio captured so far."""
        with self._lock:
            frame_count = len(self._frames)
        return frame_count * self._chunk_size / self._sample_rate

    async def record_duration(self, duration: float) -> bytes:
        """Record audio for a fixed duration."""
        await self.start_recording()
        await asyncio.sleep(duration)
        return await self.stop_recording()

    async def record_until_silence(
        self,
        max_duration: float = 15.0,
        silence_duration: float = 1.2,
        initial_grace: float = 1.0,
    ) -> bytes:
        """Record until the speaker stops talking, or ``max_duration`` elapses.

        Waits ``initial_grace`` seconds before silence can end the recording,
        so a slow start does not cut the utterance off immediately.
        """
        await self.start_recording()

        poll = 0.1
        elapsed = 0.0
        quiet_for = 0.0

        try:
            while elapsed < max_duration:
                await asyncio.sleep(poll)
                elapsed += poll

                if not self._is_recording:
                    break

                if elapsed < initial_grace:
                    continue

                if self._tail_rms(silence_duration) < SILENCE_RMS_THRESHOLD:
                    quiet_for += poll
                    if quiet_for >= silence_duration:
                        logger.debug(f"Silence detected after {elapsed:.1f}s")
                        break
                else:
                    quiet_for = 0.0
        except asyncio.CancelledError:
            self._is_recording = False
            raise

        return await self.stop_recording()

    @property
    def is_recording(self) -> bool:
        return self._is_recording


class AudioPlayback:
    """Plays audio through the speakers."""

    def __init__(self):
        self._settings = get_settings()
        self._device_index = self._settings.voice.speaker_device_index
        self._is_playing = False

    def _play_blocking(self, audio_data: bytes) -> None:
        """Blocking playback; runs on a worker thread."""
        pa = None
        stream = None
        try:
            import pyaudio

            buffer = io.BytesIO(audio_data)
            with wave.open(buffer, "rb") as wf:
                pa = pyaudio.PyAudio()
                stream = pa.open(
                    format=pa.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    output_device_index=self._device_index,
                )

                data = wf.readframes(CHUNK_SIZE)
                while data and self._is_playing:
                    stream.write(data)
                    data = wf.readframes(CHUNK_SIZE)

        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if pa is not None:
                try:
                    pa.terminate()
                except Exception:
                    pass

    async def play(self, audio_data: bytes) -> None:
        """Play audio data without blocking the event loop."""
        if self._is_playing or not audio_data:
            return

        self._is_playing = True
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self._play_blocking, audio_data
            )
        finally:
            self._is_playing = False

    async def play_file(self, file_path: Path) -> None:
        """Play audio from a file."""
        audio_data = await asyncio.get_running_loop().run_in_executor(
            None, file_path.read_bytes
        )
        await self.play(audio_data)

    async def stop(self) -> None:
        """Stop playback. The worker thread exits at its next chunk."""
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing
