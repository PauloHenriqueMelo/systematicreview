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
    page_title="Specialist Reviewer - Blinded Validation",
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
st.sidebar.markdown("### ⚙️ Controls")
only_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
prompts_map = load_prompts()
df = fetch_sheet(only_unreviewed)
total = len(df)

st.sidebar.markdown(f"""
<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 0.8rem 1rem; 
            border-radius: 10px; 
            margin: 0.5rem 0;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3);'>
    <div style='font-size: 0.65rem; color: rgba(255,255,255,0.75); font-weight: 600; letter-spacing: 0.8px;'>
        TOTAL RECORDS
    </div>
    <div style='font-size: 1.8rem; color: white; font-weight: 700; line-height: 1; margin-top: 0.2rem;'>
        {total}
    </div>
</div>
""", unsafe_allow_html=True)

if "pos" not in st.session_state:
    st.session_state.pos = 0
if "decision_saved" not in st.session_state:
    st.session_state.decision_saved = False
if "last_row" not in st.session_state:
    st.session_state.last_row = None

if total == 0:
    st.markdown("""
    <div style='text-align: center; padding: 2.5rem 1rem;'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🎉</div>
        <div style='font-size: 1.3rem; font-weight: 700; color: #10b981;'>All Done!</div>
        <div style='font-size: 0.85rem; color: rgba(255,255,255,0.5); margin-top: 0.2rem;'>Validation complete.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

sheet_rows = df["_row"].tolist()
current_row = df.iloc[st.session_state.pos]["_row"]

jump = st.sidebar.selectbox(
    "Jump to row",
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

# Reset flag when moving to a new row
if st.session_state.last_row != sheet_row_num:
    st.session_state.decision_saved = False
    st.session_state.last_row = sheet_row_num

# -------------------------------------------------------------------
# HEADER
# -------------------------------------------------------------------
progress_pct = ((st.session_state.pos + 1) / total) * 100
st.markdown(
    f"""
    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.8rem 1rem; background: rgba(255,255,255,0.02); border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);'>
        <div style='display: flex; align-items: center; gap: 0.8rem;'>
            <div style='font-size: 1.8rem;'>🧠</div>
            <div>
                <div style='font-size: 1.3rem; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #a78bfa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Specialist Reviewer</div>
                <div style='font-size: 0.65rem; color: rgba(255,255,255,0.4); font-weight: 500;'>Blinded Validation</div>
            </div>
        </div>
        <div style='text-align: right; min-width: 140px;'>
            <div style='font-size: 0.65rem; color: rgba(255,255,255,0.5); font-weight: 600;'>ROW {sheet_row_num} • {st.session_state.pos + 1}/{total}</div>
            <div style='background: rgba(255,255,255,0.08); height: 5px; border-radius: 10px; overflow: hidden;'>
                <div style='background: linear-gradient(90deg, #667eea 0%, #a78bfa 100%); height: 100%; width: {progress_pct}%; transition: width 0.3s ease;'></div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------------
# MAIN CONTENT
# -------------------------------------------------------------------
col_main, col_side = st.columns([3, 1.2], gap="medium")

with col_main:
    st.markdown(f"""
        <div style='background: rgba(255,255,255,0.03); border-left: 3px solid #667eea; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.8rem;'>
            <div style='font-size: 0.65rem; color: rgba(255,255,255,0.5); font-weight: 600;'>📄 TITLE</div>
            <div style='font-size: 1rem; color: white; font-weight: 600; line-height: 1.4;'>{title or '<em style="color: rgba(255,255,255,0.3);">(no title)</em>'}</div>
        </div>
        <div style='background: rgba(255,255,255,0.03); border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.8rem;'>
            <div style='font-size: 0.65rem; color: rgba(255,255,255,0.5); font-weight: 600;'>📋 ABSTRACT</div>
            <div style='font-size: 0.85rem; color: rgba(255,255,255,0.85); line-height: 1.6; max-height: 280px; overflow-y: auto;'>{abstract or '<em style="color: rgba(255,255,255,0.3);">(no abstract)</em>'}</div>
        </div>
        <div style='background: rgba(255,255,255,0.03); border-radius: 8px; padding: 0.8rem 1rem;'>
            <div style='font-size: 0.65rem; color: rgba(255,255,255,0.5); font-weight: 600;'>🧬 SYSTEMATIC REVIEW</div>
            <div style='font-size: 1rem; color: white; font-weight: 700; margin-top: 0.2rem;'>{sr_label}</div>
            <div style='font-size: 0.8rem; color: rgba(255,255,255,0.8); line-height: 1.5; background: rgba(0,0,0,0.12); padding: 0.7rem; border-radius: 6px; margin-top: 0.4rem;'>{sr_prompt or '<em style="color: rgba(255,255,255,0.4);">(no prompt)</em>'}</div>
        </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------------
# DECISION PANEL
# -------------------------------------------------------------------
with col_side:
    st.markdown("### 🧩 Your Decision")
    dec_opts = ["", "Yes", "No"]
    decision = st.selectbox(
        "Decision",
        dec_opts,
        index=dec_opts.index(decision_val) if decision_val in dec_opts else 0,
        label_visibility="collapsed"
    )

    if st.button("💾 Save Decision", type="primary", use_container_width=True):
        if not decision:
            st.warning("⚠️ Select Yes/No")
        else:
            payload = {"Poenaru_Decision": decision, "Reviewed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            ok = save_row(sheet_row_num, payload)
            if ok:
                st.session_state.decision_saved = True
                st.success("✅ Saved!")
                fetch_sheet.clear()
                st.rerun()
            else:
                st.error("❌ Failed")

    # --- Reveal AI only after user saves
    if st.session_state.get("decision_saved", False):
        st.markdown("<hr>", unsafe_allow_html=True)
        if ai_val in ["1", "yes"]:
            ai_color, ai_text, ai_icon = "#10b981", "YES", "✓"
        elif ai_val in ["0", "no"]:
            ai_color, ai_text, ai_icon = "#ef4444", "NO", "✗"
        else:
            ai_color, ai_text, ai_icon = "#6b7280", "N/A", "?"
        st.markdown(
            f"""
            <div style='background: rgba(255,255,255,0.04); border-radius: 8px; padding: 0.8rem; border: 1px solid rgba(255,255,255,0.08);'>
                <div style='font-size: 0.65rem; color: rgba(255,255,255,0.5); font-weight: 600;'>🤖 AI DECISION</div>
                <div style='background: rgba(0,0,0,0.15); border: 2px solid {ai_color}; border-radius: 6px; padding: 0.6rem; text-align: center;'>
                    <div style='font-size: 1.3rem;'>{ai_icon}</div>
                    <div style='font-size: 0.85rem; color: {ai_color}; font-weight: 700;'>{ai_text}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if ai_just.strip():
            st.markdown(
                f"""
                <div style='background: rgba(255,255,255,0.03); border-radius: 6px; padding: 0.7rem; margin-top: 0.7rem; font-size: 0.75rem; color: rgba(255,255,255,0.65); line-height: 1.5; max-height: 120px; overflow-y: auto;'>
                    <div style='color: rgba(255,255,255,0.9); font-weight: 600; font-size: 0.65rem; letter-spacing: 0.5px; margin-bottom: 0.4rem;'>JUSTIFICATION</div>
                    {ai_just}
                </div>
                """,
                unsafe_allow_html=True
            )

        if ai_val in ["1", "yes", "0", "no"]:
            match = (decision == "Yes" and ai_val in ["1", "yes"]) or (decision == "No" and ai_val in ["0", "no"])
            agreement_color, agreement_bg, agreement_text, agreement_icon = (
                ("#10b981", "rgba(16,185,129,0.12)", "Agreement", "✓") if match else
                ("#f59e0b", "rgba(245,158,11,0.12)", "Disagreement", "!")
            )
            st.markdown(
                f"""
                <div style='background: {agreement_bg}; border: 2px solid {agreement_color}; border-radius: 6px; padding: 0.6rem; margin-top: 0.7rem; text-align: center;'>
                    <div style='font-size: 1.1rem;'>{agreement_icon}</div>
                    <div style='font-size: 0.75rem; color: {agreement_color}; font-weight: 700;'>{agreement_text}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

# -------------------------------------------------------------------
# NAVIGATION
# -------------------------------------------------------------------
st.markdown("<div style='margin-top: 0.8rem;'></div>", unsafe_allow_html=True)
nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])

with nav_col1:
    if st.button("⬅️ Prev", use_container_width=True, disabled=st.session_state.pos == 0):
        st.session_state.pos -= 1
        st.rerun()
with nav_col2:
    st.markdown(f"<div style='text-align:center; color:rgba(255,255,255,0.6);'><b style='color:white;'>{st.session_state.pos+1}</b> / {total}</div>", unsafe_allow_html=True)
with nav_col3:
    if st.button("Next ➡️", use_container_width=True, disabled=st.session_state.pos >= total-1):
        st.session_state.pos += 1
        st.rerun()

# -------------------------------------------------------------------
# STYLE
# -------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp {font-family:'Inter',sans-serif; background-color:#0e1117;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-thumb{background:rgba(102,126,234,0.3);border-radius:10px;}
::-webkit-scrollbar-thumb:hover{background:rgba(102,126,234,0.5);}
.stButton>button{border-radius:8px;font-weight:600;font-size:0.85rem;padding:0.45rem 0.9rem;}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#1a1f2e 0%,#0e1117 100%);border-right:1px solid rgba(102,126,234,0.1);}
.block-container{padding:1.2rem 1rem 0.8rem 1rem !important;max-width:100% !important;}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# OPTIONAL:

