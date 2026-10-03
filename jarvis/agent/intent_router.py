"""Intent Router

Turns everyday computer commands into tool steps without a language model.

"open chrome", "volume up 20", "make a folder called Work on the desktop",
"open notepad and type hello" -- these are common, unambiguous, and should
be instant and free. The router recognises them directly; anything it does
not fully understand is left for the LLM planner.

A goal is split into clauses ("... and ...", "... then ..."). The router
answers only when every clause is recognised, so a half-understood goal is
never half-executed.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from jarvis.agent.task import TaskStep
from jarvis.tools.paths import known_folder, resolve_path
from jarvis.tools.windows import APP_ALIASES, settings_uri

# Websites that can be opened by name.
SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "google drive": "https://drive.google.com",
    "google maps": "https://maps.google.com",
}

# Keyboard shortcuts that have a plain-language name.
SHORTCUTS = {
    "copy": ["ctrl", "c"],
    "paste": ["ctrl", "v"],
    "cut": ["ctrl", "x"],
    "undo": ["ctrl", "z"],
    "redo": ["ctrl", "y"],
    "select all": ["ctrl", "a"],
    "save": ["ctrl", "s"],
    "save it": ["ctrl", "s"],
    "save the file": ["ctrl", "s"],
    "new tab": ["ctrl", "t"],
    "close tab": ["ctrl", "w"],
    "close this tab": ["ctrl", "w"],
    "refresh": ["f5"],
    "reload": ["f5"],
    "switch window": ["alt", "tab"],
    "close this window": ["alt", "f4"],
    "close the window": ["alt", "f4"],
    "close current window": ["alt", "f4"],
    "open task view": ["win", "tab"],
    "open run": ["win", "r"],
}

CAPABILITIES = (
    "I can open and close apps, open Settings pages, files, folders and websites, "
    "search the web, create, move, copy, rename and delete files and folders, "
    "control volume, brightness and media, switch dark/light mode, take "
    "screenshots, manage windows, type and press keys, lock the computer, and "
    "tell you the time, battery and system status. Try: \"open chrome\", "
    "\"volume up\", \"make a folder called Work on the desktop\", or "
    "\"open notepad and type hello\"."
)

_POLITE_PREFIX = re.compile(
    r"^(?:(?:hey|ok|okay|hi|yo)\s+)?(?:jarvis[,\s]+)?"
    r"(?:(?:please|kindly|plz|zara)\s+)?"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:i\s+(?:want|need)\s+you\s+to\s+)?"
    r"(?:(?:please|kindly)\s+)?",
    re.IGNORECASE,
)
_POLITE_SUFFIX = re.compile(r"[\s,]*(?:please|plz|for me|thanks|thank you|now)?[\s.!?]*$", re.IGNORECASE)

_CLAUSE_SPLIT = re.compile(r"\s*(?:,?\s+and\s+then\s+|,?\s+then\s+|\s+and\s+|\s+phir\s+|\s+aur\s+|;\s*)", re.IGNORECASE)

# Clauses whose argument is free text and may itself contain "and".
_GREEDY_TOOLS = {"type_text", "web_search", "respond", "create_file"}

# Roman Urdu phrasings, rewritten to the English form the rules understand.
_URDU_REWRITES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(.+?)\s+(?:kholo|khol\s*do|khol\s*dein?|open\s+kar(?:o|\s*do|\s*dein?)|chala(?:o|\s*do))$", re.I), r"open \1"),
    (re.compile(r"^(.+?)\s+(?:band\s+kar(?:o|\s*do|\s*dein?)|close\s+kar(?:o|\s*do))$", re.I), r"close \1"),
    (re.compile(r"^(?:awaz|awaaz|volume)\s+(?:barha(?:o|\s*do)|tez\s+kar(?:o|\s*do)|zyada\s+kar(?:o|\s*do))$", re.I), "volume up"),
    (re.compile(r"^(?:awaz|awaaz|volume)\s+(?:kam\s+kar(?:o|\s*do)|ahista\s+kar(?:o|\s*do))$", re.I), "volume down"),
    (re.compile(r"^screenshot\s+(?:lo|le\s*lo|lelo)$", re.I), "take a screenshot"),
    (re.compile(r"^(?:time|waqt)\s+(?:kya\s+)?(?:hai|hua|ho\s+raha)(?:\s+hai)?$", re.I), "what time is it"),
    (re.compile(r"^(.+?)\s+(?:naam\s+ka\s+)?folder\s+bana(?:o|\s*do)$", re.I), r"create folder \1"),
    (re.compile(r"^(.+?)\s+(?:search|dhoondo|dhundo)\s+kar(?:o|\s*do)$", re.I), r"search for \1"),
]


def _clean(text: str) -> str:
    """Strip greetings, politeness and trailing punctuation from a clause."""
    text = text.strip()
    text = _POLITE_PREFIX.sub("", text, count=1)
    text = _POLITE_SUFFIX.sub("", text, count=1)
    return text.strip().strip('"').strip()


def _unquote(text: str) -> str:
    return text.strip().strip('"').strip("'").strip()


def _amount(text: str, default: int) -> int:
    match = re.search(r"(\d{1,3})", text)
    return max(0, min(100, int(match.group(1)))) if match else default


def _location(text: Optional[str]) -> Path:
    """Folder named in a command; the Desktop when none was given."""
    desktop = known_folder("desktop") or Path.home()
    if not text:
        return desktop
    cleaned = re.sub(r"^(?:my|the)\s+", "", text.strip(), flags=re.I)
    cleaned = re.sub(r"\s+folder$", "", cleaned, flags=re.I)
    return resolve_path(cleaned, default_dir=desktop)


def _step(description: str, tool: str, **args) -> TaskStep:
    return TaskStep(description=description, tool_name=tool, tool_args=args)


class IntentRouter:
    """Recognises direct computer commands."""

    def __init__(self):
        # Order matters: specific rules come before the generic "open X".
        self._rules: list[Callable[[str], Optional[list[TaskStep]]]] = [
            self._smalltalk,
            self._shortcut,
            self._settings,
            self._theme,
            self._volume,
            self._brightness,
            self._youtube,
            self._media,
            self._screenshot,
            self._power,
            self._windows,
            self._web_search,
            self._file_ops,
            self._typing,
            self._info,
            self._close,
            self._open,
        ]

    # -- public --------------------------------------------------------------

    def route(self, goal: str) -> Optional[list[TaskStep]]:
        """Steps for a goal, or None when any part of it is not understood."""
        goal = _clean(goal)
        if not goal:
            return None

        steps: list[TaskStep] = []
        clauses = [c for c in _CLAUSE_SPLIT.split(goal) if c and c.strip()]
        previous_text: Optional[str] = None
        previous_count = 0

        for clause in clauses:
            parsed = self._parse_clause(clause)

            if parsed is None and previous_text is not None and steps and \
                    steps[-1].tool_name in _GREEDY_TOOLS:
                # "type salt and pepper": the split cut free text in two.
                merged = f"{previous_text} and {clause}"
                reparsed = self._parse_clause(merged)
                if reparsed is not None:
                    del steps[len(steps) - previous_count:]
                    steps.extend(reparsed)
                    previous_text, previous_count = merged, len(reparsed)
                    continue

            if parsed is None:
                return None

            steps.extend(parsed)
            previous_text, previous_count = clause, len(parsed)

        return self._add_waits(steps) or None

    # -- internals -----------------------------------------------------------

    def _parse_clause(self, clause: str) -> Optional[list[TaskStep]]:
        clause = _clean(clause)
        if not clause:
            return None

        for pattern, replacement in _URDU_REWRITES:
            if pattern.match(clause):
                clause = pattern.sub(replacement, clause)
                break

        for rule in self._rules:
            steps = rule(clause)
            if steps:
                return steps
        return None

    @staticmethod
    def _add_waits(steps: list[TaskStep]) -> list[TaskStep]:
        """Pause after launching something, so input lands in the new window."""
        launchers = {"open_application", "open_path", "open_url", "open_settings"}
        needs_focus = {"type_text", "press_key", "hotkey"}
        out: list[TaskStep] = []
        for i, step in enumerate(steps):
            out.append(step)
            following = steps[i + 1] if i + 1 < len(steps) else None
            if step.tool_name in launchers and following and following.tool_name in needs_focus:
                out.append(_step("Wait for the window to open", "wait", seconds=2.0))
        return out

    # -- rules ---------------------------------------------------------------

    def _smalltalk(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if re.fullmatch(r"(hi|hello|hey|salam|assalam[ou] ?alaikum|aoa|good (morning|afternoon|evening))( jarvis)?", low):
            return [_step("Greet", "respond", message="Hello. What would you like me to do?")]
        if re.fullmatch(r"(who|what) are you|what('?s| is) your name", low):
            return [_step("Introduce", "respond", message="I'm JARVIS, your computer assistant. " + CAPABILITIES)]
        if re.fullmatch(r"(help|what can you do|what do you do|commands|kya kar sakte ho)", low):
            return [_step("Explain capabilities", "respond", message=CAPABILITIES)]
        if re.fullmatch(r"(thanks|thank you|shukriya|great|nice|good job)", low):
            return [_step("Acknowledge", "respond", message="You're welcome.")]
        return None

    def _shortcut(self, c: str) -> Optional[list[TaskStep]]:
        keys = SHORTCUTS.get(c.lower())
        if keys:
            if len(keys) == 1:
                return [_step(f"Press {keys[0]}", "press_key", key=keys[0])]
            return [_step(f"Press {'+'.join(keys)}", "hotkey", keys=keys)]
        return None

    def _settings(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(
            r"(?:open|show|go to|launch|take me to)?\s*(?:the\s+|my\s+|windows\s+)?(.*?)\s*settings?", c, re.I
        )
        if not match:
            return None
        page = match.group(1).strip()
        if page and settings_uri(page) is None:
            return None
        label = f"{page} settings" if page else "Settings"
        return [_step(f"Open {label}", "open_settings", page=page)]

    def _theme(self, c: str) -> Optional[list[TaskStep]]:
        match = re.search(r"\b(dark|light)\s+(?:mode|theme)\b", c, re.I)
        if not match:
            return None
        if re.search(r"\b(off|disable)\b", c, re.I):
            mode = "light" if match.group(1).lower() == "dark" else "dark"
        else:
            mode = match.group(1).lower()
        return [_step(f"Switch to {mode} mode", "set_theme", mode=mode)]

    def _volume(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if re.fullmatch(r"(?:un)?mute(?: (?:the )?(?:volume|sound|audio|computer|pc))?", low):
            return [_step("Toggle mute", "volume", action="mute")]
        if not re.search(r"\b(volume|sound|audio|louder|quieter)\b", low):
            return None
        if re.search(r"\b(mute|unmute)\b", low):
            return [_step("Toggle mute", "volume", action="mute")]
        if re.search(r"\b(set|to)\b.*\d|\d+\s*(%|percent)\s*$", low) and not re.search(r"\bby\b", low):
            level = _amount(low, 50)
            return [_step(f"Set volume to {level}%", "volume", action="set", amount=level)]
        if re.search(r"\b(up|increase|raise|louder|higher|more)\b", low):
            amount = _amount(low, 10)
            return [_step(f"Volume up {amount}%", "volume", action="up", amount=amount)]
        if re.search(r"\b(down|decrease|lower|reduce|quieter|less)\b", low):
            amount = _amount(low, 10)
            return [_step(f"Volume down {amount}%", "volume", action="down", amount=amount)]
        if re.search(r"\b(max|full)\b", low):
            return [_step("Set volume to 100%", "volume", action="set", amount=100)]
        return None

    def _brightness(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if "brightness" not in low and not re.search(r"\b(brighter|dimmer|dim the screen)\b", low):
            return None
        if re.search(r"\b(set|to)\b.*\d|\d+\s*(%|percent)\s*$", low) and not re.search(r"\bby\b", low):
            level = _amount(low, 50)
            return [_step(f"Set brightness to {level}%", "brightness", action="set", amount=level)]
        if re.search(r"\b(up|increase|raise|brighter|higher|more)\b", low):
            amount = _amount(low, 10)
            return [_step(f"Brightness up {amount}%", "brightness", action="up", amount=amount)]
        if re.search(r"\b(down|decrease|lower|reduce|dimmer|dim|less)\b", low):
            amount = _amount(low, 10)
            return [_step(f"Brightness down {amount}%", "brightness", action="down", amount=amount)]
        if re.search(r"\b(max|full)\b", low):
            return [_step("Set brightness to 100%", "brightness", action="set", amount=100)]
        return None

    def _youtube(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(r"(?:play|search|find|look up|open)\s+(.+?)\s+on\s+youtube", c, re.I) or \
            re.fullmatch(r"(?:search\s+)?youtube\s+(?:for\s+)?(.+)", c, re.I)
        if not match:
            return None
        query = _unquote(match.group(1))
        return [_step(f"Search YouTube for {query}", "web_search", query=query, site="youtube")]

    def _media(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if re.fullmatch(r"(pause|resume|play|play/pause|pause (the )?(music|song|video)|play (the )?music|resume (the )?(music|song|video))", low):
            return [_step("Play/pause media", "media_control", action="play_pause")]
        if re.fullmatch(r"(next|skip)( (the )?(song|track|video))?|next one", low):
            return [_step("Next track", "media_control", action="next")]
        if re.fullmatch(r"(previous|prev|last)( (song|track|video))?|go back a song", low):
            return [_step("Previous track", "media_control", action="previous")]
        if re.fullmatch(r"stop (the )?(music|song|video|playback)", low):
            return [_step("Stop media", "media_control", action="stop")]
        return None

    def _screenshot(self, c: str) -> Optional[list[TaskStep]]:
        if not re.search(r"\bscreen\s?shot\b|\bcapture (?:the |my )?screen\b", c, re.I):
            return None
        pictures = known_folder("pictures") or Path.home()
        name = f"Screenshot {datetime.now():%Y-%m-%d %H-%M-%S}.png"
        path = pictures / "Screenshots" / name
        return [_step("Take a screenshot", "take_screenshot", save_path=str(path))]

    def _power(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        machine = r"(?: (?:the |my |this )?(?:computer|pc|laptop|system|screen|windows))?"
        if re.fullmatch(r"cancel (?:the )?(?:shut ?down|restart|reboot)", low):
            return [_step("Cancel the pending shutdown", "power_action", action="cancel")]
        if re.fullmatch(r"lock" + machine, low):
            return [_step("Lock the computer", "lock_screen")]
        if re.fullmatch(r"(?:shut ?down|power off|turn off)" + machine, low):
            return [_step("Shut down the computer", "power_action", action="shutdown")]
        if re.fullmatch(r"(?:restart|reboot)" + machine, low):
            return [_step("Restart the computer", "power_action", action="restart")]
        if re.fullmatch(r"(?:sleep|go to sleep|put" + machine + r" to sleep|hibernate)" + machine, low):
            return [_step("Put the computer to sleep", "power_action", action="sleep")]
        if re.fullmatch(r"(?:sign|log) ?(?:out|off)", low):
            return [_step("Sign out", "power_action", action="sign_out")]
        return None

    def _windows(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if re.fullmatch(r"show (?:the |my )?desktop|minimi[sz]e (?:all|everything|all windows)|hide (?:all|everything)", low):
            return [_step("Show the desktop", "show_desktop")]
        if re.fullmatch(r"(?:list|show|what are)(?: me)?(?: the| my)?(?: open| all)? windows(?: open)?|which windows are open", low):
            return [_step("List open windows", "list_windows")]
        match = re.fullmatch(r"(minimi[sz]e|maximi[sz]e|restore)\s+(?:the\s+)?(.+?)(?:\s+window)?", c, re.I)
        if match:
            action = {"minimise": "minimize", "maximise": "maximize"}.get(
                match.group(1).lower(), match.group(1).lower()
            )
            title = _unquote(match.group(2))
            return [_step(f"{action.capitalize()} {title}", "window_action", title=title, action=action)]
        match = re.fullmatch(r"(?:switch to|focus(?: on)?|bring up|go to)\s+(?:the\s+)?(.+?)(?:\s+window)?", c, re.I)
        if match and not re.search(r"\.\w{2,}$", match.group(1)):
            title = _unquote(match.group(1))
            return [_step(f"Switch to {title}", "focus_window", title=title)]
        return None

    def _web_search(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(
            r"(?:google|search(?: the web| google| online| the internet)?(?: for)?|look up|web search(?: for)?)\s+(.+)",
            c, re.I,
        )
        if not match:
            return None
        query = _unquote(match.group(1))
        if re.match(r"(?:files?|folders?)\b", query, re.I):
            return None  # "search files ..." belongs to the file rules
        return [_step(f"Search the web for {query}", "web_search", query=query, site="google")]

    def _file_ops(self, c: str) -> Optional[list[TaskStep]]:
        where = r"(?:\s+(?:on|in|inside|at|under|to)\s+(?:the\s+|my\s+)?(.+?))?"

        # create folder
        match = re.fullmatch(
            r"(?:create|make|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:folder|directory)"
            r"(?:\s+(?:called|named))?\s+(.+?)" + where, c, re.I)
        if match:
            name = _unquote(match.group(1))
            path = _location(match.group(2)) / name
            return [_step(f"Create folder {name}", "create_directory", path=str(path))]

        # create file
        match = re.fullmatch(
            r"(?:create|make|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:text\s+)?(?:file|note|document)"
            r"(?:\s+(?:called|named))?\s+(.+?)"
            r"(?:\s+(?:on|in|inside|at)\s+(?:the\s+|my\s+)?(.+?))??"
            r"(?:\s+(?:with|containing|saying)\s+(?:the\s+)?(?:content|text|words)?\s*(.+))?", c, re.I)
        if match:
            name = _unquote(match.group(1))
            if "." not in name:
                name += ".txt"
            path = _location(match.group(2)) / name
            content = _unquote(match.group(3)) if match.group(3) else ""
            return [_step(f"Create file {name}", "create_file", path=str(path), content=content)]

        # rename
        match = re.fullmatch(
            r"rename\s+(?:the\s+)?(?:file\s+|folder\s+)?(.+?)"
            r"(?:\s+(?:on|in)\s+(?:the\s+|my\s+)?(.+?))?\s+(?:to|as)\s+(.+)", c, re.I)
        if match:
            source = _location(match.group(2)) / _unquote(match.group(1))
            new_name = _unquote(match.group(3))
            if source.suffix and "." not in new_name:
                new_name += source.suffix
            return [_step(f"Rename {source.name} to {new_name}", "move_path",
                          source=str(source), destination=str(source.parent / new_name))]

        # move / copy
        match = re.fullmatch(
            r"(move|copy)\s+(?:the\s+)?(?:file\s+|folder\s+)?(.+?)"
            r"(?:\s+from\s+(?:the\s+|my\s+)?(.+?))?\s+(?:to|into)\s+(?:the\s+|my\s+)?(.+)", c, re.I)
        if match:
            verb = match.group(1).lower()
            source = _location(match.group(3)) / _unquote(match.group(2))
            destination = _location(match.group(4))
            tool = "move_path" if verb == "move" else "copy_path"
            return [_step(f"{verb.capitalize()} {source.name} to {destination}", tool,
                          source=str(source), destination=str(destination))]

        # delete (to the Recycle Bin)
        match = re.fullmatch(
            r"(?:delete|remove|trash|recycle|erase)\s+(?:the\s+)?(?:file\s+|folder\s+)?(.+?)"
            r"(?:\s+(?:from|on|in)\s+(?:the\s+|my\s+)?(.+?))?", c, re.I)
        if match:
            target = _location(match.group(2)) / _unquote(match.group(1))
            return [_step(f"Send {target.name} to the Recycle Bin", "recycle_path", path=str(target))]

        # list a folder
        match = re.fullmatch(
            r"(?:what(?:'s| is)|show(?: me)?(?: what(?:'s| is))?|list)(?: the)?(?: files| contents| everything)?"
            r"\s+(?:in|on|of|inside)\s+(?:the\s+|my\s+)?(.+?)(?:\s+folder)?", c, re.I)
        if match and known_folder(match.group(1).strip()) is not None:
            folder = known_folder(match.group(1).strip())
            return [_step(f"List {folder.name}", "list_directory", path=str(folder))]

        # find files
        match = re.fullmatch(
            r"(?:find|locate|search(?: for)?)\s+(?:the\s+|a\s+|my\s+)?(?:files?|folders?)\s+"
            r"(?:named\s+|called\s+)?(.+?)(?:\s+(?:in|on|inside)\s+(?:the\s+|my\s+)?(.+?))?", c, re.I) or \
            re.fullmatch(
                r"(?:find|locate)\s+(?:the\s+|my\s+)?(.+?)(?:\s+(?:in|on|inside)\s+(?:the\s+|my\s+)?(.+?))?",
                c, re.I)
        if match:
            name = _unquote(match.group(1))
            root = _location(match.group(2)) if match.group(2) else Path.home()
            pattern = name if any(ch in name for ch in "*?") else f"*{name}*"
            return [_step(f"Find {name}", "search_files", pattern=pattern, root=str(root), max_results=20)]

        return None

    def _typing(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(r"type(?:\s+out)?\s+(.+)", c, re.I)
        if match:
            text = _unquote(match.group(1))
            return [_step(f"Type '{text}'", "type_text", text=text)]

        # "write" is ambiguous: `write "hello"` means type it, but "write a
        # report about sales" asks for something to be composed, which needs
        # the language model. Only literal-looking text is typed.
        match = re.fullmatch(r"write(?:\s+out|\s+down)?\s+(.+)", c, re.I)
        if match:
            raw = match.group(1).strip()
            quoted = raw[:1] in "\"'" and raw[-1:] in "\"'"
            composing = re.match(r"(?:a|an|the|some|me|us|my|our|about|up)\b", raw, re.I)
            if quoted or (not composing and len(raw.split()) <= 6):
                text = _unquote(raw)
                return [_step(f"Type '{text}'", "type_text", text=text)]

        match = re.fullmatch(r"(?:press|hit|tap)\s+(?:the\s+)?(.+?)(?:\s+key)?", c, re.I)
        if match:
            raw = match.group(1).lower().replace(" plus ", "+").replace(" and ", "+")
            keys = [k.strip() for k in re.split(r"\s*\+\s*|\s+", raw) if k.strip()]
            keys = [{"control": "ctrl", "windows": "win", "escape": "esc", "return": "enter"}.get(k, k) for k in keys]
            if len(keys) == 1:
                return [_step(f"Press {keys[0]}", "press_key", key=keys[0])]
            if 1 < len(keys) <= 4:
                return [_step(f"Press {'+'.join(keys)}", "hotkey", keys=keys)]
        return None

    def _info(self, c: str) -> Optional[list[TaskStep]]:
        low = c.lower()
        if re.search(r"\bwhat(?:'s| is)? (?:the )?(?:current )?(?:time|date|day)\b|\bwhat time\b|\bwhat day\b|^(?:time|date)$|\btell me the (?:time|date)\b|\btoday'?s date\b", low):
            return [_step("Get the current time", "get_current_time")]
        if "battery" in low or re.search(r"\b(charge|charging)\b", low):
            return [_step("Check the battery", "battery_status")]
        if "clipboard" in low and re.search(r"\b(what|read|show|get)\b", low):
            return [_step("Read the clipboard", "get_clipboard")]
        if re.search(r"\b(system|computer|pc|laptop)\b.*\b(info|information|status|specs?|health|usage)\b|\b(cpu|ram|memory|disk|storage) (usage|status|space)\b|how much (ram|memory|disk|storage)", low):
            return [_step("Get system information", "get_system_info")]
        if re.search(r"\b(list|show|what|which)\b.*\b(process|processes|running apps|running programs)\b", low):
            return [_step("List running processes", "list_processes", limit=10, sort_by="memory")]
        if re.fullmatch(r"git status", low):
            return [_step("Run git status", "git_status")]
        if re.fullmatch(r"(?:run|execute)(?: the| my)? (?:unit )?tests?|(?:run )?pytest", low):
            return [_step("Run the tests", "run_tests")]
        if re.fullmatch(r"(?:list|show)(?: me)?(?: my| the)? projects|which projects.*", low):
            return [_step("List remembered projects", "list_projects")]
        return None

    def _close(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(r"(?:close|quit|exit|kill|end)\s+(?:the\s+)?(.+?)(?:\s+(?:app|application|program|window))?", c, re.I)
        if not match:
            return None
        name = _unquote(match.group(1))
        if len(name.split()) > 4 or name.lower() in ("it", "this", "that", "everything", "all"):
            return None
        return [_step(f"Close {name}", "close_application", app_name=name)]

    def _open(self, c: str) -> Optional[list[TaskStep]]:
        match = re.fullmatch(
            r"(?:open|launch|start|run|show|go to|visit|browse to|browse)(?:\s+up)?\s+(?:the\s+|my\s+)?(.+?)"
            r"(?:\s+(?:app|application|program))?", c, re.I)
        if not match:
            return None
        target = _unquote(match.group(1))
        low = target.lower()

        # "file X on the desktop" / "X folder" / "X in downloads"
        located = re.fullmatch(
            r"(?:the\s+)?(?:file\s+|folder\s+)?(.+?)\s+(?:on|in|from|inside)\s+(?:the\s+|my\s+)?(.+?)(?:\s+folder)?",
            target, re.I)
        if located and known_folder(located.group(2).strip()) is not None:
            path = known_folder(located.group(2).strip()) / _unquote(located.group(1))
            return [_step(f"Open {path.name}", "open_path", path=str(path))]

        folder_name = re.sub(r"\s+folder$", "", low)
        if known_folder(folder_name) is not None:
            return [_step(f"Open {folder_name}", "open_path", path=str(known_folder(folder_name)))]

        if low in APP_ALIASES:
            return [_step(f"Open {target}", "open_application", app_name=target)]

        site = re.sub(r"\s+(?:website|site)$", "", low)
        if site in SITES:
            return [_step(f"Open {site}", "open_url", url=SITES[site])]

        if re.fullmatch(r"(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?", target) and not Path(target).exists():
            return [_step(f"Open {target}", "open_url", url=target)]

        if re.search(r"[\\/]|^[a-zA-Z]:|\.\w{1,5}$", target):
            path = resolve_path(target, default_dir=known_folder("desktop"))
            return [_step(f"Open {path.name}", "open_path", path=str(path))]

        # An app we have no alias for: let the launcher look it up, as long as
        # this still reads like a name and not a sentence.
        if len(target.split()) <= 3 and c.lower().split()[0] in ("open", "launch", "start", "run"):
            return [_step(f"Open {target}", "open_application", app_name=target)]

        return None


_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get the shared intent router."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
