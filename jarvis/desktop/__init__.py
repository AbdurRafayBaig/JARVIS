"""JARVIS Desktop

Provides screen capture, vision analysis, and UI element detection.
"""

from jarvis.desktop.vision import VisionCapture
from jarvis.desktop.screen_analyzer import ScreenAnalyzer
from jarvis.desktop.element_detector import ElementDetector

__all__ = [
    "VisionCapture",
    "ScreenAnalyzer",
    "ElementDetector",
]
