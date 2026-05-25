# 🤖 Kevin — Personal Arabic AI Assistant

> **Public repo, private access.** Anyone can read the code, but only the owner with the password can run it.

Personal AI assistant with Arabic voice recognition, dual AI providers (Claude + Gemini), Arabic text-to-speech, and an Excel-powered knowledge base.

---

## 🇪🇬 بالعربي

كيفن مساعد ذكي شخصي بيتكلم عربي مصري، بيفهم صوتك وبيرد عليك بصوت، وعنده قاعدة معرفة من ملفات Excel.

### المميزات
- 🎙️ التعرف على الكلام بالعربية (Whisper)
- 🧠 ذكاء اصطناعي مزدوج: Claude + Gemini
- 🔊 رد صوتي بالعربية (Edge-TTS)
- 📚 قاعدة معرفة من ملفات Excel
- 🔒 محمي بكلمة مرور — مفيش حد يقدر يشغّله غير المالك
- 💬 ذاكرة محادثة دائمة

### التشغيل بسرعة
```powershell
# 1. تنصيب المتطلبات
pip install -r requirements.txt

# 2. تجهيز ملف .env
copy env.example .env
# عدّل .env وحط فيه مفاتيحك وكلمة المرور

# 3. تشغيل كيفن
python kevin.py
```

افتح المتصفح على `http://localhost:8000` وادخل كلمة المرور.

---

## 🇬🇧 English

### Features
- 🎙️ Arabic speech recognition (Whisper)
- 🧠 Dual AI: Claude + Gemini (switchable)
- 🔊 Arabic text-to-speech (Edge-TTS)
- 📚 Excel-powered knowledge base
- 🔒 Password-gated — public code, private access
- 💬 Persistent conversation history
- 📱 Responsive UI works on phone and laptop

### Tech Stack
- **Backend:** FastAPI + uvicorn
- **STT:** OpenAI Whisper (local, no API key)
- **TTS:** Microsoft Edge TTS (free)
- **LLM:** Anthropic Claude / Google Gemini
- **Auth:** HMAC-signed cookies, password-gated

---

## 🛠️ Setup

### 1. Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (required by Whisper)
- A Gemini API key (free): https://aistudio.google.com/apikey
- Optionally, an Anthropic API key: https://console.anthropic.com

### 2. Install
```bash
git clone https://github.com/YOUR_USERNAME/kevin-assistant.git
cd kevin-assistant
pip install -r requirements.txt
```

### 3. Configure
```bash
cp env.example .env       # macOS / Linux
copy env.example .env     # Windows
```

Edit `.env` and set:
```env
GEMINI_API_KEY=your_real_gemini_key
ANTHROPIC_API_KEY=your_real_anthropic_key   # optional
KEVIN_PASSWORD=pick-a-strong-password-here
KEVIN_SESSION_SECRET=any-random-32-byte-string
```

Generate a strong password and session secret:
```bash
python -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#$%^&*') for _ in range(24)))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Add Your Knowledge Base (Optional)
Drop any `.xlsx` files into `upload/data/`. Kevin will read all sheets and use them to answer your questions.

### 5. Run
```bash
python kevin.py
```

Then open `http://localhost:8000`. You'll be redirected to a login screen — enter your password and you're in. Sessions last 30 days.

---

## 🔒 Security Notes

- **Never commit `.env`** — it's in `.gitignore`. If you accidentally push a real key, rotate it immediately.
- Login uses HMAC-SHA256 signed cookies — no plaintext password ever crosses the wire after the initial POST.
- Passwords are compared with `hmac.compare_digest` (constant-time).
- If you deploy this beyond `localhost`, set `secure=True` on the cookie and put TLS in front.
- The Excel knowledge base may contain sensitive data — review what you commit.

---

## 📁 Project Layout

```
kevin-assistant/
├── kevin.py                  # Main app (FastAPI + UI + auth + AI routing)
├── requirements.txt          # Python dependencies
├── env.example               # Template for .env
├── .env                      # Your secrets (gitignored)
├── .gitignore
├── README.md
├── LICENSE
└── upload/
    ├── data/                 # Your Excel knowledge base lives here
    │   └── *.xlsx
    └── archive/              # Backups and old versions (gitignored if you want)
```

---

## 🤝 License

MIT — see [LICENSE](LICENSE).

The code is public, but the access is private. Fork it, learn from it, build your own Kevin. Just set your own password.
