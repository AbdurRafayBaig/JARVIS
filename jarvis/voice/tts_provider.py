"""Text-to-Speech Provider

Provides audio synthesis. Piper gives the best quality but needs a voice
model on disk; Windows SAPI needs nothing at all, so it is the fallback that
makes JARVIS speak on a fresh install.

Every provider returns WAV bytes, which is what jarvis.voice.audio plays.
"""

import asyncio
import shutil
import tempfile
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
from loguru import logger

from jarvis.core.config import get_settings


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Optional[Path] = None) -> bytes:
        """Synthesize text to WAV audio."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass


class PiperTTS(TTSProvider):
    """TTS provider using piper-tts."""

    def __init__(self):
        self._settings = get_settings()
        # TTS_MODEL names the voice model (e.g. en_US-lessac-medium);
        # TTS_VOICE optionally overrides it.
        self._voice = self._settings.tts.voice or self._settings.tts.model
        self._model_path = None

    def _get_model_path(self) -> Optional[Path]:
        """Get the path to the piper voice model, if one is installed."""
        if self._model_path:
            return self._model_path

        if not self._voice:
            return None

        model_dir = Path(self._settings.get_data_dir()) / "tts_models"
        candidates = [
            model_dir / f"{self._voice}.onnx",
            model_dir / self._voice / f"{self._voice}.onnx",
            Path(self._voice),  # an absolute path given directly
        ]

        for candidate in candidates:
            if candidate.is_file():
                self._model_path = candidate
                return candidate

        return None

    async def synthesize(self, text: str, output_path: Optional[Path] = None) -> bytes:
        """Synthesize text to audio using piper-tts."""
        model_path = self._get_model_path()
        if not model_path:
            logger.debug(f"Piper voice model not found: {self._voice}")
            return b""

        if not shutil.which("piper"):
            logger.debug("piper executable not on PATH")
            return b""

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            cmd = [
                "piper",
                "--model", str(model_path),
                "--output_file", str(tmp_path),
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate(input=text.encode())

            if process.returncode != 0 or not tmp_path.exists():
                logger.error(f"Piper TTS failed: {stderr.decode(errors='replace')}")
                return b""

            audio_data = tmp_path.read_bytes()
            if output_path:
                output_path.write_bytes(audio_data)
            return audio_data

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return b""
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    async def health_check(self) -> bool:
        """Check if piper-tts and a voice model are both available."""
        return bool(shutil.which("piper")) and self._get_model_path() is not None


class SystemTTS(TTSProvider):
    """TTS provider using the Windows speech API (SAPI).

    Available on any Windows install with no model download, which makes it
    the dependable fallback when Piper has no voice model.
    """

    def __init__(self):
        self._settings = get_settings()
        self._voice = self._settings.tts.voice
        self._rate = self._speed_to_sapi_rate(self._settings.tts.speed)

    @staticmethod
    def _speed_to_sapi_rate(speed: float) -> int:
        """Map a 0.5-2.0 speed multiplier onto SAPI's -10..10 rate scale."""
        return max(-10, min(10, round((speed - 1.0) * 10)))

    def _synthesize_blocking(self, text: str) -> bytes:
        """Drive SAPI to a WAV file. Runs on a worker thread (COM is blocking)."""
        import win32com.client

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            voice = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")

            if self._voice:
                for candidate in voice.GetVoices():
                    if self._voice.lower() in candidate.GetDescription().lower():
                        voice.Voice = candidate
                        break

            voice.Rate = self._rate
            voice.Volume = int(max(0.0, min(1.0, self._settings.voice.volume)) * 100)

            stream.Open(str(tmp_path), 3)  # SSFMCreateForWrite
            voice.AudioOutputStream = stream
            voice.Speak(text)
            stream.Close()

            return tmp_path.read_bytes()

        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    async def synthesize(self, text: str, output_path: Optional[Path] = None) -> bytes:
        """Synthesize text using Windows SAPI."""
        if not text:
            return b""

        try:
            audio_data = await asyncio.get_running_loop().run_in_executor(
                None, self._synthesize_blocking, text
            )
            if output_path and audio_data:
                output_path.write_bytes(audio_data)
            return audio_data
        except Exception as e:
            logger.error(f"System TTS failed: {e}")
            return b""

    async def health_check(self) -> bool:
        """Check if SAPI is reachable."""
        try:
            import win32com.client

            win32com.client.Dispatch("SAPI.SpVoice")
            return True
        except Exception:
            return False


class EdgeTTS(TTSProvider):
    """TTS provider using edge-tts (Microsoft Edge voices).

    edge-tts returns MP3, which the WAV playback path cannot read, so the
    audio is converted with ffmpeg when it is available.
    """

    def __init__(self):
        self._settings = get_settings()
        self._voice = self._settings.tts.voice or "en-US-GuyNeural"

    async def synthesize(self, text: str, output_path: Optional[Path] = None) -> bytes:
        """Synthesize text using edge-tts."""
        mp3_path = None
        wav_path = None
        try:
            import edge_tts

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                mp3_path = Path(tmp.name)

            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(str(mp3_path))

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                logger.error("edge-tts produces MP3; ffmpeg is required to convert it to WAV")
                return b""

            wav_path = mp3_path.with_suffix(".wav")
            process = await asyncio.create_subprocess_exec(
                ffmpeg, "-y", "-i", str(mp3_path), "-ar", "16000", "-ac", "1", str(wav_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.communicate()

            if not wav_path.exists():
                return b""

            audio_data = wav_path.read_bytes()
            if output_path:
                output_path.write_bytes(audio_data)
            return audio_data

        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            return b""
        finally:
            for path in (mp3_path, wav_path):
                if path and path.exists():
                    path.unlink(missing_ok=True)

    async def health_check(self) -> bool:
        """Check if edge-tts is available."""
        try:
            import edge_tts  # noqa: F401

            return shutil.which("ffmpeg") is not None
        except ImportError:
            return False


_PROVIDERS = {
    "piper": PiperTTS,
    "system": SystemTTS,
    "sapi": SystemTTS,
    "edge": EdgeTTS,
    "edge_tts": EdgeTTS,
}


async def create_tts_provider() -> Optional[TTSProvider]:
    """Build the configured TTS provider, falling back to one that works.

    Piper sounds best but needs a downloaded voice model, so an install that
    has not fetched one still gets speech through Windows SAPI rather than
    silence.
    """
    settings = get_settings()
    configured = (settings.tts.provider or "piper").lower()

    order = [configured] + [name for name in ("piper", "system") if name != configured]

    for name in order:
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            logger.warning(f"Unknown TTS provider: {name}")
            continue

        try:
            provider = provider_cls()
            if await provider.health_check():
                if name != configured:
                    logger.warning(
                        f"TTS provider '{configured}' is unavailable; using '{name}' instead."
                    )
                else:
                    logger.info(f"TTS provider: {name}")
                return provider
        except Exception as e:
            logger.debug(f"TTS provider {name} unavailable: {e}")

    logger.error("No TTS provider is available; JARVIS will not speak.")
    return None
