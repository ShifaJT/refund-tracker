import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Refund Tracker", page_icon="💰", layout="wide")

# ================= STYLING =================
st.markdown("""
<style>
body { background-color: #ffffff; }
.title { font-size: 28px; font-weight: bold; color: #2e7d32; }
.success-box {
    background: #e8f5e9;
    border-left: 5px solid #2e7d32;
    padding: 15px;
    border-radius: 8px;
}
.deny-box {
    background: #ffebee;
    border-left: 5px solid #c62828;
    padding: 15px;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ================= HEADER =================
col1, col2 = st.columns([1,5])
with col1:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Leaf_icon.svg/512px-Leaf_icon.svg.png", width=50)
with col2:
    st.markdown('<div class="title">Refund Tracker Dashboard</div>', unsafe_allow_html=True)

st.markdown("### Check BZID Refund Eligibility")
st.info("Rule: < 3 refunds → APPROVE | ≥ 3 → DENY")

# ================= CONNECTION =================
@st.cache_resource
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
@st.cache_data(ttl=600)
def load_data(sheet_id):
    client = get_client()
    sheet = client.open_by_key(sheet_id)
    ws = sheet.worksheet("Form Responses 1")
    return pd.DataFrame(ws.get_all_records())

cash_df = load_data(st.secrets["cash_upi_sheet_id"])
jc_df = load_data(st.secrets["jumbocash_sheet_id"])

# ================= INPUT =================
col1, col2 = st.columns(2)

with col1:
    bzid_input = st.text_input("Enter BZID")

with col2:
    month_input = st.selectbox("Select Month", list(range(1, 13)))

# ================= PROCESS =================
if st.button("Fetch Details", type="primary"):

    if not bzid_input:
        st.warning("Enter BZID")
        st.stop()

    bzid = bzid_input.strip().upper()

    # ================= CLEAN DATA =================
    # Cash sheet
    cash_df["BZID_CLEAN"] = cash_df["Business ID"].astype(str).str.strip().str.upper()
    cash_df["Date_clean"] = pd.to_datetime(cash_df["Date"], errors='coerce')
    cash_df["Timestamp_clean"] = pd.to_datetime(cash_df["Timestamp"], errors='coerce')
    cash_df["Final_Date"] = cash_df["Date_clean"].fillna(cash_df["Timestamp_clean"])

    # Jumbocash sheet
    jc_df["BZID_CLEAN"] = jc_df["BZID"].astype(str).str.strip().str.upper()

    # ================= FILTER =================
    cash_matches = cash_df[
        (cash_df["BZID_CLEAN"] == bzid) &
        (cash_df["Final_Date"].notna()) &
        (cash_df["Final_Date"].dt.month == month_input)
    ]

    jc_matches = jc_df[
        (jc_df["BZID_CLEAN"] == bzid) &
        (jc_df["Month"].astype(int) == month_input)
    ]

    # ================= CALCULATIONS =================
    cash_count = cash_matches["Ticket Number"].nunique() if not cash_matches.empty else 0
    jc_count = jc_matches["Ticket ID"].nunique() if not jc_matches.empty else 0

    cash_amount = cash_matches["Amount"].sum() if not cash_matches.empty else 0
    jc_amount = jc_matches["Amount"].sum() if not jc_matches.empty else 0

    total_count = cash_count + jc_count
    total_amount = cash_amount + jc_amount

    # ================= METRICS =================
    st.markdown("### 📊 Summary")
    m1, m2, m3 = st.columns(3)

    m1.metric("💵 Cash / UPI", cash_count, f"₹ {cash_amount}")
    m2.metric("🎫 Jumbocash", jc_count, f"₹ {jc_amount}")
    m3.metric("📊 Total", total_count, f"₹ {total_amount}")

    # ================= DECISION =================
    st.markdown("### 📌 Decision")

    if total_count < 3:
        st.markdown(f"""
        <div class="success-box">
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

    # ================= DATA TABLE =================
    st.markdown("### 📋 Transactions")

    if not cash_matches.empty:
        st.write("Cash / UPI Refunds")
        st.dataframe(cash_matches, use_container_width=True)

    if not jc_matches.empty:
        st.write("Jumbocash Refunds")
        st.dataframe(jc_matches, use_container_width=True)

    if cash_matches.empty and jc_matches.empty:
        st.warning("No data found for this BZID")

    # ================= DEBUG =================
    st.markdown("### 🧠 Debug Info")
    st.write("Cash rows found:", len(cash_matches))
    st.write("Jumbocash rows found:", len(jc_matches))
