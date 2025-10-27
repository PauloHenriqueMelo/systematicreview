# app.py
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Minerva Reviewer", layout="wide")

GAS_URL = "https://script.google.com/macros/s/AKfycbwQ-XHCjJd2s6sENQJh6Z9Qm-8De9J8_UThZ-pM1rGgm04FCT-qPBSyBFaqOoSreZ1-/exec"
GAS_TOKEN = "MINERVA_SECRET"

@st.cache_data
def load_prompts() -> dict:
    try:
        p = pd.read_csv("prompts.csv")
    except Exception:
        p = pd.read_csv("prompts.csv", sep=None, engine="python")
    req = {"SR","Prompt"}
    if not req.issubset(p.columns):
        st.error("prompts.csv must have columns: SR, Prompt"); st.stop()
    p["SR"] = pd.to_numeric(p["SR"], errors="coerce").fillna(0).astype(int)
    return {int(r.SR): str(r.Prompt) for r in p.itertuples(index=False)}

@st.cache_data
def fetch_sheet(only_unreviewed: bool = False) -> pd.DataFrame:
    r = requests.get(GAS_URL, params={"token": GAS_TOKEN}, timeout=20)
    js = r.json()
    if not js.get("ok"):
        st.error(js.get("error", "failed to load sheet")); st.stop()
    df = pd.DataFrame(js["rows"])
    for c in ["Title","Abstract","SR","Poenaru_Decision","AI","AI_Justification","_row"]:
        if c not in df.columns: df[c] = ""
    df["_row"] = pd.to_numeric(df["_row"], errors="coerce").fillna(0).astype(int)
    df["SR"] = pd.to_numeric(df["SR"], errors="coerce").fillna(0).astype(int)
    if only_unreviewed:
        df = df[df["Poenaru_Decision"].astype(str).str.strip().eq("")]
    return df.sort_values("_row").reset_index(drop=True)

def save_row(sheet_row:int, fields:dict)->bool:
    try:
        r = requests.post(GAS_URL, params={"token": GAS_TOKEN},
                          json={"row": int(sheet_row), "fields": fields}, timeout=20)
        js = r.json()
        return bool(js.get("ok"))
    except Exception:
        return False

prompts_map = load_prompts()
only_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
df = fetch_sheet(only_unreviewed)

if "pos" not in st.session_state:
    st.session_state.pos = 0

total = len(df)
st.sidebar.write(f"Total rows: **{total}**")
if total == 0:
    st.info("No rows to review."); st.stop()

sheet_rows = df["_row"].tolist()
current_row = df.iloc[st.session_state.pos]["_row"]
jump = st.sidebar.selectbox(
    "Jump to sheet row",
    options=sheet_rows,
    index=sheet_rows.index(current_row),
)
if jump != current_row:
    st.session_state.pos = sheet_rows.index(jump)

row = df.iloc[st.session_state.pos]
sheet_row_num = int(row["_row"])
title = str(row["Title"])
abstract = str(row["Abstract"])
sr_val = int(row["SR"]) if pd.notna(row["SR"]) else 0
sr_prompt = prompts_map.get(sr_val, "")

st.title("Minerva Reviewer")
st.subheader(f"Row {sheet_row_num}")
st.markdown(f"**Title**: {title if title else '_(empty)_'}")
with st.expander("Abstract", expanded=True):
    st.write(abstract if abstract else "_(empty)_")
with st.expander(f"SR Prompt (SR={sr_val})", expanded=True):
    st.write(sr_prompt if sr_prompt else "_(no prompt for this SR in prompts.csv)_")

dec_opts = ["", "Include", "Exclude", "Unclear"]
dec_val = str(row["Poenaru_Decision"]).strip()
try: dec_idx = dec_opts.index(dec_val) if dec_val in dec_opts else 0
except: dec_idx = 0
decision = st.selectbox("Decision", options=dec_opts, index=dec_idx)

ai_opts = ["", "yes", "no"]
ai_val = str(row["AI"]).strip().lower()
try: ai_idx = ai_opts.index(ai_val) if ai_val in ai_opts else 0
except: ai_idx = 0
ai_flag = st.selectbox("Use AI?", options=ai_opts, index=ai_idx)

ai_just = st.text_area(
    "AI Justification",
    value=str(row["AI_Justification"]) if pd.notna(row["AI_Justification"]) else "",
    height=140
)

save_col, nav_prev, nav_next = st.columns([2,1,1])
with save_col:
    if st.button("💾 Save"):
        payload = {"Poenaru_Decision": decision, "AI": ai_flag, "AI_Justification": ai_just}
        ok = save_row(sheet_row_num, payload)
        if ok:
            st.success(f"Saved row {sheet_row_num}.")
            fetch_sheet.clear()
        else:
            st.error("Save failed.")

with nav_prev:
    if st.button("⬅️ Prev") and st.session_state.pos > 0:
        st.session_state.pos -= 1; st.rerun()
with nav_next:
    if st.button("Next ➡️") and st.session_state.pos < total - 1:
        st.session_state.pos += 1; st.rerun()

st.markdown("""
<style>
.stButton>button{border-radius:10px;padding:.45rem .9rem}
.stSelectbox,.stTextArea{margin-bottom:.4rem}
</style>
""", unsafe_allow_html=True)
