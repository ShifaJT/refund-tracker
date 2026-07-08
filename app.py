import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np
import re

# ================= CONFIG =================
st.set_page_config(page_title="Refund Tracker", layout="wide")

st.title("💰 Refund Tracker")
st.info("Rule: Less than 5 refunds → APPROVE | 5 or more refunds → DENY")

# ================= CITY NAME STANDARDIZATION =================
def standardize_city_name(city):
    """
    Standardize city names to handle spelling variations.
    ONLY standardizes actual city names, NOT hub codes.
    """
    if pd.isna(city) or city == "" or city == "Unknown":
        return "Unknown"
    
    city = str(city).strip()
    city_lower = city.lower()
    
    # City mapping dictionary - ONLY for actual city names
    city_mapping = {
        # Bengaluru variations
        'bengaluru': 'Bengaluru',
        'bangalore': 'Bengaluru',
        'bengaluru ': 'Bengaluru',
        'bengaluur': 'Bengaluru',
        'bengaluruu': 'Bengaluru',
        'bengaliuru': 'Bengaluru',
        'bengaluur': 'Bengaluru',
        'banglore': 'Bengaluru',
        'bangalore ': 'Bengaluru',
        'bengaluru x': 'Bengaluru',
        'bengaluru ,': 'Bengaluru',
        'bengaluru,': 'Bengaluru',
        'bnegaluru': 'Bengaluru',
        'brngaluru': 'Bengaluru',
        'benaluru': 'Bengaluru',
        'bengaluruw': 'Bengaluru',
        'begaluru': 'Bengaluru',
        'bengaluru, ': 'Bengaluru',
        'bengaluru,': 'Bengaluru',
        
        # Bhubaneswar variations
        'bhubaneswar': 'Bhubaneswar',
        'bhubaneswar ': 'Bhubaneswar',
        'bhubaneswar,': 'Bhubaneswar',
        'bhuvaneswar': 'Bhubaneswar',
        'bhuabaneswar': 'Bhubaneswar',
        'bhubaneswar,': 'Bhubaneswar',
        'bhubaneswar, ': 'Bhubaneswar',
        'bhubaneswar,': 'Bhubaneswar',
        
        # Hyderabad variations
        'hyderabad': 'Hyderabad',
        'hyderabad ': 'Hyderabad',
        'hyderabafd': 'Hyderabad',
        'hyderabd': 'Hyderabad',
        'hydrabad': 'Hyderabad',
        'hyderavad': 'Hyderabad',
        'hyfderabad': 'Hyderabad',
        'hyd': 'Hyderabad',
        'hydersbad': 'Hyderabad',
        'hyderabad,': 'Hyderabad',
        'hyd,': 'Hyderabad',
        'hyderabad, ': 'Hyderabad',
        'hyderabad,': 'Hyderabad',
        
        # Pune variations
        'pune': 'Pune',
        'pune ': 'Pune',
        'pune,': 'Pune',
        'punr': 'Pune',
        'pune1': 'Pune',
        'pune`': 'Pune',
        'pune, ': 'Pune',
        'pune,': 'Pune',
        
        # Lucknow variations
        'lucknow': 'Lucknow',
        'lucknow ': 'Lucknow',
        'lucknow,': 'Lucknow',
        'lucknow, ': 'Lucknow',
        'lukcnow': 'Lucknow',
        'luckmow': 'Lucknow',
        'lucknw': 'Lucknow',
        'luckno': 'Lucknow',
        'lucknoe': 'Lucknow',
        'lucknonw': 'Lucknow',
        'lucknowq': 'Lucknow',
        'luckow': 'Lucknow',
        'lucknoq': 'Lucknow',
        'luknow': 'Lucknow',
        'luckmnow': 'Lucknow',
        'lucknow,': 'Lucknow',
        'lucknow q': 'Lucknow',
        'lucknow.': 'Lucknow',
        'lucKNOW': 'Lucknow',
        'lUCKNOW': 'Lucknow',
        'lucknow,': 'Lucknow',
        'lucknow ': 'Lucknow',
        'lucknow,': 'Lucknow',
        'lucknow, ': 'Lucknow',
        'lucknow,': 'Lucknow',
        
        # Patna variations
        'patna': 'Patna',
        'patna ': 'Patna',
        'patna,': 'Patna',
        'patna, ': 'Patna',
        'patbna': 'Patna',
        'pstna': 'Patna',
        'patha': 'Patna',
        'patna,': 'Patna',
        'patna, ': 'Patna',
        'patna,': 'Patna',
        
        # Ranchi variations
        'ranchi': 'Ranchi',
        'ranchi ': 'Ranchi',
        'ranchi,': 'Ranchi',
        'ranchi, ': 'Ranchi',
        'ranhi': 'Ranchi',
        'ranci': 'Ranchi',
        'rancchi': 'Ranchi',
        'ranc': 'Ranchi',
        'rachi': 'Ranchi',
        'ranchio': 'Ranchi',
        'rancihi': 'Ranchi',
        'ranch,': 'Ranchi',
        'ranch, ': 'Ranchi',
        
        # Jamshedpur variations
        'jamshedpur': 'Jamshedpur',
        'jamshedpur ': 'Jamshedpur',
        'jamshedpur,': 'Jamshedpur',
        'jhamshedpur': 'Jamshedpur',
        'jhemshedpur': 'Jamshedpur',
        'jamshedpur,': 'Jamshedpur',
        'jamshedpur, ': 'Jamshedpur',
        'jamshedpur,': 'Jamshedpur',
        'jhamshedpur': 'Jamshedpur',
        
        # Mysore variations
        'mysore': 'Mysore',
        'mysore ': 'Mysore',
        'mysore,': 'Mysore',
        'mysuru': 'Mysore',
        'mysuru ': 'Mysore',
        'mysore,': 'Mysore',
        'mysore, ': 'Mysore',
        
        # Tumkur variations
        'tumkur': 'Tumkur',
        'tumkur ': 'Tumkur',
        'tumkur,': 'Tumkur',
        'tumkur, ': 'Tumkur',
        
        # Hosur variations
        'hosur': 'Hosur',
        'hosur ': 'Hosur',
        'hosur,': 'Hosur',
        'hosur, ': 'Hosur',
        
        # Hassan variations
        'hassan': 'Hassan',
        'hassan ': 'Hassan',
        'hassan,': 'Hassan',
        
        # Chennai variations
        'chennai': 'Chennai',
        'chennai ': 'Chennai',
        'chennai,': 'Chennai',
        'chennai, ': 'Chennai',
        
        # Ahmedabad variations
        'ahmedabad': 'Ahmedabad',
        'ahmedabad ': 'Ahmedabad',
        'ahmedabad,': 'Ahmedabad',
        'ahamedabad': 'Ahmedabad',
        'ahmedabadh': 'Ahmedabad',
        'ahemdabad': 'Ahmedabad',
        'ahmedabad,': 'Ahmedabad',
        'ahmedabad, ': 'Ahmedabad',
        'ahmedabad,': 'Ahmedabad',
        'ahmedabad,': 'Ahmedabad',
        
        # Mandya variations
        'mandya': 'Mandya',
        'mandya ': 'Mandya',
        'mandya,': 'Mandya',
        
        # Sangareddy variations
        'sangareddy': 'Sangareddy',
        'sangareddy ': 'Sangareddy',
        'sangareddy,': 'Sangareddy',
        
        # Kanpur variations
        'kanpur': 'Kanpur',
        'kanpur ': 'Kanpur',
        'kanpur,': 'Kanpur',
        'kanpur, ': 'Kanpur',
        
        # Vizag variations
        'vizag': 'Vizag',
        'vizag ': 'Vizag',
        'vizag,': 'Vizag',
        
        # Unnao variations
        'unnao': 'Unnao',
        'unnao ': 'Unnao',
        'unnao,': 'Unnao',
        
        # Samastipur variations
        'samastipur': 'Samastipur',
        'samastipur ': 'Samastipur',
        'samastipur,': 'Samastipur',
        
        # Siddipet variations
        'siddipet': 'Siddipet',
        'siddipet ': 'Siddipet',
        'siddipet,': 'Siddipet',
        
        # Krishnagiri variations
        'krishnagiri': 'Krishnagiri',
        'krishnagiri ': 'Krishnagiri',
        'krishnagiri,': 'Krishnagiri',
        
        # Other variations
        'arihant': 'Bengaluru',
        'aslali': 'Ahmedabad',
        'hennur': 'Bengaluru',
        'kudlu': 'Bengaluru',
        'lonikand': 'Pune',
        'marathahalli': 'Bengaluru',
        'peenya': 'Bengaluru',
        'srinivas': 'Unknown',
        'bhubaneswar,': 'Bhubaneswar',
        'bhubaneswar, ': 'Bhubaneswar',
        'bhubaneswar,': 'Bhubaneswar',
        'bhubaneswar,': 'Bhubaneswar',
    }
    
    # Check if city exists in mapping (case insensitive)
    if city_lower in city_mapping:
        return city_mapping[city_lower]
    
    # Check if city contains known city names
    for key, value in city_mapping.items():
        if key in city_lower or city_lower in key:
            return value
    
    # Remove extra characters and try again
    city_clean = re.sub(r'[,._\-()]', ' ', city)
    city_clean = ' '.join(city_clean.split())
    
    if city_clean.lower() in city_mapping:
        return city_mapping[city_clean.lower()]
    
    # If it's a phone number or numeric, keep as is
    if re.match(r'^[\d\s]+$', city):
        return city
    
    # If it contains underscore, it might be a hub code - keep as is
    if '_' in city and len(city) <= 15:
        return city
    
    # If it's a known hub code pattern (BLR_, BLR_, etc.), keep as is
    hub_patterns = ['BLR_', 'HYD_', 'PUN_', 'LKO_', 'OD_', 'BH_', 'MYS_', '3P_']
    for pattern in hub_patterns:
        if pattern in city.upper():
            return city
    
    return city

# ================= Custom CSS =================
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
    .kpi-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border: 1px solid #dee2e6;
        margin: 5px;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
    .kpi-label {
        font-size: 12px;
        color: #6c757d;
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

# ================= ANALYTICS FUNCTIONS =================
@st.cache_data(ttl=300)
def get_monthly_summary(cash_df, jc_df, manual_df, year, current_month):
    """Data 1: Month Total request Received, Refunded cases, Amount"""
    
    def prepare_summary_df(df):
        if df.empty:
            return pd.DataFrame(columns=["Date", "Amount"])
        
        df = df.copy()
        
        # Find Date column
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            return pd.DataFrame(columns=["Date", "Amount"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[df["Date"].dt.year == year]
        df = df[df["Date"].dt.month <= current_month]
        
        if df.empty:
            return pd.DataFrame(columns=["Date", "Amount"])
        
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
        
        df["Month"] = df["Date"].dt.strftime("%B %Y")
        
        return df[["Month", "Amount"]]
    
    cash_summary = prepare_summary_df(cash_df)
    jc_summary = prepare_summary_df(jc_df)
    manual_summary = prepare_summary_df(manual_df)
    
    all_summary = pd.concat([cash_summary, jc_summary, manual_summary], ignore_index=True)
    
    if all_summary.empty:
        return pd.DataFrame()
    
    monthly_data = all_summary.groupby("Month").agg(
        Refunded_Cases=("Amount", "count"),
        Total_Amount=("Amount", "sum")
    ).reset_index()
    
    monthly_data["Total_Requests_Received"] = monthly_data["Refunded_Cases"]
    
    return monthly_data

@st.cache_data(ttl=300)
def get_product_refund_data(cash_df, jc_df, manual_df, year, current_month):
    """Data 6: Product Title, Ticket Count, Total Amount (with actual product names)"""
    
    def prepare_product_df(df, source_type):
        if df.empty:
            return pd.DataFrame(columns=["Product", "Amount", "BZID", "City", "Hub"])
        
        df = df.copy()
        
        # Find Date column
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            return pd.DataFrame(columns=["Product", "Amount", "BZID", "City", "Hub"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[df["Date"].dt.year == year]
        df = df[df["Date"].dt.month <= current_month]
        
        if df.empty:
            return pd.DataFrame(columns=["Product", "Amount", "BZID", "City", "Hub"])
        
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
        
        # Find BZID column
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        
        if bzid_col:
            df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        else:
            df["BZID"] = "Unknown"
        
        # Find Product column - prioritize actual product names
        product_col = None
        for col in ["Product Name", "Product", "Product name", "product_name", "Item Name", "item_name"]:
            if col in df.columns:
                product_col = col
                break
        
        if product_col:
            df["Product"] = df[product_col].astype(str)
        else:
            # For cash/UPI sheet, try to get from Order Item ID or DH NAME
            for col in ["Order Item ID", "Order Item Id", "DH NAME", "DH Name"]:
                if col in df.columns:
                    df["Product"] = df[col].astype(str)
                    break
            else:
                df["Product"] = "Unknown Product"
        
        # Clean product names
        df["Product"] = df["Product"].str.replace("BLTORDITM-", "", regex=False)
        df["Product"] = df["Product"].str.replace("_", " ", regex=False)
        df["Product"] = df["Product"].str.strip()
        
        # Find City column and standardize (but keep hub codes as-is)
        city_col = None
        for col in ["City", "city", "City Name", "CityName"]:
            if col in df.columns:
                city_col = col
                break
        
        if city_col:
            df["City"] = df[city_col].astype(str).apply(standardize_city_name)
        else:
            df["City"] = "Unknown"
        
        # Find Hub column - keep original hub codes
        hub_col = None
        for col in ["Hub", "hub", "Hub ID", "HUB ID", "Hub Name"]:
            if col in df.columns:
                hub_col = col
                break
        
        if hub_col:
            df["Hub"] = df[hub_col].astype(str)
        else:
            df["Hub"] = "Unknown"
        
        return df[["Product", "Amount", "BZID", "City", "Hub"]]
    
    cash_product = prepare_product_df(cash_df, "cash")
    jc_product = prepare_product_df(jc_df, "jc")
    manual_product = prepare_product_df(manual_df, "manual")
    
    all_product = pd.concat([cash_product, jc_product, manual_product], ignore_index=True)
    
    if all_product.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Product summary
    product_summary = all_product.groupby("Product").agg(
        Ticket_Count=("Amount", "count"),
        Total_Amount=("Amount", "sum"),
        Unique_Customers=("BZID", "nunique")
    ).reset_index().sort_values("Total_Amount", ascending=False).head(20)
    
    # Hub-wise product refunds
    hub_product = all_product.groupby(["Hub", "Product"]).agg(
        Ticket_Count=("Amount", "count"),
        Total_Amount=("Amount", "sum")
    ).reset_index().sort_values(["Hub", "Total_Amount"], ascending=[True, False])
    
    # City-wise product refunds (with standardized city names)
    city_product = all_product.groupby(["City", "Product"]).agg(
        Ticket_Count=("Amount", "count"),
        Total_Amount=("Amount", "sum")
    ).reset_index().sort_values(["City", "Total_Amount"], ascending=[True, False])
    
    return product_summary, hub_product, city_product

@st.cache_data(ttl=300)
def get_hub_analysis(cash_df, jc_df, manual_df, year, current_month):
    """Hub-wise analysis with counts and amounts (keeps original hub codes)"""
    
    def prepare_hub_df(df):
        if df.empty:
            return pd.DataFrame(columns=["Hub", "Amount", "BZID"])
        
        df = df.copy()
        
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            return pd.DataFrame(columns=["Hub", "Amount", "BZID"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[df["Date"].dt.year == year]
        df = df[df["Date"].dt.month <= current_month]
        
        if df.empty:
            return pd.DataFrame(columns=["Hub", "Amount", "BZID"])
        
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        
        if bzid_col:
            df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        else:
            df["BZID"] = "Unknown"
        
        hub_col = None
        for col in ["Hub", "hub", "Hub ID", "HUB ID", "Hub Name"]:
            if col in df.columns:
                hub_col = col
                break
        
        if hub_col:
            df["Hub"] = df[hub_col].astype(str)
        else:
            df["Hub"] = "Unknown"
        
        return df[["Hub", "Amount", "BZID"]]
    
    cash_hub = prepare_hub_df(cash_df)
    jc_hub = prepare_hub_df(jc_df)
    manual_hub = prepare_hub_df(manual_df)
    
    all_hub = pd.concat([cash_hub, jc_hub, manual_hub], ignore_index=True)
    
    if all_hub.empty:
        return pd.DataFrame()
    
    hub_summary = all_hub.groupby("Hub").agg(
        Total_Instances=("Amount", "count"),
        Total_Amount=("Amount", "sum"),
        Unique_Customers=("BZID", "nunique")
    ).reset_index().sort_values("Total_Amount", ascending=False)
    
    return hub_summary

@st.cache_data(ttl=300)
def get_city_analysis(cash_df, jc_df, manual_df, year, current_month):
    """City-wise analysis with standardized city names"""
    
    def prepare_city_df(df):
        if df.empty:
            return pd.DataFrame(columns=["City", "Amount", "BZID"])
        
        df = df.copy()
        
        date_col = None
        for col in ["Date", "date", "Timestamp", "timestamp"]:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            return pd.DataFrame(columns=["City", "Amount", "BZID"])
        
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["Date"].notna()]
        df = df[df["Date"].dt.year == year]
        df = df[df["Date"].dt.month <= current_month]
        
        if df.empty:
            return pd.DataFrame(columns=["City", "Amount", "BZID"])
        
        amount_col = None
        for col in ["Amount", "amount", "Refund Amount"]:
            if col in df.columns:
                amount_col = col
                break
        
        if amount_col:
            df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        else:
            df["Amount"] = 0
        
        bzid_col = None
        for col in ["BZID", "Business ID", "BZD", "bzid"]:
            if col in df.columns:
                bzid_col = col
                break
        
        if bzid_col:
            df["BZID"] = df[bzid_col].astype(str).str.strip().str.upper()
        else:
            df["BZID"] = "Unknown"
        
        city_col = None
        for col in ["City", "city", "City Name", "CityName"]:
            if col in df.columns:
                city_col = col
                break
        
        if city_col:
            # Apply city name standardization (hub codes will be kept as-is)
            df["City"] = df[city_col].astype(str).apply(standardize_city_name)
        else:
            df["City"] = "Unknown"
        
        return df[["City", "Amount", "BZID"]]
    
    cash_city = prepare_city_df(cash_df)
    jc_city = prepare_city_df(jc_df)
    manual_city = prepare_city_df(manual_df)
    
    all_city = pd.concat([cash_city, jc_city, manual_city], ignore_index=True)
    
    if all_city.empty:
        return pd.DataFrame()
    
    city_summary = all_city.groupby("City").agg(
        Total_Instances=("Amount", "count"),
        Total_Amount=("Amount", "sum"),
        Unique_Customers=("BZID", "nunique")
    ).reset_index().sort_values("Total_Amount", ascending=False)
    
    return city_summary

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
        
        # ===== DEFAULTER DETECTION =====
        # Check if customer has 4+ refunds in every month (consistent defaulter)
        consistent_defaulter = all(count >= 4 for count in monthly_counts[:current_month])
        
        # Check if customer has 5+ refunds in any month (policy breach)
        has_policy_breach = max_monthly_refunds >= 5
        
        # Check if customer has refunds in 4+ months (frequent user)
        frequent_user = months_with_refunds >= 4
        
        # ===== UPDATED RISK ASSESSMENT =====
        # 1. EXTREME: (Amount > 500 AND Avg >= 3) OR Consistent Defaulter (4+ every month) OR Policy Breach
        if (total_amount > 500 and avg_refunds >= 3) or consistent_defaulter or has_policy_breach:
            risk_level = "🔴🔴 EXTREME"
        # 2. HIGH: Amount <= 500 AND Avg >= 3
        elif total_amount <= 500 and avg_refunds >= 3:
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
tabs = st.tabs(["🔍 Individual Search", "📊 High Risk Customers", "📦 Product Refunds", "🏪 Hub Analysis", "🏙️ City Analysis", "📊 Monthly Summary"])

# ================= TAB 1: Individual Search =================
with tabs[0]:
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
            
            tabs_inner = st.tabs(["💳 Cash/UPI", "🏦 Jumbocash", "💵 Manual Cash"])
            
            with tabs_inner[0]:
                if not cash_current_matches.empty:
                    st.dataframe(
                        cash_current_matches.reset_index(drop=True),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No Cash/UPI refunds for this month")
            
            with tabs_inner[1]:
                if not jc_current_matches.empty:
                    st.dataframe(
                        jc_current_matches.reset_index(drop=True),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No Jumbocash refunds for this month")
            
            with tabs_inner[2]:
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
with tabs[1]:
    st.markdown("## 🚨 High Risk Customers - 10X Approach")
    
    st.markdown("""
    <div class="info-box">
        <b>📖 Defaulter Detection & Risk Assessment:</b><br><br>
        <b>🔴🔴 EXTREME RISK:</b> (Total Amount > ₹500 AND Avg >= 3) OR (4+ refunds EVERY month) OR (5+ refunds in ANY month)<br>
        <b>🔴 HIGH RISK:</b> Total Amount <= ₹500 AND Avg >= 3<br>
        <b>🟡 POTENTIAL RISK:</b> Avg >= 2 OR Active in 3+ months OR Refunds in 4+ months<br><br>
        <b>Why this approach identifies defaulters:</b><br>
        • <b>Consistent Defaulter</b> (4+ refunds every month) = 🔴🔴 EXTREME<br>
        • <b>Policy Breacher</b> (5+ refunds in any month) = 🔴🔴 EXTREME<br>
        • <b>Frequent User</b> (Refunds in 4+ months) = 🟡 POTENTIAL
    </div>
    """, unsafe_allow_html=True)
    
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
    
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
    
    if st.button("🔄 Load High Risk Customers"):
        cash_df, jc_df, manual_df = load_all_data()
        with st.spinner("Analyzing customer data..."):
            high_risk_df = get_high_risk_customers_optimized(
                cash_df, jc_df, manual_df, current_year, current_month
            )
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
        
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:current_month]
        
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
        
        styled_df = high_risk_df.style.apply(highlight_risk, axis=1)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        csv = high_risk_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Report",
            data=csv,
            file_name=f"high_risk_customers_{current_year}.csv",
            mime="text/csv"
        )
        
    elif st.session_state.high_risk_data is not None and st.session_state.high_risk_data.empty:
        st.info("✅ No high-risk customers found!")

# ================= TAB 3: Product Refunds =================
with tabs[2]:
    st.markdown("## 📦 Product Refund Analysis")
    st.markdown("*Product-wise refund ticket count, amounts, and hub/city breakdown*")
    
    @st.cache_data(ttl=300)
    def load_product_data():
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
    
    if st.button("🔄 Load Product Analysis"):
        cash_df, jc_df, manual_df = load_product_data()
        product_summary, hub_product, city_product = get_product_refund_data(
            cash_df, jc_df, manual_df, current_year, current_month
        )
        st.session_state.product_summary = product_summary
        st.session_state.hub_product = hub_product
        st.session_state.city_product = city_product
    
    if 'product_summary' in st.session_state and not st.session_state.product_summary.empty:
        # Top Products
        st.markdown("### 🏆 Top Products by Refund Amount")
        st.dataframe(
            st.session_state.product_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn("Product Name"),
                "Ticket_Count": st.column_config.NumberColumn("Ticket Count", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                "Unique_Customers": st.column_config.NumberColumn("Unique Customers", format="%d")
            }
        )
        
        # Hub-wise Product Breakdown
        st.markdown("### 🏪 Hub-wise Product Refund Breakdown")
        hub_filter = st.selectbox("Select Hub", ["All"] + sorted(st.session_state.hub_product["Hub"].unique().tolist()))
        
        if hub_filter != "All":
            filtered_hub = st.session_state.hub_product[st.session_state.hub_product["Hub"] == hub_filter]
        else:
            filtered_hub = st.session_state.hub_product
        
        st.dataframe(
            filtered_hub,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hub": st.column_config.TextColumn("Hub"),
                "Product": st.column_config.TextColumn("Product Name"),
                "Ticket_Count": st.column_config.NumberColumn("Ticket Count", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f")
            }
        )
        
        # City-wise Product Breakdown
        st.markdown("### 🏙️ City-wise Product Refund Breakdown")
        city_filter = st.selectbox("Select City", ["All"] + sorted(st.session_state.city_product["City"].unique().tolist()))
        
        if city_filter != "All":
            filtered_city = st.session_state.city_product[st.session_state.city_product["City"] == city_filter]
        else:
            filtered_city = st.session_state.city_product
        
        st.dataframe(
            filtered_city,
            use_container_width=True,
            hide_index=True,
            column_config={
                "City": st.column_config.TextColumn("City"),
                "Product": st.column_config.TextColumn("Product Name"),
                "Ticket_Count": st.column_config.NumberColumn("Ticket Count", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f")
            }
        )
        
    elif 'product_summary' in st.session_state:
        st.info("Click 'Load Product Analysis' to view data")

# ================= TAB 4: Hub Analysis =================
with tabs[3]:
    st.markdown("## 🏪 Hub Analysis")
    st.markdown("*Hub-wise refund instances, amounts, and unique customers*")
    
    @st.cache_data(ttl=300)
    def load_hub_data():
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
    
    if st.button("🔄 Load Hub Analysis"):
        cash_df, jc_df, manual_df = load_hub_data()
        hub_data = get_hub_analysis(cash_df, jc_df, manual_df, current_year, current_month)
        st.session_state.hub_data = hub_data
    
    if 'hub_data' in st.session_state and not st.session_state.hub_data.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Hubs", st.session_state.hub_data["Hub"].nunique())
        with col2:
            st.metric("Total Instances", st.session_state.hub_data["Total_Instances"].sum())
        with col3:
            st.metric("Total Amount", f"₹{st.session_state.hub_data['Total_Amount'].sum():,.2f}")
        
        st.dataframe(
            st.session_state.hub_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hub": st.column_config.TextColumn("Hub"),
                "Total_Instances": st.column_config.NumberColumn("Total Instances", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                "Unique_Customers": st.column_config.NumberColumn("Unique Customers", format="%d")
            }
        )
        
        # Top Hubs chart
        st.markdown("### 🔝 Top Hubs by Refund Amount")
        st.bar_chart(st.session_state.hub_data.set_index("Hub")["Total_Amount"].head(10))
        
    elif 'hub_data' in st.session_state:
        st.info("Click 'Load Hub Analysis' to view data")

# ================= TAB 5: City Analysis =================
with tabs[4]:
    st.markdown("## 🏙️ City Analysis")
    st.markdown("*City-wise refund instances, amounts, and unique customers (standardized city names)*")
    
    @st.cache_data(ttl=300)
    def load_city_data():
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
    
    if st.button("🔄 Load City Analysis"):
        cash_df, jc_df, manual_df = load_city_data()
        city_data = get_city_analysis(cash_df, jc_df, manual_df, current_year, current_month)
        st.session_state.city_data = city_data
    
    if 'city_data' in st.session_state and not st.session_state.city_data.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cities", st.session_state.city_data["City"].nunique())
        with col2:
            st.metric("Total Instances", st.session_state.city_data["Total_Instances"].sum())
        with col3:
            st.metric("Total Amount", f"₹{st.session_state.city_data['Total_Amount'].sum():,.2f}")
        
        st.dataframe(
            st.session_state.city_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "City": st.column_config.TextColumn("City"),
                "Total_Instances": st.column_config.NumberColumn("Total Instances", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f"),
                "Unique_Customers": st.column_config.NumberColumn("Unique Customers", format="%d")
            }
        )
        
        # Top Cities chart
        st.markdown("### 🔝 Top Cities by Refund Amount")
        st.bar_chart(st.session_state.city_data.set_index("City")["Total_Amount"].head(10))
        
    elif 'city_data' in st.session_state:
        st.info("Click 'Load City Analysis' to view data")

# ================= TAB 6: Monthly Summary =================
with tabs[5]:
    st.markdown("## 📊 Monthly Summary")
    st.markdown("*Month-wise refund cases and amounts*")
    
    @st.cache_data(ttl=300)
    def load_monthly_data():
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
    
    if st.button("🔄 Load Monthly Summary"):
        cash_df, jc_df, manual_df = load_monthly_data()
        monthly_data = get_monthly_summary(cash_df, jc_df, manual_df, current_year, current_month)
        st.session_state.monthly_data = monthly_data
    
    if 'monthly_data' in st.session_state and not st.session_state.monthly_data.empty:
        st.dataframe(
            st.session_state.monthly_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Month": st.column_config.TextColumn("Month"),
                "Total_Requests_Received": st.column_config.NumberColumn("Total Requests", format="%d"),
                "Refunded_Cases": st.column_config.NumberColumn("Refunded Cases", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount (₹)", format="₹%.2f")
            }
        )
        
        st.markdown("### 📈 Monthly Refund Trends")
        st.bar_chart(st.session_state.monthly_data.set_index("Month")["Total_Amount"])
        
    elif 'monthly_data' in st.session_state:
        st.info("Click 'Load Monthly Summary' to view data")

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
