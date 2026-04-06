import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Refund Tracker", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    .approve-box { background: #e8f5e9; border-left: 4px solid #2e7d32; padding: 1rem; border-radius: 10px; margin: 1rem 0; }
    .deny-box { background: #fee; border-left: 4px solid #c62828; padding: 1rem; border-radius: 10px; margin: 1rem 0; }
    </style>
""", unsafe_allow_html=True)

st.title("💰 Refund Tracker Dashboard")
st.markdown("### For Champs - Check BZID refund eligibility")

st.info("📋 Rule: If total refunds (Cash + UPI + Jumbocash) < 3 → APPROVE | ≥ 3 → DENY")

# ================== GOOGLE CONNECTION ==================
def get_client():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
    return gspread.authorize(credentials)

# ================== LOAD DATA ==================
@st.cache_data(ttl=300)
def load_cash_upi():
    try:
        client = get_client()
        sheet = client.open_by_key(st.secrets["cash_upi_sheet_id"])
        worksheet = sheet.worksheet("Form Responses 1")
        return pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"Cash/UPI Error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_jumbocash():
    try:
        client = get_client()
        sheet = client.open_by_key(st.secrets["jumbocash_sheet_id"])
        worksheet = sheet.worksheet("Form Responses 1")
        return pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"Jumbocash Error: {e}")
        return pd.DataFrame()

cash_df = load_cash_upi()
jc_df = load_jumbocash()

# ================== INPUT ==================
col1, col2 = st.columns(2)

with col1:
    bzid = st.text_input("🔍 Enter BZID")

with col2:
    months = list(range(1, 13))
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    month_map = dict(zip(month_names, months))
    
    selected = st.selectbox("📅 Select Month", [f"{m} 2026" for m in month_names])
    month_text, year = selected.split()
    month_num = month_map[month_text]
    year = int(year)

# ================== PROCESS ==================
if st.button("Fetch Refund Details"):

    if not bzid:
        st.warning("Enter BZID")
        st.stop()

    bzid = bzid.strip().upper()

    # ---------- CASH / UPI ----------
    cash_matches = pd.DataFrame()
    if not cash_df.empty:
        cash_df["Timestamp"] = pd.to_datetime(cash_df["Timestamp"], errors='coerce')

        cash_matches = cash_df[
            (cash_df["Business ID"].astype(str).str.strip().str.upper() == bzid) &
            (cash_df["Timestamp"].dt.month == month_num) &
            (cash_df["Timestamp"].dt.year == year)
        ]

    # ---------- JUMBOCASH ----------
    jc_matches = pd.DataFrame()
    if not jc_df.empty:
        jc_df["Timestamp"] = pd.to_datetime(jc_df["Timestamp"], errors='coerce')

        jc_matches = jc_df[
            (jc_df["BZID"].astype(str).str.strip().str.upper() == bzid) &
            (jc_df["Timestamp"].dt.month == month_num) &
            (jc_df["Timestamp"].dt.year == year)
        ]

    # ================== CALCULATIONS ==================
    cash_count = cash_matches["Ticket Number"].nunique() if not cash_matches.empty else 0
    jc_count = jc_matches["Ticket ID"].nunique() if not jc_matches.empty else 0

    cash_amount = cash_matches["Amount"].sum() if "Amount" in cash_matches else 0
    jc_amount = jc_matches["Amount"].sum() if "Amount" in jc_matches else 0

    total_count = cash_count + jc_count
    total_amount = cash_amount + jc_amount

    # ================== UI ==================
    c1, c2, c3 = st.columns(3)

    c1.metric("💵 Cash/UPI", cash_count, f"₹{cash_amount}")
    c2.metric("🎫 Jumbocash", jc_count, f"₹{jc_amount}")
    c3.metric("📊 Total", total_count, f"₹{total_amount}")

    # ================== DECISION ==================
    if total_count < 3:
        st.markdown(f"""
        <div class="approve-box">
        <h2>✅ APPROVE</h2>
        <p>{total_count} refunds in selected month</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="deny-box">
        <h2>❌ DENY</h2>
        <p>{total_count} refunds in selected month</p>
        </div>
        """, unsafe_allow_html=True)

    # ================== TABLE ==================
    st.subheader("Transactions")

    if not cash_matches.empty:
        st.write("Cash/UPI")
        st.dataframe(cash_matches)

    if not jc_matches.empty:
        st.write("Jumbocash")
        st.dataframe(jc_matches)

    if cash_matches.empty and jc_matches.empty:
        st.info("No data found")
