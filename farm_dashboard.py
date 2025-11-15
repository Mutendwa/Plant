# farm_dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ========================================
# SWAHILI CONFIG & UI
# ========================================
st.set_page_config(page_title="Dashibodi ya Uzalishaji Shambani", layout="wide")
st.title("Dashibodi ya Uzalishaji Shambani")

# ========================================
# PAKIA FAILI
# ========================================
uploaded = st.sidebar.file_uploader(
    "Pakia **Oltepesi DA Test Workbook.xlsx**",
    type=["xlsx"],
    help="Bofya au buruta faili hapa"
)

if uploaded is None:
    st.info("Tafadhali pakia faili lako la Excel ili uanze.")
    st.stop()

# Hifadhi faili
with open("temp_data.xlsx", "wb") as f:
    f.write(uploaded.getbuffer())

try:
    df = pd.read_excel("temp_data.xlsx")
except Exception as e:
    st.error(f"Hitilafu kusoma faili: {e}")
    st.stop()

df.columns = df.columns.str.strip()

# ========================================
# MIPANGILIO
# ========================================
SICK_FACTOR = 0.06
HARVESTER_OUTPUT_PER_DAY = 100.0
WORKING_DAYS_PER_HARVESTER_PER_YEAR = 250.0
FORECAST_ROLLING_WEEKS = 4
TOP_VARIETIES_TO_PLOT = 6

# ========================================
# KUSAFISHA DATA
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
df['YearWeekDay'] = (
    df['Year'].astype(str) + "_" +
    df['Week'].astype(str).str.zfill(2) + "_" +
    df['Day'].astype(str)
)

group_keys = ['Variety'] + (['ProductionNumber'] if 'ProductionNumber' in df.columns else [])
sort_by = group_keys + (['PlantDate'] if 'PlantDate' in df.columns else ['Year','Week','Day'])
df = df.sort_values(sort_by).reset_index(drop=True)
df['Nth Day'] = df.groupby(group_keys).cumcount() + 1
df['Nth Week'] = ((df['Nth Day'] - 1) // 7 + 1).astype(int)

# Hesabu
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

# Jumla ya Wiki
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

# USALAMA: Tumia 'EstimatedTotal' – sio 'EstimatedProduction'
weekly_variety['AccuracyRate_pct'] = np.where(
    weekly_variety['EstimatedTotal'].replace(0, np.nan).notna(),
    weekly_variety['ActualTotal'] / weekly_variety['EstimatedTotal'] * 100,
    np.nan
)

# ========================================
# CHATI 1: Jumla ya Wiki
# ========================================
st.subheader("1. Jumla ya Uzalishaji kwa Wiki")
weekly_totals = df.groupby('WeekStart', dropna=False)['Total'].sum().reset_index()
fig, ax = plt.subplots(figsize=(11,4))
ax.plot(weekly_totals['WeekStart'], weekly_totals['Total'], marker='o', color='teal')
ax.set_title("Jumla ya Wiki"); ax.set_xlabel("Wiki"); ax.set_ylabel("Vitengo"); ax.grid(True)
st.pyplot(fig)

# ========================================
# CHATI 2: Aina Bora
# ========================================
st.subheader("2. Aina Bora – Halisi dhidi ya Makadirio")
top_varieties = weekly_variety.groupby('Variety')['EstimatedTotal'].sum().nlargest(TOP_VARIETIES_TO_PLOT).index.tolist()
variety_filter = st.selectbox("Chagua Aina", ["<Zote Bora>"] + top_varieties)

if variety_filter == "<Zote Bora>":
    cols = st.columns(2)
    for i, v in enumerate(top_varieties):
        sub = weekly_variety[weekly_variety['Variety'] == v]
        fig, ax = plt.subplots(figsize=(5.5,3))
        ax.plot(sub['WeekStart'], sub['ActualTotal'], 'o-', label='Halisi')
        ax.plot(sub['WeekStart'], sub['EstimatedTotal'], 's--', label='Makadirio')
        ax.set_title(v, fontsize=10); ax.legend(fontsize=8); ax.grid(True)
        with cols[i % 2]:
            st.pyplot(fig)
else:
    sub = weekly_variety[weekly_variety['Variety'] == variety_filter]
    fig, (ax1, ax2) = plt.subplots(2,1,figsize=(10,6), sharex=True)
    ax1.plot(sub['WeekStart'], sub['ActualTotal'], 'o-', label='Halisi')
    ax1.plot(sub['WeekStart'], sub['EstimatedTotal'], 's--', label='Makadirio')
    ax1.set_title(f"{variety_filter} – Uzalishaji"); ax1.legend(); ax1.grid(True)
    ax2.plot(sub['WeekStart'], sub['MeanActualCoeff'], 'o-', color='green')
    ax2.set_title("Mgawo Wastani Halisi (%)"); ax2.grid(True)
    st.pyplot(fig)

# ========================================
# CHATI 3: Utabiri
# ========================================
st.subheader("3. Utabiri wa Mgawo wa Mzunguko Ujao")
forecast_rows = []
for v in weekly_variety['Variety'].dropna().unique():
    sub = weekly_variety[weekly_variety['Variety'] == v].sort_values('WeekStart')
    if sub.empty: continue
    rolling = sub['MeanActualCoeff'].rolling(window=FORECAST_ROLLING_WEEKS, min_periods=1).mean()
    forecast = rolling.iloc[-1]
    if pd.notna(forecast):
        forecast_rows.append({'Aina': v, 'Utabiri (%)': round(forecast, 1)})
forecast_df = pd.DataFrame(forecast_rows).sort_values('Utabiri (%)', ascending=False)
st.dataframe(forecast_df)
st.download_button("Pakua Utabiri", forecast_df.to_csv(index=False).encode(), "utabiri.csv", "text/csv")

# ========================================
# CHATI 4: Mahitaji ya Wafanyakazi 2026
# ========================================
st.subheader("4. Mahitaji ya Wafanyakazi 2026")
mean_week = df.groupby('WeekStart')['EstimatedProduction'].sum().mean()
est2026 = mean_week * 52 * (1 - SICK_FACTOR)
days_needed = est2026 / HARVESTER_OUTPUT_PER_DAY
harvesters = days_needed / WORKING_DAYS_PER_HARVESTER_PER_YEAR

col1, col2, col3 = st.columns(3)
col1.metric("Vitengo vya 2026", f"{est2026:,.0f}")
col2.metric("Siku za Mvunaji", f"{days_needed:,.0f}")
col3.metric("Wavunaji Wastaafu", f"{harvesters:,.1f}")

st.write("**Uchanganuzi: Patonzoa la Mvunaji kwa Siku**")
perf_opts = [50, 75, 100, 150, 200]
sens = pd.DataFrame([
    {'Patonzoa/Siku': p,
     'Siku Zinazohitajika': round(est2026/p),
     'Wavunaji': round((est2026/p)/WORKING_DAYS_PER_HARVESTER_PER_YEAR, 1)}
    for p in perf_opts
])
st.dataframe(sens)
st.download_button("Pakua Uchanganuzi", sens.to_csv(index=False).encode(), "uchanganuzi.csv", "text/csv")

# ========================================
# IMEMALIZIKA
# ========================================
st.success("Dashibodi imepakiwa kikamilifu! Tembelea juu ili uone chati zote.")
st.caption(f"Imetengenezwa kwa @Edwinmute • {pd.Timestamp.now().strftime('%d %B %Y, %I:%M %p')} EAT")
