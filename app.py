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
    if pd.isna(city) or city == "" or city == "Unknown":
        return "Unknown"
    city = str(city).strip()
    city_lower = city.lower()
    city_mapping = {
        'bengaluru': 'Bengaluru', 'bangalore': 'Bengaluru',
        'bengaluur': 'Bengaluru', 'bengaluruu': 'Bengaluru', 'bengaliuru': 'Bengaluru',
        'banglore': 'Bengaluru', 'bnegaluru': 'Bengaluru', 'brngaluru': 'Bengaluru',
        'benaluru': 'Bengaluru', 'begaluru': 'Bengaluru',
        'hyderabad': 'Hyderabad', 'hyderabafd': 'Hyderabad',
        'hyderabd': 'Hyderabad', 'hydrabad': 'Hyderabad', 'hyderavad': 'Hyderabad',
        'hyd': 'Hyderabad', 'hydersbad': 'Hyderabad',
        'pune': 'Pune', 'punr': 'Pune', 'pune1': 'Pune',
        'lucknow': 'Lucknow', 'lukcnow': 'Lucknow',
        'luckmow': 'Lucknow', 'lucknw': 'Lucknow', 'luckno': 'Lucknow',
        'lucknoe': 'Lucknow', 'lucknonw': 'Lucknow', 'lucknowq': 'Lucknow',
        'luckow': 'Lucknow', 'luknow': 'Lucknow', 'luckmnow': 'Lucknow',
        'patna': 'Patna', 'patbna': 'Patna', 'pstna': 'Patna', 'patha': 'Patna',
        'ranchi': 'Ranchi', 'ranhi': 'Ranchi', 'ranci': 'Ranchi',
        'rancchi': 'Ranchi', 'ranc': 'Ranchi', 'rachi': 'Ranchi', 'ranchio': 'Ranchi',
        'jamshedpur': 'Jamshedpur', 'jhamshedpur': 'Jamshedpur',
        'jhemshedpur': 'Jamshedpur',
        'mysore': 'Mysore', 'mysuru': 'Mysore',
        'tumkur': 'Tumkur', 'hosur': 'Hosur', 'hassan': 'Hassan',
        'chennai': 'Chennai',
        'ahmedabad': 'Ahmedabad', 'ahamedabad': 'Ahmedabad',
        'ahemdabad': 'Ahmedabad', 'ahmedabadh': 'Ahmedabad',
        'mandya': 'Mandya', 'sangareddy': 'Sangareddy', 'kanpur': 'Kanpur',
        'vizag': 'Vizag', 'unnao': 'Unnao', 'samastipur': 'Samastipur',
        'siddipet': 'Siddipet', 'krishnagiri': 'Krishnagiri',
        'bhubaneswar': 'Bhubaneswar', 'bhuvaneswar': 'Bhubaneswar',
        'bhuabaneswar': 'Bhubaneswar',
    }
    if city_lower in city_mapping:
        return city_mapping[city_lower]
    hub_patterns = ['BLR_', 'HYD_', 'PUN_', 'LKO_', 'OD_', 'BH_', 'MYS_', '3P_']
    for pattern in hub_patterns:
        if pattern in city.upper():
            return city
    if '_' in city and len(city) <= 15:
        return city
    return city

# ================= GOOGLE AUTH (READ-ONLY) =================
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
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

# ================= FIND COLUMN NAME =================
def find_column(df, possible_names):
    if df.empty:
        return None
    cols_lower = {c.lower(): c for c in df.columns}
    for name in possible_names:
        if name in df.columns:
            return name
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    return None

# ================= ROBUST DATE PARSER =================
def parse_dates_robust(series):
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().sum() > 0:
        return parsed
    formats_to_try = [
        "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y",
        "%m/%d/%y", "%d/%m/%y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y",
        "%b %d, %Y", "%B %d, %Y",
    ]
    for fmt in formats_to_try:
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            if parsed.notna().sum() > 0:
                return parsed
        except:
            continue
    try:
        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.notna().sum() > 0:
            parsed = pd.to_datetime(numeric_series, unit='D', origin='1899-12-30', errors="coerce")
            if parsed.notna().sum() > 0:
                return parsed
    except:
        pass
    return pd.Series([pd.NaT] * len(series), index=series.index)

# ================= LOAD SHEETS (READ-ONLY) =================
@st.cache_data(ttl=600, show_spinner=False)
def load_sheet(sheet_id, sheet_name):
    try:
        client = get_client()
        sheet = client.open_by_key(sheet_id)
        try:
            ws = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            available_sheets = [ws.title for ws in sheet.worksheets()]
            if available_sheets:
                ws = sheet.worksheet(available_sheets[0])
            else:
                return pd.DataFrame()
        data = ws.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame()
        headers = [str(col).strip() if col else f"Column_{i}" for i, col in enumerate(data[0])]
        data_rows = []
        for row in data[1:]:
            non_empty = sum(1 for cell in row if cell and str(cell).strip())
            if non_empty >= 2:
                data_rows.append(row)
        if not data_rows:
            return pd.DataFrame()
        max_len = len(headers)
        padded_rows = []
        for row in data_rows:
            if len(row) < max_len:
                padded_rows.append(row + [''] * (max_len - len(row)))
            elif len(row) > max_len:
                padded_rows.append(row[:max_len])
            else:
                padded_rows.append(row)
        df = pd.DataFrame(padded_rows, columns=headers)
        df.columns = df.columns.str.strip()
        df = fix_duplicate_columns(df)
        return df
    except Exception as e:
        st.error(f"Error loading sheet: {str(e)}")
        return pd.DataFrame()

# ================= LOAD FREEBIE DATA =================
@st.cache_data(ttl=600, show_spinner=False)
def load_freebie_data():
    try:
        freebie_sheet_id = st.secrets["freebie_sheet_id"]
        freebie_df = load_sheet(freebie_sheet_id, "Sheet1")
        if not freebie_df.empty:
            freebie_df.columns = freebie_df.columns.str.strip()
            required_cols = ['Date', 'Item', 'Mentioned Freebie', 'Refund value']
            missing_cols = [col for col in required_cols if col not in freebie_df.columns]
            if missing_cols:
                return pd.DataFrame()
            freebie_df['Date'] = parse_dates_robust(freebie_df['Date'])
        return freebie_df
    except Exception:
        return pd.DataFrame()

# ================= PROCESS DATAFRAME =================
def process_refund_df(df):
    if df.empty:
        return df
    df = df.copy()
    bzid_col = find_column(df, ["BZID", "Business ID", "BZD", "bzid"])
    if bzid_col:
        df["BZID"] = df[bzid_col].astype(str).str.replace(r'\s+', '', regex=True).str.upper()
    else:
        df["BZID"] = ""
    date_col = find_column(df, ["Date", "date", "Timestamp", "timestamp"])
    if date_col:
        df["Date"] = parse_dates_robust(df[date_col])
    else:
        df["Date"] = pd.NaT
    month_col = find_column(df, ["Month", "month", "MONTH"])
    if month_col and (df["Date"].isna().all() or df["Date"].notna().sum() < len(df) * 0.5):
        year_col = find_column(df, ["Year", "year", "YEAR"])
        def construct_date(row):
            try:
                month_val = int(float(str(row[month_col]).strip()))
                if month_val < 1 or month_val > 12:
                    return pd.NaT
                year_val = None
                if year_col and pd.notna(row.get(year_col)):
                    try:
                        year_val = int(float(str(row[year_col]).strip()))
                    except:
                        pass
                if year_val is None and date_col and pd.notna(row.get(date_col)):
                    date_str = str(row[date_col])
                    ym = re.search(r'20\d{2}', date_str)
                    if ym:
                        year_val = int(ym.group())
                if year_val is None:
                    year_val = datetime.now().year
                return pd.Timestamp(year=year_val, month=month_val, day=1)
            except:
                return pd.NaT
        df["Date"] = df.apply(construct_date, axis=1)
    return df

# ================= GET CUSTOMER MONTHLY REFUND COUNT =================
@st.cache_data(ttl=600, show_spinner=False)
def get_customer_monthly_refund_count(cash_df, jc_df, manual_df, bzid, month, year):
    total_count = 0
    for df in [cash_df, jc_df, manual_df]:
        if not df.empty and "BZID" in df.columns and "Date" in df.columns:
            mask = (
                (df["BZID"] == bzid) &
                (df["Date"].notna()) &
                (df["Date"].dt.month == month) &
                (df["Date"].dt.year == year)
            )
            total_count += int(mask.sum())
    return total_count

# ================= GET REFUND COUNT FOR PERIOD =================
@st.cache_data(ttl=600, show_spinner=False)
def get_refund_count_for_period(df, bzid, year, start_month=1, end_month=12):
    if df.empty:
        return 0
    mask = (
        (df["BZID"] == bzid) &
        (df["Date"].notna()) &
        (df["Date"].dt.year == year) &
        (df["Date"].dt.month >= start_month) &
        (df["Date"].dt.month <= end_month)
    )
    return int(mask.sum())

# ================= GET MONTHLY COUNTS =================
@st.cache_data(ttl=600, show_spinner=False)
def get_monthly_counts(df, bzid, year):
    if df.empty:
        return [datetime(year, m, 1).strftime("%B") for m in range(1, 13)], [0] * 12
    df_bzid = df[(df["BZID"] == bzid) & (df["Date"].notna()) & (df["Date"].dt.year == year)]
    if df_bzid.empty:
        return [datetime(year, m, 1).strftime("%B") for m in range(1, 13)], [0] * 12
    monthly = df_bzid.groupby(df_bzid["Date"].dt.month).size().to_dict()
    counts = [monthly.get(m, 0) for m in range(1, 13)]
    names = [datetime(year, m, 1).strftime("%B") for m in range(1, 13)]
    return names, counts

# ================= HIGH RISK CUSTOMERS (OPTIMIZED, 3-TIER) =================
@st.cache_data(ttl=600, show_spinner=False)
def get_high_risk_customers_optimized(cash_df, jc_df, manual_df, year, current_month):
    if current_month is None:
        return pd.DataFrame()

    def prepare_df(df, source_label):
        if df.empty or "BZID" not in df.columns or "Date" not in df.columns:
            return pd.DataFrame(columns=["BZID", "Month", "Amount", "Source"])
        df = df[df["Date"].notna()].copy()
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Month", "Amount", "Source"])
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
        if df.empty:
            return pd.DataFrame(columns=["BZID", "Month", "Amount", "Source"])
        amount_col = find_column(df, ["Amount", "amount", "Refund Amount"])
        df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0) if amount_col else 0.0
        df["Month"] = df["Date"].dt.month
        df["Source"] = source_label
        return df[["BZID", "Month", "Amount", "Source"]]

    cash_prep = prepare_df(cash_df, "cash")
    jc_prep = prepare_df(jc_df, "jc")
    manual_prep = prepare_df(manual_df, "manual")

    parts = [p for p in [cash_prep, jc_prep, manual_prep] if not p.empty]
    if not parts:
        return pd.DataFrame()

    all_data = pd.concat(parts, ignore_index=True)
    if all_data.empty:
        return pd.DataFrame()

    source_totals = all_data.groupby(["BZID", "Source"])["Amount"].sum().unstack(fill_value=0)
    for src_col in ["cash", "jc", "manual"]:
        if src_col not in source_totals.columns:
            source_totals[src_col] = 0.0

    monthly_summary = all_data.groupby(["BZID", "Month"]).agg(
        Refund_Count=("Amount", "size"),
        Total_Amount=("Amount", "sum")
    ).reset_index()

    counts_pivot = monthly_summary.pivot(index="BZID", columns="Month", values="Refund_Count").fillna(0)
    amounts_pivot = monthly_summary.pivot(index="BZID", columns="Month", values="Total_Amount").fillna(0)

    for m in range(1, current_month + 1):
        if m not in counts_pivot.columns:
            counts_pivot[m] = 0
        if m not in amounts_pivot.columns:
            amounts_pivot[m] = 0.0

    counts_pivot = counts_pivot[sorted(counts_pivot.columns)]
    amounts_pivot = amounts_pivot[sorted(amounts_pivot.columns)]

    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def stats_for_window(start_m, end_m):
        months_in_window = list(range(start_m, end_m + 1))
        counts_w = counts_pivot[months_in_window]
        amounts_w = amounts_pivot[months_in_window]

        total_refunds = counts_w.sum(axis=1).astype(int)
        total_amount = amounts_w.sum(axis=1).astype(float)
        months_active = (counts_w > 0).sum(axis=1).astype(int)
        max_monthly_refunds = counts_w.max(axis=1).astype(int)
        max_monthly_amount = amounts_w.max(axis=1).astype(float)
        avg_refunds = (total_refunds / len(months_in_window)).round(2)

        last_2_cols = months_in_window[-2:] if len(months_in_window) >= 2 else months_in_window
        active_recently = (counts_w[last_2_cols] > 0).any(axis=1)

        mask = total_refunds > 0
        if not mask.any():
            return pd.DataFrame()

        result = pd.DataFrame({
            "BZID": counts_w.index[mask],
            "Total Refunds": total_refunds[mask].values,
            "Total Amount": total_amount[mask].round(2).values,
            "Monthly Average": avg_refunds[mask].values,
            "Months Active": months_active[mask].values,
            "Max Monthly Refunds": max_monthly_refunds[mask].values,
            "Max Monthly Amount": max_monthly_amount[mask].round(2).values,
            "Active Recently": active_recently[mask].values,
        })

        src_join = source_totals.reindex(result["BZID"].values)
        result["Cash_UPI"] = src_join["cash"].values.round(2)
        result["Jumbocash"] = src_join["jc"].values.round(2)
        result["Manual_Cash"] = src_join["manual"].values.round(2)

        counts_masked = counts_w[mask]
        amounts_masked = amounts_w[mask]
        for m in months_in_window:
            abbr = month_abbr[m - 1]
            c_vals = counts_masked[m].values
            a_vals = amounts_masked[m].values
            result[abbr] = [
                f"{int(c)} [₹{a:.0f}]" if c > 0 else "0"
                for c, a in zip(c_vals, a_vals)
            ]
        return result

    m3_start = max(1, current_month - 2)
    m6_start = max(1, current_month - 5)

    df_3m = stats_for_window(m3_start, current_month)
    df_6m = stats_for_window(m6_start, current_month)
    df_yr = stats_for_window(1, current_month)

    if df_3m.empty and df_6m.empty and df_yr.empty:
        return pd.DataFrame()

    def risk_level_for(row, window_months):
        total_amt = row["Total Amount"]
        avg = row["Monthly Average"]
        max_m = row["Max Monthly Refunds"]
        months_active = row["Months Active"]
        if (total_amt > 500 and avg >= 3) or max_m >= 5 or (months_active >= window_months and avg >= 3):
            return "🔴🔴 EXTREME"
        if avg >= 3 or max_m >= 4:
            return "🔴 HIGH"
        if avg >= 2 or months_active >= max(2, window_months - 1):
            return "🟡 POTENTIAL"
        return None

    classified_bzids = set()
    final_rows = []

    def process_tier(df_tier, tier_num, window_label, window_months, window_start, window_end):
        if df_tier.empty:
            return
        for row in df_tier.to_dict("records"):
            bzid = row["BZID"]
            if bzid in classified_bzids:
                continue
            lvl = risk_level_for(row, window_months)
            if not lvl:
                continue
            row["Risk Level"] = lvl
            row["Analysis Window"] = window_label
            row["Window Months"] = window_months
            row["Window Start"] = window_start
            row["Window End"] = window_end
            row["Status"] = "🔴 Active" if row.get("Active Recently") else "⏸️ Inactive"
            row["Tier Priority"] = tier_num
            final_rows.append(row)
            classified_bzids.add(bzid)

    process_tier(df_3m, 1, f"📅 Last 3 Months ({m3_start}-{current_month})", 3, m3_start, current_month)
    process_tier(df_6m, 2, f"📅 Last 6 Months ({m6_start}-{current_month})", 6, m6_start, current_month)
    process_tier(df_yr, 3, f"📆 Full Year (1-{current_month})", current_month, 1, current_month)

    if not final_rows:
        return pd.DataFrame()

    return pd.DataFrame(final_rows)

# ================= CITY ANALYSIS =================
@st.cache_data(ttl=600, show_spinner=False)
def get_city_analysis(cash_df, jc_df, manual_df, year, current_month):
    def prepare(df):
        if df.empty or "Date" not in df.columns:
            return pd.DataFrame(columns=["City", "Amount"])
        df = df[df["Date"].notna()].copy()
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
        if df.empty:
            return pd.DataFrame(columns=["City", "Amount"])
        amount_col = find_column(df, ["Amount", "amount", "Refund Amount"])
        df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0) if amount_col else 0
        city_col = find_column(df, ["City", "city", "City Name", "CityName"])
        df["City"] = df[city_col].astype(str).apply(standardize_city_name) if city_col else "Unknown"
        return df[["City", "Amount"]]
    all_city = pd.concat([prepare(cash_df), prepare(jc_df), prepare(manual_df)], ignore_index=True)
    if all_city.empty:
        return pd.DataFrame()
    return all_city.groupby("City").agg(
        Total_Amount=("Amount", "sum"),
        Total_Instances=("Amount", "count")
    ).reset_index().sort_values("Total_Amount", ascending=False)

# ================= HUB ANALYSIS =================
@st.cache_data(ttl=600, show_spinner=False)
def get_hub_analysis(cash_df, jc_df, manual_df, year, current_month):
    def prepare(df):
        if df.empty or "Date" not in df.columns:
            return pd.DataFrame(columns=["Hub", "Amount"])
        df = df[df["Date"].notna()].copy()
        df = df[(df["Date"].dt.year == year) & (df["Date"].dt.month <= current_month)]
        if df.empty:
            return pd.DataFrame(columns=["Hub", "Amount"])
        amount_col = find_column(df, ["Amount", "amount", "Refund Amount"])
        df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0) if amount_col else 0
        hub_col = find_column(df, ["Hub", "hub", "Hub ID", "HUB ID", "Hub Name"])
        df["Hub"] = df[hub_col].astype(str) if hub_col else "Unknown"
        return df[["Hub", "Amount"]]
    all_hub = pd.concat([prepare(cash_df), prepare(jc_df), prepare(manual_df)], ignore_index=True)
    if all_hub.empty:
        return pd.DataFrame()
    return all_hub.groupby("Hub").agg(
        Total_Amount=("Amount", "sum"),
        Total_Instances=("Amount", "count")
    ).reset_index().sort_values("Total_Amount", ascending=False)

# ================= BANK TRANSFER DATA =================
def get_bank_transfer_data(bank_df, ticket_id):
    if bank_df.empty:
        return pd.DataFrame()
    df = bank_df.copy()
    ticket_col = None
    for col in df.columns:
        if col and 'ticket' in col.lower() and ('id' in col.lower() or 'no' in col.lower()):
            ticket_col = col
            break
    if ticket_col is None:
        return pd.DataFrame()
    df[ticket_col] = df[ticket_col].astype(str).str.replace(r'\s+', '', regex=True)
    ticket_id_str = str(ticket_id).strip().replace(" ", "")
    df = df[df[ticket_col] == ticket_id_str]
    if df.empty:
        return pd.DataFrame()
    rename_map = {}
    for col in df.columns:
        cl = col.lower() if col else ''
        if 'ticket' in cl and 'id' in cl: rename_map[col] = "Ticket ID"
        elif 'phone' in cl: rename_map[col] = "Phone Number"
        elif cl in ['hub', 'hub name']: rename_map[col] = "Hub"
        elif cl in ['city', 'city name']: rename_map[col] = "City"
        elif 'reason' in cl: rename_map[col] = "Reason"
        elif 'amount' in cl: rename_map[col] = "Amount"
        elif 'utr' in cl: rename_map[col] = "UTR Number"
        elif 'status' in cl: rename_map[col] = "Status"
        elif cl in ['date', 'date1']: rename_map[col] = "Date"
    df = df.rename(columns=rename_map)
    if "City" in df.columns:
        df["City"] = df["City"].astype(str).apply(standardize_city_name)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True).dt.strftime("%d-%m-%Y")
    display_cols = ["Ticket ID", "Phone Number", "Hub", "City", "Reason", "Amount", "UTR Number", "Status", "Date"]
    df_display = df[[col for col in display_cols if col in df.columns]].copy()
    if "Amount" in df_display.columns:
        df_display["Amount"] = pd.to_numeric(df_display["Amount"], errors="coerce")
        df_display["Amount"] = df_display["Amount"].apply(lambda x: f"₹{x:.2f}" if pd.notna(x) else "₹0.00")
        df_display.rename(columns={"Amount": "Amount (₹)"}, inplace=True)
    return df_display

# ================= PARSE HELPERS =================
def parse_refund_value(value):
    if pd.isna(value):
        return None, False
    value_str = str(value).strip()
    if value_str.upper() == 'SP':
        return None, True
    value_str = value_str.replace('/-', '').strip()
    try:
        return float(value_str), False
    except:
        return None, False

def parse_freebie_offer(offer_text):
    if pd.isna(offer_text) or offer_text == "":
        return None, None
    offer_text = str(offer_text).lower().strip()
    offer_indicators = ['+', 'buy', 'get', 'free']
    if not any(word in offer_text for word in offer_indicators):
        return 1, 1
    if '+' in offer_text:
        parts = offer_text.split('+')
        if len(parts) == 2:
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except:
                pass
    if 'buy' in offer_text and 'get' in offer_text:
        numbers = re.findall(r'\d+', offer_text)
        if len(numbers) >= 2:
            try:
                return int(numbers[0]), int(numbers[1])
            except:
                pass
    return 1, 1

def calculate_freebie_refund_from_sheet(row, ordered_qty, manual_refund_value=None):
    freebie_offer = row.get('Mentioned Freebie', '')
    if pd.isna(freebie_offer) or freebie_offer == '':
        return 0, "No freebie offer found"
    refund_value_raw = row.get('Refund value', '')
    parsed_value, is_sp = parse_refund_value(refund_value_raw)
    if is_sp:
        if manual_refund_value is not None and manual_refund_value > 0:
            refund_value = manual_refund_value
        else:
            return 0, "SP (Selling Price) - Please enter the selling price"
    else:
        if parsed_value is None or parsed_value == 0:
            return 0, f"No refund value specified for offer: {freebie_offer}"
        refund_value = parsed_value
    ordered_required, free_given = parse_freebie_offer(freebie_offer)
    if ordered_required is None or free_given is None:
        return 0, f"Could not parse offer: '{freebie_offer}'."
    expected_freebies = (ordered_qty // ordered_required) * free_given
    if expected_freebies == 0:
        return 0, f"No freebies due for {ordered_qty} items."
    refund_amount = expected_freebies * refund_value
    return refund_amount, f"Missing {expected_freebies} freebie(s) x Rs.{refund_value} = Rs.{refund_amount}"

# ================= REFRESH =================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ================= TAB SELECTION =================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Individual Search",
    "🏦 Bank Transfer Refund Details",
    "📊 High Risk Customers",
    "🏙️ City Analysis",
    "🏪 Hub Analysis",
    "🎁 Freebie Calculator"
])

current_year = datetime.now().year
current_month = datetime.now().month

# ================= TAB 1: Individual Search =================
with tab1:
    col1, col2 = st.columns(2)
    bzid_input = col1.text_input("Enter BZID")
    month_options = {datetime(current_year, i, 1).strftime("%B %Y"): i for i in range(1, 13)}
    selected_month_label = col2.selectbox("Select Month", list(month_options.keys()))
    month_input = month_options[selected_month_label]
    selected_year = int(selected_month_label.split()[-1])
   
    if st.button("Fetch Details"):
        if not bzid_input:
            st.warning("Enter BZID")
            st.stop()
        bzid = bzid_input.strip().replace(" ", "").upper()
       
        with st.spinner("Fetching data..."):
            cash_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1"))
            jc_df = process_refund_df(load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1"))
            manual_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund"))
            
            with st.expander("🔧 Debug Info (click to expand)", expanded=False):
                st.write(f"**Searching for BZID:** `{bzid}`")
                st.write(f"**Cash/UPI rows:** {len(cash_df)} | Valid dates: {cash_df['Date'].notna().sum() if not cash_df.empty else 0}")
                st.write(f"**Jumbocash rows:** {len(jc_df)} | Valid dates: {jc_df['Date'].notna().sum() if not jc_df.empty else 0}")
                st.write(f"**Manual Cash rows:** {len(manual_df)} | Valid dates: {manual_df['Date'].notna().sum() if not manual_df.empty else 0}")
                if not jc_df.empty and "BZID" in jc_df.columns:
                    matching = jc_df[jc_df['BZID'].str.contains(bzid, na=False, regex=False)]
                    st.write(f"**Rows matching BZID in Jumbocash:** {len(matching)}")
           
            cash_matches = cash_df[
                (cash_df["BZID"] == bzid) & (cash_df["Date"].notna()) &
                (cash_df["Date"].dt.month == month_input) & (cash_df["Date"].dt.year == selected_year)
            ] if not cash_df.empty and "BZID" in cash_df.columns else pd.DataFrame()
            jc_matches = jc_df[
                (jc_df["BZID"] == bzid) & (jc_df["Date"].notna()) &
                (jc_df["Date"].dt.month == month_input) & (jc_df["Date"].dt.year == selected_year)
            ] if not jc_df.empty and "BZID" in jc_df.columns else pd.DataFrame()
            manual_matches = manual_df[
                (manual_df["BZID"] == bzid) & (manual_df["Date"].notna()) &
                (manual_df["Date"].dt.month == month_input) & (manual_df["Date"].dt.year == selected_year)
            ] if not manual_df.empty and "BZID" in manual_df.columns else pd.DataFrame()
           
            cash_count = len(cash_matches)
            jc_count = len(jc_matches)
            manual_count = len(manual_matches)
            total_count = cash_count + jc_count + manual_count
           
            cash_amount = pd.to_numeric(cash_matches["Amount"], errors="coerce").sum() if not cash_matches.empty and "Amount" in cash_matches.columns else 0
            jc_amount = pd.to_numeric(jc_matches["Amount"], errors="coerce").sum() if not jc_matches.empty and "Amount" in jc_matches.columns else 0
            manual_amount = pd.to_numeric(manual_matches["Amount"], errors="coerce").sum() if not manual_matches.empty and "Amount" in manual_matches.columns else 0
            total_amount = cash_amount + jc_amount + manual_amount
           
            all_refunds_list = []
            for df in [cash_df, jc_df, manual_df]:
                if not df.empty and "BZID" in df.columns and "Date" in df.columns:
                    all_refunds_list.append(df[["BZID", "Date"]])
            all_refunds = pd.concat(all_refunds_list, ignore_index=True) if all_refunds_list else pd.DataFrame()
            if not all_refunds.empty:
                current_year_count = get_refund_count_for_period(all_refunds, bzid, current_year, 1, current_month)
                last_year_count = get_refund_count_for_period(all_refunds, bzid, current_year - 1, 1, current_month)
                month_names, monthly_counts = get_monthly_counts(all_refunds, bzid, current_year)
            else:
                current_year_count = 0
                last_year_count = 0
                month_names, monthly_counts = [], []
       
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown("## 📊 Current Month")
            st.markdown(f"### {selected_month_label}")
            if total_count < 5:
                st.markdown(f"""
                <div style="background-color: #d4edda; padding: 20px; border-radius: 10px; text-align: center;">
                    <h1 style="color: #28a745; margin: 0;">✅ APPROVED</h1>
                    <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count} (Less than 5)</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #f8d7da; padding: 20px; border-radius: 10px; text-align: center;">
                    <h1 style="color: #dc3545; margin: 0;">❌ DENIED</h1>
                    <p style="font-size: 18px; margin: 5px 0;">Total Refunds: {total_count} (5 or more - Limit reached)</p>
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
           
            c1, c2 = st.columns(2)
            with c1:
                st.metric("💳 Cash / UPI", cash_count, f"₹{round(cash_amount, 2)}")
                st.metric("💵 Manual Cash", manual_count, f"₹{round(manual_amount, 2)}")
            with c2:
                st.metric("🏦 Jumbocash", jc_count, f"₹{round(jc_amount, 2)}")
                st.metric("📦 Total", total_count, f"₹{round(total_amount, 2)}")
       
        with col_right:
            st.markdown("## 📋 Refund Details")
            st.markdown(f"### {selected_month_label}")
            tabs_inner = st.tabs(["💳 Cash/UPI", "🏦 Jumbocash", "💵 Manual Cash"])
            with tabs_inner[0]:
                if not cash_matches.empty:
                    st.dataframe(cash_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Cash/UPI refunds for this month")
            with tabs_inner[1]:
                if not jc_matches.empty:
                    st.dataframe(jc_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Jumbocash refunds for this month")
            with tabs_inner[2]:
                if not manual_matches.empty:
                    st.dataframe(manual_matches.reset_index(drop=True), use_container_width=True, height=300)
                else:
                    st.info("No Manual Cash refunds for this month")
       
        if month_names:
            st.markdown("---")
            st.markdown(f"## 📈 Yearly Refund Trend (Jan - {datetime(current_year, current_month, 1).strftime('%B')})")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.markdown(f"""
                <div style="background-color: #667eea; border-radius: 10px; padding: 20px; color: white;">
                    <p style="margin: 0; opacity: 0.8;">Current Year</p>
                    <h2 style="margin: 5px 0;">{current_year}</h2>
                    <h1 style="margin: 5px 0;">{current_year_count}</h1>
                    <p style="margin: 0; opacity: 0.9;">Jan - {datetime(current_year, current_month, 1).strftime('%b')} Total</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="background-color: #764ba2; border-radius: 10px; padding: 20px; color: white;">
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
                    <p style="margin: 0; color: #6c757d; font-size: 14px;">Year-over-Year Change</p>
                    <h2 style="margin: 5px 0; color: {'#28a745' if current_year_count >= last_year_count else '#dc3545'}">{change_text}</h2>
                    <p style="margin: 0; color: #6c757d; font-size: 14px;">{current_year_count} vs {last_year_count} refunds</p>
                </div>
                """, unsafe_allow_html=True)
           
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
   
    ticket_id_input = st.text_input("Enter Ticket ID")
    if st.button("🔍 Search Bank Transfer"):
        if not ticket_id_input:
            st.warning("Please enter a Ticket ID")
            st.stop()
        ticket_id = ticket_id_input.strip()
        with st.spinner(f"Searching for Ticket ID: {ticket_id}..."):
            bank_df = load_sheet(st.secrets["bank_transfer_sheet_id"], "CD Refund Sheet")
            if bank_df.empty:
                st.warning("⚠️ No data found in the bank transfer sheet.")
                st.stop()
            bank_match = get_bank_transfer_data(bank_df, ticket_id)
        if bank_match.empty:
            st.warning(f"No bank transfer records found for Ticket ID: {ticket_id}")
        else:
            st.success(f"✅ Found {len(bank_match)} bank transfer record(s) for Ticket ID: {ticket_id}")
            st.markdown("---")
            st.markdown("## 📋 Bank Transfer Details")
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
                    </table>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("### 📊 Data View")
            st.dataframe(bank_match, use_container_width=True, hide_index=True)
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
    <div style="background-color: #e7f3ff; padding: 15px; border-radius: 10px; border-left: 4px solid #2196F3;">
        <b>📖 Risk Assessment (3-Tier Time Window):</b><br>
        <b>📅 Tier 1 — Last 3 Months</b> (highest priority): Recent high-frequency + high-amount refunds<br>
        <b>📅 Tier 2 — Last 6 Months</b>: Not caught in Tier 1 but sustained over 6 months<br>
        <b>📆 Tier 3 — Full Year</b>: Final catch-all for the rest of the year<br><br>
        <b>Risk Levels:</b><br>
        🔴🔴 <b>EXTREME</b>: (Amount > ₹500 AND Avg ≥ 3) OR 5+ in any month OR active every month<br>
        🔴 <b>HIGH</b>: Avg ≥ 3 OR 4+ in any month<br>
        🟡 <b>POTENTIAL</b>: Avg ≥ 2 OR almost every month active<br><br>
        <i>Each customer appears only ONCE — in the highest-priority tier they qualify for.</i>
    </div>
    """, unsafe_allow_html=True)
   
    if 'high_risk_data' not in st.session_state:
        st.session_state.high_risk_data = None
   
    if st.button("🔄 Load High Risk Customers"):
        with st.spinner("Analyzing customer data across 3 tiers..."):
            cash_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1"))
            jc_df = process_refund_df(load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1"))
            manual_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund"))
            st.session_state.high_risk_data = get_high_risk_customers_optimized(
                cash_df, jc_df, manual_df, current_year, current_month
            )
   
    if st.session_state.high_risk_data is not None and not st.session_state.high_risk_data.empty:
        high_risk_df = st.session_state.high_risk_data.copy()

        risk_order = {"🔴🔴 EXTREME": 0, "🔴 HIGH": 1, "🟡 POTENTIAL": 2}
        high_risk_df["Risk_Order"] = high_risk_df["Risk Level"].map(risk_order).fillna(3)
        high_risk_df = high_risk_df.sort_values(
            ["Tier Priority", "Risk_Order", "Total Amount"],
            ascending=[True, True, False]
        ).reset_index(drop=True)
       
        st.success(f"Found **{len(high_risk_df)}** high-risk customers across all tiers")
       
        tier1 = high_risk_df[high_risk_df["Tier Priority"] == 1]
        tier2 = high_risk_df[high_risk_df["Tier Priority"] == 2]
        tier3 = high_risk_df[high_risk_df["Tier Priority"] == 3]

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.metric("📅 Last 3 Months", len(tier1))
        with col2: st.metric("📅 Last 6 Months", len(tier2))
        with col3: st.metric("📆 Full Year", len(tier3))
        with col4: st.metric("🔴🔴 Extreme", len(high_risk_df[high_risk_df["Risk Level"] == "🔴🔴 EXTREME"]))
        with col5: st.metric("Total Amount", f"₹{high_risk_df['Total Amount'].sum():,.2f}")

        st.markdown("---")

        tier_tabs = st.tabs([
            f"📅 Last 3 Months ({len(tier1)})",
            f"📅 Last 6 Months ({len(tier2)})",
            f"📆 Full Year ({len(tier3)})",
            f"👥 All ({len(high_risk_df)})"
        ])

        month_abbr_full = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        base_cols_prefix = [
            "BZID", "Risk Level", "Analysis Window", "Status",
            "Total Refunds", "Monthly Average", "Months Active",
            "Max Monthly Refunds", "Total Amount",
            "Cash_UPI", "Jumbocash", "Manual_Cash",
        ]

        column_config = {
            "BZID": st.column_config.TextColumn("BZID"),
            "Risk Level": st.column_config.TextColumn("Risk Level"),
            "Analysis Window": st.column_config.TextColumn("Analysis Window"),
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
        for m in month_abbr_full:
            column_config[m] = st.column_config.TextColumn(m)

        def highlight_risk(row):
            risk = row.get('Risk Level', '')
            if 'EXTREME' in risk:
                return ['background-color: #dc3545; color: white; font-weight: bold;'] * len(row)
            elif 'HIGH' in risk:
                return ['background-color: #f8d7da; font-weight: bold;'] * len(row)
            elif 'POTENTIAL' in risk:
                return ['background-color: #fff3cd;'] * len(row)
            return [''] * len(row)

        def render_tier(df_subset, key_suffix, window_start, window_end):
            if df_subset.empty:
                st.info("No customers in this tier.")
                return
            window_months = [month_abbr_full[m - 1] for m in range(window_start, window_end + 1)]
            display_cols = base_cols_prefix + window_months
            display_df = df_subset[[c for c in display_cols if c in df_subset.columns]].copy()
            st.dataframe(
                display_df.style.apply(highlight_risk, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
                key=f"tier_table_{key_suffix}"
            )

        with tier_tabs[0]:
            st.markdown(f"### 📅 Tier 1 — Customers with high refund activity in the **last 3 months**")
            st.caption("Showing ONLY the last 3 months below. These are the most urgent cases.")
            render_tier(tier1, "t1", max(1, current_month - 2), current_month)

        with tier_tabs[1]:
            st.markdown(f"### 📅 Tier 2 — Customers flagged over the **last 6 months**")
            st.caption("Showing ONLY the last 6 months below.")
            render_tier(tier2, "t2", max(1, current_month - 5), current_month)

        with tier_tabs[2]:
            st.markdown(f"### 📆 Tier 3 — Customers flagged over the **full year**")
            st.caption("Showing all months of the year below.")
            render_tier(tier3, "t3", 1, current_month)

        with tier_tabs[3]:
            st.markdown("### 👥 All High Risk Customers")
            st.caption("Full view — every customer, all months of the year.")
            render_tier(high_risk_df, "all", 1, current_month)

        export_df = high_risk_df.copy()
        csv = export_df.to_csv(index=False)
        st.download_button(
            "📥 Download High Risk Report (CSV)",
            data=csv,
            file_name=f"high_risk_customers_{current_year}_month{current_month}.csv",
            mime="text/csv"
        )
       
    elif st.session_state.high_risk_data is not None:
        st.info("✅ No high-risk customers found across any tier!")

# ================= TAB 4: City Analysis =================
with tab4:
    st.markdown("## 🏙️ City-wise Refund Analysis")
    st.markdown("*City-wise refund amounts and instances (standardized city names)*")
   
    if 'city_data' not in st.session_state:
        st.session_state.city_data = None
   
    if st.button("🔄 Load City Analysis"):
        with st.spinner("Analyzing city data..."):
            cash_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1"))
            jc_df = process_refund_df(load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1"))
            manual_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund"))
            st.session_state.city_data = get_city_analysis(cash_df, jc_df, manual_df, current_year, current_month)
   
    if st.session_state.city_data is not None and not st.session_state.city_data.empty:
        city_df = st.session_state.city_data
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Cities", city_df["City"].nunique())
        with col2: st.metric("Total Instances", city_df["Total_Instances"].sum())
        with col3: st.metric("Total Amount", f"₹{city_df['Total_Amount'].sum():,.2f}")
        st.dataframe(
            city_df, use_container_width=True, hide_index=True,
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
   
    if 'hub_data' not in st.session_state:
        st.session_state.hub_data = None
   
    if st.button("🔄 Load Hub Analysis"):
        with st.spinner("Analyzing hub data..."):
            cash_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1"))
            jc_df = process_refund_df(load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1"))
            manual_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund"))
            st.session_state.hub_data = get_hub_analysis(cash_df, jc_df, manual_df, current_year, current_month)
   
    if st.session_state.hub_data is not None and not st.session_state.hub_data.empty:
        hub_df = st.session_state.hub_data
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Hubs", hub_df["Hub"].nunique())
        with col2: st.metric("Total Instances", hub_df["Total_Instances"].sum())
        with col3: st.metric("Total Amount", f"₹{hub_df['Total_Amount'].sum():,.2f}")
        st.dataframe(
            hub_df, use_container_width=True, hide_index=True,
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

# ================= TAB 6: Freebie Calculator =================
with tab6:
    st.markdown("## 🎁 Freebie Refund Calculator")
    st.markdown("*Enter BZID, select product and month, enter quantity to calculate freebie refund and get approval decision*")
    
    try:
        cash_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "Form Responses 1"))
        jc_df = process_refund_df(load_sheet(st.secrets["jumbocash_sheet_id"], "Form Responses 1"))
        manual_df = process_refund_df(load_sheet(st.secrets["cash_upi_sheet_id"], "cash refund"))
        freebie_df = load_freebie_data()
    except:
        cash_df = pd.DataFrame()
        jc_df = pd.DataFrame()
        manual_df = pd.DataFrame()
        freebie_df = pd.DataFrame()
    
    if freebie_df.empty:
        st.error("❌ Could not load freebie data. Please check your configuration.")
        st.stop()
    
    freebie_df = freebie_df.dropna(subset=['Item', 'Mentioned Freebie', 'Refund value'])
    
    if freebie_df.empty:
        st.warning("No freebie data found in the sheet.")
        st.stop()
    
    st.markdown("### 📋 Available Freebie Offers")
    st.dataframe(
        freebie_df[['Date', 'Item', 'Mentioned Freebie', 'Refund value']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date"),
            "Item": st.column_config.TextColumn("Product Item"),
            "Mentioned Freebie": st.column_config.TextColumn("Freebie Offer"),
            "Refund value": st.column_config.TextColumn("Refund Value")
        }
    )
    
    has_sp = any(freebie_df['Refund value'].astype(str).str.upper().str.strip() == 'SP')
    
    if has_sp:
        st.warning("⚠️ Some products have 'SP' (Selling Price) as refund value. You will need to enter the selling price manually for those products.")
    
    st.markdown("---")
    st.markdown("### 📋 Enter Refund Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        bzid_input_fb = st.text_input("Enter BZID", help="Customer Business ID - required for approval decision", key="freebie_bzid")
        product_options = freebie_df['Item'].unique().tolist()
        selected_product = st.selectbox("Select Product", product_options, help="Select the product with freebie offer")
    
    with col2:
        month_options = {datetime(current_year, i, 1).strftime("%B %Y"): i for i in range(1, 13)}
        selected_month_label = st.selectbox("Select Month for Refund Count", list(month_options.keys()), key="freebie_month")
        selected_month = month_options[selected_month_label]
        selected_year = int(selected_month_label.split()[-1])
        ordered_qty = st.number_input("📦 Quantity Ordered", min_value=0, value=10, step=1, help="Total quantity of the item the customer ordered")
    
    selected_row = freebie_df[freebie_df['Item'] == selected_product].iloc[0] if selected_product else None
    
    if selected_row is not None:
        freebie_offer = selected_row.get('Mentioned Freebie', '')
        refund_value_raw = selected_row.get('Refund value', '')
        freebie_date = selected_row.get('Date', '')
        parsed_value, is_sp = parse_refund_value(refund_value_raw)
        display_value = "SP" if is_sp else (f"₹{parsed_value:.2f}" if parsed_value is not None else refund_value_raw)
        st.info(f"**Freebie Offer:** {freebie_offer} | **Refund Value:** {display_value} | **Date Added:** {freebie_date}")
        ordered_required, free_given = parse_freebie_offer(freebie_offer)
        if ordered_required and free_given:
            st.info(f"**Offer Details:** Buy {ordered_required} get {free_given} free")
        else:
            st.warning(f"⚠️ Could not parse freebie offer: '{freebie_offer}'.")
    
    manual_price = None
    if selected_row is not None:
        _, is_sp = parse_refund_value(selected_row.get('Refund value', ''))
        if is_sp:
            manual_price = st.number_input("💰 Enter Selling Price (₹)", min_value=0.0, value=10.0, step=1.0, help="Enter the selling price of the product")
    
    if st.button("🧮 Calculate Refund", type="primary"):
        if not bzid_input_fb:
            st.error("❌ Please enter BZID")
            st.stop()
        bzid = bzid_input_fb.strip().replace(" ", "").upper()
        if selected_row is None:
            st.error("❌ Please select a product")
            st.stop()
        if ordered_qty <= 0:
            st.error("❌ Quantity Ordered must be greater than 0")
            st.stop()
        _, is_sp = parse_refund_value(selected_row.get('Refund value', ''))
        if is_sp and (manual_price is None or manual_price <= 0):
            st.error("❌ Please enter the selling price for this product")
            st.stop()
        
        refund_amount, calculation_details = calculate_freebie_refund_from_sheet(selected_row, ordered_qty, manual_price)
        total_monthly_count = get_customer_monthly_refund_count(cash_df, jc_df, manual_df, bzid, selected_month, selected_year)
        
        st.markdown("---")
        st.markdown("## 📊 Refund Calculation & Decision")
        st.markdown("### 📈 Calculation Breakdown")
        
        ordered_required, free_given = parse_freebie_offer(freebie_offer)
        expected_freebies = (ordered_qty // ordered_required) * free_given if ordered_required else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Refund Details")
            st.write(f"**BZID:** {bzid}")
            st.write(f"**Product:** {selected_product}")
            st.write(f"**Freebie Offer:** {freebie_offer}")
            st.write(f"**Quantity Ordered:** {ordered_qty}")
            st.write(f"**Freebies Expected:** {expected_freebies}")
            if is_sp:
                st.write(f"**Selling Price (Manual):** ₹{manual_price:.2f}")
            else:
                parsed_val, _ = parse_refund_value(selected_row.get('Refund value', ''))
                st.write(f"**Refund Value per Freebie:** ₹{parsed_val:.2f}" if parsed_val else "**Refund Value:** N/A")
            if refund_amount == 0:
                st.write(f"**Refund Amount:** ₹{refund_amount:.2f} (No refund due)")
            else:
                st.write(f"**Refund Amount:** ₹{refund_amount:.2f}")
        
        with col2:
            st.markdown("#### Decision")
            st.write(f"**Month:** {selected_month_label}")
            st.write(f"**Total Monthly Refund Count:** {total_monthly_count}")
            
            if refund_amount == 0:
                decision = "NO REFUND"
                color = "#ffc107"
                message = "No missing freebies found or offer could not be parsed"
            elif refund_amount >= 100:
                decision = "❌ DENIED"
                color = "#dc3545"
                message = f"Refund amount ₹{refund_amount:.2f} exceeds ₹100 limit"
            elif total_monthly_count >= 5:
                decision = "❌ DENIED"
                color = "#dc3545"
                message = f"{total_monthly_count} total refund(s) this month (5 or more - Limit reached)"
            else:
                decision = "✅ APPROVED"
                color = "#28a745"
                message = f"Refund ₹{refund_amount:.2f} (< ₹100) and only {total_monthly_count} refund(s) this month"
            
            st.markdown(f"""
            <div style="background-color: {color}; padding: 20px; border-radius: 10px; color: white; text-align: center;">
                <h2>{decision}</h2>
                <p>{message}</p>
                <p><b>Refund Amount: ₹{refund_amount:.2f}</b></p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 📋 Detailed Breakdown")
        
        if is_sp:
            display_refund_value = manual_price
        else:
            parsed_val, _ = parse_refund_value(selected_row.get('Refund value', ''))
            display_refund_value = parsed_val if parsed_val else 0
        
        offer_parsed = "✅ Parsed" if (ordered_required and free_given) else "❌ Could not parse"
        
        st.markdown(f"""
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
            <tr style="background-color: #667eea; color: white;">
                <th style="padding: 10px; text-align: left;">Description</th>
                <th style="padding: 10px; text-align: left;">Value</th>
            </tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">BZID</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{bzid}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Product</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{selected_product}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Freebie Offer</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{freebie_offer}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Offer Parse Status</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{offer_parsed}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Quantity Ordered</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{ordered_qty}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Freebies Expected</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{expected_freebies}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Refund Value per Freebie</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">₹{display_refund_value:.2f}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Total Refund Amount</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">₹{refund_amount:.2f}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">Monthly Refund Count (All Types)</td><td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{total_monthly_count}</td></tr>
            <tr style="background-color: {'#d4edda' if refund_amount > 0 and refund_amount < 100 and total_monthly_count < 5 else '#f8d7da'}; font-weight: bold;">
                <td style="padding: 10px;">Decision</td>
                <td style="padding: 10px; color: {'#28a745' if refund_amount > 0 and refund_amount < 100 and total_monthly_count < 5 else '#dc3545' if refund_amount > 0 else '#ffc107'};">
                    {'✅ APPROVED' if refund_amount > 0 and refund_amount < 100 and total_monthly_count < 5 else '❌ DENIED' if refund_amount > 0 else 'ℹ️ NO REFUND'}
                </td>
            </tr>
            <tr style="background-color: #d4edda; font-weight: bold;">
                <td style="padding: 10px;">Final Refund Amount</td>
                <td style="padding: 10px; color: #28a745; font-size: 18px;">₹{refund_amount:.2f}</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)
        
        if not ordered_required or not free_given:
            st.warning("""
            ⚠️ **Could not parse the freebie offer.**
            
            The freebie offer should follow one of these formats:
            - `22+2` (Buy 22 get 2 free)
            - `11+1` (Buy 11 get 1 free)
            - `Buy 12 Get 2 Free` (Buy 12 get 2 free)
            - `Buy 2 get 1` (Buy 2 get 1 free)
            - Or just the product name for 1:1 freebie ratio
            """)
        
        if refund_amount > 0 and refund_amount < 100 and total_monthly_count < 5:
            st.markdown("---")
            st.markdown("### 🚀 Process Refund")
            if st.button(f"💰 Process ₹{refund_amount:.2f} Directly", type="primary"):
                st.success(f"✅ Refund of ₹{refund_amount:.2f} initiated successfully for BZID: {bzid}!")
                st.info("📌 Please verify the refund in the Refund Tracker")
    
    st.markdown("---")
    st.markdown("""
    <div style="background-color: #f0f7ff; padding: 15px; border-radius: 10px; border-left: 4px solid #2196F3;">
        <b>📌 Freebie Refund Rules:</b><br>
        1. Refund amount must be < ₹100 to be approved<br>
        2. Customer must have less than 5 total refunds in the month<br>
        3. Both conditions must be met for APPROVAL<br><br>
        <b>🎁 Freebie Offer Formats:</b><br>
        • <b>Product Name only</b> (e.g., "Scrub pad") → 1:1 ratio (Buy 1 get 1 free)<br>
        • <b>"22+2"</b> → Buy 22 get 2 free<br>
        • <b>"11+1"</b> → Buy 11 get 1 free<br>
        • <b>"Buy 12 Get 2 Free"</b> → Buy 12 get 2 free<br>
        • <b>"Buy 2 get 1"</b> → Buy 2 get 1 free<br><br>
        <b>Special Case - SP (Selling Price):</b><br>
        • When refund value is "SP", you need to enter the selling price manually<br><br>
        <b>How it works:</b><br>
        1. Enter the customer's BZID<br>
        2. Select the product and month<br>
        3. Enter the quantity the customer ordered<br>
        4. If SP is shown, enter the selling price<br>
        5. Click "Calculate Refund" to see the decision
    </div>
    """, unsafe_allow_html=True)

# ================= FOOTER =================
st.markdown("---")
st.caption("💰 Refund Tracker | Made with ❤️")
