import os
import sqlite3
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
import pytesseract

try:
    from ai_engine_gemini import analyze_with_ai, assess_claim_with_sources
except Exception:
    analyze_with_ai = None
    assess_claim_with_sources = None

try:
    from claim_verifier import search_claim
except Exception:
    search_claim = None

try:
    from social_media import search_youtube
except Exception:
    search_youtube = None


# --------------------------- Configuration ---------------------------
APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "cybershield_history.db"
DEFAULT_KEYWORDS = [
    "cybercrime India",
    "online payment fraud India",
    "digital arrest scam India",
    "fake news India",
]
TOPIC_STOPWORDS = {
    "about", "after", "again", "against", "also", "amid", "among", "and",
    "are", "because", "been", "before", "being", "between", "breaking",
    "but", "can", "could", "from", "have", "into", "just", "more", "most",
    "news", "over", "said", "says", "shorts", "some", "than", "that", "the",
    "their", "there", "these", "they", "this", "those", "through", "today",
    "under", "very", "was", "were", "what", "when", "where", "which", "while",
    "with", "would", "youtube", "your", "india", "indian", "video", "videos",
}

st.set_page_config(
    page_title="CyberShield AI | Threat Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
        :root {
            --canvas: #11112f; --surface: #1d1d45; --surface-raised: #252550;
            --ink: #f3f2ff; --muted: #a2a1c8; --line: #34345f;
            --violet: #6657f5; --violet-bright: #887cff; --sidebar: #19193d;
        }
        html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
        .stApp {
            background: radial-gradient(ellipse at 74% -12%, #24204f 0%, #141438 42%, var(--canvas) 78%);
            color: var(--ink);
        }
        [data-testid="stHeader"] { background: rgba(17,17,47,.92); }
        [data-testid="stSidebar"] {
            background: var(--sidebar); border-right: 1px solid #2a2a53;
            width: 210px !important; min-width: 210px !important;
        }
        [data-testid="stSidebar"] * { color: #e6e5f7; }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] .stCaption {
            color: #9292b7; font-size: .56rem; line-height: 1.3; letter-spacing: 0;
        }
        [data-testid="stSidebar"] h2 {
            color: #f8f7ff; font-size: 1.05rem; font-weight: 800;
            letter-spacing: 0; margin-bottom: .2rem;
        }
        [data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
        [data-testid="stSidebar"] input[type="radio"] { accent-color: #b9b1ff; }
        [data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {
            background: #b9b1ff !important; border-color: #b9b1ff !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            background: transparent; border: 1px solid transparent;
            border-radius: 6px; padding: 6px 7px; color: #aaa9ca;
            font-size: .78rem;
            transition: background .16s ease, border-color .16s ease, color .16s ease;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: #29284f; border-color: #393866;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: linear-gradient(105deg, #6757f5, #5445e7);
            border-color: #7669ff; color: #ffffff;
            box-shadow: 0 5px 16px rgba(91, 75, 235, .24);
        }
        .block-container { max-width: 1600px; padding: 1.15rem 2rem 3rem; }
        h1, h2, h3, h4 { color: #f5f4ff; letter-spacing: 0; }
        h2, h3 { margin-top: .65rem; }
        h3 { font-size: 1rem !important; line-height: 1.3; }
        p, label, [data-testid="stMarkdownContainer"] { color: #d2d1e9; }
        .workspace-header {
            display: flex; align-items: center; gap: 14px;
            padding: .1rem 0 .65rem; margin-bottom: .8rem;
            border-bottom: 1px solid var(--line);
        }
        .brand-mark {
            display: grid; place-items: center; flex: 0 0 36px; height: 36px;
            border-radius: 7px; background: linear-gradient(145deg, #7568ff, #503ee1); color: #ffffff;
            font-size: .75rem; font-weight: 800; letter-spacing: .04em;
            box-shadow: 0 5px 16px rgba(98, 81, 235, .28);
        }
        .workspace-header h1 {
            margin: 0; color: #f5f4ff; font-size: 1.02rem;
            font-weight: 800; letter-spacing: 0;
        }
        .workspace-header p {
            margin: .12rem 0 0; color: var(--muted); font-size: .75rem;
        }
        .hero {
            display: grid; grid-template-columns: minmax(0, 1fr) auto;
            column-gap: 1rem; row-gap: .12rem;
            position: relative; overflow: hidden; padding: .25rem 0 .7rem;
            border-radius: 0; margin-bottom: .65rem;
            background: transparent; border: 0; box-shadow: none;
        }
        .hero:after { display: none; }
        .hero h1 {
            grid-column: 1; grid-row: 2;
            margin: 0; color: #f7f6ff; font-size: 1.35rem; font-weight: 800;
        }
        .hero p { grid-column: 1; grid-row: 3; color: #b8b7d7; margin: .2rem 0 0; font-size: .78rem; }
        .hero-eyebrow { grid-column: 1 / -1; color: #b5adff; font-size: .6rem; font-weight: 800; letter-spacing: .13em; }
        .status-row {
            grid-column: 2; grid-row: 2 / span 2; align-self: center;
            display: flex; flex-direction: column; align-items: flex-start;
            gap: 7px; margin-top: 0;
        }
        .status-chip {
            display: inline-block; padding: 5px 8px; border: 1px solid #504c91;
            border-radius: 5px; background: #302d65; color: #c7c1ff;
            font-size: .66rem; font-weight: 800; letter-spacing: .05em;
        }
        .status-meta { color: #d1cfee; font-size: .72rem; }
        .small-note { color: #9594b8; font-size: .84rem; }
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #5545e7, #4637c9);
            border: 1px solid #7569ff; border-radius: 8px;
            padding: 9px 10px 8px; box-shadow: 0 8px 20px rgba(10, 8, 45, .22);
            min-height: 78px; color: #ffffff;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {
            background: linear-gradient(135deg, #36a8e8, #3984db);
            border-color: #65bcf0;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {
            background: linear-gradient(135deg, #a12bea, #7915d0);
            border-color: #bf60f1;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] {
            background: linear-gradient(135deg, #d44be5, #b52bcf);
            border-color: #e875ec;
        }
        [data-testid="stMetricLabel"] p {
            color: #e0dcff !important; font-size: .62rem !important;
            font-weight: 700 !important; text-transform: none; letter-spacing: 0;
            line-height: 1.2;
        }
        [data-testid="stMetricValue"] {
            color: #ffffff !important; font-size: 1.25rem !important; font-weight: 800;
        }
        [data-testid="stMetricDelta"] { color: #e5e2ff !important; font-weight: 700; }
        div[data-testid="stAlert"] { border-radius: 7px; }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border: 1px solid var(--line); border-radius: 8px; overflow: hidden;
            background: var(--surface);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface); border: 1px solid var(--line) !important;
            border-radius: 8px !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) > div[data-testid="stColumn"] {
            padding: 14px; border: 1px solid var(--line); border-radius: 8px;
            background: var(--surface);
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(105deg, #6959f5, #5344df); color: #ffffff;
            border: 1px solid #786cff; border-radius: 6px; font-weight: 700;
            box-shadow: 0 4px 12px rgba(91, 75, 235, .2);
        }
        .stButton > button[kind="primary"]:hover {
            background: #786aff; color: #ffffff; border-color: #9288ff;
        }
        .stButton > button { border: 1px solid #41416d; border-radius: 6px; }
        input, textarea, [data-baseweb="select"] > div {
            background-color: #171738 !important; color: var(--ink) !important;
            border-color: #3d3d6a !important; border-radius: 6px !important;
        }
        input:focus, textarea:focus, [data-baseweb="select"] > div:focus-within {
            border-color: var(--violet-bright) !important;
            box-shadow: 0 0 0 1px var(--violet-bright) !important;
        }
        hr { border-color: var(--line); }
        @media (max-width: 640px) {
            .block-container { padding: .75rem 1rem 3rem; }
            .hero { display: block; padding: .25rem 0 .65rem; }
            .hero h1 { font-size: 1.2rem; }
            .status-row { flex-direction: row; flex-wrap: wrap; margin-top: .5rem; }
            .workspace-header { margin-bottom: .85rem; }
            [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
            [data-testid="stSidebar"] { width: min(82vw, 260px) !important; min-width: min(82vw, 260px) !important; }
            div[data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) > div[data-testid="stColumn"] {
                padding: 10px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------- Persistent history ---------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT NOT NULL,
                keyword TEXT NOT NULL,
                result_count INTEGER NOT NULL,
                flagged_count INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collected_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                video_id TEXT,
                title TEXT,
                description TEXT,
                channel TEXT,
                published_at TEXT,
                url TEXT,
                score INTEGER,
                level TEXT,
                indicators TEXT,
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )
        """)
        existing_video_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(collected_videos)").fetchall()
        }
        if "description" not in existing_video_columns:
            conn.execute("ALTER TABLE collected_videos ADD COLUMN description TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyzer_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                score INTEGER NOT NULL,
                level TEXT NOT NULL,
                indicators TEXT NOT NULL,
                reviewed INTEGER NOT NULL DEFAULT 0,
                url TEXT,
                ai_label TEXT,
                ai_risk_score INTEGER,
                ai_threat_type TEXT,
                ai_explanation TEXT
            )
        """)


def load_demo_posts():
    """Read messages published on demo_website.py when both apps share this folder."""
    demo_db = APP_DIR / "cybershield_demo.db"
    if not demo_db.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(demo_db) as conn:
            return pd.read_sql_query(
                "SELECT id, created_at, author, message, score, level, indicators, status "
                "FROM demo_posts ORDER BY id DESC",
                conn,
            )
    except Exception:
        return pd.DataFrame()


def load_history():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT collected_at, keyword, result_count, flagged_count "
            "FROM collections ORDER BY id ASC", conn
        )


def load_analyzer_alerts():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        alerts = conn.execute(
            """SELECT id, created_at AS time, source, text, score, level, indicators,
                      reviewed, url, ai_label, ai_risk_score, ai_threat_type, ai_explanation
               FROM analyzer_alerts ORDER BY id DESC"""
        ).fetchall()
    return [{**dict(alert), "reviewed": bool(alert["reviewed"])} for alert in alerts]


def save_analyzer_alert(entry):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """INSERT INTO analyzer_alerts
               (created_at, source, text, score, level, indicators, reviewed, url,
                ai_label, ai_risk_score, ai_threat_type, ai_explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                entry.get("source", "Unknown"), entry.get("text", ""),
                int(entry.get("score", 0) or 0), entry.get("level", "LOW"),
                entry.get("indicators", "None detected"),
                int(bool(entry.get("reviewed", False))), entry.get("url"),
                entry.get("ai_label"), entry.get("ai_risk_score"),
                entry.get("ai_threat_type"), entry.get("ai_explanation"),
            ),
        )
        alert_id = cursor.lastrowid
    return {**entry, "id": alert_id, "reviewed": bool(entry.get("reviewed", False))}


def mark_analyzer_alert_reviewed(alert_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE analyzer_alerts SET reviewed = 1 WHERE id = ?",
            (alert_id,),
        )


def save_collection(keyword, videos, analyzed):
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    flagged = sum(1 for item in analyzed if item["indicators"])
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO collections (collected_at, keyword, result_count, flagged_count) VALUES (?, ?, ?, ?)",
            (timestamp, keyword, len(videos), flagged),
        )
        collection_id = cursor.lastrowid
        for video, result in zip(videos, analyzed):
            video_id = video.get("url", "").split("v=")[-1]
            conn.execute(
                """INSERT INTO collected_videos
                (collection_id, video_id, title, description, channel, published_at, url, score, level, indicators)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    collection_id, video_id, video.get("title", ""),
                    video.get("description", ""), video.get("channel", ""),
                    video.get("published_at", ""),
                    video.get("url", ""), result["score"], result["level"],
                    ", ".join(result["indicators"]),
                ),
            )
    return timestamp


def extract_topic_terms(text):
    terms = set()
    token = []
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    for character in normalized:
        if unicodedata.category(character)[0] in {"L", "M"}:
            token.append(character)
        elif token:
            word = "".join(token)
            if len(word) >= 3 and word not in TOPIC_STOPWORDS:
                terms.add(word)
            token.clear()
    if token:
        word = "".join(token)
        if len(word) >= 3 and word not in TOPIC_STOPWORDS:
            terms.add(word)
    return terms


def get_emerging_topics(keyword):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.collected_at, v.title, v.description
            FROM collections AS c
            LEFT JOIN collected_videos AS v ON v.collection_id = c.id
            WHERE c.keyword = ?
              AND c.id IN (
                  SELECT id FROM collections WHERE keyword = ? ORDER BY id DESC LIMIT 2
              )
            ORDER BY c.id DESC, v.id DESC
            """,
            (keyword, keyword),
        ).fetchall()

    snapshots = {}
    for collection_id, collected_at, title, description in rows:
        snapshot = snapshots.setdefault(
            collection_id, {"collected_at": collected_at, "terms": Counter()}
        )
        snapshot["terms"].update(
            extract_topic_terms(f"{title or ''} {description or ''}")
        )

    latest_two = list(snapshots.values())
    if not latest_two:
        return {"snapshots": 0, "comparison_available": False, "terms": []}

    latest = latest_two[0]
    previous = latest_two[1] if len(latest_two) > 1 else None
    terms = []
    for term, latest_count in latest["terms"].most_common():
        previous_count = previous["terms"].get(term, 0) if previous else None
        increase = latest_count - previous_count if previous else None
        if previous is None or increase > 0:
            terms.append({
                "term": term,
                "latest_videos": latest_count,
                "previous_videos": previous_count,
                "increase": increase,
            })
    if previous:
        terms.sort(key=lambda item: (item["increase"], item["latest_videos"]), reverse=True)

    return {
        "snapshots": len(latest_two),
        "latest_at": latest["collected_at"],
        "previous_at": previous["collected_at"] if previous else None,
        "comparison_available": previous is not None,
        "terms": terms[:10],
    }


init_db()

if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []
if "alerts" not in st.session_state:
    st.session_state.alerts = load_analyzer_alerts()
else:
    for alert_index, alert in enumerate(st.session_state.alerts):
        if "id" not in alert:
            st.session_state.alerts[alert_index] = save_analyzer_alert(alert)
if "youtube_results" not in st.session_state:
    st.session_state.youtube_results = []
if "posts_analyzed" not in st.session_state:
    st.session_state.posts_analyzed = 0


# --------------------------- Transparent indicator rules ---------------------------
PATTERNS = {
    "Urgency": [
        "urgent", "immediately", "breaking", "right now", "act now",
        "before it's too late", "before it is too late", "last chance",
    ],
    "Fear-inducing language": [
        "panic", "danger", "terrified", "disaster", "everyone will die",
        "emergency", "they don't want you to know",
    ],
    "Sharing pressure": [
        "share this", "forward this", "send to everyone",
        "share immediately", "forward to everyone",
    ],
    "Potential financial threat": [
        "withdraw your money", "bank will close", "account suspended",
        "send your otp", "share your password", "verify your bank account",
        "payment blocked", "upi pin",
    ],
    "Potential impersonation or scam": [
        "police will arrest", "cbi", "digital arrest", "gift card",
        "claim your prize", "click this link", "impersonation scam",
    ],
}


def analyze_post(text):
    lowered = (text or "").lower()
    matches = {}
    for category, phrases in PATTERNS.items():
        found = [phrase for phrase in phrases if phrase in lowered]
        if found:
            matches[category] = found

    # Heuristic triage score only; it is not a probability.
    score = min(100, sum(min(2, len(v)) * 18 for v in matches.values()) + min(10, len(lowered) // 80))
    level = "HIGH" if score >= 55 else "MEDIUM" if score >= 25 else "LOW"
    indicators = list(matches.keys())

    if not indicators:
        recommendation = "No listed indicators detected. This does not guarantee the content is safe."
    elif "Potential financial threat" in indicators or "Potential impersonation or scam" in indicators:
        recommendation = "Do not share OTPs, passwords, UPI PINs, or money. Verify through an official channel and request human review."
    else:
        recommendation = "Check the original source and corroborate the claim before sharing. Request human review."

    return {
        "score": score, "level": level, "indicators": indicators,
        "matches": matches, "recommendation": recommendation,
    }


def record_analysis(text, source):
    # Keep the original transparent rules, and add Gemini as a separate advisory signal.
    result = analyze_post(text)
    ai_result = None
    if analyze_with_ai is not None:
        try:
            ai_result = analyze_with_ai(text)
        except Exception as exc:
            ai_result = {
                "available": False,
                "label": "AI_UNAVAILABLE",
                "confidence": None,
                "explanation": f"AI engine error: {str(exc)[:180]}",
                "model": "Gemini",
            }
    else:
        ai_result = {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": "Could not import ai_engine_gemini.py. Check that it is beside app.py and its dependencies are installed.",
            "model": "Gemini",
        }

    result["ai"] = ai_result
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source, "text": text[:500], "score": result["score"],
        "level": result["level"],
        "indicators": ", ".join(result["indicators"]) or "None detected",
        "ai_label": ai_result.get("label", "AI_UNAVAILABLE"),
        "ai_risk_score": ai_result.get("risk_score"),
        "ai_threat_type": ai_result.get("threat_type", "Unknown"),
        "ai_explanation": ai_result.get("explanation", ""),
    }
    st.session_state.analysis_history.insert(0, entry)
    st.session_state.posts_analyzed += 1

    # Preserve existing rule-based alerts; also create a review alert for AI-high risk.
    ai_high = ai_result.get("available") and (ai_result.get("risk_score") or 0) >= 7
    if (result["level"] in ("HIGH", "MEDIUM") and result["indicators"]) or ai_high:
        st.session_state.alerts.insert(0, save_analyzer_alert(entry))
    return result


def show_result(result):
    left, right = st.columns([1, 2])
    with left:
        st.metric("Heuristic score", f'{result["score"]}/100')
        st.metric("Indicator level", result["level"])
    with right:
        st.write("**Detected indicators**")
        if result["matches"]:
            for category, phrases in result["matches"].items():
                st.write(f"- **{category}:** {', '.join(phrases)}")
        else:
            st.info("No predefined indicators detected.")
        st.write("**Recommended action:**", result["recommendation"])

    ai = result.get("ai")
    st.markdown("### Gemini AI assessment")
    if not ai:
        st.info("No AI assessment was returned.")
    elif not ai.get("available"):
        st.warning(f'Gemini AI unavailable: {ai.get("explanation", "Check API configuration.")}')
    else:
        ai_left, ai_right = st.columns([1, 2])
        with ai_left:
            st.metric("AI risk score", f'{ai.get("risk_score", 0)}/10')
            st.write(f'**AI label:** {ai.get("label", "Unknown")}')
            st.write(f'**Threat type:** {ai.get("threat_type", "Unknown")}')
        with ai_right:
            st.write("**AI explanation**")
            st.write(ai.get("explanation", "No explanation returned."))
        st.caption(f'Model: {ai.get("model", "Gemini")}')

    st.caption("Heuristic and AI scores are advisory triage signals, not proof of malicious activity or calibrated probabilities.")


def get_tesseract():
    windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(windows_path):
        pytesseract.pytesseract.tesseract_cmd = windows_path


def collect_keyword(keyword, max_results):
    if search_youtube is None:
        return [], [], "Could not import search_youtube from social_media.py."
    response = search_youtube(keyword, max_results=max_results)
    if response.get("error"):
        return [], [], response["error"]
    videos = response.get("videos", [])
    analyzed = [
        analyze_post(f'{v.get("title", "")} {v.get("description", "")}')
        for v in videos
    ]
    save_collection(keyword, videos, analyzed)
    return videos, analyzed, None


# --------------------------- Sidebar ---------------------------
st.sidebar.markdown("## ◈ CYBERSHIELD AI")
st.sidebar.caption("THREAT INTELLIGENCE WORKSPACE")
page = st.sidebar.radio(
    "Navigation",
    [
        "Executive Dashboard",
        "Early Indicator Monitor",
        "Social Media Analyzer",
        "Image Analyzer",
        "YouTube Threat Monitor",
        "Claim Verification",
        "Alert Center",
    ],
)
st.sidebar.divider()
st.sidebar.caption("Early-indicator trends are based on repeated YouTube keyword-search snapshots, not a complete live social feed.")

st.markdown(
    """
        <div class="workspace-header">
            <div class="brand-mark">CS</div>
            <div>
                <h1>CyberShield AI</h1>
                <p>Threat intelligence workspace · suspicious-content triage · analyst review</p>
            </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------- Dashboard ---------------------------
if page == "Executive Dashboard":
    history = load_history()
    demo_posts = load_demo_posts()
    demo_alerts = int(demo_posts["level"].isin(["HIGH", "MEDIUM"]).sum()) if not demo_posts.empty else 0
    high_priority = int((demo_posts["level"] == "HIGH").sum()) if not demo_posts.empty else 0
    pending_review = int(demo_posts["status"].astype(str).str.contains("pending|review", case=False, na=False).sum()) if not demo_posts.empty else 0
    avg_risk = round(pd.to_numeric(demo_posts["score"], errors="coerce").dropna().median()) if not demo_posts.empty and pd.to_numeric(demo_posts["score"], errors="coerce").notna().any() else 0

    st.markdown("""
      <div class="hero">
        <div class="hero-eyebrow">SECURITY OPERATIONS&nbsp; / &nbsp;LIVE OVERVIEW</div>
        <h1>Threat intelligence overview</h1>
        <p>A clear view of emerging patterns, risk signals, and items awaiting analyst review.</p>
        <div class="status-row"><span class="status-chip">● MONITORING ACTIVE</span><span class="status-meta">Sample workspace · refreshed just now</span></div>
      </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signals reviewed", st.session_state.posts_analyzed, help="Items analyzed in this app session")
    c2.metric("High-priority signals", f"{high_priority:02d}", help="Demo social posts marked HIGH")
    c3.metric("Awaiting analyst", f"{pending_review:02d}", help="Demo posts whose status indicates review")
    c4.metric("Median risk score", f"{avg_risk}/100", help="Median score from demo website posts; 0 when no scores exist")

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown("### Signal volume")
        st.caption("Collected YouTube results across saved snapshots · not a complete live social feed")
        if not history.empty:
            trend = history.copy()
            trend["collected_at"] = pd.to_datetime(trend["collected_at"], errors="coerce")
            trend = trend.dropna(subset=["collected_at"]).sort_values("collected_at").tail(12)
            if not trend.empty:
                trend["Snapshot"] = trend["collected_at"].dt.strftime("%d %b %H:%M")
                chart = trend.set_index("Snapshot")[["result_count", "flagged_count"]].rename(columns={"result_count":"Results collected", "flagged_count":"Flagged indicators"})
                st.line_chart(chart, use_container_width=True)
            else:
                st.info("Collect a YouTube snapshot to start the signal-volume chart.")
        else:
            st.info("No saved snapshots yet. Open **Early Indicator Monitor** and collect a snapshot to populate this chart.")
    with right:
        st.markdown("### Threat distribution")
        st.caption("Signals by review level in demo social posts")
        if not demo_posts.empty and "level" in demo_posts:
            distribution = demo_posts["level"].fillna("UNCLASSIFIED").astype(str).str.upper().value_counts()
            st.bar_chart(distribution.rename_axis("Risk level").to_frame("Signals"), use_container_width=True)
        else:
            st.info("Publish a sample message from demo_website.py to populate threat distribution.")
        st.markdown("#### System status")
        st.success("Text indicators and local AI engine: available when dependencies are installed")
        st.success("Snapshot history: SQLite persistence enabled")
        st.info("YouTube search requires YOUTUBE_API_KEY. Claims and alerts still need human review.")

    st.markdown("### Latest messages received from Demo Social Media")
    if not demo_posts.empty:
        st.dataframe(demo_posts[["created_at", "author", "message", "score", "level", "indicators", "status"]].head(10), use_container_width=True, hide_index=True)
    else:
        st.info("No demo website posts found yet. Run demo_website.py from this same project folder and publish a demo message.")

    st.markdown("### Recent analysis activity")
    if st.session_state.analysis_history:
        st.dataframe(pd.DataFrame(st.session_state.analysis_history[:10]), use_container_width=True, hide_index=True)
    else:
        st.info("Analyze a message, image, or YouTube result to populate activity.")
    st.warning("Prototype limitation: this system does not continuously monitor every social post, and automated indicators are not proof that content is false or harmful.")


elif page == "Early Indicator Monitor":
    st.subheader("Early Indicator Monitor")
    st.write("Collect timestamped YouTube search snapshots, then compare repeated searches for unusual changes in matching results.")
    st.info(
        "This is a small sampling system. Search results depend on YouTube's search ranking and quota; "
        "counts are not the total number of posts on the platform and a spike is not proof of coordinated activity."
    )

    keyword = st.selectbox("Topic to track", DEFAULT_KEYWORDS)
    max_results = st.slider("Results per collection", min_value=5, max_value=25, value=10, step=5)
    if st.button("Collect current snapshot", type="primary"):
        with st.spinner(f"Collecting YouTube search results for: {keyword}"):
            videos, analyzed, error = collect_keyword(keyword, max_results)
        if error:
            st.error(error)
        else:
            st.session_state.youtube_results = videos
            if videos:
                st.success(f"Saved snapshot: {len(videos)} video results; {sum(1 for x in analyzed if x['indicators'])} had predefined indicators.")
            else:
                st.warning("Search returned no videos. No snapshot was saved.")

    history = load_history()
    if history.empty:
        st.warning("No snapshots have been collected yet. Click **Collect current snapshot**. Repeat this later to begin comparing observations.")
    else:
        st.markdown("### Collected activity over time")
        chosen = history[history["keyword"] == keyword].copy()
        if chosen.empty:
            st.info("No saved snapshots for this keyword yet. Collect one to start its history.")
        else:
            chosen["collected_at"] = pd.to_datetime(chosen["collected_at"], errors="coerce")
            chosen = chosen.dropna(subset=["collected_at"]).sort_values("collected_at")
            chart_data = chosen.set_index("collected_at")[["result_count", "flagged_count"]]
            chart_data.columns = ["Videos returned by search", "Videos with keyword indicators"]
            st.line_chart(chart_data)
            if len(chosen) >= 2:
                previous = chosen.iloc[-2]
                current = chosen.iloc[-1]
                delta = int(current["flagged_count"]) - int(previous["flagged_count"])
                a, b, c = st.columns(3)
                a.metric("Latest results returned", int(current["result_count"]))
                b.metric("Latest results with indicators", int(current["flagged_count"]), delta=delta)
                c.metric("Change from previous snapshot", f"{delta:+d} flagged results")
                if delta >= 3:
                    st.warning("Review signal: more indicator-matching results appeared in this sample than in the previous snapshot. This is a prompt for human review, not proof of a real-world threat spike.")
                elif delta > 0:
                    st.info("Small increase in indicator-matching results. Collect more snapshots and review the source content.")
                else:
                    st.info("No increase in indicator-matching results compared with the previous snapshot.")
            else:
                st.info("One snapshot is not enough to establish a trend. Collect another snapshot later to compare.")
        st.markdown("### Snapshot log")
        st.dataframe(history.sort_values("collected_at", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("### Emerging terms in search results")
    topic_activity = get_emerging_topics(keyword)
    st.caption(
        "Counts distinct sampled videos whose titles or descriptions contain each term. "
        "Search ranking changes can affect these counts; an increase is not proof of coordinated activity."
    )
    if topic_activity["snapshots"] == 0:
        st.info("Collect a snapshot with video results to extract candidate terms.")
    else:
        if not topic_activity["comparison_available"]:
            st.info("One snapshot provides a starting vocabulary. Collect another snapshot later to identify terms that increase.")
        if topic_activity["terms"]:
            topic_frame = pd.DataFrame(topic_activity["terms"]).rename(
                columns={
                    "term": "Term",
                    "latest_videos": "Latest sample videos",
                    "previous_videos": "Previous sample videos",
                    "increase": "Increase",
                }
            )
            st.dataframe(topic_frame, use_container_width=True, hide_index=True)
        elif topic_activity["comparison_available"]:
            st.info("No extracted terms increased in the latest sample compared with the previous snapshot.")

    st.markdown("### Messages published on the Demo Social Media website")
    demo_posts = load_demo_posts()
    if demo_posts.empty:
        st.info("No demo posts received yet. Publish a message in demo_website.py; it will appear here when both apps use the same project folder.")
    else:
        st.dataframe(
            demo_posts[["created_at", "author", "message", "score", "level", "indicators", "status"]].head(20),
            use_container_width=True,
            hide_index=True,
        )
        demo_flagged = demo_posts[demo_posts["level"].isin(["HIGH", "MEDIUM"])]
        if not demo_flagged.empty:
            st.warning(f"{len(demo_flagged)} demo message(s) currently match the HIGH/MEDIUM indicator rules. These are simulated messages for demonstration, not confirmed real-world threats.")
    st.markdown("### How to use this as an early indicator")
    st.markdown(
        "1. Collect a snapshot now.  2. Collect again later using the same keyword.  "
        "3. Compare the number of results matching the predefined indicators.  "
        "4. Open the video sources and have a person review them before escalating."
    )


elif page == "Social Media Analyzer":
    st.subheader("Social Media Analyzer")
    text = st.text_area("Content to analyze", height=180, placeholder="Paste a public post, message, caption, or transcript excerpt...")
    if st.button("Analyze text", type="primary"):
        if not text.strip():
            st.warning("Enter some text first.")
        else:
            show_result(record_analysis(text.strip(), "Manual text"))


elif page == "Image Analyzer":
    st.subheader("Image Analyzer")
    st.write("OCR extracts readable text from the uploaded image; the detector checks that extracted text for predefined indicators.")
    uploaded = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg", "webp"])
    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded image", use_container_width=True)
        if st.button("Extract and analyze text", type="primary"):
            try:
                get_tesseract()
                extracted = pytesseract.image_to_string(image).strip()
                st.text_area("OCR-extracted text", value=extracted, height=150)
                if extracted:
                    show_result(record_analysis(extracted, "Image OCR"))
                else:
                    st.warning("No readable text detected. Try a clearer image.")
            except Exception as exc:
                st.error(f"OCR failed: {exc}")


elif page == "YouTube Threat Monitor":
    st.subheader("YouTube Threat Monitor")
    st.write("Search public YouTube video metadata and inspect available titles and descriptions.")
    st.info("This is keyword search, not a live feed. It does not analyze video audio or every comment.")
    if search_youtube is None:
        st.error("Could not import search_youtube from social_media.py. Save that file beside app.py.")
    else:
        with st.form("youtube_search_form"):
            query = st.text_input("Search topic", value="cybercrime India")
            max_results = st.slider("Maximum results", min_value=1, max_value=25, value=10)
            submitted = st.form_submit_button("Search YouTube", type="primary")
        if submitted:
            if not query.strip():
                st.warning("Enter a search topic.")
            else:
                with st.spinner("Searching YouTube..."):
                    response = search_youtube(query.strip(), max_results=max_results)
                if response.get("error"):
                    st.session_state.youtube_results = []
                    st.error(response["error"])
                else:
                    videos = response.get("videos", [])
                    st.session_state.youtube_results = videos
                    st.success(f"Retrieved {len(videos)} result(s).")
        for index, video in enumerate(st.session_state.youtube_results):
            result = analyze_post(f'{video.get("title", "")} {video.get("description", "")}')
            with st.container(border=True):
                st.markdown(f'### [{video.get("title", "Untitled")}]({video.get("url", "")})')
                st.caption(f'Channel: {video.get("channel", "Unknown")} • Published: {video.get("published_at", "Unknown")}')
                st.write(video.get("description", "")[:600])
                st.write(f'**Indicator level:** {result["level"]} • **Heuristic score:** {result["score"]}/100')
                st.write("**Indicators:** " + (", ".join(result["indicators"]) or "None detected"))
                if st.button("Run Gemini AI analysis", key=f"youtube_ai_{index}"):
                    if analyze_with_ai is None:
                        st.error("Gemini engine not available. Check ai_engine_gemini.py and installed dependencies.")
                    else:
                        with st.spinner("Analyzing this result with Gemini..."):
                            try:
                                ai_video = analyze_with_ai(
                                    f'{video.get("title", "")}\n{video.get("description", "")}'
                                )
                                if ai_video.get("available"):
                                    st.success(
                                        f'AI: {ai_video.get("label")} · '
                                        f'Risk {ai_video.get("risk_score", 0)}/10 · '
                                        f'{ai_video.get("threat_type", "Unknown")}'
                                    )
                                    st.write(ai_video.get("explanation", ""))
                                else:
                                    st.warning(ai_video.get("explanation", "Gemini analysis unavailable."))
                            except Exception as exc:
                                st.error(f"Gemini analysis failed: {exc}")

                if st.button("Create review alert", key=f"youtube_alert_{index}"):
                    entry = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "YouTube search",
                        "text": video.get("title", ""),
                        "score": result["score"],
                        "level": result["level"],
                        "indicators": ", ".join(result["indicators"]) or "None detected",
                        "reviewed": False,
                        "url": video.get("url", ""),
                    }
                    st.session_state.alerts.insert(0, save_analyzer_alert(entry))
                    st.session_state.analysis_history.insert(0, entry)
                    st.session_state.posts_analyzed += 1
                    st.success("Alert added for human review.")


elif page == "Claim Verification":
    st.subheader("Claim Verification")
    st.write("Search for candidate sources about a claim. Results are leads for investigation, not proof.")
    claim = st.text_area("Claim to investigate", placeholder="Example: Has the government banned all online payments in India?")
    if search_claim is None:
        st.error("Could not import search_claim from claim_verifier.py.")
    elif st.button("Search evidence", type="primary"):
        if not claim.strip():
            st.warning("Enter a claim first.")
        else:
            try:
                results = search_claim(claim.strip())
                if not results:
                    st.warning("No results returned.")
                else:
                    if assess_claim_with_sources is None:
                        assessment = {
                            "available": False,
                            "assessment": "INCONCLUSIVE",
                            "explanation": "Gemini claim assessment is unavailable.",
                        }
                    else:
                        with st.spinner("Comparing the claim with retrieved source snippets..."):
                            assessment = assess_claim_with_sources(claim.strip(), results)

                    if assessment.get("available"):
                        st.warning(
                            f'AI preliminary assessment: {assessment["assessment"]}. '
                            "This is advisory and based only on search-result snippets."
                        )
                        st.write("**Evidence summary:**", assessment.get("explanation", ""))
                        st.caption(
                            f'Model: {assessment.get("model", "Gemini")}. '
                            "Open and verify the linked sources before making a decision."
                        )
                    else:
                        st.warning(
                            "Assessment: INCONCLUSIVE — "
                            f'{assessment.get("explanation", "Sources remain unverified.")}'
                        )
                    for result in results:
                        st.markdown(f'**[{result.get("title", "Untitled")}]({result.get("url", "")})**')
                        st.write(result.get("snippet", ""))
                        st.divider()
            except Exception as exc:
                st.error(f"Claim search failed: {exc}")


elif page == "Alert Center":
    st.subheader("Alert Center")
    st.markdown("### Alerts from the separate Demo Social Media website")
    demo_posts = load_demo_posts()
    if demo_posts.empty:
        st.info("No demo messages yet. Publish a message on demo_website.py to send it into this monitoring dashboard.")
    else:
        demo_alerts = demo_posts[demo_posts["level"].isin(["HIGH", "MEDIUM"])]
        if demo_alerts.empty:
            st.success("Demo website is connected, but no messages matched the current MEDIUM/HIGH rules.")
        else:
            for _, row in demo_alerts.iterrows():
                with st.container(border=True):
                    st.error(f'🚨 {row["level"]} INDICATOR — Demo post #{row["id"]}')
                    st.caption(f'{row["created_at"]} • Score: {row["score"]}/100 • Status: {row["status"]}')
                    st.write(row["message"])
                    st.write("**Detected indicators:**", row["indicators"])
                    st.caption("This is a simulated demo post. A keyword match is not proof that a real threat exists.")
    st.divider()
    st.markdown("### Alerts from the CyberShield AI analyzer")
    if not st.session_state.alerts:
        st.info("No additional analyzer alerts yet. Analyze content or create a review alert from a YouTube result.")
    else:
        for idx, alert in enumerate(st.session_state.alerts):
            with st.container(border=True):
                st.markdown(f'**{alert.get("level", "LOW")} risk — {alert.get("source", "Unknown source")}**')
                st.caption(f'{alert.get("time", "")} • Score: {alert.get("score", 0)}/100')
                st.write(alert.get("text", ""))
                st.write("**Indicators:**", alert.get("indicators", "None detected"))
                if alert.get("url"):
                    st.markdown(f'[Open source video]({alert["url"]})')
                if alert.get("reviewed"):
                    st.success("Reviewed")
                elif st.button("Mark as reviewed", key=f"review_{idx}"):
                    mark_analyzer_alert_reviewed(alert["id"])
                    st.session_state.alerts[idx]["reviewed"] = True
                    st.rerun()


st.divider()
st.markdown(
    '<p class="small-note">CyberShield AI is a prototype for preliminary triage. Search sampling, keyword matches, and heuristic scores can produce false positives and false negatives. Human review and independent verification are required before action.</p>',
    unsafe_allow_html=True,
)
