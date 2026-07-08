import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: Less than 5 refunds → APPROVE | 5 or more refunds → DENY")

# Custom CSS for better styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin: 5px;
    }
    .trend-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        margin: 5px;
    }
    .trend-card-previous {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 10px;
        padding: 20px;
        color: white;
        margin: 5px;
    }
    .decision-approve {
        background-color: #d4edda;
        border-radius: 10px;
        padding: 20px;
        border-left: 5px solid #28a745;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    .decision-deny {
        background-color: #f8d7da;
        border-radius: 10px;
        padding: 20px;
        border-left: 5px solid #dc3545;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    .decision-icon {
        font-size: 48px;
        line-height: 1;
    }
    .decision-text {
        flex: 1;
    }
    .decision-text h2 {
        margin: 0;
    }
    .decision-text p {
        margin: 5px 0 0 0;
        font-size: 18px;
    }
    .info-box {
        background-color: #e7f3ff;
        border-left: 4px solid #2196F3;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .risk-extreme {
        background-color: #dc3545;
        color: white;
        font-weight: bold;
    }
    .risk-high {
        background-color: #f8d7da;
        font-weight: bold;
    }
    .risk-potential {
        background-color: #fff3cd;
    }
    </style>
""", unsafe_allow_html=True)

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

    client = get_client()

    sheet = client.open_by_key(sheet_id)

    ws = sheet.worksheet(sheet_name)

    data = ws.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])

    df.columns = df.columns.str.strip()

    df = fix_duplicate_columns(df)

    return df


# ================= GET REFUND COUNT FOR PERIOD =================
@st.cache_data(ttl=300)
def get_refund_count_for_period(df, bzid, year, start_month=1, end_month=12):
    """Get unique refund count for a specific period within a year"""
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
    """Get refund counts for each month of a year"""
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

# ================= GET PRODUCT AND CITY ANALYSIS =================
@st.cache_data(ttl=300)
def get_product_city_analysis(cash_df, jc_df, manual_df, year, current_month, selected_month=None):
    """Analyze product and city trends for refunds using actual Product Names"""
    
    def prepare_analysis_df(df):
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Product", "City"])
        
        df = df.copy()
        
        # Find BZID column
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        
        if bzid_col is None:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Product", "City"])
        
        df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        
        # Find Date column
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Product", "City"])
        
        # Convert to datetime - FIXED
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        
        # If date conversion failed, try alternative
        if df["Date"].isna().all():
            try:
                df["Date"] = pd.to_datetime(df[date_col], errors="coerce", infer_datetime_format=True)
            except:
                pass
        
        # Drop rows with invalid dates
        df = df[df["Date"].notna()]
        
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Product", "City"])
        
        # Filter to current year
        df = df[df["Date"].dt.year == year]
        
        # If a specific month is selected, filter by that month
        if selected_month is not None:
            df = df[df["Date"].dt.month == selected_month]
        
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Product", "City"])
        
        # Find Amount column
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        # Find Product Name column - prioritize actual product names
        product_col = None
        for col in ["Product Name", "Product", "Product name", "product_name", "Item Name", "item_name"]:
            if col in df.columns:
                product_col = col
                break
        
        if product_col:
            df["Product"] = df[product_col].astype(str)
        else:
            for col in ["Order Item ID", "Order Item Id", "Order item ID", "DH NAME", "DH Name"]:
                if col in df.columns:
                    df["Product"] = df[col].astype(str)
                    break
            else:
                df["Product"] = "Unknown Product"
        
        # Find City column
        city_col = None
        for col in ["City", "city", "Hub", "hub", "City Name", "CityName"]:
            if col in df.columns:
                city_col = col
                break
        
        if city_col:
            df["City"] = df[city_col].astype(str)
        else:
            df["City"] = "Unknown City"
        
        return df[["BZID", "Date", "Amount", "Product", "City"]]
    
    # Prepare all dataframes
    cash_analysis = prepare_analysis_df(cash_df)
    jc_analysis = prepare_analysis_df(jc_df)
    manual_analysis = prepare_analysis_df(manual_df)
    
    # Combine all data
    all_analysis = pd.concat([cash_analysis, jc_analysis, manual_analysis], ignore_index=True)
    
    if all_analysis.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Clean product names
    all_analysis["Product"] = all_analysis["Product"].str.replace("BLTORDITM-", "", regex=False)
    all_analysis["Product"] = all_analysis["Product"].str.replace("_", " ", regex=False)
    all_analysis["Product"] = all_analysis["Product"].str.strip()
    
    # Add month name - FIXED: Ensure Date is datetime first
    if not pd.api.types.is_datetime64_any_dtype(all_analysis["Date"]):
        all_analysis["Date"] = pd.to_datetime(all_analysis["Date"], errors="coerce")
    
    all_analysis["Month"] = all_analysis["Date"].dt.strftime("%B")
    
    # Top products by refund amount
    top_products = all_analysis.groupby("Product").agg(
        Total_Amount=("Amount", "sum"),
        Refund_Count=("BZID", "count"),
        Unique_Customers=("BZID", "nunique")
    ).reset_index().sort_values("Total_Amount", ascending=False).head(10)
    
    # Top cities by refund amount
    top_cities = all_analysis.groupby("City").agg(
        Total_Amount=("Amount", "sum"),
        Refund_Count=("BZID", "count"),
        Unique_Customers=("BZID", "nunique")
    ).reset_index().sort_values("Total_Amount", ascending=False).head(10)
    
    # Monthly product breakdown
    monthly_products = all_analysis.groupby(["Month", "Product"]).agg(
        Total_Amount=("Amount", "sum"),
        Refund_Count=("BZID", "count")
    ).reset_index().sort_values(["Month", "Total_Amount"], ascending=[True, False])
    
    # Identify repeated product issues (products that appear in multiple months)
    product_months = all_analysis.groupby("Product").agg(
        Months=("Month", lambda x: list(x.unique())),
        Month_Count=("Month", "nunique"),
        Total_Amount=("Amount", "sum"),
        Total_Refunds=("BZID", "count")
    ).reset_index()
    
    repeated_products = product_months[product_months["Month_Count"] >= 2].sort_values("Month_Count", ascending=False)
    repeated_products["Months"] = repeated_products["Months"].apply(lambda x: ", ".join(x))
    
    return top_products, top_cities, monthly_products, repeated_products

# ================= OPTIMIZED: GET HIGH RISK CUSTOMERS =================
@st.cache_data(ttl=300)
def get_high_risk_customers_optimized(cash_df, jc_df, manual_df, year, current_month):
    """
    ULTRA-OPTIMIZED version using vectorized operations only
    """
    if current_month is None:
        return pd.DataFrame()
    
    # Prepare all dataframes with common structure
    def prepare_df(df, df_type):
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        df = df.copy()
        
        # Find BZID column
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        
        if bzid_col is None:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        
        # Find Date column
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
        
        # Filter to current year up to current month
        df = df[
            (df["Date"].dt.year == year) &
            (df["Date"].dt.month <= current_month) &
            (df["Date"].notna())
        ]
        
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Date", "Amount", "Ticket"])
        
        # Find Amount column
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        # Find Ticket column
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
    
    # Prepare all three dataframes
    cash_prep = prepare_df(cash_df, "cash")
    jc_prep = prepare_df(jc_df, "jc")
    manual_prep = prepare_df(manual_df, "manual")
    
    # Combine all data
    all_data = pd.concat([cash_prep, jc_prep, manual_prep], ignore_index=True)
    
    if all_data.empty:
        return pd.DataFrame()
    
    # Ensure Date is datetime
    if not pd.api.types.is_datetime64_any_dtype(all_data["Date"]):
        all_data["Date"] = pd.to_datetime(all_data["Date"], errors="coerce")
    
    all_data = all_data[all_data["Date"].notna()]
    
    if all_data.empty:
        return pd.DataFrame()
    
    # Extract month from date
    all_data["Month"] = all_data["Date"].dt.month
    
    # Group by BZID and month
    monthly_summary = all_data.groupby(["BZID", "Month"]).agg(
        Refund_Count=("Ticket", "nunique"),
        Total_Amount=("Amount", "sum")
    ).reset_index()
    
    # Pivot to get monthly counts
    monthly_counts_pivot = monthly_summary.pivot(
        index="BZID", 
        columns="Month", 
        values="Refund_Count"
    ).fillna(0)
    
    # Pivot to get monthly amounts
    monthly_amounts_pivot = monthly_summary.pivot(
        index="BZID", 
        columns="Month", 
        values="Total_Amount"
    ).fillna(0)
    
    # Fill missing months with 0
    for month in range(1, current_month + 1):
        if month not in monthly_counts_pivot.columns:
            monthly_counts_pivot[month] = 0
        if month not in monthly_amounts_pivot.columns:
            monthly_amounts_pivot[month] = 0
    
    # Sort columns
    monthly_counts_pivot = monthly_counts_pivot[sorted(monthly_counts_pivot.columns)]
    monthly_amounts_pivot = monthly_amounts_pivot[sorted(monthly_amounts_pivot.columns)]
    
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    results = []
    
    for bzid in monthly_counts_pivot.index:
        monthly_counts = monthly_counts_pivot.loc[bzid].values.tolist()
        monthly_amounts = monthly_amounts_pivot.loc[bzid].values.tolist()
        
        # Skip if no data
        if sum(monthly_counts) == 0:
            continue
        
        # Calculate metrics
        total_refunds = sum(monthly_counts)
        avg_refunds = total_refunds / current_month
        months_with_refunds = sum(1 for c in monthly_counts if c > 0)
        max_monthly_refunds = max(monthly_counts) if monthly_counts else 0
        
        # Check if active in last 3 months
        last_3_months = monthly_counts[-3:] if len(monthly_counts) >= 3 else monthly_counts
        active_in_last_3 = sum(1 for c in last_3_months if c > 0) >= 2
        
        # Get total amount
        total_amount = sum(monthly_amounts)
        
        # Get payment type breakdown
        cash_total = cash_prep[cash_prep["BZID"] == bzid]["Amount"].sum() if not cash_prep.empty else 0
        jc_total = jc_prep[jc_prep["BZID"] == bzid]["Amount"].sum() if not jc_prep.empty else 0
        manual_total = manual_prep[manual_prep["BZID"] == bzid]["Amount"].sum() if not manual_prep.empty else 0
        
        # ===== DEFUALTER DETECTION =====
        # Check if customer has 4+ refunds in every month (consistent defaulter)
        consistent_defaulter = all(count >= 4 for count in monthly_counts[:current_month])
        
        # Check if customer has 5+ refunds in any month (policy breach)
        has_policy_breach = max_monthly_refunds >= 5
        
        # Check if customer has refunds in 4+ months (frequent user)
        frequent_user = months_with_refunds >= 4
        
        # ===== UPDATED RISK ASSESSMENT =====
        # 1. EXTREME: (Amount > 500 AND Avg >= 3) OR Consistent Defaulter (4+ every month)
        if (total_amount > 500 and avg_refunds >= 3) or consistent_defaulter:
            risk_level = "🔴🔴 EXTREME"
        # 2. HIGH: Amount <= 500 AND Avg >= 3 OR Policy Breach (5+ in a month)
        elif (total_amount <= 500 and avg_refunds >= 3) or has_policy_breach:
            risk_level = "🔴 HIGH"
        # 3. POTENTIAL: Avg >= 2 OR Active in 3+ months OR Frequent user (4+ months)
        elif avg_refunds >= 2 or months_with_refunds >= 3 or frequent_user:
            risk_level = "🟡 POTENTIAL"
        else:
            continue
        
        # Create monthly breakdown
        monthly_breakdown = {}
        for i, (count, amount) in enumerate(zip(monthly_counts, monthly_amounts)):
            if i < current_month:
                if count > 0:
                    monthly_breakdown[month_abbr[i]] = f"{int(count)} [₹{amount:.0f}]"
                else:
                    monthly_breakdown[month_abbr[i]] = "0"
        
        # Add activity status
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

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= TAB SELECTION =================
tab1, tab2, tab3 = st.tabs(["🔍 Individual Search", "📊 High Risk Customers", "📈 Product & City Analysis"])

# ================= TAB 1: Individual Search =================
with tab1:
    # ================= INPUT =================
    col1, col2 = st.columns(2)

    bzid_input = col1.text_input("Enter BZID")

    current_year = datetime.now().year
    current_month = datetime.now().month

    month_options = {
        datetime(current_year, i, 1).strftime("%B %Y"): i
        for i in range(1, 13)
    }

    selected_month_label = col2.selectbox(
        "Select Month",
        list(month_options.keys())
    )

    month_input = month_options[selected_month_label]

    selected_year = int(selected_month_label.split()[-1])

    # ================= PROCESS =================
    if st.button("Fetch Details"):

        if not bzid_input:
            st.warning("Enter BZID")
            st.stop()

        bzid = bzid_input.strip().upper()

        with st.spinner("Fetching data..."):
            # ================= LOAD SHEETS =================
            cash_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "Form Responses 1"
            )

            jc_df = load_sheet(
                st.secrets["jumbocash_sheet_id"],
                "Form Responses 1"
            )

            manual_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "cash refund"
            )

            # =====================================================
            # CASH / UPI - Clean and prepare data
            # =====================================================

            cash_df["BZID"] = (
                cash_df["Business ID"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            cash_df["Date"] = pd.to_datetime(
                cash_df["Date"],
                errors="coerce"
            )

            if "Timestamp" in cash_df.columns:
                cash_df["Date"] = cash_df["Date"].fillna(
                    pd.to_datetime(
                        cash_df["Timestamp"],
                        errors="coerce"
                    )
                )

            cash_current_matches = cash_df[
                (cash_df["BZID"] == bzid) &
                (cash_df["Date"].notna()) &
                (cash_df["Date"].dt.month == month_input) &
                (cash_df["Date"].dt.year == selected_year)
            ]

            # =====================================================
            # JUMBOCASH - Clean and prepare data
            # =====================================================

            jc_df.columns = jc_df.columns.str.strip()

            jc_df["BZID"] = (
                jc_df["BZID"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            if "date" in jc_df.columns:
                jc_df["Date"] = pd.to_datetime(
                    jc_df["date"],
                    errors="coerce"
                )
            elif "Date" in jc_df.columns:
                jc_df["Date"] = pd.to_datetime(
                    jc_df["Date"],
                    errors="coerce"
                )
            else:
                jc_df["Date"] = pd.NaT

            if "Timestamp" in jc_df.columns:
                jc_df["Date"] = jc_df["Date"].fillna(
                    pd.to_datetime(
                        jc_df["Timestamp"],
                        errors="coerce"
                    )
                )

            jc_current_matches = jc_df[
                (jc_df["BZID"] == bzid) &
                (jc_df["Date"].notna()) &
                (jc_df["Date"].dt.month == month_input) &
                (jc_df["Date"].dt.year == selected_year)
            ]

            # =====================================================
            # MANUAL CASH - Clean and prepare data
            # =====================================================

            manual_df["BZID"] = (
                manual_df["BZID"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            manual_df["Date"] = pd.to_datetime(
                manual_df["Date"],
                errors="coerce"
            )

            if "Timestamp" in manual_df.columns:
                manual_df["Date"] = manual_df["Date"].fillna(
                    pd.to_datetime(
                        manual_df["Timestamp"],
                        errors="coerce"
                    )
                )

            manual_current_matches = manual_df[
                (manual_df["BZID"] == bzid) &
                (manual_df["Date"].notna()) &
                (manual_df["Date"].dt.month == month_input) &
                (manual_df["Date"].dt.year == selected_year)
            ]

            # =====================================================
            # COUNTS FOR CURRENT MONTH
            # =====================================================

            cash_count_current = (
                cash_current_matches["Ticket Number"].nunique()
                if not cash_current_matches.empty
                else 0
            )

            jc_count_current = (
                jc_current_matches["Ticket ID"].nunique()
                if not jc_current_matches.empty
                else 0
            )

            manual_count_current = (
                manual_current_matches["Ticket No"].nunique()
                if not manual_current_matches.empty
                else 0
            )

            total_count_current = cash_count_current + jc_count_current + manual_count_current

            # =====================================================
            # AMOUNTS FOR CURRENT MONTH
            # =====================================================

            cash_amount_current = (
                pd.to_numeric(
                    cash_current_matches["Amount"],
                    errors="coerce"
                ).sum()
                if not cash_current_matches.empty
                else 0
            )

            jc_amount_current = (
                pd.to_numeric(
                    jc_current_matches["Amount"],
                    errors="coerce"
                ).sum()
                if not jc_current_matches.empty
                else 0
            )

            manual_amount_current = (
                pd.to_numeric(
                    manual_current_matches["Amount"],
                    errors="coerce"
                ).sum()
                if not manual_current_matches.empty
                else 0
            )

            total_amount_current = cash_amount_current + jc_amount_current + manual_amount_current

            # =====================================================
            # GET YEARLY TREND DATA
            # =====================================================
            
            all_refunds = pd.concat([
                cash_df[["BZID", "Date"]],
                jc_df[["BZID", "Date"]],
                manual_df[["BZID", "Date"]]
            ], ignore_index=True)
            
            current_year_count = get_refund_count_for_period(
                all_refunds, 
                bzid, 
                current_year, 
                start_month=1, 
                end_month=current_month
            )
            
            last_year_count = get_refund_count_for_period(
                all_refunds, 
                bzid, 
                current_year - 1, 
                start_month=1, 
                end_month=current_month
            )
            
            month_names, monthly_counts = get_monthly_counts(all_refunds, bzid, current_year)

        # =====================================================
        # DISPLAY: Individual Search Results
        # =====================================================
        
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
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #721c24;">
                        Limit reached! Walk away from this request.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="text-align: center; padding: 10px; background-color: #d4edda; border-radius: 10px; margin-top: 10px;">
                    <span style="font-size: 32px;">✅</span>
                    <span style="font-size: 24px; margin-left: 10px;">👍</span>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #155724;">
                        All good! Proceed with the refund.
                    </p>
                </div>
                """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="💳 Cash / UPI",
                    value=cash_count_current,
                    delta=f"₹{round(cash_amount_current, 2)}",
                    delta_color="off"
                )
            
            with col2:
                st.metric(
                    label="🏦 Jumbocash",
                    value=jc_count_current,
                    delta=f"₹{round(jc_amount_current, 2)}",
                    delta_color="off"
                )
            
            col3, col4 = st.columns(2)
            with col3:
                st.metric(
                    label="💵 Manual Cash",
                    value=manual_count_current,
                    delta=f"₹{round(manual_amount_current, 2)}",
                    delta_color="off"
                )
            
            with col4:
                st.metric(
                    label="📦 Total",
                    value=total_count_current,
                    delta=f"₹{round(total_amount_current, 2)}",
                    delta_color="off"
                )
        
        with col_right:
            st.markdown(f"## 📋 Refund Details")
            st.markdown(f"### {selected_month_label}")
            
            tabs = st.tabs(["💳 Cash/UPI", "🏦 Jumbocash", "💵 Manual Cash"])
            
            with tabs[0]:
                if not cash_current_matches.empty:
                    st.dataframe(
                        cash_current_matches.reset_index(drop=True),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No Cash/UPI refunds for this month")
            
            with tabs[1]:
                if not jc_current_matches.empty:
                    st.dataframe(
                        jc_current_matches.reset_index(drop=True),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No Jumbocash refunds for this month")
            
            with tabs[2]:
                if not manual_current_matches.empty:
                    st.dataframe(
                        manual_current_matches.reset_index(drop=True),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No Manual Cash refunds for this month")

        # =====================================================
        # YEARLY TREND
        # =====================================================
        
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
                <p style="margin: 0; color: #6c757d; font-size: 14px;">
                    {current_year_count} vs {last_year_count} refunds
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Monthly breakdown
        st.markdown("### 📅 Monthly Breakdown")
        
        monthly_data = []
        for i, month in enumerate(month_names):
            status = "📍 Current" if i == month_input - 1 else ""
            if selected_year == current_year and i >= current_month:
                status = "⏳ Future" if status != "📍 Current" else status
            monthly_data.append({
                "Month": month,
                "Refunds": monthly_counts[i],
                "Status": status
            })
        
        monthly_df = pd.DataFrame(monthly_data)
        
        def highlight_current(row):
            if row['Status'] == '📍 Current':
                return ['background-color: #e3f2fd'] * len(row)
            elif row['Status'] == '⏳ Future':
                return ['background-color: #f5f5f5; color: #999'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            monthly_df.style.apply(highlight_current, axis=1),
            use_container_width=True,
            hide_index=True
        )

# ================= TAB 2: High Risk Customers =================
with tab2:
    st.markdown("## 🚨 High Risk Customers - 10X Approach")
    
    # Add explanation box with updated criteria
    st.markdown("""
    <div class="info-box">
        <b>📖 Defaulter Detection & Risk Assessment:</b><br><br>
        <b>🔴🔴 EXTREME RISK:</b> (Total Amount > ₹500 AND Avg >= 3) OR (4+ refunds EVERY month) OR (5+ refunds in ANY month)<br>
        <b>🔴 HIGH RISK:</b> Total Amount <= ₹500 AND Avg >= 3<br>
        <b>🟡 POTENTIAL RISK:</b> Avg >= 2 OR Active in 3+ months OR Refunds in 4+ months<br><br>
        <b>Why this approach identifies defaulters:</b><br>
        • <b>Consistent Defaulter</b> (4+ refunds every month) = 🔴🔴 EXTREME<br>
        • <b>Policy Breacher</b> (5+ refunds in any month) = 🔴🔴 EXTREME<br>
        • <b>Frequent User</b> (Refunds in 4+ months) = 🟡 POTENTIAL<br>
        • BZID-1304447852 with 4 refunds every month = 🔴🔴 EXTREME ✅
    </div>
    """, unsafe_allow_html=True)
    
    # Load data once and cache it
    @st.cache_data(ttl=300)
    def load_all_data():
        with st.spinner("Loading data from Google Sheets..."):
            cash_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "Form Responses 1"
            )
            
            jc_df = load_sheet(
                st.secrets["jumbocash_sheet_id"],
                "Form Responses 1"
            )
            
            manual_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "cash refund"
            )
            
            return cash_df, jc_df, manual_df
    
    # Initialize session state
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
    
    if st.button("🔄 Load High Risk Customers"):
        # Load all data with caching
        cash_df, jc_df, manual_df = load_all_data()
        
        # Get high risk customers using optimized function
        with st.spinner("Analyzing customer data..."):
            high_risk_df = get_high_risk_customers_optimized(
                cash_df, 
                jc_df, 
                manual_df, 
                current_year, 
                current_month
            )
            
            st.session_state.high_risk_data = high_risk_df
    
    # Display high risk data from session state
    if st.session_state.high_risk_data is not None and not st.session_state.high_risk_data.empty:
        high_risk_df = st.session_state.high_risk_data
        
        # Sort by risk level
        risk_order = {"🔴🔴 EXTREME": 0, "🔴 HIGH": 1, "🟡 POTENTIAL": 2}
        high_risk_df["Risk_Order"] = high_risk_df["Risk Level"].map(risk_order)
        high_risk_df = high_risk_df.sort_values(["Risk_Order", "Total Amount"], ascending=[True, False])
        high_risk_df = high_risk_df.drop(columns=["Risk_Order"])
        
        st.success(f"Found {len(high_risk_df)} high-risk customers")
        
        # Display metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total High Risk", len(high_risk_df))
        with col2:
            extreme_count = len(high_risk_df[high_risk_df["Risk Level"] == "🔴🔴 EXTREME"])
            st.metric("🔴🔴 Extreme", extreme_count)
        with col3:
            high_count = len(high_risk_df[high_risk_df["Risk Level"] == "🔴 HIGH"])
            st.metric("🔴 High Risk", high_count)
        with col4:
            potential_count = len(high_risk_df[high_risk_df["Risk Level"] == "🟡 POTENTIAL"])
            st.metric("🟡 Potential", potential_count)
        with col5:
            st.metric("Total Amount", f"₹{high_risk_df['Total Amount'].sum():,.2f}")
        
        # Get month columns
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:current_month]
        
        # Column config
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
        
        # Display dataframe with styling
        st.markdown("### 📊 Customer Monthly Refund Breakdown")
        
        # Apply styling
        def highlight_risk(row):
            risk = row.get('Risk Level', '')
            
            if 'EXTREME' in risk:
                return ['background-color: #dc3545; color: white; font-weight: bold;'] * len(row)
            elif 'HIGH' in risk:
                return ['background-color: #f8d7da; font-weight: bold;'] * len(row)
            elif 'POTENTIAL' in risk:
                return ['background-color: #fff3cd;'] * len(row)
            return [''] * len(row)
        
        styled_df = high_risk_df.style.apply(highlight_risk, axis=1)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        # Download button
        csv = high_risk_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Report",
            data=csv,
            file_name=f"high_risk_customers_{current_year}.csv",
            mime="text/csv"
        )
        
    elif st.session_state.high_risk_data is not None and st.session_state.high_risk_data.empty:
        st.info("✅ No high-risk customers found!")

# ================= TAB 3: Product & City Analysis =================
with tab3:
    st.markdown("## 📦 Product & City Refund Analysis")
    st.markdown("*Identify which products and cities are driving the highest refunds*")
    
    # Month filter
    month_filter = st.selectbox(
        "Select Month (Optional - All Months shows full year)",
        ["All Months"] + [datetime(current_year, i, 1).strftime("%B") for i in range(1, current_month + 1)]
    )
    
    # Get selected month number
    selected_month_num = None
    if month_filter != "All Months":
        month_names = [datetime(current_year, i, 1).strftime("%B") for i in range(1, 13)]
        selected_month_num = month_names.index(month_filter) + 1
    
    # Load data
    @st.cache_data(ttl=300)
    def load_analysis_data():
        with st.spinner("Loading data..."):
            cash_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "Form Responses 1"
            )
            
            jc_df = load_sheet(
                st.secrets["jumbocash_sheet_id"],
                "Form Responses 1"
            )
            
            manual_df = load_sheet(
                st.secrets["cash_upi_sheet_id"],
                "cash refund"
            )
            
            return cash_df, jc_df, manual_df
    
    if st.button("🔄 Load Analysis"):
        cash_df, jc_df, manual_df = load_analysis_data()
        
        with st.spinner("Analyzing product and city trends..."):
            top_products, top_cities, monthly_products, repeated_products = get_product_city_analysis(
                cash_df, jc_df, manual_df, current_year, current_month, selected_month_num
            )
            
            st.session_state.top_products = top_products
            st.session_state.top_cities = top_cities
            st.session_state.monthly_products = monthly_products
            st.session_state.repeated_products = repeated_products
            st.session_state.selected_month = month_filter
    
    # Display analysis
    if 'top_products' in st.session_state:
        
        # Show current filter
        st.info(f"📅 Viewing data for: **{st.session_state.selected_month}**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏆 Top Products by Refund Amount")
            if not st.session_state.top_products.empty:
                st.dataframe(
                    st.session_state.top_products,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Product": st.column_config.TextColumn("Product Name"),
                        "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                        "Refund_Count": st.column_config.NumberColumn("Refund Count", format="%d"),
                        "Unique_Customers": st.column_config.NumberColumn("Unique Customers", format="%d")
                    }
                )
            else:
                st.info("No product data for selected month")
        
        with col2:
            st.markdown("### 🏙️ Top Cities by Refund Amount")
            if not st.session_state.top_cities.empty:
                st.dataframe(
                    st.session_state.top_cities,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "City": st.column_config.TextColumn("City"),
                        "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                        "Refund_Count": st.column_config.NumberColumn("Refund Count", format="%d"),
                        "Unique_Customers": st.column_config.NumberColumn("Unique Customers", format="%d")
                    }
                )
            else:
                st.info("No city data for selected month")
        
        # Repeated Product Issues
        st.markdown("---")
        st.markdown("### 🔄 Repeated Product Issues (Products with refunds in multiple months)")
        
        if 'repeated_products' in st.session_state and not st.session_state.repeated_products.empty:
            st.markdown("*Products that appear in multiple months - indicating recurring refund issues*")
            
            st.dataframe(
                st.session_state.repeated_products,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Product": st.column_config.TextColumn("Product Name"),
                    "Months": st.column_config.TextColumn("Months with Refunds"),
                    "Month_Count": st.column_config.NumberColumn("Number of Months", format="%d"),
                    "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                    "Total_Refunds": st.column_config.NumberColumn("Total Refunds", format="%d")
                }
            )
        else:
            st.info("No products with repeated refund issues found")
        
        # Monthly Product Breakdown
        st.markdown("---")
        st.markdown("### 📊 Monthly Product Refund Breakdown")
        
        if 'monthly_products' in st.session_state and not st.session_state.monthly_products.empty:
            st.dataframe(
                st.session_state.monthly_products,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Month": st.column_config.TextColumn("Month"),
                    "Product": st.column_config.TextColumn("Product Name"),
                    "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                    "Refund_Count": st.column_config.NumberColumn("Refund Count", format="%d")
                }
            )
        else:
            st.info("No monthly product data available")

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
