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
    page_title="Minerva Reviewer (Blinded Validation)",
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
# FETCH SHEET FROM GAS
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
# SAVE ROW
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
# SIDEBAR CONTROLS
# -------------------------------------------------------------------
st.sidebar.title("⚙️ Controls")
only_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
prompts_map = load_prompts()
df = fetch_sheet(only_unreviewed)
total = len(df)
st.sidebar.markdown(f"**Total rows:** {total}")

if "pos" not in st.session_state:
    st.session_state.pos = 0

if total == 0:
    st.info("🎉 All rows reviewed.")
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
decision_val = str(row["Poenaru_Decision"]).strip()

ai_val = str(row["AI"]).strip().lower()
ai_just = str(row["AI_Justification"]) if pd.notna(row["AI_Justification"]) else ""

# -------------------------------------------------------------------
# COLOR THEME LOGIC
# -------------------------------------------------------------------
if ai_val in ["1", "yes"]:
    bg_color = "#002b00"  # dark green
elif ai_val in ["0", "no"]:
    bg_color = "#330000"  # dark red
else:
    bg_color = "#0e1117"  # default dark

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {bg_color} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------------
# HEADER + STUDY DISPLAY
# -------------------------------------------------------------------
st.title("🧠 Minerva Reviewer — Blinded Validation")
st.caption(f"Row {sheet_row_num} | Progress: {st.session_state.pos + 1}/{total}")

col_main, col_side = st.columns([2.5, 1])

with col_main:
    st.markdown(f"### 📄 Title")
    st.markdown(f"**{title or '_(empty)_'}**")

    with st.expander("Abstract", expanded=True):
        st.markdown(abstract or "_(empty)_", unsafe_allow_html=True)

    with st.expander(f"SR Prompt (SR={sr_val})", expanded=False):
        st.info(sr_prompt or "_(no prompt found in prompts.csv)_")

# -------------------------------------------------------------------
# REVIEW PANEL
# -------------------------------------------------------------------
with col_side:
    st.markdown("### 🧩 Your Decision")
    dec_opts = ["", "Yes", "No"]
    decision = st.selectbox(
        "Does this study meet inclusion criteria?",
        dec_opts,
        index=dec_opts.index(decision_val) if decision_val in dec_opts else 0
    )

    save_col = st.container()
    with save_col:
        if st.button("💾 Save Decision", type="primary", use_container_width=True):
            if not decision:
                st.warning("Please select Yes or No.")
            else:
                payload = {
                    "Poenaru_Decision": decision,
                    "Reviewed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                ok = save_row(sheet_row_num, payload)
                if ok:
                    st.success(f"✅ Saved decision for Row {sheet_row_num}")
                    fetch_sheet.clear()
                    st.rerun()
                else:
                    st.error("❌ Save failed")

    # Reveal AI info *after saving*
    if decision_val in ["Yes", "No"]:
        st.markdown("---")
        st.markdown("### 🤖 AI Decision (Unblinded)")
        if ai_val in ["1", "yes"]:
            st.success("AI decision: **YES (Include)**")
        elif ai_val in ["0", "no"]:
            st.error("AI decision: **NO (Exclude)**")
        else:
            st.info("AI decision unavailable.")

        if ai_just.strip():
            st.markdown(f"**Justification:**\n\n{ai_just}")

        # Agreement indicator
        if ai_val in ["1", "yes", "0", "no"]:
            match = (
                (decision_val == "Yes" and ai_val in ["1", "yes"])
                or (decision_val == "No" and ai_val in ["0", "no"])
            )
            if match:
                st.success("✅ You and AI agreed!")
            else:
                st.error("❌ You and AI disagreed.")

# -------------------------------------------------------------------
# NAVIGATION + PROGRESS
# -------------------------------------------------------------------
st.markdown("---")
prev_col, prog_col, next_col = st.columns([1, 3, 1])

with prev_col:
    if st.button("⬅️ Previous") and st.session_state.pos > 0:
        st.session_state.pos -= 1
        st.rerun()

with prog_col:
    st.progress((st.session_state.pos + 1) / total)
    st.caption(f"Review {st.session_state.pos + 1} of {total}")

with next_col:
    if st.button("Next ➡️") and st.session_state.pos < total - 1:
        st.session_state.pos += 1
        st.rerun()

# -------------------------------------------------------------------
# STYLING
# -------------------------------------------------------------------
st.markdown("""
<style>
.stButton>button {
    border-radius: 12px !important;
    font-weight: 600;
}
[data-testid="stSidebar"] {
    background-color: #10161f;
}
.stSelectbox, .stTextArea {
    margin-bottom: .5rem;
}
h1, h2, h3, h4, h5 {
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)
