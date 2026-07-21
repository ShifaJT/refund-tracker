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
        
        # Try to get the worksheet by name
        try:
            ws = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # If worksheet not found, list all available worksheets
            available_sheets = [ws.title for ws in sheet.worksheets()]
            st.error(f"❌ Worksheet '{sheet_name}' not found!")
            st.info(f"📋 Available worksheets in this sheet: {', '.join(available_sheets)}")
            # Try to use the first available worksheet
            if available_sheets:
                st.info(f"💡 Trying to use '{available_sheets[0]}' instead...")
                ws = sheet.worksheet(available_sheets[0])
            else:
                return pd.DataFrame()
        
        # Get all values
        data = ws.get_all_values()
        
        if len(data) <= 1:
            st.warning(f"⚠️ Worksheet '{sheet_name}' has no data (only headers or empty)")
            return pd.DataFrame()
        
        # Find the header row - more flexible detection
        header_row_idx = None
        for i, row in enumerate(data):
            # Check if this row contains typical column headers
            row_str = ' '.join(str(cell).lower() for cell in row if cell)
            # Look for any of these keywords in the row
            has_ticket = any(keyword in row_str for keyword in ['ticket', 'bzid', 'business id', 'id'])
            has_phone = any(keyword in row_str for keyword in ['phone', 'mobile', 'contact'])
            has_hub = any(keyword in row_str for keyword in ['hub', 'h ub'])
            has_date = any(keyword in row_str for keyword in ['date', 'timestamp'])
            has_amount = any(keyword in row_str for keyword in ['amount', 'refund'])
            
            # If we find at least 3 of these keywords, it's likely a header row
            header_score = sum([has_ticket, has_phone, has_hub, has_date, has_amount])
            if header_score >= 3:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            # If no header found, use first row as header
            header_row_idx = 0
        
        # Get headers from the identified header row
        headers = [str(col).strip() if col else f"Column_{i}" for i, col in enumerate(data[header_row_idx])]
        
        # Get data rows (after header)
        data_rows = []
        for row in data[header_row_idx + 1:]:
            # Check if row has at least one non-empty cell
            if any(cell for cell in row):
                # Check if the row looks like actual data (has at least 2 non-empty cells)
                non_empty = sum(1 for cell in row if cell and str(cell).strip())
                if non_empty >= 2:
                    data_rows.append(row)
        
        if not data_rows:
            st.warning(f"⚠️ No data rows found in worksheet '{sheet_name}'")
            return pd.DataFrame()
        
        # Ensure all rows have the same length as headers
        max_len = len(headers)
        for i, row in enumerate(data_rows):
            if len(row) < max_len:
                data_rows[i] = row + [''] * (max_len - len(row))
            elif len(row) > max_len:
                data_rows[i] = row[:max_len]
        
        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # Clean up column names
        df.columns = df.columns.str.strip()
        
        # Clean up data - remove completely empty rows
        df = df.dropna(how='all')
        
        # Fix duplicate columns
        df = fix_duplicate_columns(df)
        
        # Try to identify and standardize common column names
        rename_map = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if 'ticket' in col_lower or 'tkt' in col_lower:
                if 'id' in col_lower or 'no' in col_lower or 'number' in col_lower:
                    rename_map[col] = 'Ticket ID'
            elif 'phone' in col_lower or 'mobile' in col_lower or 'contact' in col_lower:
                rename_map[col] = 'Phone Number'
            elif 'hub' in col_lower:
                rename_map[col] = 'Hub'
            elif 'city' in col_lower:
                rename_map[col] = 'City'
            elif 'reason' in col_lower or 'issue' in col_lower:
                rename_map[col] = 'Reason'
            elif 'amount' in col_lower or 'amt' in col_lower:
                rename_map[col] = 'Amount'
            elif 'utr' in col_lower:
                rename_map[col] = 'UTR Number'
            elif 'status' in col_lower:
                rename_map[col] = 'Status'
            elif 'date' in col_lower:
                rename_map[col] = 'Date'
            elif 'bzid' in col_lower or 'business id' in col_lower:
                rename_map[col] = 'BZID'
            elif 'approved by' in col_lower:
                rename_map[col] = 'Approved By'
        
        # Apply renaming
        df = df.rename(columns=rename_map)
        
        # Reset index to avoid duplicate index issues
        df = df.reset_index(drop=True)
        
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet not found! Sheet ID: {sheet_id}")
        st.info("Please check if the sheet ID is correct and the service account has access.")
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

# ================= PREPARE DATA FORMATTING =================
def prepare_refund_df(df, source_name):
    """Prepare a refund dataframe with standardized columns"""
    # Define the standard columns we want
    standard_columns = ["BZID", "Date", "Amount", "Ticket", "Source"]
    
    if df.empty:
        return pd.DataFrame(columns=standard_columns)
    
    df = df.copy()
    
    # Find BZID column
    bzid_col = None
    for col in ["BZID", "Business ID", "BZD", "bzid"]:
        if col in df.columns:
            bzid_col = col
            break
    if bzid_col is None:
        # Try to find any column that might contain BZID
        for col in df.columns:
            if 'bzid' in col.lower() or 'business' in col.lower():
                bzid_col = col
                break
    
    if bzid_col is None:
        # If no BZID column, return empty dataframe with standard columns
        return pd.DataFrame(columns=standard_columns)
    
    df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
    
    # Find Date column
    date_col = None
    for col in ["Date", "date", "Timestamp", "timestamp"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        # Try to find any column with date in name
        for col in df.columns:
            if 'date' in col.lower() or 'timestamp' in col.lower():
                date_col = col
                break
    
    if date_col is None:
        # If no date column, return empty dataframe
        return pd.DataFrame(columns=standard_columns)
    
    # Convert date - handle different formats
    try:
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        if df["Date"].isna().all():
            # Try with dayfirst=True for DD-MM-YYYY format
            df["Date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    except:
        try:
            df["Date"] = pd.to_datetime(df[date_col], errors="coerce", infer_datetime_format=True)
        except:
            df["Date"] = pd.NaT
    
    if df["Date"].isna().all():
        return pd.DataFrame(columns=standard_columns)
    
    # Find Amount column
    amount_col = None
    for col in ["Amount", "amount", "Refund Amount"]:
        if col in df.columns:
            amount_col = col
            break
    if amount_col is None:
        for col in df.columns:
            if 'amount' in col.lower() or 'amt' in col.lower():
                amount_col = col
                break
    
    # Convert amount to numeric
    if amount_col and amount_col in df.columns:
        try:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        except (TypeError, ValueError):
            df["Amount"] = 0
    else:
        df["Amount"] = 0
    
    # Find Ticket column
    ticket_col = None
    for col in ["Ticket Number", "Ticket ID", "Ticket No", "Ticket Number_1", "Ticket ID_1"]:
        if col in df.columns:
            ticket_col = col
            break
    if ticket_col is None:
        for col in df.columns:
            if 'ticket' in col.lower():
                ticket_col = col
                break
    
    if ticket_col and ticket_col in df.columns:
        df["Ticket"] = df[ticket_col].astype(str)
    else:
        df["Ticket"] = df.index.astype(str)
    
    # Add source
    df["Source"] = source_name
    
    # Select only the columns we need
    result_df = df[["BZID", "Date", "Amount", "Ticket", "Source"]].copy()
    
    # Reset index to avoid duplicate index issues
    result_df = result_df.reset_index(drop=True)
    
    return result_df

# ================= OPTIMIZED: GET HIGH RISK CUSTOMERS =================
@st.cache_data(ttl=300)
def get_high_risk_customers_optimized(all_refunds_df, year, current_month):
    if current_month is None or all_refunds_df.empty:
        return pd.DataFrame()
    
    df = all_refunds_df.copy()
    
    # Ensure Date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()]
    if df.empty:
        return pd.DataFrame()
    
    # Filter to current year and up to current month
    df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
    if df.empty:
        return pd.DataFrame()
    
    df["Month"] = df["Date"].dt.month
    
    monthly_summary = df.groupby(["BZID", "Month"]).agg(
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
        
        # Calculate totals by source
        cash_total = df[(df["BZID"] == bzid) & (df["Source"] == "Cash/UPI")]["Amount"].sum()
        jc_total = df[(df["BZID"] == bzid) & (df["Source"] == "Jumbocash")]["Amount"].sum()
        manual_total = df[(df["BZID"] == bzid) & (df["Source"] == "Manual Cash")]["Amount"].sum()
        bank_total = df[(df["BZID"] == bzid) & (df["Source"] == "Bank Transfer")]["Amount"].sum()
        
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
            "Bank_Transfer": round(bank_total, 2),
            **monthly_breakdown
        })
    
    return pd.DataFrame(results)

# ================= BANK TRANSFER DETAIL SEARCH =================
def get_bank_transfer_data(bank_df, ticket_id):
    """Search for a ticket by ID in bank transfer sheet (CD Refund Sheet)"""
    if bank_df.empty:
        return pd.DataFrame()
    
    df = bank_df.copy()
    
    # Find Ticket ID column (case insensitive)
    ticket_col = None
    for col in df.columns:
        if col and 'ticket' in col.lower() and ('id' in col.lower() or 'no' in col.lower()):
            ticket_col = col
            break
    
    if ticket_col is None:
        st.warning("⚠️ Could not find Ticket ID column in bank transfer sheet")
        st.info(f"📋 Available columns: {', '.join(df.columns)}")
        return pd.DataFrame()
    
    # Filter by ticket ID
    df[ticket_col] = df[ticket_col].astype(str).str.strip()
    ticket_id_str = str(ticket_id).strip()
    df = df[df[ticket_col] == ticket_id_str]
    
    if df.empty:
        return pd.DataFrame()
    
    # Rename columns for better display
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower() if col else ''
        if 'ticket' in col_lower and 'id' in col_lower:
            rename_map[col] = "Ticket ID"
        elif 'phone' in col_lower:
            rename_map[col] = "Phone Number"
        elif col_lower in ['hub', 'hub name']:
            rename_map[col] = "Hub"
        elif col_lower in ['city', 'city name']:
            rename_map[col] = "City"
        elif 'reason' in col_lower or 'issue' in col_lower:
            rename_map[col] = "Reason"
        elif 'amount' in col_lower:
            rename_map[col] = "Amount"
        elif 'utr' in col_lower:
            rename_map[col] = "UTR Number"
        elif 'status' in col_lower:
            rename_map[col] = "Status"
        elif col_lower in ['date', 'date1']:
            rename_map[col] = "Date"
        elif 'approved by' in col_lower:
            rename_map[col] = "Approved By"
    
    df = df.rename(columns=rename_map)
    
    # Standardize city names if City column exists
    if "City" in df.columns:
        df["City"] = df["City"].astype(str).apply(standardize_city_name)
    
    # Convert date if exists
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
        df["Date"] = df["Date"].dt.strftime("%d-%m-%Y")
    
    # Select only columns we want to display
    display_cols = ["Ticket ID", "Phone Number", "Hub", "City", "Reason", "Amount", "UTR Number", "Status", "Date", "Approved By"]
    df_display = df[[col for col in display_cols if col in df.columns]].copy()
    
    # Format amount
    if "Amount" in df_display.columns:
        try:
            df_display["Amount"] = pd.to_numeric(df_display["Amount"], errors="coerce")
            df_display["Amount"] = df_display["Amount"].apply(lambda x: f"₹{x:.2f}" if pd.notna(x) else "₹0.00")
            df_display.rename(columns={"Amount": "Amount (₹)"}, inplace=True)
        except:
            df_display["Amount"] = "₹0.00"
            df_display.rename(columns={"Amount": "Amount (₹)"}, inplace=True)
    
    return df_display

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= TAB SELECTION =================
tab1, tab2, tab3 = st.tabs(["🔍 Individual Search", "🏦 Bank Transfer Refund Details", "📊 High Risk Customers"])

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
            # Load all sheets
            cash_df = load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1")
            jc_df = load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1")
            manual_df = load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund")
            bank_transfer_count_df = load_sheet(st.secrets["new_bank_transfer_sheet_id"], "trxn details")
            
            # Prepare dataframes with standardized columns
            cash_prep = prepare_refund_df(cash_df, "Cash/UPI")
            jc_prep = prepare_refund_df(jc_df, "Jumbocash")
            manual_prep = prepare_refund_df(manual_df, "Manual Cash")
            bank_prep = prepare_refund_df(bank_transfer_count_df, "Bank Transfer")
            
            # Filter out empty dataframes before concatenation
            dfs_to_concat = []
            if not cash_prep.empty:
                dfs_to_concat.append(cash_prep)
            if not jc_prep.empty:
                dfs_to_concat.append(jc_prep)
            if not manual_prep.empty:
                dfs_to_concat.append(manual_prep)
            if not bank_prep.empty:
                dfs_to_concat.append(bank_prep)
            
            if not dfs_to_concat:
                st.warning("No refund data found!")
                st.stop()
            
            # Combine all refunds
            all_refunds = pd.concat(dfs_to_concat, ignore_index=True)
            
            if all_refunds.empty:
                st.warning("No refund data found!")
                st.stop()
            
            # Filter by BZID
            bzid_refunds = all_refunds[all_refunds["BZID"] == bzid]
            
            if bzid_refunds.empty:
                st.warning(f"No refunds found for BZID: {bzid}")
                st.stop()
            
            # Filter by selected month and year
            month_refunds = bzid_refunds[
                (bzid_refunds["Date"].dt.month == month_input) &
                (bzid_refunds["Date"].dt.year == selected_year)
            ]
            
            # Count refunds by source for current month
            cash_count = len(month_refunds[month_refunds["Source"] == "Cash/UPI"])
            jc_count = len(month_refunds[month_refunds["Source"] == "Jumbocash"])
            manual_count = len(month_refunds[month_refunds["Source"] == "Manual Cash"])
            bank_count = len(month_refunds[month_refunds["Source"] == "Bank Transfer"])
            total_count = len(month_refunds)
            
            # Calculate amounts by source for current month
            cash_amount = month_refunds[month_refunds["Source"] == "Cash/UPI"]["Amount"].sum()
            jc_amount = month_refunds[month_refunds["Source"] == "Jumbocash"]["Amount"].sum()
            manual_amount = month_refunds[month_refunds["Source"] == "Manual Cash"]["Amount"].sum()
            bank_amount = month_refunds[month_refunds["Source"] == "Bank Transfer"]["Amount"].sum()
            total_amount = month_refunds["Amount"].sum()
            
            # Yearly trend counts
            current_year_count = get_refund_count_for_period(all_refunds, bzid, current_year, 1, current_month)
            last_year_count = get_refund_count_for_period(all_refunds, bzid, current_year - 1, 1, current_month)
            month_names, monthly_counts = get_monthly_counts(all_refunds, bzid, current_year)
            
            # Get detailed dataframes for display - filter by BZID if column exists
            cash_details = cash_df[cash_df["BZID"] == bzid] if "BZID" in cash_df.columns else pd.DataFrame()
            jc_details = jc_df[jc_df["BZID"] == bzid] if "BZID" in jc_df.columns else pd.DataFrame()
            manual_details = manual_df[manual_df["BZID"] == bzid] if "BZID" in manual_df.columns else pd.DataFrame()
            bank_details = bank_transfer_count_df[bank_transfer_count_df["BZID"] == bzid] if "BZID" in bank_transfer_count_df.columns else pd.DataFrame()
        
        # DISPLAY
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.markdown(f"## 📊 Current Month")
            st.markdown(f"### {selected_month_label}")
            
            if total_count < 5:
                st.markdown(f"""
                <div class="decision-approve">
                    <div class="decision-icon tick-mark">✅</div>
                    <div class="decision-text">
                        <h2 style="color: #28a745; margin: 0;">APPROVED</h2>
                        <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count} (Less than 5)</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="decision-deny">
                    <div class="decision-icon cross-mark">❌</div>
                    <div class="decision-text">
                        <h2 style="color: #dc3545; margin: 0;">DENIED</h2>
                        <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count} (5 or more - Limit reached)</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if total_count >= 5:
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
            
            # Metrics with 3 columns
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("💳 Cash / UPI", cash_count, f"₹{round(cash_amount, 2)}")
                st.metric("💵 Manual Cash", manual_count, f"₹{round(manual_amount, 2)}")
            with c2:
                st.metric("🏦 Jumbocash", jc_count, f"₹{round(jc_amount, 2)}")
                st.metric("🏦 Bank Transfer (New)", bank_count, f"₹{round(bank_amount, 2)}")
            with c3:
                st.metric("📦 Total", total_count, f"₹{round(total_amount, 2)}")
        
        with col_right:
            st.markdown(f"## 📋 Refund Details")
            st.markdown(f"### {selected_month_label}")
            
            tabs_inner = st.tabs(["💳 Cash/UPI", "🏦 Jumbocash", "💵 Manual Cash", "🏦 Bank Transfer"])
            
            with tabs_inner[0]:
                if not cash_details.empty:
                    st.dataframe(cash_details, use_container_width=True, height=300)
                else:
                    st.info("No Cash/UPI refunds for this month")
            
            with tabs_inner[1]:
                if not jc_details.empty:
                    st.dataframe(jc_details, use_container_width=True, height=300)
                else:
                    st.info("No Jumbocash refunds for this month")
            
            with tabs_inner[2]:
                if not manual_details.empty:
                    st.dataframe(manual_details, use_container_width=True, height=300)
                else:
                    st.info("No Manual Cash refunds for this month")
            
            with tabs_inner[3]:
                if not bank_details.empty:
                    st.dataframe(bank_details, use_container_width=True, height=300)
                else:
                    st.info("No Bank Transfer refunds for this month")
        
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

# ================= TAB 2: Bank Transfer Refund Details (CD Refund Sheet) =================
with tab2:
    st.markdown("## 🏦 Bank Transfer Refund Details")
    st.markdown("*Search for a bank transfer refund by Ticket ID and view all details including UTR number, status, and transaction information*")
    
    ticket_id_input = st.text_input("Enter Ticket ID")
    
    if st.button("🔍 Search Bank Transfer"):
        if not ticket_id_input:
            st.warning("Please enter a Ticket ID")
            st.stop()
        
        ticket_id = ticket_id_input.strip()
        
        with st.spinner(f"Searching for Ticket ID: {ticket_id}..."):
            # Load bank transfer data from CD Refund Sheet
            bank_df = load_sheet(st.secrets["bank_transfer_sheet_id"], "CD Refund Sheet")
            
            if bank_df.empty:
                st.warning("⚠️ No data found in the bank transfer sheet. Please check if the sheet has data.")
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
                status_color = "#28a745" if str(row.get('Status', '')).lower() == "success" else "#dc3545"
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 10px 0; border: 1px solid #dee2e6;">
                    <h4>💰 Bank Transfer Information</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 8px; font-weight: bold; width: 40%;">Ticket ID:</td><td style="padding: 8px;">{row.get('Ticket ID', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Phone Number:</td><td style="padding: 8px;">{row.get('Phone Number', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Hub:</td><td style="padding: 8px;">{row.get('Hub', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">City:</td><td style="padding: 8px;">{row.get('City', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Reason:</td><td style="padding: 8px;">{row.get('Reason', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Amount:</td><td style="padding: 8px; color: #28a745; font-weight: bold;">{row.get('Amount (₹)', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">UTR Number:</td><td style="padding: 8px; font-family: monospace;">{row.get('UTR Number', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Status:</td><td style="padding: 8px; color: {status_color}; font-weight: bold;">{row.get('Status', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Date:</td><td style="padding: 8px;">{row.get('Date', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Approved By:</td><td style="padding: 8px;">{row.get('Approved By', 'N/A')}</td></tr>
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
                try:
                    total_amount = bank_match["Amount (₹)"].str.replace("₹", "").str.replace(",", "").astype(float).sum()
                except:
                    total_amount = 0
            
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
        bank_df = load_sheet(st.secrets["new_bank_transfer_sheet_id"], "trxn details")
        
        # Prepare all dataframes
        cash_prep = prepare_refund_df(cash_df, "Cash/UPI")
        jc_prep = prepare_refund_df(jc_df, "Jumbocash")
        manual_prep = prepare_refund_df(manual_df, "Manual Cash")
        bank_prep = prepare_refund_df(bank_df, "Bank Transfer")
        
        # Filter out empty dataframes
        dfs_to_concat = []
        if not cash_prep.empty:
            dfs_to_concat.append(cash_prep)
        if not jc_prep.empty:
            dfs_to_concat.append(jc_prep)
        if not manual_prep.empty:
            dfs_to_concat.append(manual_prep)
        if not bank_prep.empty:
            dfs_to_concat.append(bank_prep)
        
        # Combine all refunds
        if dfs_to_concat:
            all_refunds = pd.concat(dfs_to_concat, ignore_index=True)
        else:
            all_refunds = pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket", "Source"])
        
        return all_refunds
    
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
    
    if st.button("🔄 Load High Risk Customers"):
        with st.spinner("Analyzing customer data..."):
            all_refunds = load_all_data()
            high_risk_df = get_high_risk_customers_optimized(all_refunds, current_year, current_month)
            st.session_state.high_risk_data = high_risk_df
    
    if st.session_state.high_risk_data is not None and not st.session_state.high_risk_data.empty:
        high_risk_df = st.session_state.high_risk_data
        risk_order = {"🔴🔴 EXTREME": 0, "🔴 HIGH": 1, "🟡 POTENTIAL": 2}
        high_risk_df["Risk_Order"] = high_risk_df["Risk Level"].map(risk_order)
        high_risk_df = high_risk_df.sort_values(["Risk_Order", "Total Amount"], ascending=[True, False])
        high_risk_df = high_risk_df.drop(columns=["Risk_Order"])
        
        st.success(f"Found {len(high_risk_df)} high-risk customers")
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
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
        with col6:
            st.metric("Total Refunds", high_risk_df['Total Refunds'].sum())
        
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
            "Bank_Transfer": st.column_config.NumberColumn("Bank Transfer (₹)", format="₹%.2f"),
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

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
