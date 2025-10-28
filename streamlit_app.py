#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from pathlib import Path

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
# LOAD PROMPTS (version cache by file mtime)
# -------------------------------------------------------------------
def _read_prompts_csv(file_path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(file_path)
    except Exception:
        # sniff delimiter if needed
        return pd.read_csv(file_path, sep=None, engine="python")

@st.cache_data(show_spinner=False)
def load_prompts_versioned(file_path: str, file_mtime: float) -> dict:
    """Cache key includes file mtime so changes invalidate the cache."""
    p = _read_prompts_csv(file_path)
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

# Prompts cache keyed by file mtime
prompts_path = Path(PROMPTS_FILE)
if not prompts_path.exists():
    st.sidebar.error("prompts.csv not found next to app.py")
mtime = prompts_path.stat().st_mtime if prompts_path.exists() else 0.0
prompts_map = load_prompts_versioned(str(prompts_path), mtime)

# Manual refresh
if st.sidebar.button("↻ Reload prompts"):
    load_prompts_versioned.clear()
    st.cache_data.clear()  # also clears fetch_sheet cache so counts refresh
    st.rerun()

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
# --------------------
