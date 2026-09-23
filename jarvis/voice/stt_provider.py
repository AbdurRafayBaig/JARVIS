"""Speech-to-Text Provider

Provides audio transcription using faster-whisper.
"""

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

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio data to text."""
        self._load_model()

        try:
            audio_file = io.BytesIO(audio_data)
            segments, info = self._model.transcribe(
                audio_file,
                language=language,
                beam_size=5,
            )

            text = " ".join([segment.text for segment in segments])
            logger.debug(f"Transcribed: {text[:100]}...")
            return text.strip()

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

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribe audio using Google Speech Recognition."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()

            audio = sr.AudioData(audio_data, sample_rate=16000)
            text = recognizer.recognize_google(audio, language=language or "en-US")
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
