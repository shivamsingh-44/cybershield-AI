import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
import pytesseract

try:
    from ai_engine import analyze_with_ai
except Exception:
    analyze_with_ai = None

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

st.set_page_config(
    page_title="CyberShield AI | Threat Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp { background: #061A19; color: #E8F7F4; }
      [data-testid="stSidebar"] { background: #041715; }
      .hero { padding: 1.4rem 1.6rem; border-radius: 18px;
        background: linear-gradient(120deg, #0D3B36, #102725 70%);
        border: 1px solid #28534D; margin-bottom: 1rem; }
      .hero h1 { margin: 0; color: #F4FFFC; font-size: 2.1rem; }
      .hero p { color: #B7D2CD; margin-bottom: 0; }
      .small-note { color: #91AAA7; font-size: .86rem; }
      div[data-testid="stMetric"] { background: #102725;
        border: 1px solid #28534D; padding: 14px; border-radius: 14px; }
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
                channel TEXT,
                published_at TEXT,
                url TEXT,
                score INTEGER,
                level TEXT,
                indicators TEXT,
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )
        """)


def load_demo_posts():
    """Read messages published on demo_website.py when both apps share this folder."""
    demo_db = APP_DIR / "cybershield_demo.db"
    if not demo_db.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(demo_db) as conn:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(demo_posts)").fetchall()
            }
            base_columns = "id, created_at, author, message, score, level, indicators, status"
            ai_columns = [
                "ai_label", "ai_confidence", "ai_explanation", "ai_model", "ai_available"
            ]
            selected = base_columns + "".join(
                f", {column}" for column in ai_columns if column in columns
            )
            return pd.read_sql_query(
                f"SELECT {selected} FROM demo_posts ORDER BY id DESC",
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
                (collection_id, video_id, title, channel, published_at, url, score, level, indicators)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    collection_id, video_id, video.get("title", ""),
                    video.get("channel", ""), video.get("published_at", ""),
                    video.get("url", ""), result["score"], result["level"],
                    ", ".join(result["indicators"]),
                ),
            )
    return timestamp


init_db()

if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []
if "alerts" not in st.session_state:
    st.session_state.alerts = []
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
    result = analyze_post(text)
    ai_result = (
        analyze_with_ai(text)
        if analyze_with_ai is not None
        else {
            "available": False,
            "label": "AI_UNAVAILABLE",
            "confidence": None,
            "explanation": "AI engine could not be imported.",
            "model": None,
        }
    )
    result["ai"] = ai_result

    # AI can raise a low heuristic score for review, but never certifies safety.
    combined_score = int(result["score"])
    if ai_result.get("available") and ai_result.get("label") == "AI_SUSPICIOUS":
        confidence = float(ai_result.get("confidence") or 0)
        combined_score = max(combined_score, min(100, max(20, round(confidence * 40))))
    result["combined_score"] = combined_score
    result["combined_level"] = (
        "HIGH" if combined_score >= 55 else "MEDIUM" if combined_score >= 25 else "LOW"
    )

    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source, "text": text[:500], "score": result["score"],
        "level": result["combined_level"],
        "indicators": ", ".join(result["indicators"]) or "None detected",
        "ai_label": ai_result.get("label", "AI_UNAVAILABLE"),
        "ai_confidence": ai_result.get("confidence"),
        "ai_explanation": ai_result.get("explanation", ""),
    }
    st.session_state.analysis_history.insert(0, entry)
    st.session_state.posts_analyzed += 1
    if result["combined_level"] in ("HIGH", "MEDIUM") and (
        result["indicators"] or ai_result.get("label") == "AI_SUSPICIOUS"
    ):
        st.session_state.alerts.insert(0, {**entry, "reviewed": False})
    return result


def show_result(result):
    left, right = st.columns([1, 2])
    with left:
        st.metric("Heuristic score", f'{result["score"]}/100')
        st.metric("Combined triage", result.get("combined_level", result["level"]))
    with right:
        st.write("**Detected indicators**")
        if result["matches"]:
            for category, phrases in result["matches"].items():
                st.write(f"- **{category}:** {', '.join(phrases)}")
        else:
            st.info("No predefined keyword indicators detected.")
        st.write("**Recommended action:**", result["recommendation"])

    ai_result = result.get("ai", {})
    st.markdown("### Local AI classification")
    if ai_result.get("available"):
        confidence = ai_result.get("confidence")
        confidence_text = f"{float(confidence):.2%}" if confidence is not None else "N/A"
        st.info(f'**{ai_result.get("label", "Unknown")}** • Model confidence: {confidence_text}')
        st.write(ai_result.get("explanation", ""))
        st.caption(ai_result.get("scope_note", "Model predictions can be wrong; human review is required."))
    else:
        st.warning(ai_result.get("explanation", "AI analysis unavailable; rule-based analysis is shown."))
    st.caption("Heuristic score and AI confidence are different measures. Neither is proof of malicious activity or proof that content is safe.")


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
st.sidebar.markdown("## 🛡️ CyberShield AI")
st.sidebar.caption("Early threat intelligence prototype")
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
    <div class="hero">
      <h1>🛡️ CyberShield AI</h1>
      <p>Social media threat signals • suspicious-content triage • human-reviewed alerts</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------- Dashboard ---------------------------
if page == "Executive Dashboard":
    st.subheader("Executive Dashboard")
    history = load_history()
    c1, c2, c3, c4 = st.columns(4)
    demo_posts = load_demo_posts()
    demo_alerts = int(demo_posts["level"].isin(["HIGH", "MEDIUM"]).sum()) if not demo_posts.empty else 0
    c1.metric("Items analyzed this session", st.session_state.posts_analyzed)
    c2.metric("Alerts created this session", len(st.session_state.alerts) + demo_alerts)
    c3.metric("Saved collection snapshots", len(history))
    c4.metric("Demo website posts", len(demo_posts))
    if not demo_posts.empty:
        st.markdown("### Latest messages received from Demo Social Media")
        dashboard_columns = [
            "created_at", "author", "message", "score", "level", "indicators", "status"
        ]
        dashboard_columns += [
            column for column in ("ai_label", "ai_confidence", "ai_explanation")
            if column in demo_posts.columns
        ]
        st.dataframe(
            demo_posts[dashboard_columns].head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No demo website posts found yet. Run demo_website.py from this same project folder and publish a demo message.")
    st.markdown("### Recent analysis activity")
    if st.session_state.analysis_history:
        st.dataframe(pd.DataFrame(st.session_state.analysis_history[:10]), use_container_width=True, hide_index=True)
    else:
        st.info("Analyze a message, image, or YouTube result to populate activity.")
    st.markdown("### System status")
    st.success("YouTube keyword search: available when YOUTUBE_API_KEY is set")
    st.success("Persistent snapshot history: SQLite database")
    st.warning("This prototype does not continuously monitor every YouTube post or independently verify claims.")


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

    st.markdown("### Messages published on the Demo Social Media website")
    demo_posts = load_demo_posts()
    if demo_posts.empty:
        st.info("No demo posts received yet. Publish a message in demo_website.py; it will appear here when both apps use the same project folder.")
    else:
        monitor_columns = [
            "created_at", "author", "message", "score", "level", "indicators", "status"
        ]
        monitor_columns += [
            column for column in ("ai_label", "ai_confidence", "ai_explanation")
            if column in demo_posts.columns
        ]
        st.dataframe(
            demo_posts[monitor_columns].head(20),
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
                    st.error(response["error"])
                else:
                    videos = response.get("videos", [])
                    st.session_state.youtube_results = videos
                    st.success(f"Retrieved {len(videos)} result(s).")
                    for index, video in enumerate(videos):
                        result = analyze_post(f'{video.get("title", "")} {video.get("description", "")}')
                        with st.container(border=True):
                            st.markdown(f'### [{video.get("title", "Untitled")}]({video.get("url", "")})')
                            st.caption(f'Channel: {video.get("channel", "Unknown")} • Published: {video.get("published_at", "Unknown")}')
                            st.write(video.get("description", "")[:600])
                            st.write(f'**Indicator level:** {result["level"]} • **Heuristic score:** {result["score"]}/100')
                            st.write("**Indicators:** " + (", ".join(result["indicators"]) or "None detected"))
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
                                st.session_state.alerts.insert(0, entry)
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
                    st.warning("Assessment: INCONCLUSIVE — sources have not been independently verified.")
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
                    if "ai_label" in row.index:
                        st.write("**AI classification:**", row.get("ai_label", "AI_UNAVAILABLE"))
                        confidence = row.get("ai_confidence")
                        if pd.notna(confidence):
                            st.caption(
                                f"Model confidence: {float(confidence):.2%}; this is confidence in "
                                "the model label, not a probability of fraud."
                            )
                        if row.get("ai_explanation"):
                            st.write("**AI explanation:**", row.get("ai_explanation"))
                    st.caption("This is a simulated demo post. AI and keyword signals can be wrong; human review is required.")
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
                    st.session_state.alerts[idx]["reviewed"] = True
                    st.rerun()


st.divider()
st.markdown(
    '<p class="small-note">CyberShield AI is a prototype for preliminary triage. Search sampling, keyword matches, and heuristic scores can produce false positives and false negatives. Human review and independent verification are required before action.</p>',
    unsafe_allow_html=True,
)
