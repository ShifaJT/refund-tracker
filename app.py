import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: Up to 5 refunds → APPROVE | 6 or more refunds → DENY")

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

    # =====================================================
    # SUMMARY - Current Month (for decision)
    # =====================================================

    st.subheader(f"📊 Current Month Summary - {selected_month_label}")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(

        "Cash / UPI",

        cash_count_current,

        f"₹ {round(cash_amount_current,2)}"

    )

    c2.metric(

        "Jumbocash",

        jc_count_current,

        f"₹ {round(jc_amount_current,2)}"

    )

    c3.metric(

        "Manual Cash",

        manual_count_current,

        f"₹ {round(manual_amount_current,2)}"

    )

    c4.metric(

        "Total",

        total_count_current,

        f"₹ {round(total_amount_current,2)}"

    )

    # =====================================================
    # DECISION (based only on current month)
    # =====================================================

    if total_count_current <= 5:

        st.success(f"✅ APPROVE ({total_count_current} refunds this month)")

    else:

        st.error(f"❌ DENY ({total_count_current} refunds this month)")

    # =====================================================
    # YEARLY TREND DISPLAY
    # =====================================================
    
    st.subheader("📈 Refund Trend (Last 2 Years)")
    
    trend_col1, trend_col2 = st.columns(2)
    
    with trend_col1:
        st.metric(
            f"Total Refunds in {current_year}",
            current_year_count,
            delta=f"Current Year"
        )
    
    with trend_col2:
        st.metric(
            f"Total Refunds in {current_year - 1}",
            last_year_count,
            delta=f"Previous Year"
        )
    
    # Show monthly breakdown for current year
    st.write("### 📅 Monthly Breakdown for Current Year")
    
    # Get monthly counts for current year
    monthly_counts = []
    for month in range(1, 13):
        month_count = get_refund_count_for_year(all_refunds, bzid, current_year)
        # Actually we need monthly breakdown - let's filter differently
        month_data = all_refunds[
            (all_refunds["BZID"] == bzid) &
            (all_refunds["Date"].dt.year == current_year) &
            (all_refunds["Date"].dt.month == month)
        ]
        monthly_counts.append(len(month_data))
    
    # Create month names
    month_names = [datetime(current_year, i, 1).strftime("%b") for i in range(1, 13)]
    
    # Display as bar chart
    trend_df = pd.DataFrame({
        "Month": month_names,
        "Refund Count": monthly_counts
    })
    
    st.bar_chart(trend_df.set_index("Month"))

    # =====================================================
    # TABLES - Current Month Details
    # =====================================================
    
    st.subheader("📋 Current Month Refund Details")

    if not cash_current_matches.empty:

        st.write("Cash / UPI")

        st.dataframe(

            cash_current_matches.reset_index(drop=True),

            use_container_width=True

        )

    if not jc_current_matches.empty:

        st.write("Jumbocash")

        st.dataframe(

            jc_current_matches.reset_index(drop=True),

            use_container_width=True

        )

    if not manual_current_matches.empty:

        st.write("Manual Cash Refund")

        st.dataframe(

            manual_current_matches.reset_index(drop=True),

            use_container_width=True

        )

    if (

        cash_current_matches.empty

        and jc_current_matches.empty

        and manual_current_matches.empty

    ):

        st.warning("No refund data found for the selected month")
