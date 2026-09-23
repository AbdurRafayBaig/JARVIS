"""JARVIS - Phase 8 UI Integration Tests"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from jarvis.run import JarvisApplication


@pytest.mark.asyncio
async def test_jarvis_application_init():
    args = MagicMock()
    args.cli = False
    app = JarvisApplication(args)
    assert app.running is False


@pytest.mark.asyncio
async def test_jarvis_application_gui_callbacks():
    args = MagicMock()
    args.cli = False
    app = JarvisApplication(args)

    with patch("jarvis.voice.voice_pipeline.get_voice_pipeline") as mock_vp:
        mock_pipe = MagicMock()
        mock_pipe.is_running = False
        mock_vp.return_value = mock_pipe

        app._toggle_voice()
        mock_vp.assert_called_once()

    with patch("jarvis.ui.settings_dialog.SettingsDialog") as mock_sd:
        app._open_settings()
        mock_sd.assert_called_once()

    with patch("jarvis.ui.command_center.CommandCenterDashboard") as mock_cc:
        mock_win = MagicMock()
        mock_cc.return_value = mock_win
        app._open_command_center()
        mock_cc.assert_called_once()
        mock_win.show.assert_called_once()
