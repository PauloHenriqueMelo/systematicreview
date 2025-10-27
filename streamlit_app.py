#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# -------------------------------------------------------------------
# PAGE CONFIGURATION
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Minerva Reviewer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------------
# CONFIGURATION CONSTANTS
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
    for c in ["Title","Abstract","SR","Poenaru_Decision","AI","AI_Justification","Reviewer","_row"]:
        if c not in df.columns:
            df[c] = ""

    df["_row"] = pd.to_numeric(df["_row"], errors="coerce").fillna(0).astype(int)
    df["SR"] = pd.to_numeric(df["SR"], errors="coerce").fillna(0).astype(int)

    if only_unreviewed:
        df = df[df["Poenaru_Decision"].astype(str).str.strip().eq("")]

    return df.sort_values("_row").reset_index(drop=True)

# -------------------------------------------------------------------
# SAVE ROW TO SHEET
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
# INTERFACE: SIDEBAR SETTINGS
# -------------------------------------------------------------------
st.sidebar.title("⚙️ Review Controls")
only_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
reviewer = st.sidebar.text_input("Reviewer Name", value=st.session_state.get("reviewer", ""))
if reviewer:
    st.session_state.reviewer = reviewer

# Load data
prompts_map = load_prompts()
df = fetch_sheet(only_unreviewed)
total = len(df)
st.sidebar.markdown(f"**Total rows:** {total}")

if total == 0:
    st.info("✅ All abstracts reviewed!")
    st.stop()

# -------------------------------------------------------------------
# NAVIGATION STATE
# -------------------------------------------------------------------
if "pos" not in st.session_state:
    st.session_state.pos = 0

sheet_rows = df["_row"].tolist()
current_row = df.iloc[st.session_state.pos]["_row"]
jump = st.sidebar.selectbox(
    "Jump to sheet row",
    options=sheet_rows,
    index=sheet_rows.index(current_row),
)
if jump != current_row:
    st.session_state.pos = sheet_rows.index(jump)
    st.rerun()

# -------------------------------------------------------------------
# CURRENT ABSTRACT DETAILS
# -------------------------------------------------------------------
row = df.iloc[st.session_state.pos]
sheet_row_num = int(row["_row"])
title = str(row["Title"])
abstract = str(row["Abstract"])
sr_val = int(row["SR"]) if pd.notna(row["SR"]) else 0
sr_prompt = prompts_map.get(sr_val, "")

# -------------------------------------------------------------------
# MAIN DISPLAY
# -------------------------------------------------------------------
st.title("🧠 Minerva Reviewer")
st.caption(f"Row {sheet_row_num} | Reviewed by: {reviewer or '—'}")

# --- Layout
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("📄 Study Information")
    st.markdown(f"**Title:** {title or '_(empty)_'}")

    with st.expander("Abstract", expanded=True):
        st.write(abstract or "_(empty)_")

    with st.expander(f"SR Prompt (SR={sr_val})", expanded=False):
        st.info(sr_prompt or "_(no prompt found in prompts.csv)_")

with col2:
    st.subheader("🧩 Review Inputs")

    dec_opts = ["", "Include", "Exclude", "Unclear"]
    decision = st.selectbox("Decision", dec_opts, index=dec_opts.index(str(row["Poenaru_Decision"]).strip()) if str(row["Poenaru_Decision"]).strip() in dec_opts else 0)

    ai_opts = ["", "yes", "no"]
    ai_flag = st.selectbox("Use AI?", ai_opts, index=ai_opts.index(str(row["AI"]).strip().lower()) if str(row["AI"]).strip().lower() in ai_opts else 0)

    ai_just = st.text_area(
        "AI Justification",
        value=str(row["AI_Justification"]) if pd.notna(row["AI_Justification"]) else "",
        height=150
    )

    st.markdown("---")
    save_btn = st.button("💾 Save Review", type="primary", use_container_width=True)
    if save_btn:
        payload = {
            "Poenaru_Decision": decision,
            "AI": ai_flag,
            "AI_Justification": ai_just,
            "Reviewer": reviewer,
            "Reviewed_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        ok = save_row(sheet_row_num, payload)
        if ok:
            st.success(f"✅ Row {sheet_row_num} saved successfully.")
            fetch_sheet.clear()
        else:
            st.error("❌ Failed to save row. Please try again.")

# -------------------------------------------------------------------
# NAVIGATION BUTTONS
# -------------------------------------------------------------------
st.markdown("---")
prev_col, prog_col, next_col = st.columns([1, 3, 1])

with prev_col:
    if st.button("⬅️ Previous") and st.session_state.pos > 0:
        st.session_state.pos -= 1
        st.rerun()

with prog_col:
    st.progress((st.session_state.pos + 1) / total)
    st.caption(f"Record {st.session_state.pos + 1} of {total}")

with next_col:
    if st.button("Next ➡️") and st.session_state.pos < total - 1:
        st.session_state.pos += 1
        st.rerun()

# -------------------------------------------------------------------
# EXTRA FEATURES
# -------------------------------------------------------------------
with st.sidebar.expander("📊 Export Options"):
    if st.button("Download current table as CSV"):
        st.download_button(
            label="📥 Export CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="minerva_reviews.csv",
            mime="text/csv"
        )

st.markdown("""
<style>
.stButton>button {
    border-radius: 10px !important;
    font-weight: 600;
}
[data-testid="stSidebar"] {
    background-color: #f7f9fc;
}
</style>
""", unsafe_allow_html=True)
