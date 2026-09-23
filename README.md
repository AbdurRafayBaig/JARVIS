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
jarvis/
├── core/           # Config, logging, database, exceptions
├── agent/          # Agent runtime, planner, tools
├── llm/            # LLM providers (OpenAI, Anthropic, Ollama)
├── tools/          # Computer, coding, browser, office tools
├── ui/             # Floating orb, side panel, command center
├── memory/         # Conversation, project, vector memory
├── security/       # Approval, permissions, audit
├── services/       # Startup, hotkeys, notifications
├── tests/          # Unit, integration, e2e tests
└── docs/           # Documentation
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

## Phased Development

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Foundation (config, logging, DB, agent core) | ✓ |
| 2 | Computer Control (apps, mouse, keyboard, windows) | 🔄 |
| 3 | Voice (wake word, STT, TTS) | ⏳ |
| 4 | Files + Terminal (fs, PowerShell, Python) | ⏳ |
| 5 | Coding Agent (workspace, tests, VS Code) | ⏳ |
| 6 | Browser + GitHub (Playwright, Git, GitHub API) | ⏳ |
| 7 | Vision (screen capture, UI understanding) | ⏳ |
| 8 | Memory (conversations, projects, retrieval) | ⏳ |
| 9 | Command Center (dashboard, timeline, metrics) | ⏳ |
| 10 | Polish (startup, animations, installer, docs) | ⏳ |

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

## Roadmap

- [ ] Phase 1: Foundation complete
- [ ] Phase 2: Computer control
- [ ] Phase 3: Voice integration
- [ ] Phase 4: Files & terminal
- [ ] Phase 5: Coding agent
- [ ] Phase 6: Browser & GitHub
- [ ] Phase 7: Screen vision
- [ ] Phase 8: Memory system
- [ ] Phase 9: Command Center
- [ ] Phase 10: Polish & release

---

**JARVIS** — Your personal AI control layer for Windows.