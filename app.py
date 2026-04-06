import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Refund Tracker", page_icon="💰", layout="wide")

# ================= STYLING =================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.metric-box {
    background: white;
    padding: 15px;
    border-radius: 12px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

st.title("💰 Refund Tracker Dashboard")
st.markdown("### For Champs - Check BZID refund eligibility")

st.info("📌 Rule: If total refunds < 3 → APPROVE | ≥ 3 → DENY")

# ================= GOOGLE CONNECTION =================
def get_client():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
    return gspread.authorize(credentials)

# ================= LOAD DATA =================
@st.cache_data(ttl=300)
def load_cash_data():
    try:
        client = get_client()
        sheet = client.open_by_key(st.secrets["cash_upi_sheet_id"])
        ws = sheet.worksheet("Form Responses 1")
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"❌ Cash/UPI Error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_jc_data():
    try:
        client = get_client()
        sheet = client.open_by_key(st.secrets["jumbocash_sheet_id"])
        ws = sheet.worksheet("Form Responses 1")
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"❌ Jumbocash Error: {e}")
        return pd.DataFrame()

cash_df = load_cash_data()
jc_df = load_jc_data()

# ================= INPUT =================
col1, col2 = st.columns(2)

with col1:
    bzid_input = st.text_input("🔍 Enter BZID")

with col2:
    month_input = st.selectbox("📅 Select Month", list(range(1, 13)))

# ================= MAIN LOGIC =================
if st.button("🚀 Fetch Refund Details"):

    if not bzid_input:
        st.warning("⚠️ Please enter BZID")
        st.stop()

    bzid = bzid_input.strip().upper()

    # ================= CASH FILTER =================
    cash_matches = pd.DataFrame()

    if not cash_df.empty:
        cash_df["BZID_CLEAN"] = cash_df["Business ID"].astype(str).str.strip().str.upper()

        cash_df["Date"] = pd.to_datetime(
            cash_df["Date"],
            errors="coerce"
        )

        cash_matches = cash_df[
            (cash_df["BZID_CLEAN"] == bzid) &
            (cash_df["Date"].notna()) &
            (cash_df["Date"].dt.month == month_input)
        ]

    # ================= JUMBOCASH FILTER =================
    jc_matches = pd.DataFrame()

    if not jc_df.empty:
        jc_df["BZID_CLEAN"] = jc_df["BZID"].astype(str).str.strip().str.upper()

        jc_matches = jc_df[
            (jc_df["BZID_CLEAN"] == bzid) &
            (jc_df["Month"].astype(str).astype(int) == month_input)
        ]

    # ================= CALCULATIONS =================
    cash_count = cash_matches["Ticket Number"].nunique() if not cash_matches.empty else 0
    jc_count = jc_matches["Ticket ID"].nunique() if not jc_matches.empty else 0

    cash_amount = cash_matches["Amount"].sum() if not cash_matches.empty else 0
    jc_amount = jc_matches["Amount"].sum() if not jc_matches.empty else 0

    total_count = cash_count + jc_count
    total_amount = cash_amount + jc_amount

    # ================= METRICS =================
    st.markdown("### 📊 Refund Summary")

    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric("💵 Cash / UPI", cash_count, f"₹ {cash_amount}")

    with m2:
        st.metric("🎫 Jumbocash", jc_count, f"₹ {jc_amount}")

    with m3:
        st.metric("📊 Total Refunds", total_count, f"₹ {total_amount}")

    # ================= DECISION =================
    if total_count < 3:
        st.success(f"✅ APPROVE — {total_count} refund(s)")
    else:
        st.error(f"❌ DENY — {total_count} refund(s)")

    # ================= TRANSACTIONS =================
    st.markdown("### 📋 Transactions")

    if not cash_matches.empty:
        st.write("💵 Cash / UPI Refunds")
        st.dataframe(cash_matches)

    if not jc_matches.empty:
        st.write("🎫 Jumbocash Refunds")
        st.dataframe(jc_matches)

    if cash_matches.empty and jc_matches.empty:
        st.warning("No data found for this BZID")

    # ================= DEBUG =================
    st.markdown("### 🧠 Debug Info (for issues)")
    st.write("Cash rows found:", len(cash_matches))
    st.write("Jumbocash rows found:", len(jc_matches))
