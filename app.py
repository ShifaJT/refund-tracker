import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: Less than 5 refunds → APPROVE | 5 or more refunds → DENY")

# ================= CITY NAME STANDARDIZATION =================
def standardize_city_name(city):
    """Standardize city names to handle spelling variations"""
    if pd.isna(city) or city == "" or city == "Unknown":
        return "Unknown"
    
    city = str(city).strip()
    city_lower = city.lower()
    
    city_mapping = {
        'bengaluru': 'Bengaluru', 'bangalore': 'Bengaluru', 'bengaluru ': 'Bengaluru',
        'bengaluur': 'Bengaluru', 'bengaluruu': 'Bengaluru', 'bengaliuru': 'Bengaluru',
        'banglore': 'Bengaluru', 'bnegaluru': 'Bengaluru', 'brngaluru': 'Bengaluru',
        'benaluru': 'Bengaluru', 'begaluru': 'Bengaluru',
        
        'hyderabad': 'Hyderabad', 'hyderabad ': 'Hyderabad', 'hyderabafd': 'Hyderabad',
        'hyderabd': 'Hyderabad', 'hydrabad': 'Hyderabad', 'hyderavad': 'Hyderabad',
        'hyd': 'Hyderabad', 'hydersbad': 'Hyderabad',
        
        'pune': 'Pune', 'pune ': 'Pune', 'punr': 'Pune', 'pune1': 'Pune',
        
        'lucknow': 'Lucknow', 'lucknow ': 'Lucknow', 'lukcnow': 'Lucknow',
        'luckmow': 'Lucknow', 'lucknw': 'Lucknow', 'luckno': 'Lucknow',
        'lucknoe': 'Lucknow', 'lucknonw': 'Lucknow', 'lucknowq': 'Lucknow',
        'luckow': 'Lucknow', 'luknow': 'Lucknow', 'luckmnow': 'Lucknow',
        
        'patna': 'Patna', 'patna ': 'Patna', 'patbna': 'Patna', 'pstna': 'Patna',
        'patha': 'Patna',
        
        'ranchi': 'Ranchi', 'ranchi ': 'Ranchi', 'ranhi': 'Ranchi', 'ranci': 'Ranchi',
        'rancchi': 'Ranchi', 'ranc': 'Ranchi', 'rachi': 'Ranchi', 'ranchio': 'Ranchi',
        
        'jamshedpur': 'Jamshedpur', 'jamshedpur ': 'Jamshedpur', 'jhamshedpur': 'Jamshedpur',
        'jhemshedpur': 'Jamshedpur',
        
        'mysore': 'Mysore', 'mysore ': 'Mysore', 'mysuru': 'Mysore',
        'tumkur': 'Tumkur', 'hosur': 'Hosur', 'hassan': 'Hassan',
        'chennai': 'Chennai', 'chennai ': 'Chennai',
        'ahmedabad': 'Ahmedabad', 'ahmedabad ': 'Ahmedabad', 'ahamedabad': 'Ahmedabad',
        'ahemdabad': 'Ahmedabad', 'ahmedabadh': 'Ahmedabad',
        'mandya': 'Mandya', 'sangareddy': 'Sangareddy', 'kanpur': 'Kanpur',
        'vizag': 'Vizag', 'unnao': 'Unnao', 'samastipur': 'Samastipur',
        'siddipet': 'Siddipet', 'krishnagiri': 'Krishnagiri',
        'bhubaneswar': 'Bhubaneswar', 'bhuvaneswar': 'Bhubaneswar',
        'bhuabaneswar': 'Bhubaneswar',
    }
    
    if city_lower in city_mapping:
        return city_mapping[city_lower]
    
    # If it's a hub code pattern, keep as is
    hub_patterns = ['BLR_', 'HYD_', 'PUN_', 'LKO_', 'OD_', 'BH_', 'MYS_', '3P_']
    for pattern in hub_patterns:
        if pattern in city.upper():
            return city
    
    if '_' in city and len(city) <= 15:
        return city
    
    return city

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

# ================= FIX DUPLICATE COLUMNS =================
def fix_duplicate_columns(df):
    cols = []
    count = {}
    for col in df.columns:
        if col in count:
            count[col] += 1
            cols.append(f"{col}_{count[col]}")
        else:
            count[col] = 0
            cols.append(col)
    df.columns = cols
    return df

# ================= LOAD SHEETS =================
@st.cache_data(ttl=300)
def load_sheet(sheet_id, sheet_name):
    try:
        client = get_client()
        sheet = client.open_by_key(sheet_id)
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        df = fix_duplicate_columns(df)
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet not found! Please check:\n1. Sheet ID: {sheet_id}\n2. Service account has access to this sheet")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Worksheet '{sheet_name}' not found in the spreadsheet!")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error loading sheet: {str(e)}")
        return pd.DataFrame()

# ================= GET REFUND COUNT =================
@st.cache_data(ttl=300)
def get_refund_count_for_period(df, bzid, year, start_month=1, end_month=12):
    if df.empty:
        return 0
    df_filtered = df[
        (df["BZID"] == bzid) &
        (df["Date"].notna()) &
        (df["Date"].dt.year == year) &
        (df["Date"].dt.month >= start_month) &
        (df["Date"].dt.month <= end_month)
    ]
    ticket_cols = ["Ticket Number", "Ticket ID", "Ticket No"]
    for col in ticket_cols:
        if col in df_filtered.columns:
            return df_filtered[col].nunique()
    return len(df_filtered)

# ================= GET MONTHLY COUNTS =================
@st.cache_data(ttl=300)
def get_monthly_counts(df, bzid, year):
    monthly_counts = []
    month_names = []
    for month in range(1, 13):
        month_data = df[
            (df["BZID"] == bzid) &
            (df["Date"].dt.year == year) &
            (df["Date"].dt.month == month)
        ]
        if not month_data.empty:
            ticket_cols = ["Ticket Number", "Ticket ID", "Ticket No"]
            found = False
            for col in ticket_cols:
                if col in month_data.columns:
                    monthly_counts.append(month_data[col].nunique())
                    found = True
                    break
            if not found:
                monthly_counts.append(len(month_data))
        else:
            monthly_counts.append(0)
        month_names.append(datetime(year, month, 1).strftime("%B"))
    return month_names, monthly_counts

# ================= OPTIMIZED: GET HIGH RISK CUSTOMERS =================
@st.cache_data(ttl=300)
def get_high_risk_customers_optimized(cash_df, jc_df, manual_df, year, current_month):
    if current_month is None:
        return pd.DataFrame()
    
    def prepare_df(df):
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        df = df.copy()
        
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        if bzid_col is None:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        if date_col is None:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        if df["Date"].isna().all():
            try:
                df["Date"] = pd.to_datetime(df[date_col], errors="coerce", infer_datetime_format=True)
            except:
                pass
        if df["Date"].isna().all():
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month) & (df["Date"].notna())]
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        ticket_col = None
        for col in ["Ticket Number", "Ticket ID", "Ticket No", "Ticket Number_1", "Ticket ID_1"]:
            if col in df.columns:
                ticket_col = col
                break
        if ticket_col:
            df["Ticket"] = df[ticket_col].astype(str)
        else:
            df["Ticket"] = df.index.astype(str)
        
        return df[["BZID", "Date", "Amount", "Ticket"]]
    
    cash_prep = prepare_df(cash_df)
    jc_prep = prepare_df(jc_df)
    manual_prep = prepare_df(manual_df)
    
    all_data = pd.concat([cash_prep, jc_prep, manual_prep], ignore_index=True)
    if all_data.empty:
        return pd.DataFrame()
    
    if not pd.api.types.is_datetime64_any_dtype(all_data["Date"]):
        all_data["Date"] = pd.to_datetime(all_data["Date"], errors="coerce")
    all_data = all_data[all_data["Date"].notna()]
    if all_data.empty:
        return pd.DataFrame()
    
    all_data["Month"] = all_data["Date"].dt.month
    
    monthly_summary = all_data.groupby(["BZID", "Month"]).agg(
        Refund_Count=("Ticket", "nunique"),
        Total_Amount=("Amount", "sum")
    ).reset_index()
    
    monthly_counts_pivot = monthly_summary.pivot(
        index="BZID", columns="Month", values="Refund_Count"
    ).fillna(0)
    monthly_amounts_pivot = monthly_summary.pivot(
        index="BZID", columns="Month", values="Total_Amount"
    ).fillna(0)
    
    for month in range(1, current_month + 1):
        if month not in monthly_counts_pivot.columns:
            monthly_counts_pivot[month] = 0
        if month not in monthly_amounts_pivot.columns:
            monthly_amounts_pivot[month] = 0
    
    monthly_counts_pivot = monthly_counts_pivot[sorted(monthly_counts_pivot.columns)]
    monthly_amounts_pivot = monthly_amounts_pivot[sorted(monthly_amounts_pivot.columns)]
    
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    results = []
    
    for bzid in monthly_counts_pivot.index:
        monthly_counts = monthly_counts_pivot.loc[bzid].values.tolist()
        monthly_amounts = monthly_amounts_pivot.loc[bzid].values.tolist()
        
        if sum(monthly_counts) == 0:
            continue
        
        total_refunds = sum(monthly_counts)
        avg_refunds = total_refunds / current_month
        months_with_refunds = sum(1 for c in monthly_counts if c > 0)
        max_monthly_refunds = max(monthly_counts) if monthly_counts else 0
        
        last_3_months = monthly_counts[-3:] if len(monthly_counts) >= 3 else monthly_counts
        active_in_last_3 = sum(1 for c in last_3_months if c > 0) >= 2
        total_amount = sum(monthly_amounts)
        
        cash_total = cash_prep[cash_prep["BZID"] == bzid]["Amount"].sum() if not cash_prep.empty else 0
        jc_total = jc_prep[jc_prep["BZID"] == bzid]["Amount"].sum() if not jc_prep.empty else 0
        manual_total = manual_prep[manual_prep["BZID"] == bzid]["Amount"].sum() if not manual_prep.empty else 0
        
        consistent_defaulter = all(count >= 4 for count in monthly_counts[:current_month])
        has_policy_breach = max_monthly_refunds >= 5
        frequent_user = months_with_refunds >= 4
        
        if (total_amount > 500 and avg_refunds >= 3) or consistent_defaulter or has_policy_breach:
            risk_level = "🔴🔴 EXTREME"
        elif total_amount <= 500 and avg_refunds >= 3:
            risk_level = "🔴 HIGH"
        elif avg_refunds >= 2 or months_with_refunds >= 3 or frequent_user:
            risk_level = "🟡 POTENTIAL"
        else:
            continue
        
        monthly_breakdown = {}
        for i, (count, amount) in enumerate(zip(monthly_counts, monthly_amounts)):
            if i < current_month:
                if count > 0:
                    monthly_breakdown[month_abbr[i]] = f"{int(count)} [₹{amount:.0f}]"
                else:
                    monthly_breakdown[month_abbr[i]] = "0"
        
        activity_status = "🔴 Active" if active_in_last_3 else "⏸️ Inactive"
        
        results.append({
            "BZID": bzid,
            "Risk Level": risk_level,
            "Status": activity_status,
            "Total Refunds": total_refunds,
            "Monthly Average": round(avg_refunds, 2),
            "Months Active": months_with_refunds,
            "Max Monthly Refunds": max_monthly_refunds,
            "Total Amount": round(total_amount, 2),
            "Cash_UPI": round(cash_total, 2),
            "Jumbocash": round(jc_total, 2),
            "Manual_Cash": round(manual_total, 2),
            **monthly_breakdown
        })
    
    return pd.DataFrame(results)

# ================= CITY ANALYSIS =================
@st.cache_data(ttl=300)
def get_city_analysis(cash_df, jc_df, manual_df, year, current_month):
    def prepare_city_df(df):
        if df.empty:
            return pd.DataFrame(columns=["City", "Amount"])
        
        df = df.copy()
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        if date_col is None:
            return pd.DataFrame(columns=["City", "Amount"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
        if df.empty:
            return pd.DataFrame(columns=["City", "Amount"])
        
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        city_col = None
        for col in ["City", "city", "City Name", "CityName"]:
            if col in df.columns:
                city_col = col
                break
        
        if city_col:
            df["City"] = df[city_col].astype(str).apply(standardize_city_name)
        else:
            df["City"] = "Unknown"
        
        return df[["City", "Amount"]]
    
    cash_city = prepare_city_df(cash_df)
    jc_city = prepare_city_df(jc_df)
    manual_city = prepare_city_df(manual_df)
    
    all_city = pd.concat([cash_city, jc_city, manual_city], ignore_index=True)
    if all_city.empty:
        return pd.DataFrame()
    
    city_summary = all_city.groupby("City").agg(
        Total_Amount=("Amount", "sum"),
        Total_Instances=("Amount", "count")
    ).reset_index().sort_values("Total_Amount", ascending=False)
    
    return city_summary

# ================= HUB ANALYSIS =================
@st.cache_data(ttl=300)
def get_hub_analysis(cash_df, jc_df, manual_df, year, current_month):
    def prepare_hub_df(df):
        if df.empty:
            return pd.DataFrame(columns=["Hub", "Amount"])
        
        df = df.copy()
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        if date_col is None:
            return pd.DataFrame(columns=["Hub", "Amount"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
        if df.empty:
            return pd.DataFrame(columns=["Hub", "Amount"])
        
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        hub_col = None
        for col in ["Hub", "hub", "Hub ID", "HUB ID", "Hub Name"]:
            if col in df.columns:
                hub_col = col
                break
        
        if hub_col:
            df["Hub"] = df[hub_col].astype(str)
        else:
            df["Hub"] = "Unknown"
        
        return df[["Hub", "Amount"]]
    
    cash_hub = prepare_hub_df(cash_df)
    jc_hub = prepare_hub_df(jc_df)
    manual_hub = prepare_hub_df(manual_df)
    
    all_hub = pd.concat([cash_hub, jc_hub, manual_hub], ignore_index=True)
    if all_hub.empty:
        return pd.DataFrame()
    
    hub_summary = all_hub.groupby("Hub").agg(
        Total_Amount=("Amount", "sum"),
        Total_Instances=("Amount", "count")
    ).reset_index().sort_values("Total_Amount", ascending=False)
    
    return hub_summary

# ================= BANK TRANSFER DATA =================
def get_bank_transfer_data(bank_df, ticket_id):
    """Search for a ticket by ID in bank transfer sheet"""
    if bank_df.empty:
        return pd.DataFrame()
    
    df = bank_df.copy()
    
    # Find Ticket ID column
    ticket_col = None
    for col in ["Ticket ID", "Ticket id", "Ticket No", "Ticket Number"]:
        if col in df.columns:
            ticket_col = col
            break
    
    if ticket_col is None:
        return pd.DataFrame()
    
    # Filter by ticket ID
    df = df[df[ticket_col].astype(str).str.strip() == str(ticket_id).strip()]
    
    if df.empty:
        return pd.DataFrame()
    
    # Format for display
    rename_map = {
        "Ticket ID": "Ticket ID",
        "Amount": "Amount (₹)",
        "UTR NUMBER": "UTR Number",
        "Status": "Status",
        "Date": "Date",
        "HUB": "Hub",
        "City": "City",
        "Reason": "Reason",
        "Phone Number": "Phone Number"
    }
    
    # Standardize city names if City column exists
    if "City" in df.columns:
        df["City"] = df["City"].astype(str).apply(standardize_city_name)
    
    # Convert date if exists
    date_col = None
    for col in ["Date", "date"]:
        if col in df.columns:
            date_col = col
            break
    
    if date_col is not None:
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    
    # Select and rename available columns
    available_cols = [col for col in rename_map.keys() if col in df.columns]
    df_display = df[available_cols].copy()
    
    for old, new in rename_map.items():
        if old in df_display.columns:
            df_display.rename(columns={old: new}, inplace=True)
    
    # Format amount
    if "Amount (₹)" in df_display.columns:
        df_display["Amount (₹)"] = df_display["Amount (₹)"].apply(lambda x: f"₹{x:.2f}" if pd.notna(x) else "₹0.00")
    
    # Format date
    if "Date" in df_display.columns and date_col is not None:
        df_display["Date"] = df_display["Date"].dt.strftime("%d-%m-%Y")
    
    return df_display

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= TAB SELECTION =================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Individual Search", "🏦 Bank Transfer Refund Details", "📊 High Risk Customers", "🏙️ City Analysis", "🏪 Hub Analysis"])

# ================= TAB 1: Individual Search =================
with tab1:
    col1, col2 = st.columns(2)
    bzid_input = col1.text_input("Enter BZID")
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    month_options = {datetime(current_year, i, 1).strftime("%B %Y"): i for i in range(1, 13)}
    selected_month_label = col2.selectbox("Select Month", list(month_options.keys()))
    month_input = month_options[selected_month_label]
    selected_year = int(selected_month_label.split()[-1])
    
    if st.button("Fetch Details"):
        if not bzid_input:
            st.warning("Enter BZID")
            st.stop()
        
        bzid = bzid_input.strip().upper()
        
        with st.spinner("Fetching data..."):
            cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
            jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
            manual_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")
            
            # CASH / UPI
            cash_df["BZID"] = cash_df["Business ID"].astype(str).str.strip().str.upper()
            cash_df["Date"] = pd.to_datetime(cash_df["Date"], errors="coerce")
            if "Timestamp" in cash_df.columns:
                cash_df["Date"] = cash_df["Date"].fillna(pd.to_datetime(cash_df["Timestamp"], errors="coerce"))
            
            # JUMBOCASH
            jc_df.columns = jc_df.columns.str.strip()
            jc_df["BZID"] = jc_df["BZID"].astype(str).str.strip().str.upper()
            if "date" in jc_df.columns:
                jc_df["Date"] = pd.to_datetime(jc_df["date"], errors="coerce")
            elif "Date" in jc_df.columns:
                jc_df["Date"] = pd.to_datetime(jc_df["Date"], errors="coerce")
            else:
                jc_df["Date"] = pd.NaT
            if "Timestamp" in jc_df.columns:
                jc_df["Date"] = jc_df["Date"].fillna(pd.to_datetime(jc_df["Timestamp"], errors="coerce"))
            
            # MANUAL CASH
            manual_df["BZID"] = manual_df["BZID"].astype(str).str.strip().str.upper()
            manual_df["Date"] = pd.to_datetime(manual_df["Date"], errors="coerce")
            if "Timestamp" in manual_df.columns:
                manual_df["Date"] = manual_df["Date"].fillna(pd.to_datetime(manual_df["Timestamp"], errors="coerce"))
            
            # FILTER BY BZID AND MONTH
            cash_current_matches = cash_df[
                (cash_df["BZID"] == bzid) &
                (cash_df["Date"].notna()) &
                (cash_df["Date"].dt.month == month_input) &
                (cash_df["Date"].dt.year == selected_year)
            ]
            
            jc_current_matches = jc_df[
                (jc_df["BZID"] == bzid) &
                (jc_df["Date"].notna()) &
                (jc_df["Date"].dt.month == month_input) &
                (jc_df["Date"].dt.year == selected_year)
            ]
            
            manual_current_matches = manual_df[
                (manual_df["BZID"] == bzid) &
                (manual_df["Date"].notna()) &
                (manual_df["Date"].dt.month == month_input) &
                (manual_df["Date"].dt.year == selected_year)
            ]
            
            # COUNTS
            cash_count_current = cash_current_matches["Ticket Number"].nunique() if not cash_current_matches.empty else 0
            jc_count_current = jc_current_matches["Ticket ID"].nunique() if not jc_current_matches.empty else 0
            manual_count_current = manual_current_matches["Ticket No"].nunique() if not manual_current_matches.empty else 0
            total_count_current = cash_count_current + jc_count_current + manual_count_current
            
            # AMOUNTS
            cash_amount_current = pd.to_numeric(cash_current_matches["Amount"], errors="coerce").sum() if not cash_current_matches.empty else 0
            jc_amount_current = pd.to_numeric(jc_current_matches["Amount"], errors="coerce").sum() if not jc_current_matches.empty else 0
            manual_amount_current = pd.to_numeric(manual_current_matches["Amount"], errors="coerce").sum() if not manual_current_matches.empty else 0
            total_amount_current = cash_amount_current + jc_amount_current + manual_amount_current
            
            # YEARLY TREND
            all_refunds = pd.concat([cash_df[["BZID", "Date"]], jc_df[["BZID", "Date"]], manual_df[["BZID", "Date"]]], ignore_index=True)
            current_year_count = get_refund_count_for_period(all_refunds, bzid, current_year, 1, current_month)
            last_year_count = get_refund_count_for_period(all_refunds, bzid, current_year - 1, 1, current_month)
            month_names, monthly_counts = get_monthly_counts(all_refunds, bzid, current_year)
        
        # DISPLAY
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.markdown(f"## 📊 Current Month")
            st.markdown(f"### {selected_month_label}")
            
            if total_count_current < 5:
                st.markdown(f"""
                <div class="decision-approve">
                    <div class="decision-icon tick-mark">✅</div>
                    <div class="decision-text">
                        <h2 style="color: #28a745; margin: 0;">APPROVED</h2>
                        <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count_current} (Less than 5)</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="decision-deny">
                    <div class="decision-icon cross-mark">❌</div>
                    <div class="decision-text">
                        <h2 style="color: #dc3545; margin: 0;">DENIED</h2>
                        <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count_current} (5 or more - Limit reached)</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if total_count_current >= 5:
                st.markdown("""
                <div style="text-align: center; padding: 10px; background-color: #f8d7da; border-radius: 10px; margin-top: 10px;">
                    <span style="font-size: 32px;">🚶</span>
                    <span style="font-size: 24px; margin-left: 10px;">❌</span>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #721c24;">Limit reached! Walk away from this request.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="text-align: center; padding: 10px; background-color: #d4edda; border-radius: 10px; margin-top: 10px;">
                    <span style="font-size: 32px;">✅</span>
                    <span style="font-size: 24px; margin-left: 10px;">👍</span>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #155724;">All good! Proceed with the refund.</p>
                </div>
                """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.metric("💳 Cash / UPI", cash_count_current, f"₹{round(cash_amount_current, 2)}")
                st.metric("💵 Manual Cash", manual_count_current, f"₹{round(manual_amount_current, 2)}")
            with c2:
                st.metric("🏦 Jumbocash", jc_count_current, f"₹{round(jc_amount_current, 2)}")
                st.metric("📦 Total", total_count_current, f"₹{round(total_amount_current, 2)}")
        
        with col_right:
            st.markdown(f"## 📋 Refund Details")
            st.markdown(f"### {selected_month_label}")
            
            tabs_inner = st.tabs(["💳 Cash/UPI", "🏦 Jumbocash", "💵 Manual Cash"])
            
            with tabs_inner[0]:
                if not cash_current_matches.empty:
                    st.dataframe(cash_current_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Cash/UPI refunds for this month")
            
            with tabs_inner[1]:
                if not jc_current_matches.empty:
                    st.dataframe(jc_current_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Jumbocash refunds for this month")
            
            with tabs_inner[2]:
                if not manual_current_matches.empty:
                    st.dataframe(manual_current_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Manual Cash refunds for this month")
        
        # YEARLY TREND
        st.markdown("---")
        st.markdown(f"## 📈 Yearly Refund Trend (Jan - {datetime(current_year, current_month, 1).strftime('%B')})")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.markdown(f"""
            <div class="trend-card">
                <p style="margin: 0; opacity: 0.8;">Current Year</p>
                <h2 style="margin: 5px 0;">{current_year}</h2>
                <h1 style="margin: 5px 0;">{current_year_count}</h1>
                <p style="margin: 0; opacity: 0.9;">Jan - {datetime(current_year, current_month, 1).strftime('%b')} Total</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="trend-card-previous">
                <p style="margin: 0; opacity: 0.8;">Previous Year</p>
                <h2 style="margin: 5px 0;">{current_year - 1}</h2>
                <h1 style="margin: 5px 0;">{last_year_count}</h1>
                <p style="margin: 0; opacity: 0.9;">Jan - {datetime(current_year, current_month, 1).strftime('%b')} Total</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if last_year_count > 0:
                change = ((current_year_count - last_year_count) / last_year_count) * 100
                direction = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                change_text = f"{direction} {abs(change):.1f}%"
            else:
                change_text = "New data" if current_year_count > 0 else "No data"
            
            st.markdown(f"""
            <div style="background-color: #f8f9fa; border-radius: 10px; padding: 20px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                <p style="margin: 0; color: #6c757d; font-size: 14px;">Year-over-Year Change<br><small style="color: #999;">(Jan - {datetime(current_year, current_month, 1).strftime('%b')})</small></p>
                <h2 style="margin: 5px 0; color: {'#28a745' if current_year_count >= last_year_count else '#dc3545'}">{change_text}</h2>
                <p style="margin: 0; color: #6c757d; font-size: 14px;">{current_year_count} vs {last_year_count} refunds</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Monthly breakdown
        st.markdown("### 📅 Monthly Breakdown")
        monthly_data = []
        for i, month in enumerate(month_names):
            status = "📍 Current" if i == month_input - 1 else ""
            if selected_year == current_year and i >= current_month:
                status = "⏳ Future" if status != "📍 Current" else status
            monthly_data.append({"Month": month, "Refunds": monthly_counts[i], "Status": status})
        
        monthly_df = pd.DataFrame(monthly_data)
        
        def highlight_current(row):
            if row['Status'] == '📍 Current':
                return ['background-color: #e3f2fd'] * len(row)
            elif row['Status'] == '⏳ Future':
                return ['background-color: #f5f5f5; color: #999'] * len(row)
            return [''] * len(row)
        
        st.dataframe(monthly_df.style.apply(highlight_current, axis=1), use_container_width=True, hide_index=True)

# ================= TAB 2: Bank Transfer Refund Details =================
with tab2:
    st.markdown("## 🏦 Bank Transfer Refund Details")
    st.markdown("*Search for a bank transfer refund by Ticket ID and view all details including UTR number, status, and transaction information*")
    
    # Show sheet access status
    st.info("📌 Sheet ID: `1QgGIeSgCSXSE_8CDosYWcAEF2NkA249Mv_EIafJrIj8`")
    st.info("📌 Service Account: `refund-tracker-app@refund-tracker-app-492509.iam.gserviceaccount.com`")
    st.info("📌 Make sure the service account has EDITOR access to the sheet")
    
    ticket_id_input = st.text_input("Enter Ticket ID")
    
    if st.button("🔍 Search Bank Transfer"):
        if not ticket_id_input:
            st.warning("Please enter a Ticket ID")
            st.stop()
        
        ticket_id = ticket_id_input.strip()
        
        with st.spinner(f"Searching for Ticket ID: {ticket_id}..."):
            # Load bank transfer data
            try:
                bank_df = load_sheet(st.secrets["bank_transfer_sheet_id"], "CD Refund Sheet")
                if bank_df.empty:
                    st.error("❌ No data found in the sheet. Please check:\n1. Sheet ID is correct\n2. Service account has access\n3. Sheet contains data")
                    st.stop()
            except Exception as e:
                st.error(f"❌ Error loading bank transfer sheet: {str(e)}")
                st.info("""
                **To fix this issue:**
                1. Open the Google Sheet: https://docs.google.com/spreadsheets/d/1QgGIeSgCSXSE_8CDosYWcAEF2NkA249Mv_EIafJrIj8/edit
                2. Click the 'Share' button (top right)
                3. Add this email as Editor:
                   `refund-tracker-app@refund-tracker-app-492509.iam.gserviceaccount.com`
                4. Click 'Send'
                5. Wait 2-3 minutes for permissions to propagate
                6. Refresh the app
                """)
                st.stop()
            
            # Search for ticket in bank transfer sheet
            bank_match = get_bank_transfer_data(bank_df, ticket_id)
        
        # Display results
        if bank_match.empty:
            st.warning(f"No bank transfer records found for Ticket ID: {ticket_id}")
        else:
            st.success(f"✅ Found {len(bank_match)} bank transfer record(s) for Ticket ID: {ticket_id}")
            
            # Display Bank Transfer details as a nice card
            st.markdown("---")
            st.markdown("## 📋 Bank Transfer Details")
            
            # Show as a nice card
            for _, row in bank_match.iterrows():
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 10px 0; border: 1px solid #dee2e6;">
                    <h4>💰 Bank Transfer Information</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 8px; font-weight: bold; width: 40%;">Ticket ID:</td><td style="padding: 8px;">{row.get('Ticket ID', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Amount:</td><td style="padding: 8px; color: #28a745; font-weight: bold;">{row.get('Amount (₹)', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">UTR Number:</td><td style="padding: 8px; font-family: monospace;">{row.get('UTR Number', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Status:</td><td style="padding: 8px;">{row.get('Status', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Date:</td><td style="padding: 8px;">{row.get('Date', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Hub:</td><td style="padding: 8px;">{row.get('Hub', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">City:</td><td style="padding: 8px;">{row.get('City', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Reason:</td><td style="padding: 8px;">{row.get('Reason', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Phone Number:</td><td style="padding: 8px;">{row.get('Phone Number', 'N/A')}</td></tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)
            
            # Also show as dataframe
            st.markdown("### 📊 Data View")
            st.dataframe(bank_match, use_container_width=True, hide_index=True)
            
            # Summary
            st.markdown("---")
            st.markdown("## 📊 Summary")
            
            total_amount = 0
            if "Amount (₹)" in bank_match.columns:
                total_amount = bank_match["Amount (₹)"].str.replace("₹", "").str.replace(",", "").astype(float).sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Records", len(bank_match))
            with col2:
                st.metric("Total Amount", f"₹{total_amount:,.2f}")
            
            # Download button
            csv = bank_match.to_csv(index=False)
            st.download_button(
                "📥 Download Bank Transfer Details",
                data=csv,
                file_name=f"bank_transfer_{ticket_id}.csv",
                mime="text/csv"
            )

# ================= TAB 3: High Risk Customers =================
with tab3:
    st.markdown("## 🚨 High Risk Customers")
    
    st.markdown("""
    <div class="info-box">
        <b>📖 Risk Assessment:</b><br>
        🔴🔴 EXTREME: (Amount > ₹500 AND Avg >= 3) OR (4+ refunds EVERY month) OR (5+ refunds in ANY month)<br>
        🔴 HIGH: Amount <= ₹500 AND Avg >= 3<br>
        🟡 POTENTIAL: Avg >= 2 OR Active in 3+ months OR Refunds in 4+ months
    </div>
    """, unsafe_allow_html=True)
    
    @st.cache_data(ttl=300)
    def load_all_data():
        cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
        jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
        manual_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")
        return cash_df, jc_df, manual_df
    
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
    
    if st.button("🔄 Load High Risk Customers"):
        cash_df, jc_df, manual_df = load_all_data()
        with st.spinner("Analyzing customer data..."):
            high_risk_df = get_high_risk_customers_optimized(cash_df, jc_df, manual_df, current_year, current_month)
            st.session_state.high_risk_data = high_risk_df
    
    if st.session_state.high_risk_data is not None and not st.session_state.high_risk_data.empty:
        high_risk_df = st.session_state.high_risk_data
        risk_order = {"🔴🔴 EXTREME": 0, "🔴 HIGH": 1, "🟡 POTENTIAL": 2}
        high_risk_df["Risk_Order"] = high_risk_df["Risk Level"].map(risk_order)
        high_risk_df = high_risk_df.sort_values(["Risk_Order", "Total Amount"], ascending=[True, False])
        high_risk_df = high_risk_df.drop(columns=["Risk_Order"])
        
        st.success(f"Found {len(high_risk_df)} high-risk customers")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total High Risk", len(high_risk_df))
        with col2:
            st.metric("🔴🔴 Extreme", len(high_risk_df[high_risk_df["Risk Level"] == "🔴🔴 EXTREME"]))
        with col3:
            st.metric("🔴 High", len(high_risk_df[high_risk_df["Risk Level"] == "🔴 HIGH"]))
        with col4:
            st.metric("🟡 Potential", len(high_risk_df[high_risk_df["Risk Level"] == "🟡 POTENTIAL"]))
        with col5:
            st.metric("Total Amount", f"₹{high_risk_df['Total Amount'].sum():,.2f}")
        
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:current_month]
        
        column_config = {
            "BZID": st.column_config.TextColumn("BZID"),
            "Risk Level": st.column_config.TextColumn("Risk Level"),
            "Status": st.column_config.TextColumn("Status"),
            "Total Refunds": st.column_config.NumberColumn("Total Refunds", format="%d"),
            "Monthly Average": st.column_config.NumberColumn("Avg/Month", format="%.2f"),
            "Months Active": st.column_config.NumberColumn("Months Active", format="%d"),
            "Max Monthly Refunds": st.column_config.NumberColumn("Max/Month", format="%d"),
            "Total Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
            "Cash_UPI": st.column_config.NumberColumn("Cash/UPI (₹)", format="₹%.2f"),
            "Jumbocash": st.column_config.NumberColumn("Jumbocash (₹)", format="₹%.2f"),
            "Manual_Cash": st.column_config.NumberColumn("Manual Cash (₹)", format="₹%.2f"),
        }
        for month in month_abbr:
            column_config[month] = st.column_config.TextColumn(month)
        
        def highlight_risk(row):
            risk = row.get('Risk Level', '')
            if 'EXTREME' in risk:
                return ['background-color: #dc3545; color: white; font-weight: bold;'] * len(row)
            elif 'HIGH' in risk:
                return ['background-color: #f8d7da; font-weight: bold;'] * len(row)
            elif 'POTENTIAL' in risk:
                return ['background-color: #fff3cd;'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            high_risk_df.style.apply(highlight_risk, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        csv = high_risk_df.to_csv(index=False)
        st.download_button("📥 Download Report", data=csv, file_name=f"high_risk_customers_{current_year}.csv", mime="text/csv")
        
    elif st.session_state.high_risk_data is not None:
        st.info("✅ No high-risk customers found!")

# ================= TAB 4: City Analysis =================
with tab4:
    st.markdown("## 🏙️ City-wise Refund Analysis")
    st.markdown("*City-wise refund amounts and instances (standardized city names)*")
    
    @st.cache_data(ttl=300)
    def load_city_data():
        cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
        jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
        manual_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")
        return cash_df, jc_df, manual_df
    
    if 'city_data' not in st.session_state:
        st.session_state.city_data = None
    
    if st.button("🔄 Load City Analysis"):
        cash_df, jc_df, manual_df = load_city_data()
        with st.spinner("Analyzing city data..."):
            city_data = get_city_analysis(cash_df, jc_df, manual_df, current_year, current_month)
            st.session_state.city_data = city_data
    
    if st.session_state.city_data is not None and not st.session_state.city_data.empty:
        city_df = st.session_state.city_data
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cities", city_df["City"].nunique())
        with col2:
            st.metric("Total Instances", city_df["Total_Instances"].sum())
        with col3:
            st.metric("Total Amount", f"₹{city_df['Total_Amount'].sum():,.2f}")
        
        st.dataframe(
            city_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "City": st.column_config.TextColumn("City"),
                "Total_Instances": st.column_config.NumberColumn("Total Instances", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f")
            }
        )
        
        st.markdown("### 🔝 Top Cities by Refund Amount")
        st.bar_chart(city_df.set_index("City")["Total_Amount"].head(15))
        
    elif st.session_state.city_data is not None:
        st.info("✅ No city data found!")

# ================= TAB 5: Hub Analysis =================
with tab5:
    st.markdown("## 🏪 Hub-wise Refund Analysis")
    st.markdown("*Hub-wise refund amounts and instances (original hub codes preserved)*")
    
    @st.cache_data(ttl=300)
    def load_hub_data():
        cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
        jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
        manual_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")
        return cash_df, jc_df, manual_df
    
    if 'hub_data' not in st.session_state:
        st.session_state.hub_data = None
    
    if st.button("🔄 Load Hub Analysis"):
        cash_df, jc_df, manual_df = load_hub_data()
        with st.spinner("Analyzing hub data..."):
            hub_data = get_hub_analysis(cash_df, jc_df, manual_df, current_year, current_month)
            st.session_state.hub_data = hub_data
    
    if st.session_state.hub_data is not None and not st.session_state.hub_data.empty:
        hub_df = st.session_state.hub_data
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Hubs", hub_df["Hub"].nunique())
        with col2:
            st.metric("Total Instances", hub_df["Total_Instances"].sum())
        with col3:
            st.metric("Total Amount", f"₹{hub_df['Total_Amount'].sum():,.2f}")
        
        st.dataframe(
            hub_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hub": st.column_config.TextColumn("Hub"),
                "Total_Instances": st.column_config.NumberColumn("Total Instances", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f")
            }
        )
        
        st.markdown("### 🔝 Top Hubs by Refund Amount")
        st.bar_chart(hub_df.set_index("Hub")["Total_Amount"].head(15))
        
    elif st.session_state.hub_data is not None:
        st.info("✅ No hub data found!")

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
