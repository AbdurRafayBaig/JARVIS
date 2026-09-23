"""Voice Pipeline

Orchestrates the complete voice interaction flow:
Wake -> Listen -> STT -> Agent -> TTS -> Speak
"""

import asyncio
from typing import Optional, Callable, Any
from loguru import logger

from jarvis.core.config import get_settings
from jarvis.voice.stt_provider import STTProvider, WhisperSTT
from jarvis.voice.tts_provider import TTSProvider, PiperTTS
from jarvis.voice.wake_word import WakeWordDetector, SimpleWakeWordDetector
from jarvis.voice.audio import AudioCapture, AudioPlayback


class VoicePipeline:
    """Complete voice interaction pipeline."""

    def __init__(self):
        self._settings = get_settings()
        self._stt: Optional[STTProvider] = None
        self._tts: Optional[TTSProvider] = None
        self._wake_word: Optional[WakeWordDetector] = None
        self._capture = AudioCapture()
        self._playback = AudioPlayback()
        self._running = False
        self._agent_callback: Optional[Callable[[str], Any]] = None
        self._wake_callback: Optional[Callable[[], Any]] = None
        self._busy = False

    def _initialize_providers(self) -> None:
        """Initialize STT and TTS providers."""
        try:
            self._stt = WhisperSTT()
        except Exception as e:
            logger.warning(f"Failed to initialize Whisper STT: {e}")

        try:
            self._tts = PiperTTS()
        except Exception as e:
            logger.warning(f"Failed to initialize Piper TTS: {e}")

        try:
            self._wake_word = WakeWordDetector()
        except Exception:
            self._wake_word = SimpleWakeWordDetector()

    async def start(self, agent_callback: Callable[[str], Any]) -> None:
        """Start the voice pipeline."""
        if self._running:
            return

        self._running = True
        self._agent_callback = agent_callback
        self._initialize_providers()

        if self._settings.voice.enabled and self._wake_word:
            await self._wake_word.start(self._on_wake_word)
            logger.info("Voice pipeline started with wake word")
        else:
            logger.info("Voice pipeline started (manual mode)")

    async def stop(self) -> None:
        """Stop the voice pipeline."""
        self._running = False

        if self._wake_word:
            await self._wake_word.stop()

        if self._capture.is_recording:
            await self._capture.stop_recording()

        if self._playback.is_playing:
            await self._playback.stop()

        logger.info("Voice pipeline stopped")

    async def _on_wake_word(self) -> None:
        """Handle wake word detection: listen, then run the utterance."""
        if self._busy:
            logger.debug("Wake word ignored - already handling an utterance")
            return

        self._busy = True
        try:
            logger.info("Wake word detected, listening...")
            if self._wake_callback:
                await self._maybe_await(self._wake_callback())

            text = await self.listen_once()
            if not text:
                logger.info("No speech captured after wake word")
                return

            await self.process_voice_input(text)
        except Exception as e:
            logger.error(f"Wake word handling failed: {e}")
        finally:
            self._busy = False

    @staticmethod
    async def _maybe_await(result: Any) -> Any:
        """Await a callback result when it is a coroutine."""
        if asyncio.iscoroutine(result):
            return await result
        return result

    def set_wake_callback(self, callback: Callable[[], Any]) -> None:
        """Set a callback fired when the wake word is detected (for UI state)."""
        self._wake_callback = callback

    async def listen_once(self) -> Optional[str]:
        """Listen for a single utterance and return transcribed text."""
        if not self._stt:
            logger.error("STT provider not initialized")
            return None

        try:
            audio_data = await self._capture.record_until_silence(
                max_duration=max(self._settings.voice.silence_timeout * 3, 10.0),
                silence_duration=min(self._settings.voice.silence_timeout, 2.0),
            )

            if not audio_data:
                return None

            text = await self._stt.transcribe(audio_data)

            if text:
                logger.info(f"Transcribed: {text}")
                return text

            return None

        except Exception as e:
            logger.error(f"Listen failed: {e}")
            return None

    async def process_voice_input(self, text: str) -> Optional[str]:
        """Process voice input through agent and return response."""
        if not self._agent_callback:
            logger.error("Agent callback not set")
            return None

        try:
            response = await self._maybe_await(self._agent_callback(text))

            # The agent callback is usually Agent.execute_task, which returns a
            # Task; speak its natural-language result, not its repr.
            spoken = getattr(response, "result", response)
            if spoken is not None and not isinstance(spoken, str):
                spoken = str(spoken)

            if spoken and self._settings.voice.enabled:
                await self.speak(spoken)

            return spoken

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            return None

    async def speak(self, text: str) -> None:
        """Convert text to speech and play."""
        if not self._tts:
            logger.error("TTS provider not initialized")
            return

        try:
            audio_data = await self._tts.synthesize(text)

            if audio_data:
                await self._playback.play(audio_data)

        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")

    async def continuous_listen(self) -> None:
        """Start continuous listening loop."""
        self._running = True

        while self._running:
            try:
                text = await self.listen_once()

                if text:
                    await self.process_voice_input(text)

                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Continuous listen error: {e}")
                await asyncio.sleep(1)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_listening(self) -> bool:
        return self._capture.is_recording

    @property
    def is_speaking(self) -> bool:
        return self._playback.is_playing


_voice_pipeline: Optional[VoicePipeline] = None


def get_voice_pipeline() -> VoicePipeline:
    """Get the global voice pipeline instance."""
    global _voice_pipeline
    if _voice_pipeline is None:
        _voice_pipeline = VoicePipeline()
    return _voice_pipeline
