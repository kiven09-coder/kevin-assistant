# 🤖 Kiven — Personal Arabic AI Assistant

> Jarvis-style multimodal assistant. Public code, private access — only the owner with the password can run it.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://www.python.org/)
[![Arabic](https://img.shields.io/badge/Language-عربي_مصري-success.svg)](#)
[![Architecture: HuggingGPT-style](https://img.shields.io/badge/Architecture-HuggingGPT--style-purple.svg)](#)

---

## 🇪🇬 بالعربي

كيفن (Kiven) مساعد شخصي ذكي بيتكلم عربي مصري، بيفهم صوتك ويرد عليك بصوت، بيبحث في النت، بيولّد صور، بيفتكر معلوماتك، وبيستخدم أكتر من موديل AI ذكي زي Jarvis.

### ⚡ المميزات

- 🎙️ **صوت عربي**: Whisper للفهم + Edge-TTS للرد (لهجة مصرية)
- 🧠 **عقلين AI**: Claude (ذكي + tool use) + Gemini (سريع + مجاني)
- 🔧 **9 أدوات احترافية**:
  - 🌐 `web_search` — أخبار وبحث (DuckDuckGo)
  - 🎨 `generate_image` — توليد صور (Pollinations/Flux)
  - 🧠 `remember` / `recall` / `forget` — ذاكرة دائمة
  - 🕒 `get_current_time` — الوقت والتاريخ
  - 🌤️ `get_weather` — الطقس (Open-Meteo)
  - 🧮 `calculate` — حسابات دقيقة
- 📚 **قاعدة معرفة** من ملفات Excel
- 🔒 **محمي بـ password** — HMAC-signed sessions
- 💾 **ذاكرة دائمة** بين الجلسات
- 📱 **واجهة web** ترد على اللابتوب والموبايل

---

## 🇬🇧 English

Kiven is a Jarvis-style personal AI assistant that speaks Egyptian Arabic, listens through your microphone, replies with voice, searches the web, generates images, remembers your facts, and orchestrates multiple AI models — all behind a password gate.

### Architecture

```
                    ┌─────────────┐
                    │   Browser   │  (web UI, Arabic RTL, password gate)
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   FastAPI   │  (auth, routing, sessions)
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      ┌─────────┐    ┌──────────┐   ┌──────────┐
      │ Whisper │    │  Edge    │   │   LLM    │
      │  (STT)  │    │  -TTS    │   │ Router   │
      └─────────┘    └──────────┘   └────┬─────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                        ┌──────────┐         ┌──────────┐
                        │  Claude  │         │  Gemini  │
                        │ (tools)  │         │(fallback)│
                        └────┬─────┘         └──────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ TOOLS_REGISTRY  │  (HuggingGPT-style)
                    └────────┬────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
 ┌──────────┐         ┌──────────┐         ┌──────────┐
 │  search  │         │   image  │         │  memory  │
 │   (DDG)  │         │ (Flux)   │         │  (JSON)  │
 └──────────┘         └──────────┘         └──────────┘
       ▼                     ▼                     ▼
 ┌──────────┐         ┌──────────┐         ┌──────────┐
 │   time   │         │  weather │         │   calc   │
 │ (ZoneInfo)│        │(OpenMeteo)│        │  (AST)   │
 └──────────┘         └──────────┘         └──────────┘
```

The LLM is the **controller**. The `TOOLS_REGISTRY` is the **model catalog**. Same architecture as Microsoft's HuggingGPT/JARVIS — just lighter, faster, Arabic-first.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A Gemini API key (FREE): https://aistudio.google.com/apikey
- Optionally, an Anthropic Claude API key: https://console.anthropic.com

### Install & Run

```bash
git clone https://github.com/kiven09-coder/kevin-assistant.git
cd kevin-assistant
pip install -r requirements.txt
cp env.example .env       # macOS / Linux
copy env.example .env     # Windows
# Edit .env: fill keys + set a strong KIVEN/KEVIN_PASSWORD
python kevin.py
```

Then open `http://localhost:8000`, enter your password, and start talking (text or voice).

> **No FFmpeg system install needed.** Kiven auto-bootstraps a portable ffmpeg via `imageio-ffmpeg` on first run.

### Configuration (`.env`)

```env
GEMINI_API_KEY=AIzaSy...        # free at aistudio.google.com
ANTHROPIC_API_KEY=sk-ant-...    # optional, console.anthropic.com
KEVIN_PASSWORD=YourStrongPass    # change this!
KEVIN_SESSION_SECRET=...         # python -c "import secrets; print(secrets.token_urlsafe(32))"
HOST=0.0.0.0
PORT=8000
```

### Knowledge Base

Drop `.xlsx` files into `upload/data/`. Kiven reads them on startup and uses them in answers.

---

## 🔧 Tools Reference

| Tool | What it does | Backend |
|------|--------------|---------|
| `web_search` | News + general search | DuckDuckGo (`ddgs`) — no key |
| `generate_image` | Text-to-image | Pollinations.ai / Flux — no key |
| `remember(fact)` | Store a fact permanently | Local JSON store |
| `recall(query)` | Search remembered facts | Local JSON store |
| `forget(id)` | Delete a remembered fact | Local JSON store |
| `get_current_time` | Now + day/date | Python `zoneinfo` |
| `get_weather(city)` | Current weather | Open-Meteo — no key |
| `calculate(expr)` | Safe math eval | AST whitelist |

Adding a tool is one entry in `TOOLS_REGISTRY` — the LLM picks it up automatically next reload.

---

## 🔒 Security

- `.env` is gitignored — never commit secrets
- Password compared with `hmac.compare_digest` (constant-time)
- Sessions are HMAC-SHA256 signed cookies (30-day TTL, httponly, samesite=lax)
- Memory file (`kiven_memory.json`) is gitignored
- Markdown in chat is HTML-escaped first, only safe tags injected (no XSS)

If you deploy beyond localhost: terminate TLS, set `secure=True` on the cookie, rotate password.

---

## 🗺️ Roadmap

### Done
- [x] Arabic voice (STT + TTS)
- [x] Claude tool-use loop
- [x] Web search
- [x] Image generation
- [x] Persistent memory
- [x] Time / Weather / Calculator
- [x] Excel knowledge base
- [x] Password-gated web UI
- [x] Markdown rendering with image embeds

### Next phases
- [ ] Microsoft Graph (Outlook for work email)
- [ ] Google OAuth (Gmail personal)
- [ ] OneDrive / Google Drive
- [ ] PDF analysis
- [ ] Image understanding (vision)
- [ ] Local LLM option (Ollama + Qwen 2.5)
- [ ] Wake word ("يا كيفن") — desktop only

---

## 🤝 License

MIT — see [LICENSE](LICENSE).

Public code, private runtime. Fork it, learn from it, build your own. Just set your own password and keys.
