<div align="center">

# 🤖 Jarvis

### A Cross-Platform, Voice-Driven Personal AI Assistant

*Hear. See. Understand. Control your computer — by voice, on any OS.*

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-yellow)](https://www.python.org/)

</div>

---

## Overview

**Jarvis** is a real-time AI assistant that runs locally on your machine and acts on your intent through natural conversation. It listens for a wake word, understands spoken commands in any language, sees what's on your screen, and carries out multi-step tasks — from opening apps and editing files to searching the web and messaging contacts.

It runs on **Windows, macOS, and Linux**, uses Google's **Gemini** models, and stores persistent memory so it gets to know your projects and preferences over time.

---

## Features

- 🎙️ **Real-time voice** — Low-latency, multilingual conversation with wake-word activation
- 🖥️ **System control** — Launch apps, manage files, change settings, run commands
- 🧩 **Autonomous tasks** — Plans and executes complex, multi-step goals on its own
- 👁️ **Screen awareness** — Captures and reasons about what's on your display
- 🧠 **Persistent memory** — Long-term recall backed by a ChromaDB vector store
- 🌐 **Web & research** — Web search, browser automation, weather, flights, YouTube transcripts
- 💬 **Telegram bridge** — Message and control the assistant remotely (optional)
- 🔌 **MCP support** — Extend capabilities with Model Context Protocol tools
- ⌨️ **Hybrid input** — Switch freely between voice and keyboard

---

## Requirements

| | |
|---|---|
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11 or 3.12 |
| **Microphone** | Required for voice interaction |
| **Gemini API key** | Free — from [Google AI Studio](https://aistudio.google.com/apikey) |

---

## Installation

```bash
# 1. Clone
git clone https://github.com/parhamje/JarvisAI.git
cd Jarvis

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate

# 3. Install dependencies + Playwright browsers
python setup.py

# 4. Configure your keys (see below), then run
python main.py
```

> **Note:** To keep the repo lightweight, some OS-specific packages aren't in `requirements.txt`. If you hit a `ModuleNotFoundError`, install the missing package with `pip install <name>`.

---

## Configuration

Create a file at **`config/api_keys.json`**:

```json
{
  "gemini_api_key": "your-gemini-api-key",
  "os_system": "windows",
  "telegram_api_id": "",
  "telegram_api_hash": "",
  "telegram_phone": ""
}
```

| Key | Required | Where to get it |
|---|:---:|---|
| `gemini_api_key` | ✅ | [Google AI Studio](https://aistudio.google.com/apikey) |
| `os_system` | ✅ | `windows`, `mac`, or `linux` |
| `telegram_api_id` | — | [my.telegram.org](https://my.telegram.org) → API development tools |
| `telegram_api_hash` | — | [my.telegram.org](https://my.telegram.org) |
| `telegram_phone` | — | Your number, with country code (e.g. `+1234567890`) |

> 🔒 **Security:** `config/api_keys.json` and the generated `jarvis.session` (your Telegram login) are git-ignored — **never commit them.** Telegram fields are optional; leave them blank to run without it.

---

## Project Structure

```
Jarvis/
├── main.py              # Application entry point
├── ui.py                # Adaptive PyQt6 interface
├── setup.py             # Installs requirements + Playwright browsers
├── config/              # API keys and OS configuration
├── core/                # System prompt and core engine
├── agent/               # Planner, executor, task queue, error handling
├── actions/             # Tools: browser, files, screen, web, Telegram, MCP, …
└── memory/              # Long-term + vector (ChromaDB) memory
```

---

## License

Released under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)** — personal and non-commercial use only.
