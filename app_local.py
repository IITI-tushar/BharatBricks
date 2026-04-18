"""
Bharat Bricks - Enhanced Local Version
AI-Powered Civic Complaint Management System
Madhya Pradesh Government | Hackathon Demo
"""

from __future__ import annotations
import asyncio
import base64
import logging
import os
import re
import uuid
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

from database import (
    init_database, insert_complaint, update_complaint_status,
    query_complaints, get_complaint_by_id, insert_vote, get_statistics,
    seed_governing_bodies
)
from mock_ml_endpoints import (
    classify_complaint, route_complaint,
    estimate_priority, estimate_resolution_time, KEYWORD_MAPPINGS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("bharat-bricks-local")

try:
    init_database()
    seed_governing_bodies()
    log.info("Database initialized successfully")
except Exception as e:
    log.error(f"DB init failed: {e}")

BODY_NAME      = os.getenv("BODY_NAME", "Madhya Pradesh State Governing Body")
BODY_ID        = os.getenv("BODY_ID", "GB001")
TREASURY_EMAIL = os.getenv("TREASURY_EMAIL", "treasury@mp.gov.in")
ADMIN_PASSWORD = "admin123"

received_complaints: dict[str, dict[str, Any]] = {}
CURRENT_USER_ID = f"USER_{str(uuid.uuid4())[:8]}"

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI backend
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Bharat Bricks Local", version="2.0.0-local")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    stats = get_statistics()
    return {"status": "ok", "mode": "local", "body": BODY_NAME,
            "database_complaints": stats["total_complaints"]}

@app.post("/complaints/receive")
async def receive_complaint(
    background_tasks: BackgroundTasks,
    complaint_id: str = Form(...), title: str = Form(...),
    description: str = Form(...), category: str = Form(...),
    city: str = Form(...), state: str = Form(...),
    user_id: str = Form(...), priority: str = Form("medium"),
    ai_category: str = Form(""), routed_departments: str = Form("[]"),
    media: list[UploadFile] = File(default=[]),
):
    saved = []
    for f in media:
        content = await f.read()
        saved.append({"filename": f.filename, "size_bytes": len(content),
                       "data_b64": base64.b64encode(content).decode()})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "complaint_id": complaint_id, "title": title, "description": description,
        "category": category, "ai_category": ai_category, "city": city, "state": state,
        "user_id": user_id, "priority": priority, "routed_departments": routed_departments,
        "media_files": saved, "received_at": now, "status": "Accepted",
        "body_id": BODY_ID, "body_name": BODY_NAME,
        "treasury_notified": False, "main_app_updated": False,
    }
    received_complaints[complaint_id] = record
    background_tasks.add_task(_process_complaint, complaint_id)
    return {"accepted": True, "complaint_id": complaint_id,
            "received_by": BODY_NAME, "received_at": now}

@app.get("/complaints")
def list_complaints(limit: int = 50):
    items = sorted(received_complaints.values(), key=lambda x: x["received_at"], reverse=True)
    return {"total": len(items), "complaints": [_strip_media(c) for c in items[:limit]]}

@app.post("/complaints/{complaint_id}/approve")
async def approve_complaint(complaint_id: str, reason: str = Form("Approved")):
    record = received_complaints.get(complaint_id)
    if not record:
        raise HTTPException(404, "Complaint not found")
    record["status"] = "Approved"
    record["approved_at"] = datetime.now(timezone.utc).isoformat()
    update_complaint_status(complaint_id, "approved")
    return {"approved": True, "complaint_id": complaint_id}

async def _process_complaint(complaint_id: str):
    await asyncio.sleep(1)
    record = received_complaints.get(complaint_id)
    if not record:
        return
    log.info(f"TREASURY NOTIFY: {complaint_id} | {record['category']} -> {TREASURY_EMAIL}")
    record["treasury_notified"] = True
    record["treasury_notified_at"] = datetime.now(timezone.utc).isoformat()
    try:
        update_complaint_status(complaint_id, "in_progress")
        record["main_app_updated"] = True
    except Exception as e:
        log.error(f"DB update failed {complaint_id}: {e}")

def _strip_media(record: dict) -> dict:
    out = {k: v for k, v in record.items() if k != "media_files"}
    out["media_count"] = len(record.get("media_files", []))
    return out

# ─────────────────────────────────────────────────────────────────────────────
# CSS / theme
# ─────────────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
/* ── Force light mode everywhere — override Gradio 6 dark defaults ── */
:root {
    --background-fill-primary:   #ffffff !important;
    --background-fill-secondary: #F1F5F9 !important;
    --border-color-primary:      #E2E8F0 !important;
    --color-accent:              #FF6B00 !important;
    --body-text-color:           #111827 !important;
    --body-text-color-subdued:   #6B7280 !important;
    --input-background-fill:     #ffffff !important;
    --block-background-fill:     #ffffff !important;
    --panel-background-fill:     #F8FAFC !important;
    --chatbot-background:        #ffffff !important;
}

/* ── Page & container ── */
html, body { background: #F1F5F9 !important; margin: 0 !important; }
.gradio-container { max-width: 100% !important; width: 100% !important;
                    background: #F1F5F9 !important; padding: 16px !important; box-sizing: border-box !important; }
.main { background: #F1F5F9 !important; }
footer { display: none !important; }

/* ── All blocks / panels ── */
.block, .form, .gap, .panel, .wrap,
[data-testid="block"], .border-none { background: #ffffff !important; }

/* ── All text dark ── */
p, span, h1, h2, h3, h4, h5, li, td, th,
.label-wrap, .label-wrap span,
.prose, .prose *, .md, .md *,
.output-markdown, .output-markdown * { color: #111827 !important; }
label span { color: #374151 !important; font-weight: 600 !important; }

/* ── Inputs ── */
input, textarea, select { background: #ffffff !important; color: #111827 !important;
                          border: 1.5px solid #D1D5DB !important; }
input::placeholder, textarea::placeholder { color: #9CA3AF !important; }

/* ── Tab titles → black ── */
.tab-nav button, .tab-nav button *, .tab-nav button span,
button[role="tab"], button[role="tab"] * { color: #000000 !important; }
.tab-nav button.selected, .tab-nav button[aria-selected="true"] { color: #FF6B00 !important; }

/* ── Chatbot → all text white (dark background) ── */
.chatbot *, .message-wrap *, .message *,
.chatbot p, .chatbot span, .chatbot li,
.chatbot strong, .chatbot em, .chatbot code,
.chatbot h1, .chatbot h2, .chatbot h3 { color: #ffffff !important; }
"""

# ─────────────────────────────────────────────────────────────────────────────
# AI helpers
# ─────────────────────────────────────────────────────────────────────────────

def generate_complaint_id() -> str:
    return f"CMP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

def get_ai_details(text: str, category: str = "") -> dict:
    dept     = classify_complaint(text)
    bodies   = route_complaint(category or dept, text)
    priority = estimate_priority(text, dept)
    hours    = estimate_resolution_time(dept, priority)
    text_low = text.lower()
    matched  = [kw for kw in KEYWORD_MAPPINGS.get(dept, []) if kw in text_low]
    return {
        "department": dept,
        "bodies": bodies,
        "priority": priority,
        "est_hours": hours,
        "matched_keywords": matched,
        "confidence": min(0.97, 0.55 + len(matched) * 0.12),
    }

def render_ai_html(ai: dict) -> str:
    kw_text  = ", ".join(ai["matched_keywords"]) if ai["matched_keywords"] else "semantic analysis"
    p_color  = {"high": "#DC2626", "medium": "#D97706", "low": "#059669"}.get(ai["priority"], "#6B7280")
    bodies_h = "".join(
        f'<span style="background:#DBEAFE;color:#1E40AF;padding:4px 12px;border-radius:20px;'
        f'margin:3px;display:inline-block;font-size:13px;font-weight:600;">🏛 {b}</span>'
        for b in ai["bodies"]
    )
    conf = int(ai["confidence"] * 100)
    return f"""
<div style="background:#F0FDF4;border:2px solid #22C55E;border-radius:14px;
            padding:22px;margin:14px 0;font-family:'Segoe UI',sans-serif;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
    <span style="font-size:28px;">🤖</span>
    <div>
      <div style="font-size:19px;font-weight:800;color:#15803D;">AI Pipeline Result</div>
      <div style="font-size:12px;color:#6B7280;">Complaint Classifier  →  Multi-Body Router</div>
    </div>
    <div style="margin-left:auto;background:#15803D;color:white;
                padding:6px 16px;border-radius:20px;font-size:14px;font-weight:700;">
      {conf}% confident
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px;">
    <div style="background:white;border-radius:10px;padding:16px;border:1px solid #E2E8F0;
                box-shadow:0 1px 4px rgba(0,0,0,0.05);">
      <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:8px;">CLASSIFIER OUTPUT</div>
      <div style="font-size:20px;font-weight:800;color:#1E40AF;">📂 {ai["department"]}</div>
      <div style="font-size:12px;color:#6B7280;margin-top:6px;">
        Matched keywords: <em style="color:#374151;">{kw_text}</em>
      </div>
    </div>
    <div style="background:white;border-radius:10px;padding:16px;border:1px solid #E2E8F0;
                box-shadow:0 1px 4px rgba(0,0,0,0.05);">
      <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:8px;">PRIORITY & SLA</div>
      <div style="font-size:20px;font-weight:800;color:{p_color};">
        ⚡ {ai["priority"].upper()}
      </div>
      <div style="font-size:12px;color:#6B7280;margin-top:6px;">
        Estimated resolution: <strong>{ai["est_hours"]} hours</strong>
      </div>
    </div>
  </div>

  <div style="background:white;border-radius:10px;padding:16px;border:1px solid #E2E8F0;
              margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
    <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;
                letter-spacing:1.5px;margin-bottom:10px;">
      MULTI-BODY ROUTER — {len(ai["bodies"])} department(s) assigned
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;">{bodies_h}</div>
  </div>

  <div style="font-size:11px;color:#9CA3AF;text-align:center;padding-top:4px;">
    Local mock model active · Databricks Model Serving (cloud) available for live deployment
  </div>
</div>"""

# ─────────────────────────────────────────────────────────────────────────────
# Citizen portal
# ─────────────────────────────────────────────────────────────────────────────

def submit_complaint(title, description, city, state, pincode, lat, lon, category, image_url):
    if not title or not description:
        return "**Error:** Title and Description are required.", None, ""
    try:
        cid  = generate_complaint_id()
        text = f"{title} {description}"
        ai   = get_ai_details(text, category or "")

        media_urls = [image_url.strip()] if image_url and image_url.strip().startswith("http") else []

        insert_complaint((
            cid, CURRENT_USER_ID, title, description,
            category if category else ai["department"], None,
            float(lat) if lat else None, float(lon) if lon else None,
            pincode, city, state or "Madhya Pradesh",
            json.dumps(media_urls), "submitted", ai["priority"],
            None, None, ai["department"], ai["priority"], ai["est_hours"], None
        ))
        log.info(f"Complaint filed: {cid} | {ai['department']} | {ai['priority']}")

        msg = f"""**Complaint Filed Successfully!**

**Complaint ID:** `{cid}`
**Status:** Submitted — Under Review
**AI Department:** {ai["department"]}
**Routed to:** {", ".join(ai["bodies"])}
**Priority:** {ai["priority"].upper()}
**Est. Resolution:** {ai["est_hours"]} hours

Save your Complaint ID to track status in the **Track** tab."""

        return msg, cid, render_ai_html(ai)

    except Exception as e:
        log.error(f"submit error: {e}", exc_info=True)
        return f"**Error:** {e}", None, ""


def get_complaints_html():
    try:
        df = query_complaints(limit=100)
        if df.empty:
            return ("<div style='text-align:center;padding:60px;color:#6B7280;"
                    "font-family:sans-serif;font-size:16px;'>"
                    "No complaints yet. Submit one to get started!</div>")

        STATUS_COLORS = {
            "submitted":   ("#FEF3C7", "#92400E"),
            "in_progress": ("#DBEAFE", "#1E40AF"),
            "approved":    ("#D1FAE5", "#065F46"),
            "resolved":    ("#DCFCE7", "#166534"),
            "rejected":    ("#FEE2E2", "#991B1B"),
        }
        PRIORITY_COLORS = {"high": "#DC2626", "medium": "#D97706", "low": "#059669"}
        PROGRESS_MAP    = {"submitted": 25, "in_progress": 50, "approved": 75, "resolved": 100}

        cards = []
        for _, c in df.iterrows():
            st      = c.status.lower().replace(" ", "_")
            bg, fg  = STATUS_COLORS.get(st, ("#F3F4F6", "#374151"))
            pct     = PROGRESS_MAP.get(st, 10)
            pc      = PRIORITY_COLORS.get(str(c.priority).lower(), "#6B7280")
            desc    = str(c.description)
            short   = desc[:220] + ("..." if len(desc) > 220 else "")

            cards.append(f"""
<div style="background:white;border:1px solid #E2E8F0;border-radius:14px;
            padding:22px;margin:14px 0;box-shadow:0 2px 10px rgba(0,0,0,0.06);
            font-family:'Segoe UI',sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              flex-wrap:wrap;gap:8px;margin-bottom:10px;">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span style="font-family:monospace;font-size:12px;color:#9CA3AF;">{c.complaint_id}</span>
      <span style="background:{bg};color:{fg};padding:3px 12px;border-radius:20px;
                  font-size:11px;font-weight:700;">{c.status.upper()}</span>
      <span style="background:white;border:1.5px solid {pc};color:{pc};
                  padding:3px 12px;border-radius:20px;font-size:11px;font-weight:700;">
        {str(c.priority).upper()}
      </span>
    </div>
    <span style="font-size:12px;color:#9CA3AF;">{str(c.created_at)[:16]}</span>
  </div>
  <div style="font-size:18px;font-weight:700;color:#111827;margin-bottom:8px;">{c.title}</div>
  <div style="font-size:14px;color:#4B5563;line-height:1.6;margin-bottom:14px;">{short}</div>
  <div style="display:flex;flex-wrap:wrap;gap:20px;font-size:13px;
              color:#6B7280;margin-bottom:14px;border-top:1px solid #F3F4F6;padding-top:12px;">
    <span>📂 <strong style="color:#374151;">{c.ai_category or "Unclassified"}</strong></span>
    <span>📍 <strong style="color:#374151;">{c.city}</strong></span>
    <span>⏱ Est. <strong style="color:#374151;">{c.ai_est_resolution_hours}h</strong></span>
    <span>🔥 <strong style="color:#374151;">{int(c.support_count)}</strong> support</span>
  </div>
  <div style="background:#F3F4F6;border-radius:8px;height:8px;width:100%;margin-bottom:6px;">
    <div style="background:linear-gradient(90deg,#FF6B00,#FF8C00);height:100%;
                width:{pct}%;border-radius:8px;transition:width .3s;"></div>
  </div>
  <div style="font-size:12px;color:#9CA3AF;">Progress: {pct}%</div>
</div>""")

        header = (f"<div style='background:linear-gradient(135deg,#FF6B00,#FF8C00);"
                  f"color:white;padding:18px 22px;border-radius:14px;margin-bottom:18px;"
                  f"font-family:sans-serif;'>"
                  f"<div style='font-size:21px;font-weight:800;'>📋 All Complaints ({len(df)})</div>"
                  f"<div style='font-size:13px;opacity:.9;margin-top:4px;'>"
                  f"Bharat Bricks Civic Feed — Madhya Pradesh</div></div>")

        return f"<div style='font-family:sans-serif;'>{header}{''.join(cards)}</div>"

    except Exception as e:
        return f"<div style='color:#DC2626;padding:20px;font-family:sans-serif;'>Error: {e}</div>"


def track_complaint(complaint_id):
    cid = (complaint_id or "").strip()
    if not cid:
        return "Enter your Complaint ID above."
    try:
        c = get_complaint_by_id(cid)
        if not c:
            return f"No complaint found with ID: `{cid}`"
        pct = {"submitted": 25, "in_progress": 50, "approved": 75, "resolved": 100}.get(
            c["status"].lower().replace(" ", "_"), 0)
        return f"""### Complaint `{c["complaint_id"]}`

**Title:** {c["title"]}
**Description:** {c["description"]}

---
| Field | Value |
|---|---|
| Status | **{c["status"].upper()}** ({pct}% complete) |
| Priority | **{c["priority"].upper()}** |
| AI Department | {c["ai_category"] or "Not Assigned"} |
| Location | {c["city"]}, {c["state"]} |
| Support | 👍 {int(c["support_count"])} people |
| Filed | {c["created_at"]} |
| Est. Resolution | {c["ai_est_resolution_hours"]} hours |"""
    except Exception as e:
        return f"Error: {e}"


def add_support(complaint_id):
    cid = (complaint_id or "").strip()
    if not cid:
        return "Enter a Complaint ID first."
    try:
        c = get_complaint_by_id(cid)
        if not c:
            return f"Complaint `{cid}` not found."
        vid = f"VOTE-{str(uuid.uuid4())[:8].upper()}"
        ok  = insert_vote(vid, cid, CURRENT_USER_ID, "support")
        if not ok:
            return "You have already supported this complaint."
        updated = get_complaint_by_id(cid)
        return f"Support recorded! Total: **{int(updated['support_count'])}** 👍"
    except Exception as e:
        return f"Error: {e}"


def get_stats():
    try:
        s = get_statistics()
        total = s["total_complaints"]
        rows  = ""
        for st, cnt in s["status_counts"].items():
            pct   = (cnt / total * 100) if total else 0
            bar   = int(pct / 5)
            rows += f"| {st.capitalize()} | {cnt} | {'█' * bar}{'░' * (20 - bar)} {pct:.1f}% |\n"
        top = "".join(
            f"- `{i['id']}` — **{i['votes']}** votes · {str(i['title'])[:40]}\n"
            for i in s["top_supported"]
        ) or "_None yet_"
        return f"""### System Statistics

**Total Complaints:** {total:,}

#### By Status
| Status | Count | Distribution |
|--------|-------|--------------|
{rows}
#### Top Supported
{top}

---
_Local SQLite mode · Last refreshed {datetime.now().strftime("%H:%M:%S")}_"""
    except Exception as e:
        return f"Error: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# AI Chatbot
# ─────────────────────────────────────────────────────────────────────────────

_chat_last_ai: dict = {}   # stores last AI result for "file" button


def chatbot_respond(message: str, history: list):
    """history is list of (user_msg, bot_msg) tuples — Gradio tuple format."""
    global _chat_last_ai
    if not message.strip():
        return history, ""

    msg_low = message.lower().strip()

    # ── greetings ──
    if any(w in msg_low for w in ["hello", "hi ", "namaste", " help", "helo", "hey", "start"]):
        reply = (
            "**Namaste! I'm BharatBot** — your AI civic assistant.\n\n"
            "I can:\n"
            "- **Classify & route** your complaint using AI\n"
            "- **Track status** — say `track CMP-XXXXXXXX-XXXXXXXX`\n"
            "- **Show statistics** — say `show stats`\n\n"
            "**Try:** *There's a broken water pipe flooding our street in Bhopal*"
        )
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    # ── track complaint ──
    cmp_match = re.search(r'CMP-\w{8}-\w{8}', message.upper())
    if cmp_match or any(w in msg_low for w in ["track ", "status of", "check complaint"]):
        if cmp_match:
            c = get_complaint_by_id(cmp_match.group())
            if c:
                reply = (f"**Complaint `{c['complaint_id']}`**\n\n"
                         f"- Title: {c['title']}\n"
                         f"- Status: **{c['status'].upper()}**\n"
                         f"- Department: {c['ai_category'] or 'Not assigned'}\n"
                         f"- Priority: {c['priority'].upper()}\n"
                         f"- Support: 👍 {int(c['support_count'])}")
            else:
                reply = f"No complaint found for `{cmp_match.group()}`."
        else:
            reply = "Please share your Complaint ID (format: `CMP-YYYYMMDD-XXXXXXXX`)."
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    # ── statistics ──
    if any(w in msg_low for w in ["stat", "how many", "total complaint", "show stat"]):
        s     = get_statistics()
        lines = "\n".join(f"- {k.capitalize()}: **{v}**" for k, v in s["status_counts"].items())
        reply = f"**System Statistics**\n\nTotal complaints: **{s['total_complaints']}**\n\n{lines}"
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    # ── default: treat as complaint text — run full AI pipeline ──
    ai = get_ai_details(message)
    _chat_last_ai = {"text": message, "ai": ai}

    kw      = ", ".join(ai["matched_keywords"]) or "semantic match"
    bodies  = "\n".join(f"  - **{b}**" for b in ai["bodies"])
    p_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(ai["priority"], "⚪")
    conf    = int(ai["confidence"] * 100)

    reply = (
        f"**AI Analysis Complete** — {conf}% confidence\n\n"
        f"---\n"
        f"**COMPLAINT CLASSIFIER**\n"
        f"- Predicted department: **{ai['department']}**\n"
        f"- Keywords matched: *{kw}*\n\n"
        f"**MULTI-BODY ROUTER**\n"
        f"- Routed to {len(ai['bodies'])} department(s):\n{bodies}\n\n"
        f"**PRIORITY ASSESSMENT**\n"
        f"- Priority: {p_emoji} **{ai['priority'].upper()}**\n"
        f"- Estimated resolution: **{ai['est_hours']} hours**\n\n"
        f"---\n"
        f"_To file this as an official complaint, enter your city below and click **File Complaint**._"
    )
    history.append((message, reply))
    return history, ""


def chatbot_file_complaint(city: str):
    global _chat_last_ai
    if not _chat_last_ai:
        return "Describe your complaint first in the chat above."
    city = city.strip()
    if not city:
        return "Enter your city name."
    try:
        text = _chat_last_ai["text"]
        ai   = _chat_last_ai["ai"]
        cid  = generate_complaint_id()
        insert_complaint((
            cid, CURRENT_USER_ID, text[:100], text,
            ai["department"], None, None, None, None,
            city, "Madhya Pradesh", json.dumps([]), "submitted",
            ai["priority"], None, None, ai["department"],
            ai["priority"], ai["est_hours"], None
        ))
        _chat_last_ai = {}
        return (f"**Complaint Filed!**\n\n"
                f"ID: `{cid}`  \nDepartment: {ai['department']}  \n"
                f"City: {city}  \nPriority: {ai['priority'].upper()}  \n"
                f"Est. Resolution: {ai['est_hours']}h\n\n"
                f"Track it in the **Track Complaint** tab.")
    except Exception as e:
        return f"Error filing complaint: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# Admin panel
# ─────────────────────────────────────────────────────────────────────────────

def admin_login(password: str):
    if password == ADMIN_PASSWORD:
        return (gr.update(visible=False),
                gr.update(visible=True),
                "**Access granted. Welcome, Officer.**")
    return (gr.update(visible=True),
            gr.update(visible=False),
            "**Incorrect password. Try again.**")


def admin_get_table():
    try:
        df = query_complaints(limit=500)
        if df.empty:
            return "<p style='padding:20px;color:#6B7280;font-family:sans-serif;'>No complaints yet.</p>"

        STATUS_BG = {
            "submitted":   "#FEF3C7", "in_progress": "#DBEAFE",
            "approved":    "#D1FAE5", "resolved":    "#DCFCE7", "rejected": "#FEE2E2",
        }
        rows = ""
        for _, c in df.iterrows():
            st  = c.status.lower().replace(" ", "_")
            bg  = STATUS_BG.get(st, "#F3F4F6")
            rows += (
                f"<tr style='border-bottom:1px solid #F3F4F6;'>"
                f"<td style='padding:10px 8px;font-family:monospace;font-size:11px;color:#6B7280;'>{c.complaint_id}</td>"
                f"<td style='padding:10px 8px;font-weight:600;color:#111827;max-width:180px;'>{str(c.title)[:50]}</td>"
                f"<td style='padding:10px 8px;'><span style='background:{bg};padding:3px 10px;"
                f"border-radius:10px;font-size:11px;font-weight:700;'>{c.status.upper()}</span></td>"
                f"<td style='padding:10px 8px;color:#374151;'>{c.ai_category or '—'}</td>"
                f"<td style='padding:10px 8px;color:#374151;'>{c.city}</td>"
                f"<td style='padding:10px 8px;font-weight:700;color:#374151;'>{str(c.priority).upper()}</td>"
                f"<td style='padding:10px 8px;color:#374151;'>{int(c.support_count)}</td>"
                f"<td style='padding:10px 8px;color:#9CA3AF;font-size:11px;'>{str(c.created_at)[:16]}</td>"
                f"</tr>"
            )

        return f"""
<div style="font-family:'Segoe UI',sans-serif;overflow-x:auto;">
  <div style="background:linear-gradient(135deg,#1E3A5F,#2D5A8E);color:white;
              padding:18px 22px;border-radius:12px 12px 0 0;">
    <div style="font-size:19px;font-weight:800;">All Complaints — {len(df)} total</div>
    <div style="font-size:12px;opacity:.8;margin-top:4px;">
      Madhya Pradesh Civic Complaint Management · Admin View
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;background:white;
                border-radius:0 0 12px 12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <thead>
      <tr style="background:#F8FAFC;border-bottom:2px solid #E2E8F0;">
        {''.join(f"<th style='padding:12px 8px;text-align:left;font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:.8px;'>{h}</th>" for h in ["ID","Title","Status","AI Dept","City","Priority","Support","Filed"])}
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""
    except Exception as e:
        return f"<div style='color:red;padding:20px;'>Error: {e}</div>"


def admin_update_status(complaint_id: str, new_status: str, notes: str):
    cid = (complaint_id or "").strip()
    if not cid:
        return "Enter a Complaint ID."
    if not new_status:
        return "Select a new status."
    try:
        c = get_complaint_by_id(cid)
        if not c:
            return f"Complaint `{cid}` not found."
        old = c["status"]
        update_complaint_status(cid, new_status)
        log.info(f"Admin: {cid} {old} -> {new_status} | {notes}")
        return (f"**Updated!** `{cid}`  \n"
                f"Status: **{old.upper()}** → **{new_status.upper()}**  \n"
                f"Notes: {notes or '—'}")
    except Exception as e:
        return f"Error: {e}"


def admin_view_detail(complaint_id: str):
    cid = (complaint_id or "").strip()
    if not cid:
        return "Enter a Complaint ID."
    try:
        c = get_complaint_by_id(cid)
        if not c:
            return f"No complaint found: `{cid}`"
        ai  = get_ai_details(f"{c['title']} {c['description']}")
        kw  = ", ".join(ai["matched_keywords"]) or "none matched"
        bod = "\n".join(f"  - {b}" for b in ai["bodies"]) or "  - None"
        return f"""### `{c["complaint_id"]}`

**Title:** {c["title"]}
**Description:** {c["description"]}
**Status:** {c["status"].upper()} | **Priority:** {c["priority"].upper()}
**City:** {c["city"]}, {c["state"]}
**Filed:** {c["created_at"]} | **Support:** 👍 {int(c["support_count"])}

---
**AI CLASSIFIER OUTPUT**
- Predicted department: **{c["ai_category"] or ai["department"]}**
- Keywords matched: *{kw}*

**MULTI-BODY ROUTER OUTPUT**
{bod}

**SLA:** Est. **{c["ai_est_resolution_hours"]} hours** to resolution"""
    except Exception as e:
        return f"Error: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="Bharat Bricks") as gradio_app:

    # ── Header ────────────────────────────────────────────────────────────────
    gr.HTML("""
<div style="background:linear-gradient(135deg,#FF6B00 0%,#FF8C00 40%,#138808 100%);
            color:white;padding:24px 30px;border-radius:16px;margin-bottom:6px;
            font-family:'Segoe UI',sans-serif;text-align:center;">
  <div style="font-size:32px;font-weight:900;letter-spacing:-0.5px;">
    🏛️ Bharat Bricks
  </div>
  <div style="font-size:16px;opacity:.92;margin-top:6px;">
    AI-Powered Civic Complaint Management · Madhya Pradesh Government
  </div>
  <div style="margin-top:10px;display:flex;justify-content:center;gap:20px;font-size:13px;opacity:.85;">
    <span>🤖 AI Classifier</span>
    <span>🔀 Multi-Body Router</span>
    <span>💬 Smart Chatbot</span>
    <span>🏛️ Admin Portal</span>
  </div>
</div>""")

    with gr.Tabs():

        # ── Tab 1: Submit Complaint ────────────────────────────────────────────
        with gr.Tab("📝 Submit Complaint"):
            gr.Markdown("### File a New Civic Complaint\nOur AI will classify your complaint and route it to the right departments automatically.")
            with gr.Row():
                with gr.Column(scale=3):
                    t_title = gr.Textbox(label="Complaint Title",
                                         placeholder="e.g., Large pothole on MG Road causing accidents")
                    t_desc  = gr.Textbox(label="Detailed Description",
                                         placeholder="Describe the issue in detail...", lines=5)
                    t_cat   = gr.Dropdown(
                        label="Category (AI will auto-detect if left blank)",
                        choices=["Roads & Infrastructure", "Water Supply", "Electricity",
                                 "Garbage Collection", "Public Health", "Education",
                                 "Law & Order", "Environment", "Street Lighting",
                                 "Drainage", "Housing", "Transportation"],
                        value=None, allow_custom_value=True)
                    t_img   = gr.Textbox(label="Image URL (optional)", placeholder="https://...")
                with gr.Column(scale=2):
                    t_city  = gr.Textbox(label="City", value="Bhopal")
                    t_state = gr.Textbox(label="State", value="Madhya Pradesh")
                    t_pin   = gr.Textbox(label="Pincode", placeholder="e.g. 462001")
                    with gr.Row():
                        t_lat = gr.Number(label="Latitude", value=None, precision=6)
                        t_lon = gr.Number(label="Longitude", value=None, precision=6)

            btn_submit = gr.Button("Submit Complaint", variant="primary", size="lg")

            with gr.Row():
                with gr.Column():
                    out_msg = gr.Markdown(label="Result")
                    out_cid = gr.Textbox(label="Your Complaint ID (save this!)", interactive=False)
                with gr.Column():
                    out_ai  = gr.HTML(label="AI Analysis")

            btn_submit.click(
                fn=submit_complaint,
                inputs=[t_title, t_desc, t_city, t_state, t_pin, t_lat, t_lon, t_cat, t_img],
                outputs=[out_msg, out_cid, out_ai]
            )

        # ── Tab 2: AI Chatbot ──────────────────────────────────────────────────
        with gr.Tab("💬 AI Chatbot"):
            gr.Markdown(
                "### BharatBot — AI Civic Assistant\n"
                "Describe your issue in plain language. BharatBot will classify it, "
                "route it, and optionally file it as an official complaint."
            )
            chatbot = gr.Chatbot(
                label="BharatBot",
                height=420,
                value=[{"role": "assistant",
                        "content": ("**Namaste! I'm BharatBot.**\n\n"
                                    "Tell me about your civic issue and I'll:\n"
                                    "1. Classify it with AI\n"
                                    "2. Route it to the right government body\n"
                                    "3. Show priority & estimated resolution time\n\n"
                                    "_Example: \"The street lights on my road have been broken for 3 weeks\"_")}]
            )
            with gr.Row():
                chat_input = gr.Textbox(
                    label="Your message",
                    placeholder="Describe your complaint or say 'hi' to start...",
                    scale=4, lines=1
                )
                chat_send  = gr.Button("Send", variant="primary", scale=1)

            gr.Markdown("---\n**Want to file the last complaint officially?**")
            with gr.Row():
                chat_city   = gr.Textbox(label="Your City", placeholder="e.g., Bhopal", scale=3)
                chat_file   = gr.Button("File Complaint from Chat", variant="secondary", scale=2)
            chat_file_out = gr.Markdown()

            chat_send.click(chatbot_respond,  [chat_input, chatbot], [chatbot, chat_input])
            chat_input.submit(chatbot_respond, [chat_input, chatbot], [chatbot, chat_input])
            chat_file.click(chatbot_file_complaint, [chat_city], [chat_file_out])

        # ── Tab 3: View All Complaints ─────────────────────────────────────────
        with gr.Tab("📋 View All Complaints"):
            gr.Markdown("### Public Complaint Feed\nAll civic complaints with real-time status, AI classification, and support counts.")
            btn_refresh = gr.Button("Refresh Feed", variant="secondary")
            feed_html   = gr.HTML(value=get_complaints_html())
            btn_refresh.click(fn=get_complaints_html, inputs=[], outputs=[feed_html])

        # ── Tab 4: Track & Support ─────────────────────────────────────────────
        with gr.Tab("🔍 Track Complaint"):
            gr.Markdown("### Track Your Complaint\nEnter your Complaint ID to see full status and show your support.")
            track_id = gr.Textbox(label="Complaint ID", placeholder="CMP-20260418-XXXXXXXX")
            with gr.Row():
                btn_track   = gr.Button("Track Status",   variant="primary")
                btn_support = gr.Button("👍 Show Support", variant="secondary")
            track_out   = gr.Markdown()
            support_out = gr.Markdown()
            btn_track.click(track_complaint, [track_id], [track_out])
            btn_support.click(add_support,   [track_id], [support_out])

        # ── Tab 5: Admin Panel ─────────────────────────────────────────────────
        with gr.Tab("🏛️ Admin Panel"):

            with gr.Group() as login_group:
                gr.HTML("""
<div style="text-align:center;padding:30px 20px;font-family:'Segoe UI',sans-serif;">
  <div style="font-size:48px;margin-bottom:12px;">🔒</div>
  <div style="font-size:22px;font-weight:700;color:#1E3A5F;margin-bottom:6px;">
    Government Officer Portal
  </div>
  <div style="font-size:14px;color:#6B7280;margin-bottom:24px;">
    Restricted access — Madhya Pradesh Civic Management
  </div>
</div>""")
                with gr.Row():
                    with gr.Column(scale=1): pass
                    with gr.Column(scale=2):
                        pw_input  = gr.Textbox(label="Admin Password", type="password",
                                                placeholder="Enter password...")
                        login_btn = gr.Button("Login", variant="primary", size="lg")
                        login_msg = gr.Markdown()
                    with gr.Column(scale=1): pass

            with gr.Group(visible=False) as admin_group:
                gr.HTML("""
<div style="background:linear-gradient(135deg,#1E3A5F,#2D5A8E);color:white;
            padding:18px 22px;border-radius:12px;margin-bottom:16px;font-family:sans-serif;">
  <div style="font-size:20px;font-weight:800;">🏛️ Government Officer Dashboard</div>
  <div style="font-size:13px;opacity:.8;margin-top:4px;">
    Madhya Pradesh Civic Complaint Management System — Admin Access
  </div>
</div>""")

                with gr.Tabs():
                    with gr.Tab("📋 All Complaints"):
                        btn_admin_refresh = gr.Button("Refresh Table", variant="secondary")
                        admin_table_html  = gr.HTML(value="Click Refresh to load.")
                        btn_admin_refresh.click(fn=admin_get_table, inputs=[], outputs=[admin_table_html])

                    with gr.Tab("✏️ Update Status"):
                        gr.Markdown("### Change Complaint Status\nManually update a complaint's status after review.")
                        with gr.Row():
                            upd_id     = gr.Textbox(label="Complaint ID",
                                                     placeholder="CMP-20260418-XXXXXXXX", scale=3)
                            upd_status = gr.Dropdown(
                                label="New Status",
                                choices=["submitted", "in_progress", "approved",
                                         "resolved", "rejected"],
                                scale=2)
                        upd_notes  = gr.Textbox(label="Officer Notes (optional)",
                                                 placeholder="Reason for status change...", lines=2)
                        btn_update = gr.Button("Update Status", variant="primary")
                        upd_out    = gr.Markdown()
                        btn_update.click(admin_update_status,
                                         [upd_id, upd_status, upd_notes], [upd_out])

                    with gr.Tab("🔎 Complaint Detail + AI"):
                        gr.Markdown("### View Full Complaint with AI Analysis\nSee classifier output, router decisions, and SLA for any complaint.")
                        detail_id  = gr.Textbox(label="Complaint ID",
                                                 placeholder="CMP-20260418-XXXXXXXX")
                        btn_detail = gr.Button("Load Detail", variant="primary")
                        detail_out = gr.Markdown()
                        btn_detail.click(admin_view_detail, [detail_id], [detail_out])

                    with gr.Tab("📊 Statistics"):
                        btn_stats = gr.Button("Refresh Stats", variant="secondary")
                        stats_out = gr.Markdown(value=get_stats())
                        btn_stats.click(fn=get_stats, inputs=[], outputs=[stats_out])

            login_btn.click(
                fn=admin_login,
                inputs=[pw_input],
                outputs=[login_group, admin_group, login_msg]
            )

        # ── Tab 6: Statistics ──────────────────────────────────────────────────
        with gr.Tab("📊 Statistics"):
            gr.Markdown("### System Analytics")
            btn_pub_stats = gr.Button("Refresh", variant="secondary")
            pub_stats_out = gr.Markdown(value=get_stats())
            btn_pub_stats.click(fn=get_stats, inputs=[], outputs=[pub_stats_out])

    # ── Footer ─────────────────────────────────────────────────────────────────
    gr.HTML("""
<div style="text-align:center;padding:18px;margin-top:8px;font-family:'Segoe UI',sans-serif;
            color:#6B7280;font-size:13px;border-top:1px solid #E2E8F0;margin-top:16px;">
  <strong style="color:#FF6B00;">Bharat Bricks</strong> · AI Civic Complaint System ·
  Built on Databricks + Delta Lake + MLflow<br>
  <span style="font-size:11px;">Local mode: SQLite + Mock ML · Admin password: <code>admin123</code></span>
</div>""")

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("Bharat Bricks — Enhanced Local Server")
    log.info("UI  : http://127.0.0.1:7861/")
    log.info("=" * 60)
    gradio_app.launch(
        server_name="127.0.0.1",
        server_port=7861,
        share=False,
        theme=gr.themes.Default(),
        css=CUSTOM_CSS,
    )
