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

st.info("📋 **Rule:** If total refunds (Cash + UPI + Jumbocash) in selected month **< 3** → L1 can **APPROVE** | If **≥ 3** → L1 must **DENY**")

# Load data from Google Sheets
@st.cache_data(ttl=300)
def load_cash_upi_data():
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(st.secrets["cash_upi_sheet_id"])
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading Cash/UPI data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_jumbocash_data():
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(st.secrets["jumbocash_sheet_id"])
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading Jumbocash data: {e}")
        return pd.DataFrame()

with st.spinner("Loading data from Google Sheets..."):
    cash_upi_df = load_cash_upi_data()
    jumbocash_df = load_jumbocash_data()

col1, col2 = st.columns(2)

with col1:
    bzid_input = st.text_input("🔍 Enter BZID", placeholder="e.g., BZID-1304476566")

with col2:
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    current_year = datetime.now().year
    month_options = [f"{m} {current_year}" for m in months] + [f"{m} {current_year-1}" for m in months]
    selected_month = st.selectbox("📅 Select Month & Year", month_options)

if st.button("🔎 Fetch Refund Details", type="primary"):
    if not bzid_input:
        st.warning("Please enter a BZID")
    else:
        month_name, year = selected_month.split()
        month_num = months.index(month_name) + 1
        year_num = int(year)
        
        # Filter Cash/UPI data
        cash_upi_matches = pd.DataFrame()
        if not cash_upi_df.empty:
            for col in cash_upi_df.columns:
                if 'bzid' in col.lower() or 'business' in col.lower():
                    bzid_col = col
                    break
            else:
                bzid_col = cash_upi_df.columns[0]
            
            cash_upi_df['Date'] = pd.to_datetime(cash_upi_df.iloc[:, 0], errors='coerce')
            cash_upi_df['Month'] = cash_upi_df['Date'].dt.month
            cash_upi_df['Year'] = cash_upi_df['Date'].dt.year
            
            cash_upi_matches = cash_upi_df[
                (cash_upi_df[bzid_col].astype(str).str.contains(bzid_input, na=False)) &
                (cash_upi_df['Month'] == month_num) &
                (cash_upi_df['Year'] == year_num)
            ]
        
        # Filter Jumbocash data
        jumbocash_matches = pd.DataFrame()
        if not jumbocash_df.empty:
            for col in jumbocash_df.columns:
                if 'bzid' in col.lower():
                    bzid_col = col
                    break
            else:
                bzid_col = jumbocash_df.columns[3] if len(jumbocash_df.columns) > 3 else jumbocash_df.columns[0]
            
            jumbocash_df['Date'] = pd.to_datetime(jumbocash_df.iloc[:, 0], errors='coerce')
            jumbocash_df['Month'] = jumbocash_df['Date'].dt.month
            jumbocash_df['Year'] = jumbocash_df['Date'].dt.year
            
            jumbocash_matches = jumbocash_df[
                (jumbocash_df[bzid_col].astype(str).str.contains(bzid_input, na=False)) &
                (jumbocash_df['Month'] == month_num) &
                (jumbocash_df['Year'] == year_num)
            ]
        
        # Calculate totals
        cash_count = len(cash_upi_matches)
        cash_total = cash_upi_matches.iloc[:, -2].sum() if not cash_upi_matches.empty and len(cash_upi_matches.columns) > 1 else 0
        jc_count = len(jumbocash_matches)
        jc_total = jumbocash_matches.iloc[:, 4].sum() if not jumbocash_matches.empty and len(jumbocash_matches.columns) > 4 else 0
        
        total_refunds = cash_count + jc_count
        total_amount = cash_total + jc_total
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("💵 Cash/UPI Refunds", f"{cash_count} time(s)", f"₹{cash_total:,.2f}")
        with col2: st.metric("🎫 Jumbocash Refunds", f"{jc_count} time(s)", f"₹{jc_total:,.2f}")
        with col3: st.metric("📊 Total Refunds", f"{total_refunds} attempt(s)", f"₹{total_amount:,.2f}")
        
        # Decision
        if total_refunds < 3:
            st.markdown(f"""
                <div class="approve-box">
                    <h2>✅ Decision: APPROVE REFUND</h2>
                    <p>Customer has {total_refunds} refund attempt(s) in {selected_month} (less than 3).</p>
                    <p><strong>L1 Action:</strong> Approve the refund request.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div class="deny-box">
                    <h2>❌ Decision: DENY REFUND</h2>
                    <p>Customer has {total_refunds} refund attempt(s) in {selected_month} (3 or more).</p>
                    <p><strong>L1 Action:</strong> Deny the request. If customer rebuttals, escalate to L2 with proof.</p>
                </div>
            """, unsafe_allow_html=True)
        
        # Show transactions
        st.subheader("📋 Refund Transactions")
        all_transactions = []
        if not cash_upi_matches.empty:
            all_transactions.append(cash_upi_matches)
        if not jumbocash_matches.empty:
            all_transactions.append(jumbocash_matches)
        
        if all_transactions:
            combined = pd.concat(all_transactions)
            st.dataframe(combined, use_container_width=True)
        else:
            st.info(f"No refunds found for {bzid_input} in {selected_month}")
