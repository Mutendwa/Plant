# farm_dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Farm KPI Dashboard", layout="wide")
st.title("Farm Production Dashboard")

# ========================================
# FILE UPLOAD
# ========================================
uploaded = st.sidebar.file_uploader(
    "Upload **Oltepesi DA Test Workbook.xlsx**",
    type=["xlsx"],
    help="Drag & drop or click to upload"
)

if uploaded is None:
    st.info("Please upload your Excel file to begin.")
    st.stop()

# Save uploaded file
with open("temp_data.xlsx", "wb") as f:
    f.write(uploaded.getbuffer())

df = pd.read_excel("temp_data.xlsx")
df.columns = df.columns.str.strip()

# ========================================
# CONFIG
# ========================================
SICK_FACTOR = 0.06
HARVESTER_OUTPUT_PER_DAY = 100.0
WORKING_DAYS_PER_HARVESTER_PER_YEAR = 250.0
FORECAST_ROLLING_WEEKS = 4
TOP_VARIETIES_TO_PLOT = 6

# ========================================
# DATA PREP
# ========================================
day_cols = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
for c in day_cols:
    df[c] = pd.to_numeric(df.get(c, pd.Series()), errors='coerce')

if 'PlantDate' in df.columns:
    df['PlantDate'] = pd.to_datetime(df['PlantDate'], errors='coerce')
if 'Year' not in df.columns and 'PlantDate' in df.columns:
    df['Year'] = df['PlantDate'].dt.year
if 'Week' not in df.columns and 'PlantDate' in df.columns:
    df['Week'] = df['PlantDate'].dt.isocalendar().week

def infer_day(row):
    if pd.notna(row.get('PlantDate')):
        return int(row['PlantDate'].weekday()) + 1
    for i, d in enumerate(day_cols, start=1):
        val = row.get(d)
        if pd.notna(val) and val != 0:
            return i
    return np.nan

df['Day'] = df.apply(infer_day, axis=1).astype('Int64')
df['Year'] = df['Year'].astype('Int64')
df['Week'] = df['Week'].astype('Int64')
df['YearWeekDay'] = df['Year'].astype(str) + "_" + df['Week'].astype(str).str.zfill(2) + "_" + df['Day'].astype(str)

group_keys = ['Variety'] + (['ProductionNumber'] if 'ProductionNumber' in df.columns else [])
sort_by = group_keys + (['PlantDate'] if 'PlantDate' in df.columns else ['Year','Week','Day'])
df = df.sort_values(sort_by).reset_index(drop=True)
df['Nth Day'] = df.groupby(group_keys).cumcount() + 1
df['Nth Week'] = ((df['Nth Day'] - 1) // 7 + 1).astype(int)

df['MotherPlants'] = pd.to_numeric(df.get('MotherPlants'), errors='coerce')
df['Total'] = pd.to_numeric(df.get('Total'), errors='coerce').fillna(0.0)
df['EstimatedCoefficient'] = pd.to_numeric(df.get('EstimatedCoefficient'), errors='coerce')

df['Actual Coefficient'] = df.apply(
    lambda r: r['Total'] / r['MotherPlants'] * 100
    if pd.notna(r['MotherPlants']) and r['MotherPlants'] > 0 else np.nan, axis=1)

est_mean = df['EstimatedCoefficient'].dropna().mean()
df['EstimatedProduction'] = df.apply(
    lambda r: r['MotherPlants'] * (r['EstimatedCoefficient']/100)
    if (pd.notna(r['EstimatedCoefficient']) and r['EstimatedCoefficient']>1 and est_mean>1.5)
    else r['MotherPlants'] * r['EstimatedCoefficient']
    if pd.notna(r['EstimatedCoefficient']) and pd.notna(r['MotherPlants']) else np.nan, axis=1)

df['% Difference'] = df.apply(
    lambda r: (r['Total'] - r['EstimatedProduction']) / r['EstimatedProduction'] * 100
    if pd.notna(r['EstimatedProduction']) and r['EstimatedProduction'] != 0 else np.nan, axis=1)

def weekstart_from_year_week(y, w):
    try:
        return pd.to_datetime(f"{int(y)}-W{int(w):02d}-1", format="%G-W%V-%u").date()
    except:
        return pd.NaT

if 'PlantDate' in df.columns and df['PlantDate'].notna().any():
    df['WeekStart'] = df['PlantDate'].dt.to_period('W').apply(lambda r: r.start_time.date())
else:
    df['WeekStart'] = df.apply(lambda r: weekstart_from_year_week(r['Year'], r['Week']), axis=1)

weekly_variety = (
    df.groupby(['WeekStart', 'Variety'], dropna=False)
      .agg(
          ActualTotal=('Total','sum'),
          EstimatedTotal=('EstimatedProduction','sum'),
          MeanActualCoeff=('Actual Coefficient','mean'),
          Records=('Total','count')
      )
      .reset_index()
      .sort_values(['Variety','WeekStart'])
)
weekly_variety['AccuracyRate_pct'] = np.where(
    weekly_variety['EstimatedTotal'].replace(0, np.nan).notna(),
    weekly_variety['ActualTotal'] / weekly_variety['EstimatedProduction'] * 100,
    np.nan
)

# ========================================
# GRAPHS
# ========================================
st.subheader("Weekly Total Production")
weekly_totals = df.groupby('WeekStart', dropna=False)['Total'].sum().reset_index()
fig, ax = plt.subplots(figsize=(11,4))
ax.plot(weekly_totals['WeekStart'], weekly_totals['Total'], marker='o', color='teal')
ax.set_title("Weekly Total"); ax.set_xlabel("Week"); ax.set_ylabel("Units"); ax.grid(True)
st.pyplot(fig)

st.subheader("Top Varieties")
top_varieties = weekly_variety.groupby('Variety')['EstimatedTotal'].sum().nlargest(TOP_VARIETIES_TO_PLOT).index.tolist()
variety_filter = st.selectbox("Select Variety", ["<All Top>"] + top_varieties)

if variety_filter == "<All Top>":
    cols = st.columns(2)
    for i, v in enumerate(top_varieties):
        sub = weekly_variety[weekly_variety['Variety'] == v]
        fig, ax = plt.subplots(figsize=(5.5,3))
        ax.plot(sub['WeekStart'], sub['ActualTotal'], 'o-', label='Actual')
        ax.plot(sub['WeekStart'], sub['EstimatedTotal'], 's--', label='Estimated')
        ax.set_title(v, fontsize=10); ax.legend(fontsize=8); ax.grid(True)
        with cols[i % 2]: st.pyplot(fig)
else:
    sub = weekly_variety[weekly_variety['Variety'] == variety_filter]
    fig, (ax1, ax2) = plt.subplots(2,1,figsize=(10,6), sharex=True)
    ax1.plot(sub['WeekStart'], sub['ActualTotal'], 'o-', label='Actual')
    ax1.plot(sub['WeekStart'], sub['EstimatedTotal'], 's--', label='Estimated')
    ax1.set_title(f"{variety_filter} – Production"); ax1.legend(); ax1.grid(True)
    ax2.plot(sub['WeekStart'], sub['MeanActualCoeff'], 'o-', color='green')
    ax2.set_title("Coefficient (%)"); ax2.grid(True)
    st.pyplot(fig)

st.success("Dashboard loaded successfully!")
