"""Wake Word Detector

Detects the wake word using Picovoice Porcupine.

Porcupine reads from the microphone with blocking calls, so detection runs on
a worker thread and hands detections back to the asyncio loop. Running it
inline would starve the loop that drives the agent and the UI.
"""

import asyncio
import struct
import threading
from typing import Optional, Callable, Any
from loguru import logger

from jarvis.core.config import get_settings


class WakeWordDetector:
    """Detects the wake word using Picovoice Porcupine."""

    def __init__(self):
        self._settings = get_settings()
        self._wake_word = self._settings.voice.wake_word
        self._porcupine = None
        self._running = False
        self._callback: Optional[Callable[[], Any]] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _initialize(self):
        """Initialize Porcupine."""
        if self._porcupine is not None:
            return

        import pvporcupine

        access_key = self._settings.voice.pv_access_key
        if not access_key:
            raise RuntimeError(
                "Porcupine needs a Picovoice access key. Set PV_ACCESS_KEY in .env "
                "to enable wake-word detection."
            )

        try:
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[self._wake_word],
            )
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            raise

        logger.info(f"Initialized Porcupine with wake word: {self._wake_word}")

    def _dispatch(self) -> None:
        """Schedule the callback on the asyncio loop from the worker thread."""
        if not self._callback or not self._loop:
            return
        try:
            result = self._callback()
            if asyncio.iscoroutine(result):
                asyncio.run_coroutine_threadsafe(result, self._loop)
        except Exception as e:
            logger.error(f"Wake word callback failed: {e}")

    def _detect_loop(self) -> None:
        """Blocking detection loop; runs on a worker thread."""
        pa = None
        stream = None
        try:
            import pyaudio

            frame_length = self._porcupine.frame_length
            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=frame_length,
            )

            logger.info("Wake word detector listening")

            while self._running:
                try:
                    pcm = stream.read(frame_length, exception_on_overflow=False)
                    # Porcupine wants int16 samples, not raw bytes.
                    samples = struct.unpack_from("%dh" % frame_length, pcm)

                    if self._porcupine.process(samples) >= 0:
                        logger.info(f"Wake word detected: {self._wake_word}")
                        self._dispatch()

                except Exception as e:
                    logger.error(f"Wake word processing error: {e}")
                    break

        except Exception as e:
            logger.error(f"Wake word detector failed: {e}")
        finally:
            self._running = False
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
            if self._porcupine is not None:
                try:
                    self._porcupine.delete()
                except Exception:
                    pass
                self._porcupine = None

    async def start(self, callback: Callable[[], Any]) -> None:
        """Start listening for the wake word and return immediately."""
        if self._running:
            return

        self._callback = callback
        self._loop = asyncio.get_running_loop()

        self._initialize()

        self._running = True
        self._thread = threading.Thread(
            target=self._detect_loop, name="jarvis-wake-word", daemon=True
        )
        self._thread.start()
        logger.info("Wake word detector started")

    async def stop(self) -> None:
        """Stop listening for the wake word."""
        if not self._running and self._thread is None:
            return

        self._running = False

        thread, self._thread = self._thread, None
        if thread is not None:
            await asyncio.get_running_loop().run_in_executor(None, thread.join, 3.0)

        logger.info("Wake word detector stopped")

    @property
    def is_running(self) -> bool:
        """Check if detector is running."""
        return self._running


class SimpleWakeWordDetector:
    """Text-based wake word fallback.

    Used when Porcupine is unavailable. It does not listen on its own -- the
    caller feeds it transcribed text via :meth:`check_audio`, which suits
    push-to-talk and continuous-transcription modes.
    """

    def __init__(self, wake_word: Optional[str] = None):
        self._wake_word = (wake_word or get_settings().voice.wake_word).lower()
        self._running = False
        self._callback: Optional[Callable[[], Any]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self, callback: Callable[[], Any]) -> None:
        """Start listening for the wake word."""
        self._callback = callback
        self._loop = asyncio.get_running_loop()
        self._running = True
        logger.warning(
            f"Porcupine unavailable - falling back to text wake-word matching for "
            f"'{self._wake_word}'. Hands-free detection is off; use the orb, the "
            f"hotkey, or push-to-talk to start a request."
        )

    async def stop(self) -> None:
        """Stop listening."""
        self._running = False

    def check_audio(self, text: str) -> bool:
        """Check whether transcribed text contains the wake word."""
        if not self._running or self._wake_word not in text.lower():
            return False

        logger.info(f"Wake word detected: {self._wake_word}")
        if self._callback:
            result = self._callback()
            if asyncio.iscoroutine(result):
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(result, self._loop)
                else:
                    result.close()
        return True

    @property
    def is_running(self) -> bool:
        return self._running
