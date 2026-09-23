"""JARVIS - Voice Module Tests"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from jarvis.voice.audio import AudioCapture, AudioPlayback
from jarvis.voice.stt_provider import GoogleSTT, WhisperSTT
from jarvis.voice.tts_provider import PiperTTS, EdgeTTS
from jarvis.voice.wake_word import SimpleWakeWordDetector
from jarvis.voice.voice_pipeline import VoicePipeline, get_voice_pipeline


@pytest.mark.asyncio
async def test_audio_capture_initialization():
    capture = AudioCapture()
    assert capture.is_recording is False


@pytest.mark.asyncio
async def test_audio_playback_initialization():
    playback = AudioPlayback()
    assert playback.is_playing is False


@pytest.mark.asyncio
async def test_simple_wake_word_detector():
    detector = SimpleWakeWordDetector(wake_word="jarvis")
    assert detector.is_running is False

    mock_callback = AsyncMock()
    await detector.start(mock_callback)
    assert detector.is_running is True

    detected = detector.check_audio("Hello jarvis please open code")
    assert detected is True
    await asyncio.sleep(0.05)
    mock_callback.assert_called_once()

    await detector.stop()
    assert detector.is_running is False


@pytest.mark.asyncio
async def test_voice_pipeline_initialization():
    pipeline = VoicePipeline()
    assert pipeline.is_running is False
    assert pipeline.is_listening is False
    assert pipeline.is_speaking is False


@pytest.mark.asyncio
async def test_voice_pipeline_process_voice_input():
    pipeline = VoicePipeline()
    mock_agent_callback = AsyncMock(return_value="Opening Visual Studio Code now.")
    pipeline._agent_callback = mock_agent_callback
    
    with patch.object(pipeline, "speak", new_callable=AsyncMock) as mock_speak:
        response = await pipeline.process_voice_input("open vscode")
        assert response == "Opening Visual Studio Code now."
        mock_agent_callback.assert_called_once_with("open vscode")
