# JARVIS — Personal AI Computer Agent

> A Tony Stark–style personal AI agent for Windows that can understand voice/text commands, control the computer, use applications, browse the web, write code, and autonomously complete multi-step tasks.

## Vision

JARVIS is not a chatbot — it's a **personal AI operating layer** for your computer. You give it goals, not commands:

> *"Jarvis, create a Python API project, open it in VS Code, implement authentication, run the tests, fix any errors, create a GitHub repository, push the code, and open the repository."*

JARVIS plans, executes, verifies, recovers from failures, and reports the result.

## Features

| Category | Capabilities |
|----------|-------------|
| **Voice Control** | Wake word "Jarvis", STT → Agent → TTS, interruptible, push-to-talk |
| **Text/Privacy Mode** | Floating panel, `Ctrl+Space` toggle, silent/hidden modes |
| **Computer Control** | Mouse, keyboard, windows, apps, clipboard, screenshots |
| **Screen Vision** | Screenshot → Vision model → UI understanding → precise actions |
| **Agent Brain** | Goal → Plan → Tool Select → Execute → Verify → Fix → Report |
| **Coding Agent** | Create projects, write code, run tests, fix errors, VS Code, Git/GitHub |
| **Browser/GitHub** | Navigate, interact, create repos, push code, verify remotely |
| **Office Automation** | Word, Excel, PDF, filesystem operations |
| **Skill System** | Modular plugins: Voice, Vision, Windows, Browser, VS Code, GitHub, Terminal, Files, Office, Web Research, Memory |
| **Long-Term Memory** | Projects, preferences, conversations, task history |
| **Self-Verification** | Every action verified; auto-retry with diagnosis on failure |
| **Permission System** | 🟢 Safe (auto), 🟡 Sensitive (ask), 🔴 Dangerous (explicit confirm) |
| **Futuristic UI** | Floating orb + side panel + Command Center dashboard |
| **Activity Timeline** | History with clickable task details |
| **Personality** | Professional/Jarvis/Minimal modes |

## Architecture

```
run.py (single entry point)
├── Interaction Layer (Voice/Text/Hotkeys/UI)
├── Agent Runtime (Intent → Plan → Execute → Verify → Recover)
├── Tool Registry (Computer, Dev, Web tools — validated schemas)
├── Memory (Conversation/Project/Vector/DB)
└── Security (Approval/Audit/Sandbox)
```

## Quick Start

### Prerequisites
- Windows 11
- Python 3.11+

### Installation

```powershell
# Clone and setup
git clone <repo>
cd jarvis
.\setup.ps1

# Edit .env with your API keys
notepad .env

# Run diagnostics
python run.py --diagnose

# Run JARVIS
python run.py
```

### CLI Mode
```bash
python run.py --cli
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# LLM Provider (openai, anthropic, ollama)
LLM_PROVIDER=openai
LLM_API_KEY=your_key_here
LLM_MODEL=gpt-4o

# Voice
VOICE_ENABLED=true
JARVIS_WAKE_WORD=jarvis

# GitHub
GITHUB_TOKEN=your_token
GITHUB_USERNAME=your_username

# Paths
JARVIS_PROJECTS_DIR=C:\Projects
```

## Usage Examples

### Voice Commands
- "Jarvis, open VS Code"
- "Jarvis, create a Python project called MyAPI"
- "Jarvis, what's wrong with this error on my screen?"

### Text Commands (Ctrl+Space)
- "Create a GitHub repository for this project and push the code"
- "Build a FastAPI backend with authentication, test it, and fix any errors"
- "Open Word and create a project report"

### Complex Goals
- "Prepare this project for GitHub" — JARVIS inspects, plans, and executes the full workflow

## Development

### Project Structure
```
run.py              # Entry point (GUI, --cli, --no-gui, --diagnose)
jarvis/
├── core/           # Config, logging, database, models, exceptions
├── agent/          # Agent runtime, planners, tool base classes, step context
├── llm/            # LLM providers (OpenAI, Azure, Anthropic, Ollama)
├── tools/          # Tool implementations registered with the agent
├── browser/        # Playwright engine, navigation, scraping
├── desktop/        # Screen capture and vision analysis
├── voice/          # Audio I/O, STT, TTS, wake word, pipeline
├── memory/         # Conversation, project, vector and task-history stores
├── security/       # Approval, audit log, sandbox
├── services/       # Global hotkeys, startup entry, notifications
├── integrations/   # GitHub API client
└── ui/             # Orb, side panel, Command Center, Settings
tests/              # Unit and integration tests
docs/               # Documentation
```

### Running Tests
```bash
# Unit tests
pytest tests/unit -v

# With coverage
pytest tests/unit --cov=jarvis

# All tests
pytest
```

### Code Quality
```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy jarvis
```

## Status

| Area | State |
|------|-------|
| Agent runtime (plan, execute, recover, report) | Working; covered by tests |
| Tools (81: system, desktop, Windows control, files, shell, coding, git, browser, GitHub, vision, memory) | Working |
| Direct commands without an LLM (apps, settings, files, volume, windows, ...) | Working; verified live |
| Memory (conversation history, projects, preferences, task history) | Working, stored in SQLite |
| Audit log and approval prompts | Working |
| GUI (orb, side panel, tray, Command Center, Settings) | Working |
| Global hotkeys | Working (Windows) |
| Speech output | Working out of the box via Windows SAPI; Piper optional |
| Speech input | Push-to-talk works; hands-free wake word needs a Picovoice key |
| Office automation (Word/Excel/PDF tools) | Not implemented yet |
| Installer | Not implemented yet |

Open-ended goals ("build an API and push it to GitHub") need a working LLM.
Without one, direct commands (below) still work and anything else is answered
with a plain "I need my language model for that".

## Direct commands (no LLM needed)

Everyday computer commands are recognised locally and run instantly, with no
API call. They work even when the language model is unavailable.

| Say or type | What happens |
|-------------|--------------|
| `open chrome` / `notepad kholo` / `close calculator` | Start or close an app |
| `open display settings`, `wifi settings`, `bluetooth settings` | Open that Settings page |
| `open downloads`, `open report.pdf in documents` | Open a folder or file |
| `open youtube`, `open github.com`, `search for ...`, `play ... on youtube` | Websites and web search |
| `create a folder called Work on the desktop` | New folder (Desktop when no place is named) |
| `create a file called todo with text buy milk` | New text file |
| `rename a.txt on desktop to b`, `move b.txt from desktop to documents`, `copy ...` | Rename, move, copy |
| `delete b.txt from documents` | Sends it to the Recycle Bin |
| `what's in my downloads`, `find resume in documents` | List and find files |
| `volume up`, `volume down by 20`, `set volume to 40`, `mute` | Volume |
| `brightness up`, `set brightness to 70` | Brightness (laptop displays) |
| `pause`, `next song`, `previous song` | Media keys |
| `dark mode`, `light mode` | Windows colour mode |
| `minimize notepad`, `switch to chrome`, `show desktop` | Windows |
| `type hello`, `press enter`, `press ctrl+shift+esc`, `copy`, `paste` | Keyboard |
| `take a screenshot` | Saved to Pictures\Screenshots |
| `lock the computer`, `shut down`, `restart`, `sleep`, `cancel shutdown` | Power (shutdown asks first, waits 30s) |
| `what time is it`, `battery`, `system info` | Status |

Commands chain with "and" / "then": `open notepad and type hello`. Changing or
removing files, closing apps and power actions ask for approval first. Anything
the router does not fully understand is passed to the language model instead.

## Hotkeys

| Keys | Action |
|------|--------|
| `Ctrl+Space` | Show / hide the panel |
| `Ctrl+Shift+J` | Push-to-talk: listen for one spoken request |
| `Ctrl+Shift+C` | Open the Command Center |
| `Ctrl+Shift+X` | Cancel the running task |

## Troubleshooting

- **`python run.py --diagnose`** checks every subsystem. `[WARN]` marks an
  optional feature that is not configured; `[FAIL]` is a real problem.
- **Answers like "I can't plan ... without my language model"**: the LLM call
  failed. Check `LLM_API_KEY` and your provider's billing, or run locally with
  `LLM_PROVIDER=ollama` and `LLM_MODEL=<a model you have pulled>`.
- **No hands-free wake word**: set `PV_ACCESS_KEY` (free at console.picovoice.ai).
- Logs are in `%APPDATA%\Jarvis\logs\jarvis.log`.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Security

- **Local-first**: Sensitive operations happen locally
- **No hardcoded secrets**: Uses `.env` with `.env.example` template
- **Permission system**: Three-tier approval for risky actions
- **Audit logging**: Every meaningful action recorded
- **Sandbox mode**: Optional isolated execution

## License

MIT License — see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

---

**JARVIS** — Your personal AI control layer for Windows.