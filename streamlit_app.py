# app.py
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Minerva Reviewer", layout="wide")

GAS_URL   = "https://script.google.com/macros/s/AKfycbwgV4Q18h4r9StS4KENSyxWGPC96pB6O58bJ5qiLItxb-POErmXKJ3X9mTIBZy85Gnc/exec"  # .../exec
GAS_TOKEN = "MINERVA_SECRET"

@st.cache_data
def load_prompts():
    p = pd.read_csv("prompts.csv")
    return {int(r.SR): str(r.Prompt) for r in p.itertuples(index=False)}

@st.cache_data
def fetch_sheet():
    r = requests.get(GAS_URL, params={"token": GAS_TOKEN}, timeout=20)
    js = r.json()
    if not js.get("ok"):
        st.error(js.get("error", "failed to load sheet")); st.stop()
    df = pd.DataFrame(js["rows"])
    # ensure columns exist
    for c in ["Title","Abstract","SR","Poenaru_Decision","AI","AI_Justification","_row"]:
        if c not in df.columns: df[c] = ""
    # coerce SR to int when possible
    df["SR"] = pd.to_numeric(df["SR"], errors="coerce").fillna(0).astype(int)
    return df

def save_row(row_idx:int, fields:dict)->bool:
    try:
        r = requests.post(GAS_URL, params={"token": GAS_TOKEN},
                          json={"row": row_idx, "fields": fields}, timeout=20)
        js = r.json()
        return bool(js.get("ok"))
    except Exception:
        return False

prompts = load_prompts()
df = fetch_sheet()

if "i" not in st.session_state: st.session_state.i = 0

st.sidebar.write(f"Total rows: **{len(df)}**")
# optional filter: show only unreviewed
show_unreviewed = st.sidebar.checkbox("Only unreviewed", value=False)
if show_unreviewed:
    mask = df["Poenaru_Decision"].astype(str).str.strip().eq("")
    view = df[mask].reset_index
