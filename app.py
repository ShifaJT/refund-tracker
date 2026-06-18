import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: Up to 5 refunds → APPROVE | 6 or more refunds → DENY")

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
    }
    .decision-deny {
        background-color: #f8d7da;
        border-radius: 10px;
        padding: 20px;
        border-left: 5px solid #dc3545;
    }
    .section-header {
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 10px;
        margin-top: 30px;
        margin-bottom: 20px;
    }
    .details-tabs {
        margin-top: 10px;
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


# ================= GET REFUND COUNT FOR YEAR =================
def get_refund_count_for_year(df, bzid, year):
    """Get unique refund count for a specific year"""
    if df.empty:
        return 0
    
    df_filtered = df[
        (df["BZID"] == bzid) &
        (df["Date"].notna()) &
        (df["Date"].dt.year == year)
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

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):

    st.cache_data.clear()

    st.rerun()


# ================= INPUT =================
col1, col2 = st.columns(2)

bzid_input = col1.text_input("Enter BZID")

current_year = datetime.now().year

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

        # Current month matches (for approval/rejection)
        cash_current_matches = cash_df[

            (cash_df["BZID"] == bzid)

            &

            (cash_df["Date"].notna())

            &

            (cash_df["Date"].dt.month == month_input)

            &

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

            (jc_df["BZID"] == bzid)

            &

            (jc_df["Date"].notna())

            &

            (jc_df["Date"].dt.month == month_input)

            &

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

            (manual_df["BZID"] == bzid)

            &

            (manual_df["Date"].notna())

            &

            (manual_df["Date"].dt.month == month_input)

            &

            (manual_df["Date"].dt.year == selected_year)

        ]

        # =====================================================
        # COUNTS FOR CURRENT MONTH (Decision)
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
        
        # Combine all dataframes for yearly trend analysis
        all_refunds = pd.concat([
            cash_df[["BZID", "Date"]],
            jc_df[["BZID", "Date"]],
            manual_df[["BZID", "Date"]]
        ], ignore_index=True)
        
        # Get refund counts for current year and last year
        current_year_count = get_refund_count_for_year(all_refunds, bzid, current_year)
        last_year_count = get_refund_count_for_year(all_refunds, bzid, current_year - 1)
        
        # Get monthly counts for current year
        month_names, monthly_counts = get_monthly_counts(all_refunds, bzid, current_year)

    # =====================================================
    # MAIN LAYOUT: Left Column (Decision) & Right Column (Details)
    # =====================================================
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        # ========== LEFT COLUMN: Current Month Summary & Decision ==========
        st.markdown(f"## 📊 Current Month")
        st.markdown(f"### {selected_month_label}")

        # Decision Card
        if total_count_current <= 5:
            st.markdown(f"""
            <div class="decision-approve">
                <h2 style="color: #28a745; margin: 0;">✅ APPROVED</h2>
                <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count_current} (Within limit of 5)</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="decision-deny">
                <h2 style="color: #dc3545; margin: 0;">❌ DENIED</h2>
                <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count_current} (Exceeds limit of 5)</p>
            </div>
            """, unsafe_allow_html=True)

        # Metrics in 2x2 grid
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
        # ========== RIGHT COLUMN: Refund Details Tabs ==========
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
    # DISPLAY SECTION: Yearly Trend (Full Width)
    # =====================================================
    
    st.markdown("---")
    st.markdown(f"## 📈 Yearly Refund Trend")
    
    # Year-over-year comparison
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        st.markdown(f"""
        <div class="trend-card">
            <p style="margin: 0; opacity: 0.8;">Current Year</p>
            <h2 style="margin: 5px 0;">{current_year}</h2>
            <h1 style="margin: 5px 0;">{current_year_count}</h1>
            <p style="margin: 0; opacity: 0.9;">Total Refunds</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="trend-card-previous">
            <p style="margin: 0; opacity: 0.8;">Previous Year</p>
            <h2 style="margin: 5px 0;">{current_year - 1}</h2>
            <h1 style="margin: 5px 0;">{last_year_count}</h1>
            <p style="margin: 0; opacity: 0.9;">Total Refunds</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Calculate percentage change
        if last_year_count > 0:
            change = ((current_year_count - last_year_count) / last_year_count) * 100
            direction = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            change_text = f"{direction} {abs(change):.1f}%"
        else:
            change_text = "New data" if current_year_count > 0 else "No data"
        
        st.markdown(f"""
        <div style="background-color: #f8f9fa; border-radius: 10px; padding: 20px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
            <p style="margin: 0; color: #6c757d; font-size: 14px;">Year-over-Year Change</p>
            <h2 style="margin: 5px 0; color: {'#28a745' if current_year_count >= last_year_count else '#dc3545'}">{change_text}</h2>
            <p style="margin: 0; color: #6c757d; font-size: 14px;">
                {current_year_count} vs {last_year_count} refunds
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Monthly breakdown as a clean table
    st.markdown("### 📅 Monthly Breakdown")
    
    # Create a clean monthly breakdown table
    monthly_data = []
    for i, month in enumerate(month_names):
        status = "📍 Current" if i == month_input - 1 else ""
        monthly_data.append({
            "Month": month,
            "Refunds": monthly_counts[i],
            "Status": status
        })
    
    monthly_df = pd.DataFrame(monthly_data)
    
    # Highlight current month with color - using the newer 'map' method
    def highlight_current(row):
        if row['Status'] == '📍 Current':
            return ['background-color: #e3f2fd'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        monthly_df.style.apply(highlight_current, axis=1),
        use_container_width=True,
        hide_index=True
    )
