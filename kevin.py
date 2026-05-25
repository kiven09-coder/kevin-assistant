"""
🤖 Kevin - Arabic AI Assistant
==================================
Personal AI assistant for Amr with:
- 🎙️ Arabic voice recognition (Whisper)
- 🧠 Dual AI: Claude + Gemini
- 🔊 Arabic voice responses (Edge-TTS)
- 📚 Knowledge base from Excel files
- 💬 Persistent memory

Renamed from "Jarvis" to "Kevin" per user preference.
"""

import os
import asyncio
import tempfile
import json
import socket
import glob
import hmac
import hashlib
import secrets
import base64
from datetime import datetime
from pathlib import Path

# ============================================
# Load .env file
# ============================================
def load_env_file():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and not os.getenv(key):
                    os.environ[key] = value
        print("✅ تم تحميل ملف .env")

load_env_file()

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response, Cookie, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from anthropic import Anthropic
import google.generativeai as genai

import whisper
import edge_tts

# ============================================
# CONFIGURATION
# ============================================
ASSISTANT_NAME = "Kevin"
ASSISTANT_NAME_AR = "كيفن"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
KEVIN_PASSWORD = os.getenv("KEVIN_PASSWORD", "").strip()
KEVIN_SESSION_SECRET = os.getenv("KEVIN_SESSION_SECRET", "").strip()

if not KEVIN_PASSWORD:
    print("⚠️ تحذير: KEVIN_PASSWORD غير محدد في .env - Kevin لن يقبل الدخول!")
if not KEVIN_SESSION_SECRET:
    print("⚠️ تحذير: KEVIN_SESSION_SECRET غير محدد - سيتم استخدام مفتاح مؤقت")
    KEVIN_SESSION_SECRET = secrets.token_urlsafe(32)

SESSION_COOKIE_NAME = "kevin_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

CLAUDE_MODEL = "claude-sonnet-4-5"
GEMINI_MODEL = "gemini-2.0-flash-exp"
WHISPER_MODEL = "medium"

ARABIC_VOICES = {
    "salma_egypt": "ar-EG-SalmaNeural",
    "shakir_egypt": "ar-EG-ShakirNeural",
    "zariyah_saudi": "ar-SA-ZariyahNeural",
    "hamed_saudi": "ar-SA-HamedNeural",
}
DEFAULT_VOICE = "shakir_egypt"  # Male voice for Kevin

HOST = "0.0.0.0"
PORT = 8000

CONVERSATION_FILE = Path("conversation_history.json")
KNOWLEDGE_BASE_FILE = Path("knowledge_base.json")

# ============================================
# KNOWLEDGE BASE - Load Excel files
# ============================================
def load_knowledge_base():
    """Load all Excel files in current directory as knowledge base."""
    kb = {"files": [], "summary": ""}

    # Check if cached version exists
    if KNOWLEDGE_BASE_FILE.exists():
        try:
            cached = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
            print(f"✅ تم تحميل قاعدة المعرفة المخزنة ({len(cached.get('files', []))} ملف)")
            return cached
        except Exception:
            pass

    search_dirs = ["upload/data", "data", "."]
    excel_files = []
    for d in search_dirs:
        excel_files.extend(glob.glob(os.path.join(d, "*.xlsx")))
        excel_files.extend(glob.glob(os.path.join(d, "*.xls")))
    seen = set()
    unique_files = []
    for f in excel_files:
        key = os.path.basename(f).lower()
        if key not in seen:
            seen.add(key)
            unique_files.append(f)
    excel_files = unique_files

    if not excel_files:
        print("ℹ️ مفيش ملفات Excel في الفولدر (شوف upload/data/)")
        return kb

    print(f"📚 جاري قراءة {len(excel_files)} ملف Excel...")

    try:
        from openpyxl import load_workbook
    except ImportError:
        print("⚠️ openpyxl مش متنصبة. شغل: pip install openpyxl")
        return kb

    for excel_file in excel_files:
        try:
            print(f"   📄 قراءة: {excel_file}")
            wb = load_workbook(excel_file, data_only=True)
            file_data = {
                "filename": excel_file,
                "sheets": []
            }

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = []
                for row in ws.iter_rows(values_only=True, max_row=200):  # Limit to 200 rows per sheet
                    if any(cell is not None and str(cell).strip() for cell in row):
                        rows.append([str(c) if c is not None else "" for c in row])

                file_data["sheets"].append({
                    "name": sheet_name,
                    "row_count": len(rows),
                    "rows": rows[:50]  # Keep only first 50 rows for context
                })
            kb["files"].append(file_data)
        except Exception as e:
            print(f"   ⚠️ خطأ في {excel_file}: {e}")

    # Build text summary for AI context
    summary_parts = [f"📚 قاعدة المعرفة المتاحة (من {len(kb['files'])} ملف Excel):\n"]
    for f in kb["files"]:
        summary_parts.append(f"\n📄 الملف: {f['filename']}")
        for sheet in f["sheets"]:
            summary_parts.append(f"  📋 الشيت: {sheet['name']} ({sheet['row_count']} صف)")
            if sheet["rows"]:
                # Add header + first 3 sample rows
                summary_parts.append(f"     الأعمدة: {' | '.join(sheet['rows'][0][:8])}")
                for row in sheet["rows"][1:4]:
                    summary_parts.append(f"     - {' | '.join(row[:5])}")

    kb["summary"] = "\n".join(summary_parts)

    # Cache for next time
    try:
        KNOWLEDGE_BASE_FILE.write_text(
            json.dumps(kb, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

    print(f"✅ تم تحميل {len(kb['files'])} ملف")
    return kb

knowledge_base = load_knowledge_base()

SYSTEM_PROMPT = f"""أنت {ASSISTANT_NAME_AR} ({ASSISTANT_NAME})، مساعد ذكي شخصي لعمرو.

عن عمرو:
- يعمل في مجال IT في شركة Egyptian Cement
- يستخدم SAP، Microsoft 365، SharePoint
- يتكلم العربية المصرية والإنجليزية

تعليمات مهمة:
- ترد دائماً بالعربية المصرية الفصحى الواضحة
- ردود قصيرة ومباشرة (2-3 أسطر كحد أقصى ما لم يُطلب التفصيل)
- ودود ومحترف
- لو السؤال بالإنجليزية، رد بالعربية ما لم يُطلب الإنجليزية صراحة
- اسمك {ASSISTANT_NAME_AR} وليس Jarvis

{knowledge_base.get('summary', '')}

استخدم قاعدة المعرفة دي للإجابة على أسئلة عمرو عن Claude Skills والـ Plugins والـ APIs المتاحة."""

# ============================================
# EMBEDDED HTML UI
# ============================================
HTML_UI = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>{ASSISTANT_NAME_AR} | المساعد الذكي</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
        :root {{
            --bg-deep: #050d1a; --bg-card: #0e1a2e; --accent: #00d4ff;
            --accent-glow: rgba(0, 212, 255, 0.4); --accent-warm: #ff6b35;
            --text: #e8f4ff; --text-dim: #7a9cc6; --success: #00ff88;
        }}
        body {{ font-family: 'Cairo', sans-serif; background: var(--bg-deep); color: var(--text); min-height: 100vh; overflow: hidden; }}
        body::before {{ content: ''; position: fixed; inset: 0; background: radial-gradient(circle at 20% 30%, rgba(0,212,255,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(255,107,53,0.05) 0%, transparent 50%); pointer-events: none; z-index: 0; }}
        .container {{ position: relative; z-index: 1; height: 100vh; display: flex; flex-direction: column; max-width: 600px; margin: 0 auto; }}
        .header {{ padding: 16px 20px; background: rgba(14,26,46,0.8); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(0,212,255,0.2); display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
        .logo-section {{ display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }}
        .arc-reactor {{ width: 40px; height: 40px; border-radius: 50%; background: radial-gradient(circle, var(--accent) 0%, rgba(0,212,255,0.2) 70%); box-shadow: 0 0 20px var(--accent-glow), inset 0 0 10px rgba(255,255,255,0.3); animation: pulse 3s ease-in-out infinite; position: relative; flex-shrink: 0; }}
        .arc-reactor::after {{ content: ''; position: absolute; inset: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 8px white; }}
        @keyframes pulse {{ 0%,100% {{ box-shadow: 0 0 20px var(--accent-glow), inset 0 0 10px rgba(255,255,255,0.3); }} 50% {{ box-shadow: 0 0 30px var(--accent-glow), 0 0 50px rgba(0,212,255,0.2); }} }}
        .title h1 {{ font-size: 18px; font-weight: 700; }}
        .title .subtitle {{ font-size: 11px; color: var(--text-dim); display: flex; align-items: center; gap: 6px; }}
        .status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 8px var(--success); animation: blink 2s infinite; flex-shrink: 0; }}
        @keyframes blink {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}

        /* Controls bar - moved to TOP, replaces old provider-bar and header-actions */
        .controls-bar {{ display: flex; gap: 6px; align-items: center; flex-shrink: 0; }}
        .provider-btn {{ padding: 8px 12px; border-radius: 10px; background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.15); color: var(--text-dim); font-family: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }}
        .provider-btn.active {{ background: rgba(0,212,255,0.15); border-color: var(--accent); color: var(--accent); box-shadow: 0 0 12px rgba(0,212,255,0.2); }}
        .provider-btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
        .icon-btn {{ width: 36px; height: 36px; border-radius: 10px; background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.2); color: var(--accent); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; }}

        .chat-area {{ flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }}
        .message {{ max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; word-wrap: break-word; }}
        .message.user {{ align-self: flex-start; background: linear-gradient(135deg, #00d4ff 0%, #0088cc 100%); color: white; border-bottom-right-radius: 4px; box-shadow: 0 4px 12px rgba(0,212,255,0.2); }}
        .message.bot {{ align-self: flex-end; background: linear-gradient(135deg, #1a2e4e 0%, #0e1a2e 100%); color: var(--text); border: 1px solid rgba(0,212,255,0.15); border-bottom-left-radius: 4px; white-space: pre-wrap; }}
        .welcome {{ text-align: center; padding: 40px 20px; color: var(--text-dim); }}
        .welcome h2 {{ color: var(--accent); font-size: 22px; margin-bottom: 12px; }}
        .welcome p {{ font-size: 14px; line-height: 1.8; }}
        .typing {{ align-self: flex-end; display: flex; gap: 5px; padding: 14px 18px; background: linear-gradient(135deg, #1a2e4e 0%, #0e1a2e 100%); border-radius: 18px; border: 1px solid rgba(0,212,255,0.15); }}
        .typing-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--accent); animation: typing 1.4s infinite; }}
        .typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
        .typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
        @keyframes typing {{ 0%,60%,100% {{ transform: translateY(0); opacity: 0.5; }} 30% {{ transform: translateY(-8px); opacity: 1; }} }}
        .input-area {{ padding: 14px 16px 20px; background: rgba(14,26,46,0.95); border-top: 1px solid rgba(0,212,255,0.2); }}
        .input-row {{ display: flex; gap: 8px; align-items: flex-end; }}
        .text-input {{ flex: 1; padding: 12px 16px; background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.2); border-radius: 22px; color: var(--text); font-family: inherit; font-size: 15px; outline: none; resize: none; max-height: 100px; min-height: 44px; }}
        .text-input:focus {{ border-color: var(--accent); }}
        .send-btn, .mic-btn {{ width: 44px; height: 44px; border-radius: 50%; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }}
        .send-btn {{ background: linear-gradient(135deg, #00d4ff 0%, #0088cc 100%); color: white; box-shadow: 0 4px 12px rgba(0,212,255,0.3); }}
        .mic-btn {{ background: rgba(255,107,53,0.15); border: 2px solid var(--accent-warm); color: var(--accent-warm); }}
        .mic-btn.recording {{ background: var(--accent-warm); color: white; box-shadow: 0 0 20px rgba(255,107,53,0.6); animation: recordPulse 1s infinite; }}
        @keyframes recordPulse {{ 0%,100% {{ box-shadow: 0 0 20px rgba(255,107,53,0.6); }} 50% {{ box-shadow: 0 0 30px rgba(255,107,53,0.9); }} }}

        /* TOAST - top-left corner, doesn't cover anything */
        .toast {{ position: fixed; top: 12px; left: 12px; max-width: 280px; padding: 10px 14px; background: var(--bg-card); border: 1px solid var(--accent); border-radius: 10px; color: var(--text); font-size: 13px; transform: translateX(calc(-100% - 20px)); transition: transform 0.3s; z-index: 9999; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
        .toast.show {{ transform: translateX(0); }}
        .toast.error {{ border-color: var(--accent-warm); }}

        .kb-badge {{ font-size: 10px; padding: 2px 6px; border-radius: 6px; background: rgba(0,255,136,0.15); color: var(--success); border: 1px solid rgba(0,255,136,0.3); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-section">
                <div class="arc-reactor"></div>
                <div class="title">
                    <h1>{ASSISTANT_NAME_AR}</h1>
                    <div class="subtitle">
                        <span class="status-dot"></span>
                        <span id="status-text">جاهز للخدمة</span>
                        <span class="kb-badge" id="kb-badge" style="display:none">📚 KB</span>
                    </div>
                </div>
            </div>
            <div class="controls-bar">
                <button class="provider-btn active" id="btn-claude" onclick="switchProvider('claude')">🧠 Claude</button>
                <button class="provider-btn" id="btn-gemini" onclick="switchProvider('gemini')">✨ Gemini</button>
                <button class="icon-btn" onclick="clearChat()" title="مسح">🗑️</button>
                <button class="icon-btn" onclick="doLogout()" title="خروج">🚪</button>
            </div>
        </div>
        <div class="chat-area" id="chat-area">
            <div class="welcome">
                <h2>أهلاً يا عمرو! 👋</h2>
                <p>أنا {ASSISTANT_NAME_AR}، مساعدك الشخصي.<br>اسألني عن أي Claude skill, plugin, أو API<br>اكتب أو اضغط 🎤 وكلّمني بالعربي</p>
            </div>
        </div>
        <div class="input-area">
            <div class="input-row">
                <button class="mic-btn" id="mic-btn" onclick="toggleRecording()">🎤</button>
                <textarea class="text-input" id="text-input" placeholder="اكتب رسالتك..." rows="1" onkeydown="handleKey(event)"></textarea>
                <button class="send-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        const API_BASE = window.location.origin;
        let currentProvider = 'gemini';
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let conversationStarted = false;
        let recordingStartTime = 0;
        let recordingTimer = null;

        window.addEventListener('load', async () => {{
            await checkStatus();
            const input = document.getElementById('text-input');
            input.addEventListener('input', () => {{ input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 100) + 'px'; }});
        }});

        async function checkStatus() {{
            try {{
                const res = await fetch(`${{API_BASE}}/api/status`);
                if (res.status === 401) {{ window.location.href = '/login'; return; }}
                const data = await res.json();
                if (!data.claude_available) document.getElementById('btn-claude').disabled = true;
                if (!data.gemini_available) document.getElementById('btn-gemini').disabled = true;
                if (!data.claude_available && data.gemini_available) switchProvider('gemini');
                else if (data.claude_available && !data.gemini_available) switchProvider('claude');
                if (data.knowledge_base_loaded > 0) {{
                    const badge = document.getElementById('kb-badge');
                    badge.style.display = 'inline-block';
                    badge.textContent = `📚 ${{data.knowledge_base_loaded}} ملف`;
                }}
            }} catch (err) {{
                showToast('❌ خطأ في الاتصال', true);
            }}
        }}

        function switchProvider(provider) {{
            if (document.getElementById(`btn-${{provider}}`).disabled) {{
                showToast(`${{provider}} غير متاح`, true);
                return;
            }}
            currentProvider = provider;
            document.querySelectorAll('.provider-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(`btn-${{provider}}`).classList.add('active');
            showToast(`✅ ${{provider}}`);
        }}

        function handleKey(event) {{
            if (event.key === 'Enter' && !event.shiftKey) {{ event.preventDefault(); sendMessage(); }}
        }}

        async function sendMessage() {{
            const input = document.getElementById('text-input');
            const message = input.value.trim();
            if (!message) return;
            input.value = '';
            input.style.height = 'auto';
            if (!conversationStarted) {{ document.querySelector('.welcome')?.remove(); conversationStarted = true; }}
            addMessage('user', message);
            const typing = showTyping();
            try {{
                const res = await fetch(`${{API_BASE}}/api/chat`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{message, provider: currentProvider}})
                }});
                typing.remove();
                if (res.status === 401) {{ window.location.href = '/login'; return; }}
                if (!res.ok) {{ const err = await res.json(); throw new Error(err.detail || 'خطأ'); }}
                const data = await res.json();
                addMessage('bot', data.response);
                speakText(data.response);
            }} catch (err) {{
                typing.remove();
                addMessage('bot', `❌ خطأ: ${{err.message}}`);
            }}
        }}

        function addMessage(type, text) {{
            const chat = document.getElementById('chat-area');
            const msg = document.createElement('div');
            msg.className = `message ${{type}}`;
            msg.textContent = text;
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        }}

        function showTyping() {{
            const chat = document.getElementById('chat-area');
            const typing = document.createElement('div');
            typing.className = 'typing';
            typing.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
            chat.appendChild(typing);
            chat.scrollTop = chat.scrollHeight;
            return typing;
        }}

        async function speakText(text) {{
            try {{
                const cleanText = text.replace(/[*_`#\\[\\]]/g, '');  // Remove markdown
                const res = await fetch(`${{API_BASE}}/api/speak`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{text: cleanText.substring(0, 500), voice: 'shakir_egypt'}})
                }});
                if (!res.ok) return;
                const blob = await res.blob();
                const audio = new Audio(URL.createObjectURL(blob));
                audio.play();
            }} catch (err) {{ console.error('TTS error:', err); }}
        }}

        async function toggleRecording() {{
            if (isRecording) stopRecording();
            else await startRecording();
        }}

        async function startRecording() {{
            try {{
                const stream = await navigator.mediaDevices.getUserMedia({{
                    audio: {{
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 44100
                    }}
                }});

                // Pick best supported MIME type
                let mimeType = 'audio/webm;codecs=opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {{
                    mimeType = 'audio/webm';
                    if (!MediaRecorder.isTypeSupported(mimeType)) {{
                        mimeType = 'audio/mp4';
                        if (!MediaRecorder.isTypeSupported(mimeType)) {{
                            mimeType = '';  // Browser default
                        }}
                    }}
                }}

                mediaRecorder = mimeType ? new MediaRecorder(stream, {{mimeType}}) : new MediaRecorder(stream);
                audioChunks = [];
                recordingStartTime = Date.now();

                mediaRecorder.ondataavailable = (e) => {{
                    if (e.data && e.data.size > 0) audioChunks.push(e.data);
                }};

                mediaRecorder.onstop = async () => {{
                    const duration = (Date.now() - recordingStartTime) / 1000;
                    const blob = new Blob(audioChunks, {{type: mediaRecorder.mimeType || 'audio/webm'}});

                    stream.getTracks().forEach(t => t.stop());

                    if (duration < 1.5) {{
                        showToast(`⚠️ تسجيل قصير (${{duration.toFixed(1)}}s)`, true);
                        document.getElementById('status-text').textContent = 'جاهز للخدمة';
                        return;
                    }}

                    if (blob.size < 2000) {{
                        showToast(`⚠️ تسجيل فارغ (${{blob.size}}b)`, true);
                        document.getElementById('status-text').textContent = 'جاهز للخدمة';
                        return;
                    }}

                    await transcribeAndSend(blob);
                }};

                mediaRecorder.start(100);  // Collect data every 100ms
                isRecording = true;
                document.getElementById('mic-btn').classList.add('recording');
                startRecordingTimer();
            }} catch (err) {{
                showToast('❌ مفيش صلاحية للميكروفون', true);
                console.error('Mic error:', err);
            }}
        }}

        function startRecordingTimer() {{
            const statusEl = document.getElementById('status-text');
            recordingTimer = setInterval(() => {{
                if (!isRecording) {{ clearInterval(recordingTimer); return; }}
                const elapsed = ((Date.now() - recordingStartTime) / 1000).toFixed(1);
                statusEl.textContent = `🔴 ${{elapsed}}s`;
            }}, 100);
        }}

        function stopRecording() {{
            if (mediaRecorder && isRecording) {{
                mediaRecorder.stop();
                isRecording = false;
                if (recordingTimer) clearInterval(recordingTimer);
                document.getElementById('mic-btn').classList.remove('recording');
                document.getElementById('status-text').textContent = 'جاري المعالجة...';
            }}
        }}

        async function transcribeAndSend(blob) {{
            const formData = new FormData();
            const ext = blob.type.includes('mp4') ? '.mp4' : '.webm';
            formData.append('audio', blob, `recording${{ext}}`);

            try {{
                const res = await fetch(`${{API_BASE}}/api/transcribe`, {{ method: 'POST', body: formData }});
                document.getElementById('status-text').textContent = 'جاهز للخدمة';
                if (!res.ok) {{
                    const err = await res.json();
                    throw new Error(err.detail || 'فشل التحويل');
                }}
                const data = await res.json();
                if (data.text && data.text.length > 1) {{
                    document.getElementById('text-input').value = data.text;
                    await sendMessage();
                }} else {{
                    showToast('⚠️ مسمعتش حاجة', true);
                }}
            }} catch (err) {{
                document.getElementById('status-text').textContent = 'جاهز للخدمة';
                showToast(`❌ ${{err.message}}`, true);
            }}
        }}

        async function doLogout() {{
            if (!confirm('تسجيل خروج؟')) return;
            try {{
                await fetch(`${{API_BASE}}/api/logout`, {{method: 'POST'}});
            }} catch (err) {{}}
            window.location.href = '/login';
        }}

        async function clearChat() {{
            if (!confirm('متأكد؟')) return;
            try {{
                await fetch(`${{API_BASE}}/api/clear_history`, {{method: 'POST'}});
                document.getElementById('chat-area').innerHTML = '<div class="welcome"><h2>اتمسحت ✨</h2><p>ابدأ من جديد</p></div>';
                conversationStarted = false;
                showToast('✅ تم المسح');
            }} catch (err) {{ showToast('❌ خطأ', true); }}
        }}

        function showToast(msg, isError = false) {{
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.toggle('error', isError);
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2200);
        }}
    </script>
</body>
</html>"""

# ============================================
# LOGIN PAGE HTML
# ============================================
LOGIN_HTML = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔒 {ASSISTANT_NAME_AR} | تسجيل الدخول</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --bg-deep: #050d1a; --bg-card: #0e1a2e; --accent: #00d4ff;
            --accent-glow: rgba(0, 212, 255, 0.4); --accent-warm: #ff6b35;
            --text: #e8f4ff; --text-dim: #7a9cc6; --danger: #ff3860;
        }}
        body {{
            font-family: 'Cairo', sans-serif; background: var(--bg-deep);
            color: var(--text); min-height: 100vh; display: flex;
            align-items: center; justify-content: center; padding: 20px;
        }}
        body::before {{
            content: ''; position: fixed; inset: 0;
            background: radial-gradient(circle at 20% 30%, rgba(0,212,255,0.08) 0%, transparent 50%),
                        radial-gradient(circle at 80% 70%, rgba(255,107,53,0.05) 0%, transparent 50%);
            pointer-events: none; z-index: 0;
        }}
        .login-card {{
            position: relative; z-index: 1; max-width: 420px; width: 100%;
            background: rgba(14,26,46,0.95); backdrop-filter: blur(20px);
            border: 1px solid rgba(0,212,255,0.3); border-radius: 24px;
            padding: 40px 32px; box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 60px rgba(0,212,255,0.1);
        }}
        .arc-reactor {{
            width: 80px; height: 80px; margin: 0 auto 20px; border-radius: 50%;
            background: radial-gradient(circle, var(--accent) 0%, rgba(0,212,255,0.2) 70%);
            box-shadow: 0 0 40px var(--accent-glow), inset 0 0 20px rgba(255,255,255,0.3);
            animation: pulse 3s ease-in-out infinite; position: relative;
        }}
        .arc-reactor::after {{
            content: ''; position: absolute; inset: 18px; border-radius: 50%;
            background: var(--accent); box-shadow: 0 0 12px white;
        }}
        @keyframes pulse {{
            0%,100% {{ box-shadow: 0 0 40px var(--accent-glow), inset 0 0 20px rgba(255,255,255,0.3); }}
            50% {{ box-shadow: 0 0 60px var(--accent-glow), 0 0 100px rgba(0,212,255,0.2); }}
        }}
        h1 {{ text-align: center; font-size: 26px; margin-bottom: 4px; }}
        .subtitle {{ text-align: center; color: var(--text-dim); font-size: 14px; margin-bottom: 32px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 8px; }}
        input[type="password"] {{
            width: 100%; padding: 14px 16px; background: rgba(0,212,255,0.05);
            border: 1px solid rgba(0,212,255,0.2); border-radius: 12px;
            color: var(--text); font-family: inherit; font-size: 16px;
            outline: none; transition: all 0.2s; direction: ltr;
        }}
        input[type="password"]:focus {{
            border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,212,255,0.15);
        }}
        button {{
            width: 100%; padding: 14px; background: linear-gradient(135deg, #00d4ff 0%, #0088cc 100%);
            color: white; border: none; border-radius: 12px; font-family: inherit;
            font-size: 16px; font-weight: 700; cursor: pointer;
            box-shadow: 0 4px 16px rgba(0,212,255,0.3); transition: transform 0.1s;
        }}
        button:hover {{ transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0,212,255,0.4); }}
        button:active {{ transform: translateY(0); }}
        button:disabled {{ opacity: 0.6; cursor: not-allowed; }}
        .error-msg {{
            display: none; margin-top: 16px; padding: 12px;
            background: rgba(255,56,96,0.1); border: 1px solid var(--danger);
            border-radius: 10px; color: var(--danger); font-size: 14px; text-align: center;
        }}
        .error-msg.show {{ display: block; }}
        .hint {{ margin-top: 24px; text-align: center; font-size: 12px; color: var(--text-dim); }}
    </style>
</head>
<body>
    <div class="login-card">
        <div class="arc-reactor"></div>
        <h1>{ASSISTANT_NAME_AR}</h1>
        <div class="subtitle">المساعد الشخصي - مطلوب كلمة المرور</div>
        <form id="login-form" onsubmit="return doLogin(event)">
            <div class="form-group">
                <label for="password">كلمة المرور</label>
                <input type="password" id="password" name="password" required autofocus
                       placeholder="••••••••••••" autocomplete="current-password">
            </div>
            <button type="submit" id="submit-btn">دخول 🔓</button>
            <div class="error-msg" id="error-msg"></div>
        </form>
        <div class="hint">🔒 الوصول مقصور على المالك</div>
    </div>
    <script>
        async function doLogin(e) {{
            e.preventDefault();
            const password = document.getElementById('password').value;
            const errorEl = document.getElementById('error-msg');
            const btn = document.getElementById('submit-btn');
            errorEl.classList.remove('show');
            btn.disabled = true;
            btn.textContent = 'جاري التحقق...';
            try {{
                const res = await fetch('/api/login', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{password}})
                }});
                if (res.ok) {{
                    window.location.href = '/';
                }} else {{
                    const data = await res.json().catch(() => ({{detail: 'كلمة مرور خاطئة'}}));
                    errorEl.textContent = '❌ ' + (data.detail || 'كلمة مرور خاطئة');
                    errorEl.classList.add('show');
                    document.getElementById('password').value = '';
                    document.getElementById('password').focus();
                }}
            }} catch (err) {{
                errorEl.textContent = '❌ خطأ في الاتصال';
                errorEl.classList.add('show');
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'دخول 🔓';
            }}
            return false;
        }}
    </script>
</body>
</html>"""

# ============================================
# SESSION / AUTH HELPERS
# ============================================
def _sign(message: str) -> str:
    mac = hmac.new(KEVIN_SESSION_SECRET.encode("utf-8"),
                   message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")

def make_session_token() -> str:
    """Create signed session token: <timestamp>.<signature>"""
    issued = str(int(datetime.now().timestamp()))
    sig = _sign(issued)
    return f"{issued}.{sig}"

def verify_session_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    try:
        issued, sig = token.rsplit(".", 1)
        expected = _sign(issued)
        if not hmac.compare_digest(sig, expected):
            return False
        issued_ts = int(issued)
        age = int(datetime.now().timestamp()) - issued_ts
        return 0 <= age <= SESSION_TTL_SECONDS
    except Exception:
        return False

def require_auth(kevin_session: str = Cookie(None)):
    """FastAPI dependency that blocks unauthenticated requests."""
    if not KEVIN_PASSWORD:
        raise HTTPException(status_code=503, detail="السيرفر غير مكوّن (KEVIN_PASSWORD مفقود)")
    if not verify_session_token(kevin_session or ""):
        raise HTTPException(status_code=401, detail="غير مسجل الدخول")
    return True

# ============================================
# INITIALIZATION
# ============================================
print(f"\n🚀 جاري تشغيل {ASSISTANT_NAME}...")

app = FastAPI(title=f"{ASSISTANT_NAME} - Arabic AI Assistant")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

print(f"📥 جاري تحميل Whisper ({WHISPER_MODEL})...")
whisper_model = whisper.load_model(WHISPER_MODEL)
print("✅ تم تحميل Whisper")

claude_client = None
gemini_model_instance = None

if ANTHROPIC_API_KEY:
    try:
        claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Claude متصل")
    except Exception as e:
        print(f"⚠️ Claude error: {e}")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_instance = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
        print("✅ Gemini متصل")
    except Exception as e:
        print(f"⚠️ Gemini error: {e}")

if not claude_client and not gemini_model_instance:
    print("⚠️ تحذير: لم يتم تكوين أي مزود AI")

def load_history():
    if CONVERSATION_FILE.exists():
        try:
            return json.loads(CONVERSATION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(history):
    CONVERSATION_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

conversation_history = load_history()

# ============================================
# AI ROUTING
# ============================================
async def chat_with_claude(message, history):
    if not claude_client:
        raise HTTPException(status_code=503, detail="Claude غير متاح")
    messages = [{"role": h["role"], "content": h["content"]} for h in history if h["role"] in ["user", "assistant"]]
    messages.append({"role": "user", "content": message})
    response = claude_client.messages.create(
        model=CLAUDE_MODEL, max_tokens=2048, system=SYSTEM_PROMPT, messages=messages
    )
    return response.content[0].text

async def chat_with_gemini(message, history):
    if not gemini_model_instance:
        raise HTTPException(status_code=503, detail="Gemini غير متاح")
    gemini_history = []
    for h in history:
        if h["role"] == "user":
            gemini_history.append({"role": "user", "parts": [h["content"]]})
        elif h["role"] == "assistant":
            gemini_history.append({"role": "model", "parts": [h["content"]]})
    chat = gemini_model_instance.start_chat(history=gemini_history)
    response = chat.send_message(message)
    return response.text

# ============================================
# ENDPOINTS
# ============================================
@app.get("/", response_class=HTMLResponse)
async def serve_ui(kevin_session: str = Cookie(None)):
    if not verify_session_token(kevin_session or ""):
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(HTML_UI)

@app.get("/login", response_class=HTMLResponse)
async def serve_login(kevin_session: str = Cookie(None)):
    if verify_session_token(kevin_session or ""):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(LOGIN_HTML)

@app.post("/api/login")
async def api_login(payload: dict, response: Response):
    if not KEVIN_PASSWORD:
        raise HTTPException(status_code=503, detail="السيرفر غير مكوّن (KEVIN_PASSWORD مفقود)")
    submitted = (payload.get("password") or "").strip()
    if not submitted:
        raise HTTPException(status_code=400, detail="ادخل كلمة المرور")
    if not hmac.compare_digest(submitted, KEVIN_PASSWORD):
        raise HTTPException(status_code=401, detail="كلمة مرور خاطئة")
    token = make_session_token()
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=token, max_age=SESSION_TTL_SECONDS,
        httponly=True, samesite="lax", secure=False, path="/",
    )
    return {"status": "ok", "message": "تم تسجيل الدخول"}

@app.post("/api/logout")
async def api_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}

@app.get("/api/status")
async def status(_auth: bool = Depends(require_auth)):
    return {
        "assistant_name": ASSISTANT_NAME,
        "claude_available": claude_client is not None,
        "gemini_available": gemini_model_instance is not None,
        "whisper_loaded": True,
        "voices": list(ARABIC_VOICES.keys()),
        "default_voice": DEFAULT_VOICE,
        "history_count": len(conversation_history),
        "knowledge_base_loaded": len(knowledge_base.get("files", [])),
    }

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...), _auth: bool = Depends(require_auth)):
    """Convert Arabic audio to text using Whisper."""
    content = await audio.read()
    audio_size = len(content)

    if audio_size < 1000:
        print(f"⚠️ تسجيل صغير: {audio_size} bytes")
        raise HTTPException(status_code=400, detail=f"التسجيل صغير ({audio_size}b). اتكلم 2-3 ثواني")

    print(f"📥 استلام صوت: {audio_size} bytes ({audio.content_type})")

    # Determine extension from content type
    ext = ".webm"
    if audio.content_type and "mp4" in audio.content_type:
        ext = ".mp4"
    elif audio.filename and "." in audio.filename:
        ext = "." + audio.filename.split(".")[-1]

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        print(f"🎯 جاري التحويل بـ Whisper ({ext})...")
        result = whisper_model.transcribe(
            temp_path,
            language="ar",
            fp16=False,
            no_speech_threshold=0.4,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        text = result["text"].strip()
        print(f"✅ النتيجة: '{text[:100]}'")

        if not text or len(text) < 2:
            raise HTTPException(status_code=400, detail="مسمعتش كلام واضح. اتكلم بصوت أعلى")

        return {"text": text, "language": "ar", "audio_size": audio_size}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ خطأ في Whisper: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"خطأ تقني: {type(e).__name__}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

@app.post("/api/chat")
async def chat(payload: dict, _auth: bool = Depends(require_auth)):
    message = payload.get("message", "").strip()
    provider = payload.get("provider", "gemini")
    if not message:
        raise HTTPException(status_code=400, detail="رسالة فارغة")
    try:
        if provider == "claude":
            response_text = await chat_with_claude(message, conversation_history)
        elif provider == "gemini":
            response_text = await chat_with_gemini(message, conversation_history)
        else:
            raise HTTPException(status_code=400, detail="مزود غير معروف")
        timestamp = datetime.now().isoformat()
        conversation_history.append({"role": "user", "content": message, "timestamp": timestamp, "provider": provider})
        conversation_history.append({"role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat(), "provider": provider})
        save_history(conversation_history)
        return {"response": response_text, "provider": provider, "timestamp": timestamp}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ: {str(e)}")

@app.post("/api/speak")
async def text_to_speech(payload: dict, _auth: bool = Depends(require_auth)):
    text = payload.get("text", "").strip()
    voice_key = payload.get("voice", DEFAULT_VOICE)
    if not text:
        raise HTTPException(status_code=400, detail="نص فارغ")
    voice = ARABIC_VOICES.get(voice_key, ARABIC_VOICES[DEFAULT_VOICE])
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        temp_path = f.name
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)
        return FileResponse(temp_path, media_type="audio/mpeg", filename="response.mp3")
    except Exception as e:
        try: os.unlink(temp_path)
        except Exception: pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear_history")
async def clear_history(_auth: bool = Depends(require_auth)):
    global conversation_history
    conversation_history = []
    save_history([])
    return {"status": "تم مسح المحادثة"}

@app.post("/api/reload_knowledge")
async def reload_knowledge(_auth: bool = Depends(require_auth)):
    """Reload the knowledge base from Excel files."""
    global knowledge_base
    # Delete cache
    if KNOWLEDGE_BASE_FILE.exists():
        KNOWLEDGE_BASE_FILE.unlink()
    knowledge_base = load_knowledge_base()
    return {"status": "تم تحديث قاعدة المعرفة", "files_loaded": len(knowledge_base.get("files", []))}

# ============================================
# STARTUP
# ============================================
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("\n" + "=" * 60)
    print(f"🤖 {ASSISTANT_NAME_AR} ({ASSISTANT_NAME}) - المساعد الذكي")
    print("=" * 60)
    kb_count = len(knowledge_base.get("files", []))
    if kb_count > 0:
        print(f"📚 قاعدة المعرفة: {kb_count} ملف Excel محمّل")
    print(f"\n📡 العناوين:")
    print(f"   💻 من اللابتوب:  http://localhost:{PORT}")
    print(f"   📱 من التلفون:   http://{local_ip}:{PORT}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
