


import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_engine import analyze_with_ai

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "cybershield_demo.db"

st.set_page_config(
    page_title="Threat Signal Demo | CyberShield AI",
    page_icon="🛡️",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
:root { --bg:#061312; --panel:#0b1e1d; --panel2:#102725; --line:#1c4b46; --teal:#35d6ce; --mint:#9cf5df; --text:#e8f7f4; --muted:#91aaa7; }
html, body, [class*="css"] { font-family:'Manrope',sans-serif; }
.stApp { background: radial-gradient(ellipse at 78% 0%, #123b39 0%, var(--bg) 48%); color:var(--text); }
[data-testid="stHeader"] { background:rgba(6,19,18,.75); }
[data-testid="stSidebar"] { background:#071614; border-right:1px solid var(--line); }
[data-testid="stSidebar"] * { color:var(--text); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:var(--muted); }
.block-container { max-width:1500px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3 { color:var(--text); letter-spacing:-.035em; }
.hero { position:relative; overflow:hidden; padding:2rem 2.2rem; border:1px solid #23625c;
  border-radius:22px; background:linear-gradient(115deg,rgba(10,40,38,.97),rgba(9,27,27,.91));
  box-shadow:0 18px 50px rgba(0,0,0,.22); margin-bottom:1.2rem; }
.hero:after { content:""; position:absolute; inset:0; pointer-events:none; opacity:.26;
  background:repeating-radial-gradient(ellipse at 75% 115%, transparent 0 22px, #28716a 23px 24px, transparent 25px 39px); }
.hero h1 { position:relative; color:#f0fffc; font-size:2.25rem; font-weight:800; margin:0; }
.hero p { position:relative; color:#a9cfca; margin:.6rem 0 0; }
div[data-testid="stMetric"] { background:linear-gradient(145deg,#102725,#0a1b1a);
  border:1px solid #1c4b46; border-radius:16px; padding:18px; box-shadow:0 10px 28px #0002; }
[data-testid="stMetricLabel"] p { color:#91aaa7 !important; font-size:.75rem !important; font-weight:800 !important; text-transform:uppercase; letter-spacing:.09em; }
[data-testid="stMetricValue"] { color:#e8f7f4 !important; font-weight:800; }
[data-testid="stMetricDelta"] { color:#35d6a0 !important; }
.stButton > button { border-radius:10px; border:1px solid #28635c; background:#102725; color:#e8f7f4; font-weight:700; transition:all .15s ease; }
.stButton > button:hover { border-color:#35d6ce; color:#9cf5df; background:#153633; }
.stButton > button[kind="primary"] { background:linear-gradient(100deg,#137c78,#22b8a8); color:#031a18; border:0; }
.stButton > button[kind="primary"]:hover { background:linear-gradient(100deg,#22b8a8,#68e5d2); color:#031a18; }
[data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid #1c4b46; }
[data-baseweb="tab"] { background:#0b1e1d; border:1px solid #1c4b46; border-radius:10px 10px 0 0; color:#a9cfca; padding:10px 16px; }
[data-baseweb="tab"][aria-selected="true"] { background:#12332f; color:#9cf5df; border-color:#35a99e; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-baseweb="select"] > div { background:#091b1a; color:#e8f7f4; border-color:#28635c; border-radius:10px; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid #1c4b46; border-radius:12px; overflow:hidden; }
div[data-testid="stAlert"] { border-radius:12px; }
hr { border-color:#1c4b46; }
</style>
""", unsafe_allow_html=True)


def init_db():
    """Create the demo table and safely add AI columns to older databases."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demo_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                author TEXT NOT NULL,
                message TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 1,
                score INTEGER NOT NULL,
                level TEXT NOT NULL,
                indicators TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(demo_posts)").fetchall()
        }
        additions = {
            "ai_label": "TEXT NOT NULL DEFAULT 'AI_UNAVAILABLE'",
            "ai_confidence": "REAL",
            "ai_explanation": "TEXT NOT NULL DEFAULT 'AI analysis not available'",
            "ai_model": "TEXT",
            "ai_available": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, sql_type in additions.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE demo_posts ADD COLUMN {column} {sql_type}")


def classify_message(message):
    """Existing transparent keyword detector; retained as a separate signal."""
    text = message.lower()
    rules = {
        "Urgency": ["urgent", "immediately", "act now", "last chance", "right now"],
        "Fear / panic": ["panic", "everyone will die", "emergency", "danger", "before it's too late"],
        "Pressure to share": ["share this", "forward this", "send to everyone", "share immediately"],
        "Financial / credential scam": [
            "send your otp", "share your password", "upi pin", "bank will close",
            "account suspended", "withdraw your money", "payment blocked",
        ],
        "Impersonation / suspicious link": [
            "digital arrest", "police will arrest", "cbi officer", "claim your prize",
            "click this link", "verify your account immediately",
        ],
    }
    matched = {
        category: [term for term in terms if term in text]
        for category, terms in rules.items()
    }
    matched = {category: terms for category, terms in matched.items() if terms}
    score = min(100, sum(min(2, len(terms)) * 20 for terms in matched.values()))
    level = "HIGH" if score >= 60 else "MEDIUM" if score >= 20 else "LOW"
    return score, level, matched


def combine_assessments(rule_score, rule_level, ai_result):
    """
    Combine independent signals without treating AI output as ground truth.
    The existing rule score remains visible; AI can raise triage, not certify safety.
    """
    ai_label = ai_result.get("label", "AI_UNAVAILABLE")
    ai_available = bool(ai_result.get("available"))
    ai_confidence = ai_result.get("confidence")

    combined_score = int(rule_score)
    reasons = []

    if rule_score > 0:
        reasons.append(f"Rule-based indicators produced score {rule_score}/100")

    if ai_available and ai_label == "AI_SUSPICIOUS":
        # Use a conservative contribution only when the model predicts its spam class.
        ai_points = round(float(ai_confidence or 0) * 40)
        combined_score = max(combined_score, min(100, max(20, ai_points)))
        reasons.append(
            f"AI model classified the text as spam-like (model confidence "
            f"{float(ai_confidence):.1%}; not a probability of fraud)"
        )
    elif ai_available:
        reasons.append(
            "AI model did not classify this text as SMS spam-like; this does not prove safety"
        )
    else:
        reasons.append("AI analysis unavailable; using the existing rule-based result")

    if combined_score >= 60:
        combined_level = "HIGH"
    elif combined_score >= 20:
        combined_level = "MEDIUM"
    else:
        combined_level = "LOW"

    return combined_score, combined_level, reasons


def add_demo_post(author, message):
    rule_score, rule_level, matched = classify_message(message)
    # AI is optional: a model/import/runtime failure must not prevent saving
    # the simulated post or displaying the rule-based assessment.
    try:
        ai_result = analyze_with_ai(message)
        if not isinstance(ai_result, dict):
            raise ValueError("AI returned an invalid result")
    except Exception as exc:
        ai_result = {
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": f"AI analysis unavailable ({type(exc).__name__}); rule-based assessment retained.",
            "model": "Unavailable",
            "available": False,
        }

    score, level, combined_reasons = combine_assessments(
        rule_score, rule_level, ai_result
    )

    indicators = "; ".join(
        f"{category}: {', '.join(terms)}" for category, terms in matched.items()
    ) or "No predefined keyword indicators"

    analysis_notes = " | ".join(combined_reasons)
    indicators = f"{indicators} | {analysis_notes}"

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO demo_posts
            (created_at, author, message, is_demo, score, level, indicators, status,
             ai_label, ai_confidence, ai_explanation, ai_model, ai_available)
            VALUES (?, ?, ?, 1, ?, ?, ?, 'Open', ?, ?, ?, ?, ?)
            """,
            (
                now, author, message, score, level, indicators,
                ai_result.get("label", "AI_UNAVAILABLE"),
                ai_result.get("confidence"),
                ai_result.get("explanation", "AI analysis not available"),
                ai_result.get("model"),
                1 if ai_result.get("available") else 0,
            ),
        )


def fetch_posts():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT id, created_at, author, message, score, level, indicators, status,
                   ai_label, ai_confidence, ai_explanation, ai_model, ai_available
            FROM demo_posts ORDER BY id DESC
            """,
            conn,
        )


init_db()
st.markdown("""
<div class="hero">
  <h1>🛡️ CyberShield AI — Threat Signal Demo</h1>
  <p>Post a clearly labelled demo message and watch the monitoring console create a review alert.</p>
</div>
""", unsafe_allow_html=True)
st.caption(
    "DEMONSTRATION ENVIRONMENT • Messages entered here are labelled as simulated demo content. "
    "This page does not publish to real social media."
)

tab_post, tab_feed, tab_alerts, tab_metrics = st.tabs(
    ["📝 Demo Social Feed", "📡 Monitoring Console", "🚨 Alerts", "📊 Demo Analytics"]
)

with tab_post:
    st.subheader("Publish a simulated message")
    st.write(
        "Enter a fictional message to demonstrate how the monitoring system responds. "
        "It is stored only in this local demo database."
    )
    examples = {
        "Choose a sample": "",
        "Simulated bank scam": "URGENT! Your bank account will be closed today. Send your OTP immediately to avoid suspension.",
        "Simulated misinformation": "BREAKING! Share this immediately with everyone before it's too late. An unverified claim is spreading.",
        "Normal college message": "Our college coding club is organizing a programming competition next Monday. Register before Friday.",
        "Simulated impersonation scam": "This is a fake demo message: a caller claims to be a CBI officer and threatens digital arrest unless money is transferred.",
    }
    chosen = st.selectbox("Load a sample", list(examples.keys()))
    default_message = examples[chosen]
    author = st.text_input("Demo author", value="Demo User")
    message = st.text_area(
        "Message text", value=default_message, height=150,
        placeholder="Write a fictional test message..."
    )
    if st.button("Publish to demo feed", type="primary"):
        if not message.strip():
            st.warning("Enter a message before publishing.")
        else:
            with st.spinner("Running AI and rule-based analysis..."):
                add_demo_post(author.strip() or "Demo User", message.strip())
            st.success("Demo message published and analysed by the AI + rule-based monitor.")
            st.rerun()

with tab_feed:
    st.subheader("Simulated social feed")
    st.write(
        "Newest demo messages appear here. No message is sent to YouTube, Instagram, X, "
        "or any real platform."
    )
    posts = fetch_posts()
    if posts.empty:
        st.info("No demo messages yet. Add one in the Demo Social Feed tab.")
    else:
        for _, row in posts.iterrows():
            with st.container(border=True):
                st.caption(
                    f'DEMO POST #{row["id"]} • {row["created_at"]} • by {row["author"]}'
                )
                st.write(row["message"])
                st.caption(
                    f'Triage: {row["level"]} • Combined score {row["score"]}/100'
                )
                st.write(f'Indicators: {row["indicators"]}')
                if int(row["ai_available"] or 0):
                    confidence = row["ai_confidence"]
                    conf_text = f"{float(confidence):.1%}" if pd.notna(confidence) else "N/A"
                    st.info(f'AI result: {row["ai_label"]} • Model confidence: {conf_text}')
                    st.caption(str(row["ai_explanation"]))
                else:
                    st.warning("AI unavailable for this post; rule-based result was retained.")

with tab_alerts:
    st.subheader("Alert Center")
    posts = fetch_posts()
    if posts.empty:
        st.info("No alerts yet. Publish a simulated message to test the monitor.")
    else:
        alert_posts = posts[posts["level"].isin(["HIGH", "MEDIUM"])].copy()
        if alert_posts.empty:
            st.success("No medium/high indicator matches in the current demo posts.")
        else:
            st.write(
                "These messages were flagged by the combined triage system. "
                "They require human review and are not confirmed threats."
            )
            for _, row in alert_posts.iterrows():
                with st.container(border=True):
                    st.error(f'🚨 {row["level"]} INDICATOR — Demo post #{row["id"]}')
                    st.caption(
                        f'{row["created_at"]} • Score {row["score"]}/100 • Status: {row["status"]}'
                    )
                    st.write(row["message"])
                    st.write("**Why it was flagged:**", row["indicators"])
                    st.write(f'**AI classification:** {row["ai_label"]}')
                    if int(row["ai_available"] or 0):
                        confidence = row["ai_confidence"]
                        conf_text = f"{float(confidence):.1%}" if pd.notna(confidence) else "N/A"
                        st.caption(
                            f'Model confidence: {conf_text}. This is confidence in the model label, '
                            "not a probability that the message is fraudulent."
                        )
                    else:
                        st.caption("AI model unavailable for this post.")
                    if row["status"] != "Reviewed":
                        if st.button("Mark reviewed", key=f'review_{row["id"]}'):
                            with sqlite3.connect(DB_PATH) as conn:
                                conn.execute(
                                    "UPDATE demo_posts SET status='Reviewed' WHERE id=?",
                                    (int(row["id"]),),
                                )
                            st.rerun()

with tab_metrics:
    st.subheader("Demo analytics")
    posts = fetch_posts()
    total = len(posts)
    flagged = int(posts["level"].isin(["HIGH", "MEDIUM"]).sum()) if total else 0
    high = int((posts["level"] == "HIGH").sum()) if total else 0
    ai_count = int((posts["ai_available"] == 1).sum()) if total else 0
    a, b, c, d = st.columns(4)
    a.metric("Demo messages", total)
    b.metric("Messages flagged for review", flagged)
    c.metric("High indicator level", high)
    d.metric("AI analyses available", ai_count)
    if total:
        chart = posts.copy()
        chart["created_at"] = pd.to_datetime(chart["created_at"], errors="coerce")
        chart = chart.dropna(subset=["created_at"]).sort_values("created_at")
        chart["Collection time"] = chart["created_at"].dt.strftime("%H:%M:%S")
        st.line_chart(chart.set_index("Collection time")[["score"]])
        st.dataframe(
            posts[["created_at", "author", "score", "level", "ai_label",
                   "ai_confidence", "indicators", "status"]],
            use_container_width=True,
            hide_index=True,
        )
    st.caption(
        "Combined scores are triage signals, not proof that a message is false. "
        "The pretrained model is SMS-spam-focused and may misclassify social-media text."
    )

st.divider()
st.caption(
    "SIH demo prototype • Simulated posts only • AI + keyword triage • Human review required"
)
