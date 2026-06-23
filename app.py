import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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
@st.cache_data(ttl=60)
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
    
    # Try to get unique count based on ticket column
    ticket_cols = ["Ticket Number", "Ticket ID", "Ticket No"]
    for col in ticket_cols:
        if col in df_filtered.columns:
            return df_filtered[col].nunique()
    
    # If no ticket column, return count of rows
    return len(df_filtered)

# ================= GET MONTHLY COUNTS =================
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
        # Try to get unique count based on ticket column
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
def get_high_risk_customers_optimized(all_refunds, cash_df, jc_df, manual_df, year, current_month):
    """
    Optimized version to find high risk customers based on:
    - Count of months with refunds >= 3
    """
    if all_refunds.empty or current_month is None:
        return pd.DataFrame(), pd.DataFrame()
    
    # Filter data for current year up to current month
    all_refunds_year = all_refunds[
        (all_refunds["Date"].dt.year == year) &
        (all_refunds["Date"].dt.month <= current_month)
    ]
    
    if all_refunds_year.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Group by BZID and month to get monthly refund counts
    monthly_counts_df = all_refunds_year.groupby(
        ["BZID", all_refunds_year["Date"].dt.month]
    ).size().reset_index(name="Refund_Count")
    
    # Get all BZIDs with their monthly counts
    bzid_monthly = monthly_counts_df.pivot(
        index="BZID", 
        columns="Date", 
        values="Refund_Count"
    ).fillna(0)
    
    # Fill missing months with 0
    for month in range(1, current_month + 1):
        if month not in bzid_monthly.columns:
            bzid_monthly[month] = 0
    
    # Sort columns
    bzid_monthly = bzid_monthly[sorted(bzid_monthly.columns)]
    
    # Month names for display
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Calculate metrics for each BZID
    results = []
    
    for bzid in bzid_monthly.index:
        monthly_counts = bzid_monthly.loc[bzid].values.tolist()
        
        # Skip if no data
        if sum(monthly_counts) == 0:
            continue
        
        # NEW CRITERIA: Count months with refunds (count > 0)
        months_with_refunds = sum(1 for count in monthly_counts if count > 0)
        
        # NEW: Check if customer has refunds in 3 or more months
        has_3_or_more_months = months_with_refunds >= 3
        
        # Flag if high risk (has refunds in 3+ months)
        if has_3_or_more_months:
            # Get amounts by payment type
            cash_amount = pd.to_numeric(
                cash_df[(cash_df["BZID"] == bzid) & 
                        (cash_df["Date"].dt.year == year) &
                        (cash_df["Date"].dt.month <= current_month)]["Amount"],
                errors="coerce"
            ).sum()
            
            jc_amount = pd.to_numeric(
                jc_df[(jc_df["BZID"] == bzid) & 
                      (jc_df["Date"].dt.year == year) &
                      (jc_df["Date"].dt.month <= current_month)]["Amount"],
                errors="coerce"
            ).sum()
            
            manual_amount = pd.to_numeric(
                manual_df[(manual_df["BZID"] == bzid) & 
                          (manual_df["Date"].dt.year == year) &
                          (manual_df["Date"].dt.month <= current_month)]["Amount"],
                errors="coerce"
            ).sum()
            
            total_amount = cash_amount + jc_amount + manual_amount
            
            # Calculate average refunds per month
            avg_refunds = sum(monthly_counts) / current_month
            
            # Create monthly breakdown with month names
            monthly_breakdown = {}
            for i, count in enumerate(monthly_counts):
                monthly_breakdown[month_abbr[i]] = int(count)
            
            results.append({
                "BZID": bzid,
                "Total Refunds": sum(monthly_counts),
                "Monthly Average": round(avg_refunds, 2),
                "Months Active": months_with_refunds,
                "Cash_UPI": round(cash_amount, 2),
                "Jumbocash": round(jc_amount, 2),
                "Manual_Cash": round(manual_amount, 2),
                "Total_Amount": round(total_amount, 2),
                **monthly_breakdown  # Add each month as a separate column
            })
    
    return pd.DataFrame(results), all_refunds

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= TAB SELECTION =================
tab1, tab2 = st.tabs(["🔍 Individual Search", "📊 High Risk Customers"])

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

            # Deny if 5 or more, Approve only if less than 5
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

            # Deny if 5 or more, Approve only if less than 5
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
    st.markdown("## 🚨 High Risk Customers")
    
    # Add explanation box with updated criteria
    st.markdown("""
    <div class="info-box">
        <b>📖 Updated Criteria - High Risk Customers:</b><br>
        • <b>High Risk</b> = Customers who have <b>refunds in 3 or more months</b> (Jan to current month)<br>
        • <b>Total Refunds</b> = Total refunds given to this customer from Jan to current month<br>
        • <b>Avg/Month</b> = Average refunds per month (Total Refunds ÷ Number of months)<br>
        • <b>Months Active</b> = Number of months where customer had at least 1 refund<br>
        • <b>Cash/UPI, Jumbocash, Manual Cash</b> = Total amount refunded through each payment method<br>
        • <b>Jan, Feb, Mar...</b> = Refund count in each specific month<br>
        • <span style="color: #cc0000; font-weight: bold;">Red numbers</span> = 3+ refunds in that month (⚠️ High Risk)
    </div>
    """, unsafe_allow_html=True)
    
    # Load data once and cache it
    @st.cache_data(ttl=300)
    def load_all_data():
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
    
    # Initialize session state for high risk data
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
    if 'all_refunds_data' not in st.session_state:
        st.session_state.all_refunds_data = None
    
    if st.button("🔄 Load High Risk Customers"):
        with st.spinner("Analyzing customer data..."):
            # Load all data with caching
            cash_df, jc_df, manual_df = load_all_data()
            
            # Clean and prepare data
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
            
            # Combine all data
            all_refunds = pd.concat([
                cash_df[["BZID", "Date"]],
                jc_df[["BZID", "Date"]],
                manual_df[["BZID", "Date"]]
            ], ignore_index=True)
            
            # Store in session state
            st.session_state.all_refunds_data = all_refunds
            
            # Get high risk customers using updated criteria
            high_risk_df, _ = get_high_risk_customers_optimized(
                all_refunds, 
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
        all_refunds = st.session_state.all_refunds_data
        
        high_risk_df = high_risk_df.sort_values("Total Refunds", ascending=False)
        
        st.success(f"Found {len(high_risk_df)} high-risk customers")
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total High Risk Customers", len(high_risk_df))
        with col2:
            st.metric("Total Refunds (All)", int(high_risk_df["Total Refunds"].sum()))
        with col3:
            st.metric("Total Cash/UPI", f"₹{high_risk_df['Cash_UPI'].sum():,.2f}")
        with col4:
            st.metric("Total Jumbocash", f"₹{high_risk_df['Jumbocash'].sum():,.2f}")
        
        # Get month columns for display
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:current_month]
        
        # Create column config for better display
        column_config = {
            "BZID": st.column_config.TextColumn("BZID", help="Customer Business ID"),
            "Total Refunds": st.column_config.NumberColumn("Total Refunds", help="Total refunds year-to-date", format="%d"),
            "Monthly Average": st.column_config.NumberColumn("Avg/Month", help="Average refunds per month", format="%.2f"),
            "Months Active": st.column_config.NumberColumn("Months Active", help="Number of months with at least 1 refund", format="%d"),
            "Cash_UPI": st.column_config.NumberColumn("Cash/UPI (₹)", help="Total amount refunded via Cash/UPI", format="₹%.2f"),
            "Jumbocash": st.column_config.NumberColumn("Jumbocash (₹)", help="Total amount refunded via Jumbocash", format="₹%.2f"),
            "Manual_Cash": st.column_config.NumberColumn("Manual Cash (₹)", help="Total amount refunded via Manual Cash", format="₹%.2f"),
            "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", help="Total amount refunded across all methods", format="₹%.2f"),
        }
        
        # Add month columns to config
        for month in month_abbr:
            column_config[month] = st.column_config.NumberColumn(
                month, 
                help=f"Refunds in {month}",
                width="small",
                format="%d"
            )
        
        # Display the dataframe with month columns
        st.markdown("### 📊 Customer Monthly Refund Breakdown")
        st.markdown("*Each column shows refunds per month. Red numbers indicate 3+ refunds in that month.*")
        
        # Apply color styling to the dataframe
        def highlight_high_risk(row):
            styles = ['' for _ in range(len(row))]
            for i, col in enumerate(row.index):
                if col in month_abbr:
                    try:
                        val = int(row[col])
                        if val >= 3:
                            styles[i] = 'background-color: #ffcccc; font-weight: bold; color: #cc0000;'
                    except:
                        pass
            return styles
        
        display_df = high_risk_df.copy()
        styled_df = display_df.style.apply(highlight_high_risk, axis=1)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        # Download button
        csv = high_risk_df.to_csv(index=False)
        st.download_button(
            label="📥 Download High Risk Customers Report",
            data=csv,
            file_name=f"high_risk_customers_{current_year}.csv",
            mime="text/csv"
        )
        
        # Show individual customer breakdown
        st.markdown("### 📊 Individual Customer Monthly Breakdown")
        st.markdown("*Select a BZID below to see their refund pattern in detail.*")
        
        selected_bzid = st.selectbox(
            "Select BZID to view details",
            high_risk_df["BZID"].tolist()
        )
        
        if selected_bzid and all_refunds is not None:
            # Get monthly counts for selected customer
            _, monthly_counts = get_monthly_counts(all_refunds, selected_bzid, current_year)
            
            # Get payment method breakdown for selected customer
            customer_row = high_risk_df[high_risk_df["BZID"] == selected_bzid].iloc[0]
            
            # Create monthly breakdown for this customer
            monthly_data = []
            total_refunds = 0
            months_with_refunds = 0
            for i, month in enumerate(month_abbr):
                count = monthly_counts[i]
                total_refunds += count
                if count > 0:
                    months_with_refunds += 1
                monthly_data.append({
                    "Month": month,
                    "Refunds": count,
                    "Status": "⚠️ High" if count >= 3 else "✅ Normal"
                })
            
            monthly_df = pd.DataFrame(monthly_data)
            
            # Show summary for selected customer with payment breakdown
            st.info(f"""
            **Customer Summary:**
            - Total Refunds: **{total_refunds}**  
            - Average per month: **{total_refunds/current_month:.2f}**  
            - Months with refunds: **{months_with_refunds}** out of {current_month}
            - Risk Status: **{'🔴 HIGH RISK' if months_with_refunds >= 3 else '✅ Normal'}**
            
            **Payment Method Breakdown:**
            - 💳 Cash/UPI: **₹{customer_row['Cash_UPI']:,.2f}**
            - 🏦 Jumbocash: **₹{customer_row['Jumbocash']:,.2f}**
            - 💵 Manual Cash: **₹{customer_row['Manual_Cash']:,.2f}**
            - 📦 Total: **₹{customer_row['Total_Amount']:,.2f}**
            """)
            
            # Display monthly breakdown
            st.dataframe(
                monthly_df,
                use_container_width=True,
                hide_index=True
            )
    elif st.session_state.high_risk_data is not None and st.session_state.high_risk_data.empty:
        st.info("✅ No high-risk customers found! No customer has refunds in 3 or more months.")

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
