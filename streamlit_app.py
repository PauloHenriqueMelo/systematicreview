#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# -------------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Minerva Reviewer — Blinded Validation",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------------
# CONFIG CONSTANTS
# -------------------------------------------------------------------
GAS_URL = "https://script.google.com/macros/s/AKfycbwQ-XHCjJd2s6sENQJh6Z9Qm-8De9J8_UThZ-pM1rGgm04FCT-qPBSyBFaqOoSreZ1-/exec"
GAS_TOKEN = "MINERVA_SECRET"
PROMPTS_FILE = "prompts.csv"

# SR → TITLE MAP
SR_TITLES = {
    1: "Eve Pathology",
    2: "Carmel EHR",
    3: "Lauren Imaging",
    4: "Alex Surgical AI",
    5: "Paulo Registry"
}

# -------------------------------------------------------------------
# LOAD PROMPTS
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_prompts() -> dict:
    try:
        p = pd.read_csv(PROMPTS_FILE)
    except Exception:
        p = pd.read_csv(PROMPTS_FILE, sep=None, engine="python")
    req = {"SR", "Prompt"}
    if not req.issubset(p.columns):
        st.error("⚠️ prompts.csv must have columns: SR, Prompt")
        st.stop()
    p["SR"] = pd.to_numeric(p["SR"], errors="coerce").fillna(0).astype(int)
    return {int(r.SR): str(r.Prompt) for r in p.itertuples(index=False)}

# -------------------------------------------------------------------
# FETCH SHEET
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_sheet(only_unreviewed=False) -> pd.DataFrame:
    r = requests.get(GAS_URL, params={"token": GAS_TOKEN}, timeout=25)
    js = r.json()
    if not js.get("ok"):
        st.error(js.get("error", "❌ Failed to load sheet"))
        st.stop()

    df = pd.DataFrame(js["rows"])
    for c in ["Title","Abstract","SR","Poenaru_Decision","AI","AI_Justification","_row"]:
        if c not in df.columns:
            df[c] = ""

    df["_row"] = pd.to_numeric(df["_row"], errors="coerce").fillna(0).astype(int)
    df["SR"] = pd.to_numeric(df["SR"], errors="coerce").fillna(0).astype(int)

    if only_unreviewed:
        df = df[df["Poenaru_Decision"].astype(str).str.strip().eq("")]

    return df.sort_values("_row").reset_index(drop=True)

# -------------------------------------------------------------------
# SAVE
# -------------------------------------------------------------------
def save_row(sheet_row:int, fields:dict)->bool:
    try:
        r = requests.post(
            GAS_URL,
            params={"token": GAS_TOKEN},
            json={"row": int(sheet_row), "fields": fields},
            timeout=25
        )
        js = r.json()
        return bool(js.get("ok"))
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
st.sidebar.title("⚙️ Controls")
only_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
prompts_map = load_prompts()
df = fetch_sheet(only_unreviewed)
total = len(df)

# Styled stats card in sidebar
st.sidebar.markdown(f"""
<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 1.5rem; 
            border-radius: 16px; 
            margin: 1rem 0;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);'>
    <div style='font-size: 0.9rem; color: rgba(255,255,255,0.8); font-weight: 500; margin-bottom: 0.3rem;'>
        TOTAL RECORDS
    </div>
    <div style='font-size: 2.5rem; color: white; font-weight: 700; line-height: 1;'>
        {total}
    </div>
</div>
""", unsafe_allow_html=True)

if "pos" not in st.session_state:
    st.session_state.pos = 0

if total == 0:
    st.markdown("""
    <div style='text-align: center; padding: 4rem 2rem;'>
        <div style='font-size: 4rem; margin-bottom: 1rem;'>🎉</div>
        <div style='font-size: 1.8rem; font-weight: 600; color: #10b981;'>All Reviews Complete!</div>
        <div style='font-size: 1rem; color: rgba(255,255,255,0.6); margin-top: 0.5rem;'>Great work on finishing the validation.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

sheet_rows = df["_row"].tolist()
current_row = df.iloc[st.session_state.pos]["_row"]

jump = st.sidebar.selectbox(
    "Jump to sheet row",
    options=sheet_rows,
    index=sheet_rows.index(current_row)
)
if jump != current_row:
    st.session_state.pos = sheet_rows.index(jump)
    st.rerun()

# -------------------------------------------------------------------
# CURRENT ROW
# -------------------------------------------------------------------
row = df.iloc[st.session_state.pos]
sheet_row_num = int(row["_row"])
title = str(row["Title"])
abstract = str(row["Abstract"])
sr_val = int(row["SR"]) if pd.notna(row["SR"]) else 0
sr_prompt = prompts_map.get(sr_val, "")
sr_label = SR_TITLES.get(sr_val, f"SR {sr_val}")

decision_val = str(row["Poenaru_Decision"]).strip()
ai_val = str(row["AI"]).strip().lower()
ai_just = str(row["AI_Justification"]) if pd.notna(row["AI_Justification"]) else ""

# -------------------------------------------------------------------
# BACKGROUND COLOR BASED ON AI
# -------------------------------------------------------------------
if ai_val in ["1", "yes"]:
    bg_color = "#0a2f1a"  # softer dark green
    accent_color = "#10b981"
elif ai_val in ["0", "no"]:
    bg_color = "#2d1115"  # softer dark red
    accent_color = "#ef4444"
else:
    bg_color = "#0e1117"  # neutral
    accent_color = "#667eea"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {{
        background-color: {bg_color} !important;
        font-family: 'Inter', sans-serif;
    }}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(255,255,255,0.2);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(255,255,255,0.3);
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------------
# HEADER
# -------------------------------------------------------------------
st.markdown(
    f"""
    <div style='text-align: center; margin-bottom: 2rem; padding: 2rem 0;'>
        <div style='font-size: 3.5rem; margin-bottom: 0.5rem;'>🧠</div>
        <h1 style='font-size: 2.8rem; font-weight: 700; margin: 0; 
                   background: linear-gradient(135deg, {accent_color} 0%, #a78bfa 100%);
                   -webkit-background-clip: text;
                   -webkit-text-fill-color: transparent;
                   background-clip: text;'>
            Minerva Reviewer
        </h1>
        <div style='font-size: 1.1rem; color: rgba(255,255,255,0.5); font-weight: 500; margin-top: 0.5rem;'>
            Blinded Validation Protocol
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Progress indicator
progress_pct = ((st.session_state.pos + 1) / total) * 100
st.markdown(
    f"""
    <div style='background: rgba(255,255,255,0.05); 
                border-radius: 12px; 
                padding: 1rem 1.5rem; 
                margin-bottom: 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);'>
        <div>
            <span style='font-size: 0.85rem; color: rgba(255,255,255,0.5); font-weight: 600;'>ROW</span>
            <span style='font-size: 1.3rem; color: white; font-weight: 700; margin-left: 0.5rem;'>{sheet_row_num}</span>
        </div>
        <div style='flex: 1; margin: 0 2rem;'>
            <div style='background: rgba(255,255,255,0.1); height: 8px; border-radius: 10px; overflow: hidden;'>
                <div style='background: linear-gradient(90deg, {accent_color} 0%, #a78bfa 100%); 
                            height: 100%; 
                            width: {progress_pct}%;
                            transition: width 0.3s ease;'></div>
            </div>
        </div>
        <div>
            <span style='font-size: 1.3rem; color: white; font-weight: 700;'>{st.session_state.pos + 1}</span>
            <span style='font-size: 0.85rem; color: rgba(255,255,255,0.5); font-weight: 600;'> / {total}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------------
# MAIN CONTENT
# -------------------------------------------------------------------
col_main, col_side = st.columns([2.5, 1], gap="large")

with col_main:
    # Title card
    st.markdown(
        f"""
        <div style='background: rgba(255,255,255,0.03); 
                    border-left: 4px solid {accent_color};
                    border-radius: 12px; 
                    padding: 1.5rem; 
                    margin-bottom: 1.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);'>
            <div style='font-size: 0.75rem; 
                        color: rgba(255,255,255,0.5); 
                        font-weight: 600; 
                        letter-spacing: 1px; 
                        margin-bottom: 0.8rem;'>
                📄 STUDY TITLE
            </div>
            <div style='font-size: 1.3rem; 
                        color: white; 
                        font-weight: 600; 
                        line-height: 1.5;'>
                {title or '<em style="color: rgba(255,255,255,0.3);">(no title provided)</em>'}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Abstract card
    st.markdown(
        f"""
        <div style='background: rgba(255,255,255,0.03); 
                    border-radius: 12px; 
                    padding: 1.5rem; 
                    margin-bottom: 1.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);'>
            <div style='font-size: 0.75rem; 
                        color: rgba(255,255,255,0.5); 
                        font-weight: 600; 
                        letter-spacing: 1px; 
                        margin-bottom: 1rem;'>
                📋 ABSTRACT
            </div>
            <div style='font-size: 1rem; 
                        color: rgba(255,255,255,0.85); 
                        line-height: 1.7;
                        max-height: 400px;
                        overflow-y: auto;'>
                {abstract or '<em style="color: rgba(255,255,255,0.3);">(no abstract provided)</em>'}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # SR prompt card
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%); 
                    border: 1px solid rgba(102, 126, 234, 0.3);
                    border-radius: 12px; 
                    padding: 1.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);'>
            <div style='font-size: 0.75rem; 
                        color: rgba(255,255,255,0.5); 
                        font-weight: 600; 
                        letter-spacing: 1px; 
                        margin-bottom: 0.5rem;'>
                🧬 SYSTEMATIC REVIEW
            </div>
            <div style='font-size: 1.4rem; 
                        color: white; 
                        font-weight: 700; 
                        margin-bottom: 1rem;'>
                {sr_label}
            </div>
            <div style='font-size: 0.95rem; 
                        color: rgba(255,255,255,0.8); 
                        line-height: 1.6;
                        background: rgba(0,0,0,0.2);
                        padding: 1rem;
                        border-radius: 8px;'>
                {sr_prompt or '<em style="color: rgba(255,255,255,0.4);">(no prompt found in prompts.csv)</em>'}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------------------------
# REVIEW PANEL
# -------------------------------------------------------------------
with col_side:
    st.markdown(
        f"""
        <div style='background: rgba(255,255,255,0.05); 
                    border-radius: 16px; 
                    padding: 1.8rem; 
                    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
                    border: 1px solid rgba(255,255,255,0.1);'>
            <div style='font-size: 0.75rem; 
                        color: rgba(255,255,255,0.5); 
                        font-weight: 600; 
                        letter-spacing: 1px; 
                        margin-bottom: 0.5rem;'>
                🧩 YOUR DECISION
            </div>
            <div style='font-size: 1.2rem; 
                        color: white; 
                        font-weight: 600; 
                        margin-bottom: 1.5rem;'>
                Inclusion Criteria
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    dec_opts = ["", "Yes", "No"]
    decision = st.selectbox(
        "Does this study meet inclusion criteria?",
        dec_opts,
        index=dec_opts.index(decision_val) if decision_val in dec_opts else 0,
        label_visibility="collapsed"
    )

    if st.button("💾 Save Decision", type="primary", use_container_width=True):
        if not decision:
            st.warning("⚠️ Please select Yes or No before saving.")
        else:
            payload = {
                "Poenaru_Decision": decision,
                "Reviewed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            ok = save_row(sheet_row_num, payload)
            if ok:
                st.success(f"✅ Decision saved for Row {sheet_row_num}")
                fetch_sheet.clear()
                st.rerun()
            else:
                st.error("❌ Failed to save decision")

    # Show AI decision after save
    if decision_val in ["Yes", "No"]:
        st.markdown("<br>", unsafe_allow_html=True)
        
        if ai_val in ["1", "yes"]:
            ai_decision_text = "YES (Include)"
            ai_color = "#10b981"
            ai_icon = "✓"
        elif ai_val in ["0", "no"]:
            ai_decision_text = "NO (Exclude)"
            ai_color = "#ef4444"
            ai_icon = "✗"
        else:
            ai_decision_text = "Unavailable"
            ai_color = "#6b7280"
            ai_icon = "?"
        
        st.markdown(
            f"""
            <div style='background: rgba(255,255,255,0.05); 
                        border-radius: 12px; 
                        padding: 1.5rem;
                        border: 1px solid rgba(255,255,255,0.1);'>
                <div style='font-size: 0.75rem; 
                            color: rgba(255,255,255,0.5); 
                            font-weight: 600; 
                            letter-spacing: 1px; 
                            margin-bottom: 1rem;'>
                    🤖 AI DECISION (UNBLINDED)
                </div>
                <div style='background: rgba({ai_color[1:]}, 0.1); 
                            border: 2px solid {ai_color};
                            border-radius: 8px; 
                            padding: 1rem;
                            text-align: center;'>
                    <div style='font-size: 2rem; margin-bottom: 0.3rem;'>{ai_icon}</div>
                    <div style='font-size: 1.1rem; 
                                color: {ai_color}; 
                                font-weight: 700;'>
                        {ai_decision_text}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if ai_just.strip():
            st.markdown(
                f"""
                <div style='background: rgba(255,255,255,0.03); 
                            border-radius: 8px; 
                            padding: 1rem; 
                            margin-top: 1rem;
                            font-size: 0.9rem; 
                            color: rgba(255,255,255,0.7); 
                            line-height: 1.6;'>
                    <strong style='color: rgba(255,255,255,0.9);'>Justification:</strong><br><br>
                    {ai_just}
                </div>
                """,
                unsafe_allow_html=True
            )

        # Agreement indicator
        if ai_val in ["1", "yes", "0", "no"]:
            match = (
                (decision_val == "Yes" and ai_val in ["1", "yes"]) or
                (decision_val == "No" and ai_val in ["0", "no"])
            )
            
            if match:
                agreement_color = "#10b981"
                agreement_text = "You and AI Agreed"
                agreement_icon = "🤝"
            else:
                agreement_color = "#f59e0b"
                agreement_text = "You and AI Disagreed"
                agreement_icon = "⚠️"
            
            st.markdown(
                f"""
                <div style='background: linear-gradient(135deg, rgba({agreement_color[1:]}, 0.2) 0%, rgba({agreement_color[1:]}, 0.05) 100%); 
                            border: 2px solid {agreement_color};
                            border-radius: 8px; 
                            padding: 1rem; 
                            margin-top: 1rem;
                            text-align: center;'>
                    <div style='font-size: 1.5rem; margin-bottom: 0.3rem;'>{agreement_icon}</div>
                    <div style='font-size: 0.95rem; 
                                color: {agreement_color}; 
                                font-weight: 700;'>
                        {agreement_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# -------------------------------------------------------------------
# NAVIGATION
# -------------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)

nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])

with nav_col1:
    prev_disabled = st.session_state.pos == 0
    if st.button("⬅️ Previous", use_container_width=True, disabled=prev_disabled):
        st.session_state.pos -= 1
        st.rerun()

with nav_col2:
    st.markdown(
        f"""
        <div style='text-align: center; padding-top: 0.5rem;'>
            <span style='font-size: 1rem; color: rgba(255,255,255,0.6);'>
                Review <strong style='color: white;'>{st.session_state.pos + 1}</strong> of <strong style='color: white;'>{total}</strong>
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

with nav_col3:
    next_disabled = st.session_state.pos >= total - 1
    if st.button("Next ➡️", use_container_width=True, disabled=next_disabled):
        st.session_state.pos += 1
        st.rerun()

# -------------------------------------------------------------------
# ENHANCED STYLING
# -------------------------------------------------------------------
st.markdown("""
<style>
/* Button styling */
.stButton>button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    transition: all 0.3s ease !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 1.2rem !important;
}

.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3) !important;
    border-color: rgba(255,255,255,0.3) !important;
}

.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important;
}

.stButton>button:disabled {
    opacity: 0.3 !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1f2e 0%, #0e1117 100%);
    border-right: 1px solid rgba(255,255,255,0.1);
}

[data-testid="stSidebar"] .stSelectbox {
    margin-top: 1rem;
}

/* Select box styling */
.stSelectbox>div>div {
    background-color: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
}

/* Checkbox styling */
.stCheckbox {
    background: rgba(255,255,255,0.03);
    padding: 0.8rem;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
}

/* Alert styling */
.stAlert {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    backdrop-filter: blur(10px);
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: rgba(255,255,255,0.03) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

/* Remove default margins */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}
</style>
""", unsafe_allow_html=True)
