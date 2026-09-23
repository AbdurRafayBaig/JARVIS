"""Speech-to-Text Provider

Provides audio transcription using faster-whisper.
"""

import asyncio
import io
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings


class STTProvider(ABC):
    """Abstract base class for STT providers."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio data to text."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass


class WhisperSTT(STTProvider):
    """STT provider using faster-whisper."""

    def __init__(self):
        self._settings = get_settings()
        self._model = None
        self._model_name = self._settings.stt.model

    def _load_model(self):
        """Load the whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self._model_name,
                    device="cpu",
                    compute_type="int8",
                )
                logger.info(f"Loaded Whisper model: {self._model_name}")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

    def _transcribe_blocking(self, audio_data: bytes, language: Optional[str]) -> str:
        """Run Whisper inference. Called on a worker thread."""
        self._load_model()

        audio_file = io.BytesIO(audio_data)
        segments, _info = self._model.transcribe(
            audio_file,
            language=language or self._settings.stt.language or None,
            beam_size=5,
        )
        return " ".join(segment.text for segment in segments).strip()

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio data to text."""
        if not audio_data:
            return ""

        try:
            # Whisper inference is synchronous and CPU-bound; keep it off the
            # loop that drives the agent and the UI.
            text = await asyncio.get_running_loop().run_in_executor(
                None, self._transcribe_blocking, audio_data, language
            )
            if text:
                logger.debug(f"Transcribed: {text[:100]}...")
            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    async def health_check(self) -> bool:
        """Check if Whisper is available."""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False


class GoogleSTT(STTProvider):
    """STT provider using Google Speech Recognition (free tier)."""

    def _transcribe_blocking(self, audio_data: bytes, language: Optional[str]) -> str:
        """Call Google Speech Recognition. Runs on a worker thread."""
        import speech_recognition as sr

        # The pipeline hands over a WAV container; read it back for the
        # raw frames and sample width AudioData expects.
        with sr.AudioFile(io.BytesIO(audio_data)) as source:
            audio = sr.Recognizer().record(source)

        return sr.Recognizer().recognize_google(audio, language=language or "en-US")

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio using Google Speech Recognition."""
        if not audio_data:
            return ""

        try:
            text = await asyncio.get_running_loop().run_in_executor(
                None, self._transcribe_blocking, audio_data, language
            )
            logger.debug(f"Google STT: {text[:100]}...")
            return text

        except Exception as e:
            logger.error(f"Google STT failed: {e}")
            return ""

    async def health_check(self) -> bool:
        """Check if Google STT is available."""
        try:
            import speech_recognition
            return True
        except ImportError:
            return False


class OpenAISTT(STTProvider):
    """STT provider using the OpenAI transcription API."""

    def __init__(self):
        self._settings = get_settings()
        self._api_key = self._settings.stt.api_key or self._settings.llm.api_key
        self._model = self._settings.stt.model or "whisper-1"

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio via the OpenAI API."""
        if not audio_data:
            return ""

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            response = await client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                language=language or self._settings.stt.language or None,
            )
            return (response.text or "").strip()

        except Exception as e:
            logger.error(f"OpenAI STT failed: {e}")
            return ""

    async def health_check(self) -> bool:
        """Check if the OpenAI transcription API is usable."""
        try:
            import openai  # noqa: F401

            return bool(self._api_key)
        except ImportError:
            return False


_PROVIDERS = {
    "whisper_cpp": WhisperSTT,
    "whisper": WhisperSTT,
    "faster_whisper": WhisperSTT,
    "openai": OpenAISTT,
    "google": GoogleSTT,
}


async def create_stt_provider() -> Optional[STTProvider]:
    """Build the configured STT provider, falling back to one that works."""
    settings = get_settings()
    configured = (settings.stt.provider or "whisper_cpp").lower()

    order = [configured] + [n for n in ("whisper_cpp", "openai") if n != configured]

    for name in order:
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            logger.warning(f"Unknown STT provider: {name}")
            continue

        try:
            provider = provider_cls()
            if await provider.health_check():
                if name != configured:
                    logger.warning(
                        f"STT provider '{configured}' is unavailable; using '{name}' instead."
                    )
                else:
                    logger.info(f"STT provider: {name}")
                return provider
        except Exception as e:
            logger.debug(f"STT provider {name} unavailable: {e}")

    logger.error("No STT provider is available; JARVIS cannot hear.")
    return None
