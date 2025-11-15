import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="Farm KPI Dashboard", layout="wide")
st.title("Farm Production Dashboard")

# ---------- Upload ----------
uploaded = st.sidebar.file_uploader(
    "Upload **Oltepesi DA Test Workbook.xlsx**", 
    type=["xlsx"], 
    help="Click to browse or drag-and-drop your Excel file"
)

# ---- STOP EARLY if no file ----
if uploaded is None:
    st.info("Please upload your Excel file to start the analysis.")
    st.stop()

# ---- Save uploaded file safely ----
temp_path = "temp_data.xlsx"
with open(temp_path, "wb") as f:
    f.write(uploaded.getbuffer())  # Safe: uploaded is not None here

df = pd.read_excel(temp_path)
df.columns = df.columns.str.strip()

# ---------- Config ----------
SICK_FACTOR = 0.06
HARVESTER_OUTPUT_PER_DAY = 100.0
WORKING_DAYS_PER_HARVESTER_PER_YEAR = 250.0
FORECAST_ROLLING_WEEKS = 4
TOP_VARIETIES_TO_PLOT = 6

# ---------- Data Prep ----------
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
        if pd.notna(val) and val != 0: return i
    return np.nan
df['Day'] = df.apply(infer_day, axis=1).astype('Int
