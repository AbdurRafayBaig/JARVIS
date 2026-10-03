"""Path helpers for tools.

Resolves the names people actually say ("desktop", "downloads/report.txt")
to real Windows paths. Known folders are asked of the shell rather than
assumed to sit under the home directory, because OneDrive commonly
redirects Desktop and Documents elsewhere.
"""

import ctypes
import os
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Optional

# Known folder GUIDs (KNOWNFOLDERID)
_KNOWN_FOLDER_IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
}

_ALIASES = {
    "desktop": "desktop",
    "documents": "documents",
    "document": "documents",
    "my documents": "documents",
    "docs": "documents",
    "downloads": "downloads",
    "download": "downloads",
    "pictures": "pictures",
    "picture": "pictures",
    "photos": "pictures",
    "images": "pictures",
    "music": "music",
    "songs": "music",
    "videos": "videos",
    "video": "videos",
    "movies": "videos",
}


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, text: str):
        super().__init__()
        u = uuid.UUID(text)
        self.Data1, self.Data2, self.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, byte in enumerate(u.bytes[8:]):
            self.Data4[i] = byte


def _shell_known_folder(name: str) -> Optional[Path]:
    """Ask the Windows shell where a known folder really is."""
    try:
        guid = _GUID(_KNOWN_FOLDER_IDS[name])
        out = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(out)
        )
        if result != 0 or not out.value:
            return None
        path = Path(out.value)
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    except Exception:
        return None


def known_folder(name: str) -> Optional[Path]:
    """Path of a named user folder such as 'desktop' or 'downloads'."""
    key = _ALIASES.get(name.strip().lower())
    if key is None:
        if name.strip().lower() in ("home", "user folder", "~"):
            return Path.home()
        return None

    return _shell_known_folder(key) or (Path.home() / key.capitalize())


def resolve_path(text: str, default_dir: Optional[Path] = None) -> Path:
    """Turn a spoken or typed location into a filesystem path.

    Accepts a known-folder name ("desktop"), a path beneath one
    ("downloads/report.txt"), "~", environment variables, or an ordinary
    path. A bare relative name is placed under ``default_dir`` when given.
    """
    raw = text.strip().strip('"').strip("'")
    if not raw:
        return default_dir or Path.cwd()

    # A real relative path wins over a folder nickname, so a project's own
    # "docs" or "music" directory is not mistaken for the user folder.
    if Path(raw).exists():
        return Path(raw)

    folder = known_folder(raw)
    if folder is not None:
        return folder

    normalized = raw.replace("\\", "/")
    head, _, rest = normalized.partition("/")
    folder = known_folder(head)
    if folder is not None and rest:
        return folder / rest

    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not path.is_absolute() and default_dir is not None:
        return default_dir / path
    return path


def is_known_folder_name(text: str) -> bool:
    """Whether text names one of the user folders."""
    return known_folder(text) is not None
