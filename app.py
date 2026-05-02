import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: ≤5 refunds → APPROVE | ≥6 → DENY")

# ================= GOOGLE AUTH =================
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
    return gspread.authorize(creds)

# ================= LOAD DATA =================
@st.cache_data(ttl=300)  # 5 min cache (fast + near real-time)
def load_sheet(sheet_id, sheet_name):
    client = get_client()
    sheet = client.open_by_key(sheet_id)
    ws = sheet.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

# ================= REFRESH BUTTON =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= INPUT =================
col1, col2 = st.columns(2)

bzid_input = col1.text_input("Enter BZID")

month_options = {
    datetime(2026, i, 1).strftime("%B 2026"): i for i in range(1, 13)
}

selected_month_label = col2.selectbox("Select Month", list(month_options.keys()))
month_input = month_options[selected_month_label]

# ================= PROCESS =================
if st.button("Fetch Details"):

    if not bzid_input:
        st.warning("Enter BZID")
        st.stop()

    bzid = bzid_input.strip().upper()

    # ===== LOAD DATA =====
    cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
    jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
    manual_cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")

    # ================= CASH / UPI =================
    cash_df["BZID"] = cash_df["Business ID"].astype(str).str.strip().str.upper()

    cash_df["Date"] = pd.to_datetime(
        cash_df["Date"], errors="coerce"
    ).fillna(pd.to_datetime(cash_df["Timestamp"], errors="coerce"))

    cash_matches = cash_df[
        (cash_df["BZID"] == bzid) &
        (cash_df["Date"].notna()) &
        (cash_df["Date"].dt.month == month_input)
    ]

    # ================= JUMBOCASH =================
    jc_df["BZID"] = jc_df["BZID"].astype(str).str.strip().str.upper()

    jc_df["Date"] = pd.to_datetime(
        jc_df["date"], errors="coerce"
    ).fillna(pd.to_datetime(jc_df["Timestamp"], errors="coerce"))

    jc_matches = jc_df[
        (jc_df["BZID"] == bzid) &
        (jc_df["Date"].notna()) &
        (jc_df["Date"].dt.month == month_input)
    ]

    # ================= MANUAL CASH =================
    manual_cash_df["BZID"] = manual_cash_df["BZID"].astype(str).str.strip().str.upper()

    manual_cash_df["Date"] = pd.to_datetime(manual_cash_df["Date"], errors="coerce")

    manual_matches = manual_cash_df[
        (manual_cash_df["BZID"] == bzid) &
        (manual_cash_df["Date"].notna()) &
        (manual_cash_df["Date"].dt.month == month_input)
    ]

    # ================= COUNTS =================
    cash_count = cash_matches["Ticket Number"].nunique() if not cash_matches.empty else 0
    jc_count = jc_matches["Ticket ID"].nunique() if not jc_matches.empty else 0
    manual_count = manual_matches["Ticke No"].nunique() if not manual_matches.empty else 0

    cash_amount = cash_matches["Amount"].sum() if not cash_matches.empty else 0
    jc_amount = jc_matches["Amount"].sum() if not jc_matches.empty else 0
    manual_amount = manual_matches["Amount"].sum() if not manual_matches.empty else 0

    total_count = cash_count + jc_count + manual_count
    total_amount = cash_amount + jc_amount + manual_amount

    # ================= OUTPUT =================
    st.subheader("Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash / UPI", cash_count, f"₹ {cash_amount}")
    c2.metric("Jumbocash", jc_count, f"₹ {jc_amount}")
    c3.metric("Manual Cash", manual_count, f"₹ {manual_amount}")
    c4.metric("Total", total_count, f"₹ {total_amount}")

    # ================= DECISION =================
    if total_count < 6:
        st.success(f"✅ APPROVE ({total_count})")
    else:
        st.error(f"❌ DENY ({total_count})")

    # ================= TABLES =================
    if not cash_matches.empty:
        st.write("Cash / UPI")
        st.dataframe(cash_matches, use_container_width=True)

    if not jc_matches.empty:
        st.write("Jumbocash")
        st.dataframe(jc_matches, use_container_width=True)

    if not manual_matches.empty:
        st.write("Manual Cash Refund")
        st.dataframe(manual_matches, use_container_width=True)

    if cash_matches.empty and jc_matches.empty and manual_matches.empty:
        st.warning("No data found")
