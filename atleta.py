import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import re
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
import math

def prepara_df_visualizzazione(df_in):
    df_out = df_in.copy()
    for col in df_out.columns:
        if df_out[col].dtype == 'object':
            df_out[col] = df_out[col].apply(lambda x: "" if pd.isna(x) else str(x).strip())
    return df_out

def parse_date_eu(val):
    if pd.isna(val) or val is None:
        return pd.NaT
    if isinstance(val, (pd.Timestamp, pd.DatetimeIndex)):
        return val.normalize() if isinstance(val, pd.Timestamp) else val
    s = str(val).strip().split(' ')[0].replace('_', '-')
    if not s or s.lower() in ['nan', 'nat', 'none', '']:
        return pd.NaT
    m_iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m_iso:
        y, p1, p2 = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if p1 > 12 and p2 <= 12: # Tindeq hardware con formato invertito YYYY-DD-MM
            res = pd.to_datetime(f"{y:04d}-{p2:02d}-{p1:02d}", format='%Y-%m-%d', errors='coerce')
        else:
            res = pd.to_datetime(f"{y:04d}-{p1:02d}-{p2:02d}", format='%Y-%m-%d', errors='coerce')
        return res.normalize() if pd.notna(res) else res
    m_eu = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$', s)
    if m_eu:
        d, m, y = int(m_eu.group(1)), int(m_eu.group(2)), int(m_eu.group(3))
        if y < 100: y += 2000
        res = pd.to_datetime(f"{y:04d}-{m:02d}-{d:02d}", format='%Y-%m-%d', errors='coerce')
        return res.normalize() if pd.notna(res) else res
    res = pd.to_datetime(s, dayfirst=True, errors='coerce')
    return res.normalize() if pd.notna(res) else res

def formatta_data_breve(val):
    if val is None or pd.isna(val):
        return "N/D"
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime('%d/%m/%Y')
    s = str(val).split(' ')[0].strip()
    if s in ['N/D', 'None', 'nan', 'NaT', '']:
        return "N/D"
    m_eu = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', s)
    if m_eu:
        return f"{int(m_eu.group(1)):02d}/{int(m_eu.group(2)):02d}/{m_eu.group(3)}"
    m_iso = re.match(r'^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$', s)
    if m_iso:
        return f"{int(m_iso.group(3)):02d}/{int(m_iso.group(2)):02d}/{m_iso.group(1)}"
    dt = parse_date_eu(s)
    if pd.notna(dt):
        return dt.strftime('%d/%m/%Y')
    return s[:10]

CARTELLA_ARCHIVIO = "Archivio_CSV"

# --- CONNESSIONE CLOUD SICURA ---
@st.cache_data(ttl=43200)
def carica_dati_cloud():
    id_db = st.secrets["link_database"].split("/d/")[1].split("/")[0]
    id_cred = st.secrets["link_credenziali"].split("/d/")[1].split("/")[0]
    
    # Il parametro decimal="," aiuta con il formato italiano
    df_atleti = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{id_db}/export?format=csv", decimal=",")
    credenziali = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{id_cred}/export?format=csv")
    
    # FILTRO GLOBALE: forza tutte le metriche di test a tornare numeri (come faceva Excel)
    for col in df_atleti.columns:
        # Escludiamo solo le vere colonne di testo
        if col not in ['Data', 'DataStr', 'Atleta', 'Gruppo']:
            if df_atleti[col].dtype == 'object':
                # Sostituisce virgole sfuggite e forza a numerico (i testi non validi diventano NaN per i grafici)
                df_atleti[col] = pd.to_numeric(df_atleti[col].astype(str).str.replace(',', '.'), errors='coerce')
                
    return df_atleti, credenziali

TESTI_FISIOLOGIA = {
    "Panca": "Maximum Strength Testing (Slow Speed Strength)\nMigliorare la tua forza massima aumenta il potenziale di impulso complessivo...",
    "Squat": "Maximum Strength Testing (Slow Speed Strength)\nMigliorare la tua forza massima aumenta il potenziale di impulso complessivo...",
    "Deadlift": "Maximum Strength Testing (Slow Speed Strength)\nLa forza totale del corpo.",
    "Concentrica": "Maximum Strength Testing (Isometria)\nAl fine di eseguire i massimi livelli di lavoro muscolare, la forza deve essere portata molto lentamente.",
    "Eccentrica": "Maximum Strength Testing (Isometria)\nAl fine di eseguire i massimi livelli di lavoro muscolare, la forza deve essere portata molto lentamente...",
    "Vertical Pull 120°": "Forza di Trazione (Upper Body)\nMisuriamo la capacità di tiro e bloccaggio. L'isometria sovrastima del 10-15% il movimento dinamico.",
    "Vertical Pull 90°": "Forza di Trazione (Upper Body)\nMisuriamo la capacità di tiro e bloccaggio ad angoli articolari specifici...",
    "RFD Dita": "Rates of Force Development (High Speed Strength - Dita)\nMisura la codifica della velocità neurale e la 'forza di contatto' (la capacità di afferrare una presa dinamicamente senza farsela sfuggire).",
    "Vertical Pull RFD": "Rates of Force Development (High Speed Strength - Tirata)\nMisura la potenza esplosiva dei grandi muscoli di tirata (dorso/braccia). Fondamentale per i lanci e i movimenti balistici dinamici.",
    "Endurance 30''": "Anaerobic Capacity (30-Second Max Effort Test)\nValutiamo la capacità del sistema energetico glicolitico senza riposo.",
    "Critical Force 7:3": "Maximum Finger Repeaters (7:3x25)\nLa Critical Force rappresenta il massimo livello di forza sostenibile in uno stato di equilibrio metabolico."
}

st.set_page_config(page_title="Vetrina Atleta", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    /* 5. Sfondo Globale: Chiaro, omogeneo e neutrale ovunque */
    html, body, .stApp, .main,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewBlockContainer"],
    header[data-testid="stHeader"] {
        background-color: #f8fafc !important;
        color: #334155 !important;
        font-family: 'Inter', sans-serif;
    }

    header[data-testid="stHeader"] { display: none !important; }
    footer { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* Titoli: Rimozione di ogni sfondo per evitare effetto pezza */
    h1, h2, h3, h4, h5,
    div[data-testid="stHeadingWithActionElements"],
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] h4,
    div[data-testid="stMarkdownContainer"] h5 {
        color: #0f172a !important;
        font-weight: 700;
        margin-bottom: 0.75rem;
        background: transparent !important;
        background-color: transparent !important;
    }

    /* Design Responsivo: 1000px max su PC, fluido su Mobile */
    @media (min-width: 1024px) {
        .main .block-container {
            max-width: 1000px !important;
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            margin: 0 auto !important;
        }
    }
    @media (max-width: 1023px) {
        .main .block-container {
            max-width: 100% !important;
            padding-top: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }

    /* 1. Metriche Native (st.metric): Testi scuri e delta ad alto contrasto */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 1rem 1.25rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stMetricLabel"] * { color: #475569 !important; font-weight: bold !important; opacity: 1 !important; }
    [data-testid="stMetricValue"] * { color: #0f172a !important; }
    div[data-testid="stMetricDelta"] {
        font-weight: 700 !important;
    }
    div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]),
    div[data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Up"],
    div[data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Up"] + div {
        color: #15803d !important;
        fill: #15803d !important;
    }
    div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]),
    div[data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Down"],
    div[data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Down"] + div {
        color: #b91c1c !important;
        fill: #b91c1c !important;
    }

    /* 2. Pulsanti e Input: Sfondo bianco/chiaro, testo scuro e bordi definiti */
    .stButton > button {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    .stButton > button:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
        color: #0f172a !important;
    }
    button[kind="primary"], .stButton > button[kind="primary"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: 1px solid #1d4ed8 !important;
    }
    button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
    }

    div[data-baseweb="input"],
    div[data-baseweb="input"] > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        color: #0f172a !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 1px #2563eb !important;
    }
    input, input[type="text"], input[type="password"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-weight: 500 !important;
    }
    input::placeholder {
        color: #94a3b8 !important;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stRadio"] label {
        color: #1e293b !important;
        font-weight: 600 !important;
    }

    /* 3. Menu a tendina (Selectbox): Sfondo bianco con testo scuro (addio sfondo nero) */
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    div[data-baseweb="select"] * {
        color: #0f172a !important;
        background-color: transparent;
    }
    div[data-baseweb="select"] svg {
        fill: #475569 !important;
        color: #475569 !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    ul[data-baseweb="menu"],
    div[data-baseweb="menu"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
    }
    li[role="option"],
    div[role="option"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-weight: 500 !important;
    }
    li[role="option"]:hover,
    div[role="option"]:hover,
    li[aria-selected="true"] {
        background-color: #f1f5f9 !important;
        color: #2563eb !important;
    }

    /* 4. Tabs: Inattivi grigio scuro su sfondo chiaro, attivi blu scuro su bianco */
    .stTabs [data-baseweb="tab"] * { color: #1e293b !important; font-weight: 600 !important; opacity: 1 !important; visibility: visible !important; }
    .stTabs [aria-selected="true"] * { color: #2563eb !important; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: transparent !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding-bottom: 0px !important;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9 !important;
        border: 1px solid #cbd5e1 !important;
        border-bottom: none !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 16px !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e2e8f0 !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #ffffff !important;
        border-top: 3px solid #2563eb !important;
        border-left: 1px solid #cbd5e1 !important;
        border-right: 1px solid #cbd5e1 !important;
        border-bottom: 2px solid #ffffff !important;
        font-weight: 700 !important;
    }

    /* Box & Card Soft Slate */
    .bio-info-box { background-color: #ffffff; padding: 15px; border-left: 4px solid #3b82f6; border-radius: 6px; font-size: 0.9em; color: #475569; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .coach-tip { background-color: #f0fdf4; padding: 15px; border-left: 4px solid #16a34a; border-radius: 6px; font-size: 0.9em; color: #166534; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); line-height: 1.5; }
    .card-container { display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }

    .metric-card { 
        background: #ffffff; 
        border: 1px solid #e2e8f0; 
        padding: 1.25rem 1.5rem; 
        border-radius: 8px; 
        flex: 1; 
        min-width: 240px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
    }
    .metric-title { font-size: 0.85rem; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .metric-value { font-size: 2.2rem; color: #0f172a; font-weight: 800; line-height: 1.2; }
    .metric-unit { font-size: 1rem; color: #64748b; font-weight: 600; }
    .metric-bw { font-size: 0.95rem; color: #10b981; font-weight: 700; margin-top: 0.25rem; display: block; }
    .metric-sub { font-size: 0.95rem; color: #334155; font-weight: 500; margin-top: 0.75rem; border-top: 1px solid #e2e8f0; padding-top: 0.5rem; }

    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #0f172a !important;
    }

    /* Alert Asimmetria */
    div.stAlert { color: #333333 !important; }
    div.stAlert * { color: #333333 !important; }
    div[data-testid="stAlert"] * { color: #333333 !important; }

    /* Risoluzione definitiva overflow popup, tooltip, toast e alert su mobile */
    div[data-baseweb="tooltip"],
    div[data-baseweb="popover"],
    div[data-testid="stTooltipContent"],
    div[role="tooltip"],
    div[data-testid="stPopoverBody"] {
        max-width: calc(100vw - 32px) !important;
        width: auto !important;
        box-sizing: border-box !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
    }

    div[data-baseweb="tooltip"] *,
    div[data-baseweb="popover"] *,
    div[data-testid="stTooltipContent"] *,
    div[role="tooltip"] *,
    div[data-testid="stPopoverBody"] * {
        max-width: 100% !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
    }

    div[data-testid="stToastContainer"] {
        max-width: calc(100vw - 24px) !important;
        width: auto !important;
        left: 12px !important;
        right: 12px !important;
        box-sizing: border-box !important;
    }

    div[data-testid="stToast"],
    div[data-baseweb="toast"],
    div[data-testid="stAlert"],
    div.stAlert {
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
    }

    div[data-testid="stToast"] *,
    div[data-baseweb="toast"] *,
    div[data-testid="stAlert"] *,
    div.stAlert * {
        max-width: 100% !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def leggi_curva_csv(file_sel):
    try:
        with open(file_sel, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        start_idx = next((i for i, l in enumerate(lines) if l.lower().startswith('time,weight') or l.lower().startswith('time,force')), -1)
        if start_idx == -1:
            return None, None, "Formato CSV non valido"
        df_curva = pd.read_csv(io.StringIO("".join(lines[start_idx:])))
        col_peso = 'weight' if 'weight' in df_curva.columns else (df_curva.columns[1] if len(df_curva.columns) > 1 else None)
        if not col_peso or col_peso not in df_curva.columns:
            return None, None, "Colonna peso non trovata"
        df_curva[col_peso] = pd.to_numeric(df_curva[col_peso], errors='coerce')
        time_raw = pd.to_numeric(df_curva['time'], errors='coerce')
        if time_raw.empty or pd.isna(time_raw.iloc[0]):
            return None, None, "Colonna tempo non valida"
        if time_raw.max() > 100000:
            df_curva['time_sec'] = (time_raw - time_raw.iloc[0]) / 1_000_000
        else:
            df_curva['time_sec'] = time_raw - time_raw.iloc[0]
        return df_curva, col_peso, None
    except Exception:
        return None, None, "Dati non disponibili (N/D)"

df, credenziali = carica_dati_cloud()
if 'Data_dt' not in df.columns and 'Data' in df.columns:
    df['Data_dt'] = df['Data'].apply(parse_date_eu)

atleti_lista = sorted(df['Atleta'].dropna().unique().tolist()) if 'Atleta' in df.columns else []

def calcola_macro_kpi_storici(df_atleta_in):
    """
    Calcola l'ultimo valore valido e il delta (differenza in kg) rispetto alla
    penultima seduta valida per le 4 macro-categorie biomeccaniche.
    """
    df_sort = df_atleta_in.sort_values(by='Data_dt').copy() if 'Data_dt' in df_atleta_in.columns else df_atleta_in.copy()
    
    # 1. Trazione 1RM (Pull-Up 1RM Calcolata o Reale)
    serie_1rm = []
    for _, row in df_sort.iterrows():
        v = None
        for col in ['Pull-Up 1RM Calcolata', 'Pull-Up 1RM Reale']:
            if col in row and pd.notna(row[col]):
                num = pd.to_numeric(str(row[col]).replace(',', '.'), errors='coerce')
                if pd.notna(num) and num > 0:
                    v = float(num)
                    break
        if v is not None:
            serie_1rm.append((v, formatta_data_breve(row.get('Data', ''))))
            
    val_1rm, delta_1rm, dt_1rm = None, None, None
    if serie_1rm:
        val_1rm, dt_1rm = serie_1rm[-1]
        if len(serie_1rm) > 1:
            delta_1rm = val_1rm - serie_1rm[-2][0]

    # 2. Forza Dita Concentrica (max DX/SX per seduta valida)
    serie_conc = []
    for _, row in df_sort.iterrows():
        v_dx = pd.to_numeric(str(row.get('Concentrica DX', '')).replace(',', '.'), errors='coerce')
        v_sx = pd.to_numeric(str(row.get('Concentrica SX', '')).replace(',', '.'), errors='coerce')
        ndx = float(v_dx) if pd.notna(v_dx) and v_dx > 0 else 0.0
        nsx = float(v_sx) if pd.notna(v_sx) and v_sx > 0 else 0.0
        if ndx > 0 or nsx > 0:
            m = max(ndx, nsx)
            lato = "DX" if ndx >= nsx else "SX"
            serie_conc.append((m, lato, formatta_data_breve(row.get('Data', ''))))
            
    val_conc, delta_conc, lato_conc, dt_conc = None, None, "", None
    if serie_conc:
        val_conc, lato_conc, dt_conc = serie_conc[-1]
        if len(serie_conc) > 1:
            delta_conc = val_conc - serie_conc[-2][0]

    # 3. Forza Dita Eccentrica (max DX/SX per seduta valida)
    serie_ecc = []
    for _, row in df_sort.iterrows():
        v_dx = pd.to_numeric(str(row.get('Eccentrica DX', '')).replace(',', '.'), errors='coerce')
        v_sx = pd.to_numeric(str(row.get('Eccentrica SX', '')).replace(',', '.'), errors='coerce')
        ndx = float(v_dx) if pd.notna(v_dx) and v_dx > 0 else 0.0
        nsx = float(v_sx) if pd.notna(v_sx) and v_sx > 0 else 0.0
        if ndx > 0 or nsx > 0:
            m = max(ndx, nsx)
            lato = "DX" if ndx >= nsx else "SX"
            serie_ecc.append((m, lato, formatta_data_breve(row.get('Data', ''))))
            
    val_ecc, delta_ecc, lato_ecc, dt_ecc = None, None, "", None
    if serie_ecc:
        val_ecc, lato_ecc, dt_ecc = serie_ecc[-1]
        if len(serie_ecc) > 1:
            delta_ecc = val_ecc - serie_ecc[-2][0]

    # 4. Endurance 30s (Media o Picco per seduta valida)
    serie_end = []
    for _, row in df_sort.iterrows():
        v_dx = pd.to_numeric(str(row.get("Endurance 30'' DX - Forza Media", '')).replace(',', '.'), errors='coerce')
        v_sx = pd.to_numeric(str(row.get("Endurance 30'' SX - Forza Media", '')).replace(',', '.'), errors='coerce')
        if not (pd.notna(v_dx) and v_dx > 0) and not (pd.notna(v_sx) and v_sx > 0):
            v_dx = pd.to_numeric(str(row.get("Endurance 30'' DX - Picco Max", row.get("Endurance 30'' DX", ''))).replace(',', '.'), errors='coerce')
            v_sx = pd.to_numeric(str(row.get("Endurance 30'' SX - Picco Max", row.get("Endurance 30'' SX", ''))).replace(',', '.'), errors='coerce')
        ndx = float(v_dx) if pd.notna(v_dx) and v_dx > 0 else 0.0
        nsx = float(v_sx) if pd.notna(v_sx) and v_sx > 0 else 0.0
        if ndx > 0 or nsx > 0:
            m = max(ndx, nsx)
            lato = "DX" if ndx >= nsx else "SX"
            serie_end.append((m, lato, formatta_data_breve(row.get('Data', ''))))
            
    val_end, delta_end, lato_end, dt_end = None, None, "", None
    if serie_end:
        val_end, lato_end, dt_end = serie_end[-1]
        if len(serie_end) > 1:
            delta_end = val_end - serie_end[-2][0]

    return {
        "1rm": (val_1rm, delta_1rm, dt_1rm),
        "conc": (val_conc, delta_conc, lato_conc, dt_conc),
        "ecc": (val_ecc, delta_ecc, lato_ecc, dt_ecc),
        "end": (val_end, delta_end, lato_end, dt_end)
    }

# ---------------- FUNZIONE DOSSIER AI ----------------
def genera_dossier_ai(df_master, atleta_nome):
    df_atleta = df_master[df_master['Atleta'] == atleta_nome].copy()
    if df_atleta.empty:
        return f"⚠️ Nessun dato disponibile per l'atleta {atleta_nome}."

    if 'Data' in df_atleta.columns:
        df_atleta['Data_dt'] = df_atleta['Data'].apply(parse_date_eu)
        df_atleta = df_atleta.sort_values(by='Data_dt')

    # Helper per estrarre l'ultimo valore valido (>0) cronologico e la relativa data
    def get_latest_val_and_date(col_names):
        if isinstance(col_names, str):
            col_names = [col_names]
        cols_exist = [c for c in col_names if c in df_atleta.columns]
        if not cols_exist:
            return None, None
        df_num = df_atleta[cols_exist].apply(lambda c: pd.to_numeric(c.astype(str).str.replace(',', '.'), errors='coerce'))
        max_per_riga = df_num.max(axis=1)
        valide = df_atleta[max_per_riga > 0]
        if not valide.empty:
            r = valide.dropna(subset=['Data']).iloc[-1]
            v = float(max_per_riga.loc[r.name])
            raw_d = r.get('Data')
            if pd.isna(raw_d) or raw_d is None:
                raw_d = r.get('DataStr')
            return v, formatta_data_breve(raw_d)
        return None, None

    # 1. Dati Antropometrici
    peso, dt_peso = get_latest_val_and_date('Peso Corporeo')
    if not peso or peso <= 0:
        return f"⚠️ Dati insufficienti per {atleta_nome}: è necessario registrare almeno una volta il Peso Corporeo dell'atleta per calcolare le metriche biomeccaniche."

    df_con_data = df_atleta.dropna(subset=['Data'])
    data_ultimo_test = formatta_data_breve(df_con_data.iloc[-1]['Data']) if not df_con_data.empty else "N/D"

    md = f"# 📋 FASCICOLO CLINICO & BIOMECCANICO ATLETA: {atleta_nome.upper()}\n\n"
    
    # 1. Dati Antropometrici
    md += "### 1. DATI ANTROPOMETRICI & RIFERIMENTO\n"
    md += f"- **Nome Atleta:** {atleta_nome}\n"
    md += f"- **Data Ultimo Test Registrato:** {data_ultimo_test}\n"
    md += f"- **Peso Corporeo Attuale:** {peso:.1f} kg (rilevato il {dt_peso or data_ultimo_test})\n\n"

    # 2. Trazione 1RM e Forza Dita (% BW)
    md += "### 2. TRAZIONE 1RM E FORZA DITA (% BW & KG)\n"
    
    # Trazione 1RM
    v_traz, dt_traz = get_latest_val_and_date(['Pull-Up 1RM Calcolata', 'Pull-Up 1RM Reale'])
    if v_traz is not None and v_traz > 0:
        perc_traz = (v_traz / peso) * 100
        carico_tot = peso + v_traz
        perc_tot = (carico_tot / peso) * 100
        md += f"- **Trazione Pull-Up 1RM:** Zavorra {v_traz:.1f} kg (**{perc_traz:.1f}% BW**) | **Carico Totale:** {carico_tot:.1f} kg (**{perc_tot:.1f}% BW**) [test: {dt_traz}]\n"
    else:
        md += "- **Trazione Pull-Up 1RM:** N/D\n"

    # Isometria Vertical Pull (se presente)
    v_vp_dx, _ = get_latest_val_and_date('Vertical Pull 120° DX')
    v_vp_sx, _ = get_latest_val_and_date('Vertical Pull 120° SX')
    if (v_vp_dx and v_vp_dx > 0) or (v_vp_sx and v_vp_sx > 0):
        vp_dx_str = f"{v_vp_dx:.1f} kg ({(v_vp_dx/peso)*100:.1f}% BW)" if v_vp_dx else "N/D"
        vp_sx_str = f"{v_vp_sx:.1f} kg ({(v_vp_sx/peso)*100:.1f}% BW)" if v_vp_sx else "N/D"
        md += f"- **Isometria Trazione 120°:** DX: {vp_dx_str} | SX: {vp_sx_str}\n"

    # Concentrica Dita
    v_c_dx, dt_c_dx = get_latest_val_and_date('Concentrica DX')
    v_c_sx, dt_c_sx = get_latest_val_and_date('Concentrica SX')
    max_c = max(v_c_dx or 0.0, v_c_sx or 0.0)
    if max_c > 0:
        c_dx_str = f"{v_c_dx:.1f} kg ({(v_c_dx/peso)*100:.1f}% BW)" if v_c_dx else "N/D"
        c_sx_str = f"{v_c_sx:.1f} kg ({(v_c_sx/peso)*100:.1f}% BW)" if v_c_sx else "N/D"
        md += f"- **Dita Concentrica (Attiva):** DX: {c_dx_str} | SX: {c_sx_str} — **Max:** {max_c:.1f} kg (**{(max_c/peso)*100:.1f}% BW**) [test: {dt_c_dx or dt_c_sx}]\n"
    else:
        md += "- **Dita Concentrica (Attiva):** N/D\n"

    # Eccentrica Dita
    v_e_dx, dt_e_dx = get_latest_val_and_date('Eccentrica DX')
    v_e_sx, dt_e_sx = get_latest_val_and_date('Eccentrica SX')
    max_e = max(v_e_dx or 0.0, v_e_sx or 0.0)
    if max_e > 0:
        e_dx_str = f"{v_e_dx:.1f} kg ({(v_e_dx/peso)*100:.1f}% BW)" if v_e_dx else "N/D"
        e_sx_str = f"{v_e_sx:.1f} kg ({(v_e_sx/peso)*100:.1f}% BW)" if v_e_sx else "N/D"
        md += f"- **Dita Eccentrica (Passiva):** DX: {e_dx_str} | SX: {e_sx_str} — **Max:** {max_e:.1f} kg (**{(max_e/peso)*100:.1f}% BW**) [test: {dt_e_dx or dt_e_sx}]\n"
    else:
        md += "- **Dita Eccentrica (Passiva):** N/D\n"

    # Dita Stese (se presente)
    v_st_dx, _ = get_latest_val_and_date('Stese DX')
    v_st_sx, _ = get_latest_val_and_date('Stese SX')
    max_st = max(v_st_dx or 0.0, v_st_sx or 0.0)
    if max_st > 0:
        st_dx_str = f"{v_st_dx:.1f} kg ({(v_st_dx/peso)*100:.1f}% BW)" if v_st_dx else "N/D"
        st_sx_str = f"{v_st_sx:.1f} kg ({(v_st_sx/peso)*100:.1f}% BW)" if v_st_sx else "N/D"
        md += f"- **Dita Stese (Open Hand):** DX: {st_dx_str} | SX: {st_sx_str} — **Max:** {max_st:.1f} kg (**{(max_st/peso)*100:.1f}% BW**)\n"

    # Profilo Metabolico (Endurance 30s & Critical Force)
    cols_end_media = [c for c in df_atleta.columns if "endurance 30''" in c.lower() and "forza media" in c.lower()]
    if not cols_end_media:
        cols_end_media = [c for c in df_atleta.columns if "endurance" in c.lower() and "30" in c.lower()]
    v_end, dt_end = get_latest_val_and_date(cols_end_media)
    if v_end and v_end > 0:
        md += f"- **Endurance 30s (Forza Media):** {v_end:.1f} kg (**{(v_end/peso)*100:.1f}% BW**) [test: {dt_end}]\n"

    v_cf, dt_cf = get_latest_val_and_date([c for c in df_atleta.columns if "critical force" in c.lower()])
    if v_cf and v_cf > 0:
        md += f"- **Critical Force 7:3:** {v_cf:.1f} kg (**{(v_cf/peso)*100:.1f}% BW**) [test: {dt_cf}]\n"

    v_rfd, dt_rfd = get_latest_val_and_date([c for c in df_atleta.columns if "rfd" in c.lower() and not "pull" in c.lower()])
    if v_rfd and v_rfd > 0:
        md += f"- **RFD / Contact Strength Dita:** {v_rfd:.1f} kg/s [test: {dt_rfd}]\n"

    md += "\n"

    # 3. Alert Asimmetrie (Bandiera Rossa > 15%)
    md += "### 3. VALUTAZIONE ASIMMETRIE LATERALI (DX vs SX)\n"

    # Asimmetria Concentrica
    if (v_c_dx and v_c_dx > 0) and (v_c_sx and v_c_sx > 0):
        gap_c = (abs(v_c_dx - v_c_sx) / max(v_c_dx, v_c_sx)) * 100
        lato_deb_c = 'DX' if v_c_dx < v_c_sx else ('SX' if v_c_sx < v_c_dx else 'Nessuno')
        if gap_c > 15.0:
            md += f"- 🚨 **ALERT CLINICO: Asimmetria DX/SX > 15%** (Dita Concentrica: **{gap_c:.1f}%**, lato debole: **{lato_deb_c}** — DX {v_c_dx:.1f} kg vs SX {v_c_sx:.1f} kg)\n"
        else:
            md += f"- ✅ **Dita Concentrica:** Gap {gap_c:.1f}% (fisiologico <= 15%, lato debole: {lato_deb_c})\n"
    else:
        md += "- **Dita Concentrica:** Dati bilaterali non completi per il calcolo asimmetria.\n"

    # Asimmetria Eccentrica
    if (v_e_dx and v_e_dx > 0) and (v_e_sx and v_e_sx > 0):
        gap_e = (abs(v_e_dx - v_e_sx) / max(v_e_dx, v_e_sx)) * 100
        lato_deb_e = 'DX' if v_e_dx < v_e_sx else ('SX' if v_e_sx < v_e_dx else 'Nessuno')
        if gap_e > 15.0:
            md += f"- 🚨 **ALERT CLINICO: Asimmetria DX/SX > 15%** (Dita Eccentrica: **{gap_e:.1f}%**, lato debole: **{lato_deb_e}** — DX {v_e_dx:.1f} kg vs SX {v_e_sx:.1f} kg)\n"
        else:
            md += f"- ✅ **Dita Eccentrica:** Gap {gap_e:.1f}% (fisiologico <= 15%, lato debole: {lato_deb_e})\n"
    else:
        md += "- **Dita Eccentrica:** Dati bilaterali non completi per il calcolo asimmetria.\n"

    # Asimmetria Trazione (se presente)
    if (v_vp_dx and v_vp_dx > 0) and (v_vp_sx and v_vp_sx > 0):
        gap_vp = (abs(v_vp_dx - v_vp_sx) / max(v_vp_dx, v_vp_sx)) * 100
        lato_deb_vp = 'DX' if v_vp_dx < v_vp_sx else ('SX' if v_vp_sx < v_vp_dx else 'Nessuno')
        if gap_vp > 15.0:
            md += f"- 🚨 **ALERT CLINICO: Asimmetria DX/SX > 15%** (Trazione 120°: **{gap_vp:.1f}%**, lato debole: **{lato_deb_vp}**)\n"
        else:
            md += f"- ✅ **Trazione 120°:** Gap {gap_vp:.1f}% (fisiologico <= 15%)\n"

    md += "\n"

    # 4. Check Strutturale (Pulegge)
    md += "### 4. CHECK STRUTTURALE (INTEGRITÀ TESSUTI CONNETTIVI & PULEGGE)\n"
    if max_c > 0 and max_e > 0:
        ratio_pe = (max_c / max_e) * 100
        if max_c >= (max_e * 0.95):
            md += f"- 🚨 **BANDIERA ROSSA: Concentrica supera o eguaglia l'Eccentrica (Rischio Pulegge)**\n"
            md += f"  - **Rapporto Attivo/Passivo (Conc/Ecc):** **{ratio_pe:.1f}%** (Soglia limite di sicurezza fisiologica: < 95%)\n"
            md += f"  - **Dettaglio:** Concentrica Max {max_c:.1f} kg ({(max_c/peso)*100:.1f}% BW) vs Eccentrica Max {max_e:.1f} kg ({(max_e/peso)*100:.1f}% BW).\n"
            md += f"  - **Indicazione Clinica:** La forza attiva contrattile eccede la tolleranza passiva dei connettivi. Rischio critico di lesione a pulegge (A2/A4) e tendini. Evitare carichi massimali dinamici ed inserire isometrie yielding/eccentriche protettive.\n"
        else:
            md += f"- ✅ **Tolleranza Strutturale Passiva Ottimale**\n"
            md += f"  - **Rapporto Attivo/Passivo (Conc/Ecc):** **{ratio_pe:.1f}%** (fisiologico e sicuro < 95%)\n"
            md += f"  - **Dettaglio:** Concentrica Max {max_c:.1f} kg vs Eccentrica Max {max_e:.1f} kg (margine di sicurezza protettivo: {max_e - max_c:.1f} kg).\n"
    else:
        md += "- ℹ️ Dati di Concentrica ed Eccentrica insufficienti nello storico per il calcolo del ratio di sicurezza tendinea.\n"

    md += "\n"

    # 5. Esercizi Accessori
    md += "### 5. ESERCIZI ACCESSORI & TEST GENERALI (ULTIMI CARICHI REGISTRATI)\n"
    v_deadlift, dt_deadlift = get_latest_val_and_date(['Deadlift', 'Stacco'])
    v_pushup, dt_pushup = get_latest_val_and_date(['Push-up MAX rep', 'Push-up', 'Push up MAX', 'Push-up MAX'])
    v_panca, dt_panca = get_latest_val_and_date(['Panca', 'Bench Press'])

    # Deadlift
    if v_deadlift is not None and v_deadlift > 0:
        md += f"- **Deadlift (Stacco da terra):** {v_deadlift:.1f} kg (**{(v_deadlift/peso)*100:.1f}% BW**) [rilevato: {dt_deadlift}]\n"
    else:
        md += "- **Deadlift (Stacco da terra):** Nessun carico registrato\n"

    # Push-up MAX rep
    if v_pushup is not None and v_pushup > 0:
        md += f"- **Push-up MAX rep:** {int(v_pushup)} ripetizioni [rilevato: {dt_pushup}]\n"
    else:
        md += "- **Push-up MAX rep:** Nessun test registrato\n"

    # Panca
    if v_panca is not None and v_panca > 0:
        md += f"- **Panca (Bench Press):** {v_panca:.1f} kg (**{(v_panca/peso)*100:.1f}% BW**) [rilevato: {dt_panca}]\n"
    else:
        md += "- **Panca (Bench Press):** Nessun carico registrato\n"

    # Altri accessori se registrati (Squat)
    v_squat, dt_squat = get_latest_val_and_date('Squat')
    if v_squat and v_squat > 0:
        md += f"- **Squat:** {v_squat:.1f} kg ({(v_squat/peso)*100:.1f}% BW) [rilevato: {dt_squat}]\n"

    md += "\n---\n"
    md += "**DIRETTIVA PER IL COACH AI:** Utilizza questi dati per calcolare i carichi target del prossimo mesociclo di arrampicata sportiva/bouldering. Se è presente un ALERT CLINICO (> 15% asimmetria), imposta un blocco correttivo unilaterale sul lato debole. Se è presente una BANDIERA ROSSA (Rapporto Concentrica/Eccentrica >= 95%), riduci l'intensità dinamica e inserisci protocolli yielding/isometrie protettive per le pulegge."
    
    return md

# ==============================================================================
# 1. GATEKEEPER: LOGIN DINAMICO DA CREDENZIALI CLOUD & PRIVACY ATLETA
# ==============================================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.ruolo = None
    st.session_state.nome_utente = None
    st.session_state.nome_atleta_esatto = None

if not st.session_state.logged_in:
    df_credenziali = credenziali.copy()
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        col_log_l, col_log_c, col_log_r = st.columns([1, 1.5, 1])
        with col_log_c:
            st.image("logo_asd.png", width=150)
        st.markdown("<div style='text-align: center; margin-top: 0.5rem; margin-bottom: 1.5rem;'>", unsafe_allow_html=True)
        st.title("Vetrina Atleta")
        st.caption("Piattaforma di consultazione dati personali Tindeq")
        st.markdown("</div>", unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            st.markdown("#### Accesso Riservato")
            user_input = st.text_input("Username:", placeholder="Inserisci il tuo username").strip()
            pass_input = st.text_input("Password:", type="password", placeholder="Inserisci la password").strip()
            btn_accedi = st.form_submit_button("Accedi alla Vetrina", type="primary", use_container_width=True)
            
            if btn_accedi:
                match_riga = None
                for _, row in df_credenziali.iterrows():
                    u_csv = str(row['username']).strip()
                    p_csv = str(row['password']).strip()
                    if u_csv.lower() == user_input.lower() and p_csv == pass_input:
                        match_riga = row
                        break
                        
                if match_riga is not None:
                    atleta_target = str(match_riga['nome_atleta_esatto']).strip()
                    u_clean = str(match_riga['username']).strip()
                    st.session_state.logged_in = True
                    st.session_state.nome_atleta_esatto = atleta_target
                    if u_clean.lower() == "admin" or atleta_target.upper() == "TUTTI":
                        st.session_state.ruolo = "Admin"
                        st.session_state.nome_utente = u_clean
                    else:
                        st.session_state.ruolo = "Atleta"
                        st.session_state.nome_utente = atleta_target
                    st.rerun()
                else:
                    st.error("Credenziali non corrette. Riprova.")
        st.stop()

# ==============================================================================
# 2. INTESTAZIONE & VINCOLO SESSIONE ATLETA (Sola Lettura)
# ==============================================================================
col_top_h, col_top_out = st.columns([3, 1])
with col_top_h:
    if st.session_state.ruolo == "Admin" or str(st.session_state.nome_atleta_esatto).upper() == "TUTTI":
        col_logo, col_titolo = st.columns([1, 8], vertical_alignment="center")
        with col_logo:
            st.image("logo_asd.png", width=80)
        with col_titolo:
            st.title("Vetrina Atleta — Vista Admin")
        col_sel_at, col_sz = st.columns([2, 1])
        with col_sel_at:
            mostra_inattivi = st.checkbox("Mostra anche atleti inattivi (> 2 anni)", value=False, key="atleta_mostra_inattivi")
            lista_atleti_sel = atleti_lista
            if not mostra_inattivi and 'Data_dt' in df.columns and 'Atleta' in df.columns:
                soglia_attivi = pd.Timestamp.now() - pd.DateOffset(years=2)
                ultimi_test = df.groupby('Atleta')['Data_dt'].max()
                atleti_attivi = set(ultimi_test[ultimi_test >= soglia_attivi].index)
                lista_filtrata = [a for a in atleti_lista if a in atleti_attivi]
                if lista_filtrata:
                    lista_atleti_sel = lista_filtrata
            atleta_selezionato = st.selectbox("Seleziona Profilo Atleta:", lista_atleti_sel, key="sel_coach_atleta")
        with col_sz:
            dim_grafico = st.radio("Dimensione Grafici:", ["Compatta (Piccola)", "Standard (Grande)"], horizontal=True, key="sel_dim_grafico")
    else:
        atleta_selezionato = st.session_state.nome_atleta_esatto
        col_logo, col_titolo = st.columns([1, 8], vertical_alignment="center")
        with col_logo:
            st.image("logo_asd.png", width=80)
        with col_titolo:
            st.title(f"Vetrina Atleta — {atleta_selezionato}")
        dim_grafico = "Standard (Grande)"

with col_top_out:
    st.write("")
    st.caption(f"**{st.session_state.nome_utente}** ({st.session_state.ruolo})")
    col_btn_sync, col_btn_logout = st.columns([1, 1])
    with col_btn_sync:
        if st.button("Sincronizza Dati", key="btn_sync_top", use_container_width=True, help="Ricarica i dati aggiornati dal Cloud Google Sheets"):
            st.cache_data.clear()
            st.rerun()
    with col_btn_logout:
        if st.button("Esci", key="btn_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.ruolo = None
            st.session_state.nome_utente = None
            st.session_state.nome_atleta_esatto = None
            st.rerun()

fig_size = (10, 4) if dim_grafico == "Standard (Grande)" else (8, 2.5)
df_atleta = df[df['Atleta'] == atleta_selezionato].copy()
if 'Data' in df_atleta.columns:
    df_atleta['Data'] = pd.to_datetime(df_atleta['Data'].apply(parse_date_eu), errors='coerce').dt.normalize()
    df_atleta = df_atleta.dropna(subset=['Data']).sort_values(by='Data').copy()
    df_atleta['Data_dt'] = df_atleta['Data']

# --- FUNZIONI DI ORDINAMENTO CRONOLOGICO MENÙ ---
def estrai_data_per_ordinamento(chiave_tendina):
    match = re.search(r'\[(\d{2}/\d{2}/\d{4})\]', chiave_tendina)
    if match:
        try: return datetime.strptime(match.group(1), "%d/%m/%Y")
        except: pass
    return datetime.min

# --- FUNZIONI DI SUPPORTO ARCHIVIO ---
def estrai_lato(nome_file_pulito):
    if 'dx' in nome_file_pulito: return "DX"
    if 'sx' in nome_file_pulito: return "SX"
    return "Lato Sconosciuto"

def individua_colonna_db(percorso):
    nome_file = os.path.basename(percorso).lower()
    nome_file_pulito = nome_file.replace("endurance_test_", "").replace("rfd_test_", "").replace("cf_test_", "").replace("data_set_", "")
    percorso_lower = percorso.lower()
    parti_percorso = percorso_lower.replace('\\', '/').split('/')
    lato = estrai_lato(nome_file_pulito)
    lato_suff = f" {lato}" if lato != "Lato Sconosciuto" else " (Lato Sconosciuto)"
    
    if '7-3x25' in parti_percorso: return f"Dita - Critical Force 7:3 {lato}" if lato != "Lato Sconosciuto" else "Dita - Critical Force 7:3"
    if '30s' in parti_percorso: return f"Endurance 30''{lato_suff} - Picco Max"
    if 'fingers' in parti_percorso:
        if 'conc' in nome_file_pulito: return f"Dita - Concentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Concentrica"
        if 'ecc' in nome_file_pulito: return f"Dita - Eccentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Eccentrica"
        return f"Dita - Stese {lato}" if lato != "Lato Sconosciuto" else "Dita - Stese"
    
    in_cartella_endurance = 'endurance' in parti_percorso
    in_cartella_peak = 'peak' in parti_percorso
    in_cartella_rfd = 'rfd' in parti_percorso
    
    if in_cartella_endurance:
        if 'cf' in nome_file_pulito or '73' in nome_file_pulito or '7-3' in nome_file_pulito or '7 3' in nome_file_pulito:
            return f"Dita - Critical Force 7:3 {lato}" if lato != "Lato Sconosciuto" else "Dita - Critical Force 7:3"
        return f"Endurance 30''{lato_suff} - Picco Max"
            
    if in_cartella_rfd:
        if 'vertical' in nome_file_pulito or 'pull' in nome_file_pulito or '120' in nome_file_pulito or '90' in nome_file_pulito: return f"Vertical Pull RFD {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull RFD (Sconosciuto)"
        return f"RFD Dita {lato}" if lato != "Lato Sconosciuto" else "RFD Dita (Sconosciuto)"
            
    if in_cartella_peak:
        if 'conc' in nome_file_pulito: return f"Dita - Concentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Concentrica"
        if 'ecc' in nome_file_pulito: return f"Dita - Eccentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Eccentrica"
        if 'stese' in nome_file_pulito: return f"Dita - Stese {lato}" if lato != "Lato Sconosciuto" else "Dita - Stese"
        if '120' in nome_file_pulito or 'vertical' in nome_file_pulito or 'pull' in nome_file_pulito: return f"Vertical Pull 120° {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull 120° (Sconosciuto)"
        if '90' in nome_file_pulito: return f"Vertical Pull 90° {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull 90° (Sconosciuto)"
        return "Test Sconosciuto"

    if 'cf' in nome_file_pulito or '73' in nome_file_pulito or '7-3' in nome_file_pulito or '7 3' in nome_file_pulito:
        return f"Dita - Critical Force 7:3 {lato}" if lato != "Lato Sconosciuto" else "Dita - Critical Force 7:3"
    if any(x in nome_file_pulito for x in ['endurance', '30s', '30 sec', '30dx', '30sx', '30 dx', '30 sx']): return f"Endurance 30''{lato_suff} - Picco Max"
    if 'rfd' in nome_file_pulito:
        if 'vertical' in nome_file_pulito or 'pull' in nome_file_pulito or '120' in nome_file_pulito or '90' in nome_file_pulito: return f"Vertical Pull RFD {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull RFD (Sconosciuto)"
        return f"RFD Dita {lato}" if lato != "Lato Sconosciuto" else "RFD Dita (Sconosciuto)"
    if 'conc' in nome_file_pulito: return f"Dita - Concentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Concentrica"
    if 'ecc' in nome_file_pulito: return f"Dita - Eccentrica {lato}" if lato != "Lato Sconosciuto" else "Dita - Eccentrica"
    if 'stese' in nome_file_pulito: return f"Dita - Stese {lato}" if lato != "Lato Sconosciuto" else "Dita - Stese"
    if '120' in nome_file_pulito or 'vertical' in nome_file_pulito or 'pull' in nome_file_pulito: return f"Vertical Pull 120° {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull 120° (Sconosciuto)"
    if '90' in nome_file_pulito: return f"Vertical Pull 90° {lato}" if lato != "Lato Sconosciuto" else "Vertical Pull 90° (Sconosciuto)"
    
    return "Test Sconosciuto"

def calcola_record_assoluto(colonna_base, df_target=None):
    df_src = df_target if df_target is not None else df_atleta
    test_manuali_esatti = ['Panca', 'Squat', 'Deadlift', 'Push-up MAX rep', "Sit-up in 30''", 'Planck palla medica sec.', 'Box Jump', 'Squat contro parete']
    if colonna_base in test_manuali_esatti:
        cols = [c for c in df_src.columns if c == colonna_base]
    else:
        cols = [c for c in df_src.columns if colonna_base in c and 'Media' not in c]
        
    val_max = 0; info = {"valore": 0, "lato": "", "data": "", "bw": 0}
    for c in cols:
        df_temp = df_src.dropna(subset=[c])
        if not df_temp.empty:
            for idx, row in df_temp.iterrows():
                val = pd.to_numeric(str(row[c]).replace(',', '.'), errors='coerce')
                if pd.notna(val) and val > val_max:
                    val_max = val
                    peso = row['Peso Corporeo'] if 'Peso Corporeo' in row and pd.notna(row['Peso Corporeo']) else 0
                    if (pd.isna(peso) or peso == 0) and 'Peso Corporeo' in df_src.columns:
                        pesi_validi = pd.to_numeric(df_src['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce').dropna()
                        peso = pesi_validi.iloc[-1] if not pesi_validi.empty else 0
                    info = {"valore": val, "lato": c.split(' ')[-1] if 'DX' in c or 'SX' in c else "Assoluto", "data": row['Data'], "bw": peso}
    return info

def render_card(titolo, info, unit="kg"):
    if info["valore"] > 0:
        html = f'<div class="metric-card"><div class="metric-title">{titolo}</div>'
        html += f'<div class="metric-value">{info["valore"]:.1f} <span class="metric-unit">{unit}</span></div>'
        
        # Conversione sicura per evitare TypeError se 'bw' è una stringa o vuoto
        bw_val = pd.to_numeric(info["bw"], errors='coerce')
        if pd.notna(bw_val) and bw_val > 0 and unit == "kg":
            perc = (info["valore"] / bw_val) * 100
            html += f'<span class="metric-bw">{perc:.1f}% BW</span>'
            
        html += f'<div class="metric-sub">Lato: {info["lato"]} | Data: <b>{info["data"]}</b></div></div>'
        return html
    return None

tab1, tab4, tab5 = st.tabs(["Record & Best", "Storico Analitico", "Analisi Avanzata"])

with tab1:

    # ==============================================================================
    # SPIDER CHART BIOMECCANICO RADIALE (% BODYWEIGHT)
    # ==============================================================================
    st.markdown("### Profilo Biomeccanico — Forza Massima & Metabolismo")

    peso_kpi = None
    if 'Peso Corporeo' in df_atleta.columns:
        p_validi = pd.to_numeric(df_atleta['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce').dropna()
        if not p_validi.empty:
            peso_kpi = float(p_validi.iloc[-1])

    if not peso_kpi or peso_kpi <= 0:
        st.warning("Peso corporeo non disponibile: registra il peso corporeo dell'atleta per visualizzare lo Spider Chart del profilo biomeccanico (% BW).")
    else:
        # Helper per estrarre l'ultimo valore valido (>0) in ordine cronologico e la rispettiva DataStr
        def estrai_ultimo_test_valido(colonne):
            cols_exist = [c for c in colonne if c in df_atleta.columns]
            if not cols_exist:
                return 0.0, None
            df_num = df_atleta[cols_exist].apply(lambda col: pd.to_numeric(col.astype(str).str.replace(',', '.'), errors='coerce'))
            max_per_riga = df_num.max(axis=1)
            valide = df_atleta[max_per_riga > 0]
            if not valide.empty:
                r = valide.dropna(subset=['Data']).iloc[-1]
                v = float(max_per_riga.loc[r.name])
                raw_dt = r.get('Data')
                if pd.isna(raw_dt) or raw_dt is None:
                    raw_dt = r.get('DataStr')
                dt = formatta_data_breve(raw_dt)
                return v, dt
            return 0.0, None

        ottieni_ultimo_valore = lambda df, cols: estrai_ultimo_test_valido(cols)

        # 1. Dita Concentrica (picco max tra DX e SX)
        val_conc, data_conc = estrai_ultimo_test_valido(['Concentrica DX', 'Concentrica SX'])

        # 2. Dita Eccentrica (picco max tra DX e SX)
        val_ecc, data_ecc = estrai_ultimo_test_valido(['Eccentrica DX', 'Eccentrica SX'])

        # 3. Dita Stese (picco max tra DX e SX)
        stese_picco, d_stese = ottieni_ultimo_valore(df_atleta, ['Stese DX', 'Stese SX'])

        # 4. Endurance 30s (Forza Media tra DX e SX)
        cols_end_media = [c for c in df_atleta.columns if "endurance 30''" in c.lower() and "forza media" in c.lower()]
        if not cols_end_media:
            cols_end_media = [c for c in df_atleta.columns if "endurance" in c.lower() and "30" in c.lower() and "media" in c.lower()]
        if not cols_end_media:
            cols_end_media = ["Endurance 30'' DX - Forza Media", "Endurance 30'' SX - Forza Media"]
        val_end, data_end = estrai_ultimo_test_valido(cols_end_media)
        if val_end <= 0:
            cols_end_backup = [c for c in df_atleta.columns if "endurance 30''" in c.lower() and "picco" in c.lower()]
            if cols_end_backup:
                val_end, data_end = estrai_ultimo_test_valido(cols_end_backup)

        # 5. Critical Force 7:3 (picco max tra DX e SX)
        cols_cf = [c for c in df_atleta.columns if "critical force" in c.lower()]
        val_cf, data_cf = estrai_ultimo_test_valido(cols_cf)

        # 6. Trazione 1RM (Pull-Up 1RM Calcolata o Reale)
        val_trazione, data_trazione = estrai_ultimo_test_valido(['Pull-Up 1RM Calcolata', 'Pull-Up 1RM Reale'])

        # Conversione in Forza Relativa (% Bodyweight) con l'ultimo peso noto
        categorie = ['Dita Concentrica', 'Dita Eccentrica', 'Dita Stese', 'Endurance 30s (Forza Media)', 'Critical Force 7:3', 'Trazione 1RM']
        valori_kg = [val_conc, val_ecc, stese_picco, val_end, val_cf, val_trazione]
        date_test = [formatta_data_breve(data_conc), formatta_data_breve(data_ecc), formatta_data_breve(d_stese), formatta_data_breve(data_end), formatta_data_breve(data_cf), formatta_data_breve(data_trazione)]
        valori_perc = [(v / peso_kpi) * 100 if v > 0 else 0.0 for v in valori_kg]
        perc_conc, perc_ecc, perc_stese, perc_end, perc_cf, perc_trazione = valori_perc

        if not any(v > 0 for v in valori_kg):
            st.info("Nessun dato valido registrato nello storico per le 6 macro-categorie dello Spider Chart.")
        else:
            # Fissaggio dinamico della scala radiale
            max_val_rilevato = max(valori_perc) if valori_perc else 0.0
            if max_val_rilevato < 100.0:
                max_scala = 100.0
            else:
                max_scala = float(math.ceil(max_val_rilevato / 10.0) * 10)

            # Chiusura ciclica del poligono radar e customdata con le date reali
            r_vals = valori_perc + [valori_perc[0]]
            theta_vals = categorie + [categorie[0]]
            customdata_vals = date_test + [date_test[0]]

            layout_radar = go.Layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, max_scala],
                        ticksuffix="%",
                        tickfont=dict(size=11, color="#475569"),
                        gridcolor="#cbd5e1",
                    ),
                    angularaxis=dict(
                        tickfont=dict(size=12, color="#0f172a", family="Inter, sans-serif"),
                        gridcolor="#e2e8f0",
                    ),
                    bgcolor="rgba(248, 250, 252, 0.5)"
                ),
                title=dict(
                    text=f"Profilo Biomeccanico — Ultimi Test Registrati (% BW — Peso: {peso_kpi:.1f} kg)",
                    font=dict(size=15, color="#0f172a"),
                    x=0.5,
                    xanchor='center'
                ),
                margin=dict(l=85, r=85, t=50, b=40),  # Aumenta i margini laterali per non tagliare le etichette di testo lunghe
                showlegend=False,
                height=450,
                dragmode=False
            )

            fig_spider = go.Figure(
                data=go.Scatterpolar(
                    r=r_vals,
                    theta=theta_vals,
                    customdata=customdata_vals,
                    fill='toself',
                    fillcolor='rgba(37, 99, 235, 0.25)',
                    line=dict(color='#2563eb', width=2),
                    marker=dict(size=7, color='#1d4ed8'),
                    name=atleta_selezionato,
                    hovertemplate="<b>%{theta}</b>: %{r:.1f}% BW<br>Data test: %{customdata}<extra></extra>"
                ),
                layout=layout_radar
            )

            st.plotly_chart(fig_spider, use_container_width=True, config={'displayModeBar': False})

            # Didascalia con le date reali degli ultimi test validi
            st.caption(
                f"Profilo basato sugli ultimi test validi — "
                f"Dita Concentrica: {formatta_data_breve(data_conc)} | "
                f"Dita Eccentrica: {formatta_data_breve(data_ecc)} | "
                f"Dita Stese: {formatta_data_breve(d_stese)} | "
                f"Endurance 30s (Forza Media): {formatta_data_breve(data_end)} | "
                f"Critical Force 7:3: {formatta_data_breve(data_cf)} | "
                f"Trazione 1RM: {formatta_data_breve(data_trazione)}"
            )

            # --- VALUTAZIONE BIOMECCANICA & CLINICA (CHECK SEPARATI) ---
            st.markdown("##### Valutazione Biomeccanica")

            # 1. Check Strutturale (Pulegge / Eccentrica vs Concentrica)
            if val_conc > 0 and val_ecc > 0:
                ratio_pe = (val_conc / val_ecc) * 100
                d_info = f"(Concentrica: {formatta_data_breve(data_conc)} | Eccentrica: {formatta_data_breve(data_ecc)})"
                if val_conc >= (0.95 * val_ecc):
                    st.error(
                        f"**1. Check Strutturale — Allarme Pulegge & Rischio Connettivale {d_info}:** La forza Concentrica "
                        f"delle dita ({val_conc:.1f} kg / {perc_conc:.1f}% BW) è al **{ratio_pe:.1f}%** della forza Eccentrica "
                        f"({val_ecc:.1f} kg / {perc_ecc:.1f}% BW). La forza attiva contrattile sta superando la tolleranza "
                        f"passiva dei tessuti connettivi: il rischio di lesione alle pulegge (A2/A4) è critico. "
                        f"Si consiglia di evitare carichi massimali dinamici e inserire isometrie yielding/eccentriche protettive."
                    )
                else:
                    st.success(
                        f"**1. Check Strutturale — Integrità Connettivale {d_info}:** Tolleranza passiva sicura. La forza Eccentrica "
                        f"({val_ecc:.1f} kg / {perc_ecc:.1f}% BW) supera la Concentrica ({val_conc:.1f} kg / {perc_conc:.1f}% BW), "
                        f"con un rapporto attivo/passivo al **{ratio_pe:.1f}%** (fisiologico se < 95%). Margine di sicurezza pulegge ottimale."
                    )
            elif val_conc > 0 or val_ecc > 0:
                st.info("1. Check Strutturale: Rilevata solo una tra forza Concentrica ed Eccentrica nello storico; eseguire entrambi i test per il calcolo del ratio di sicurezza tendinea.")

            # 2. Check Motore vs Trasmissione (Trazione 1RM vs Dita Concentrica)
            if perc_trazione > 0 and perc_conc > 0:
                diff_mt = perc_trazione - perc_conc
                d_info_mt = f"(Trazione: {formatta_data_breve(data_trazione)} | Concentrica: {formatta_data_breve(data_conc)})"
                if diff_mt > 15.0:
                    st.warning(
                        f"**2. Check Motore vs Trasmissione — Squilibrio di Potenza {d_info_mt}:** La Trazione 1RM ({perc_trazione:.1f}% BW) supera la forza Concentrica "
                        f"delle dita ({perc_conc:.1f}% BW) di **{diff_mt:.1f} punti percentuali**. C'è troppa forza di tirata rispetto "
                        f"alla capacità delle dita di trasmetterla sulle prese. Suggerimento Tecnico: Aumentare i lavori specifici "
                        f"a secco sulle dita (hangboard / sospensioni) per allineare la tenuta alla potenza del blocco braccia/dorso."
                    )
                elif diff_mt < -15.0:
                    st.info(
                        f"**2. Check Motore vs Trasmissione — Dita Dominanti {d_info_mt}:** La forza delle dita ({perc_conc:.1f}% BW) è dominante "
                        f"rispetto al motore di tirata ({perc_trazione:.1f}% BW, scarto {abs(diff_mt):.1f}%). È consigliato potenziare il blocco "
                        f"di trazione e i dorsali per sfruttare appieno la solida tenuta delle prese."
                    )
                else:
                    st.success(
                        f"**2. Check Motore vs Trasmissione — Bilanciamento Ottimale {d_info_mt}:** Rapporto equilibrato tra motore di tirata "
                        f"({perc_trazione:.1f}% BW) e trasmissione dita ({perc_conc:.1f}% BW, scarto di soli {abs(diff_mt):.1f}%). "
                        f"La potenza del tronco viene trasferita con efficienza sulle prese."
                    )
            elif perc_trazione > 0 or perc_conc > 0:
                st.info("2. Check Motore vs Trasmissione: Dati di Trazione 1RM o Concentrica parziali nello storico per il calcolo comparativo.")

            # 3. Check Metabolico (Endurance 30s Forza Media vs Dita Concentrica)
            if perc_end > 0 and perc_conc > 0:
                ratio_end = (perc_end / perc_conc) * 100
                d_info_end = f"(Endurance Forza Media: {formatta_data_breve(data_end)} | Concentrica: {formatta_data_breve(data_conc)})"
                if perc_end < (0.50 * perc_conc):
                    st.warning(
                        f"**3. Check Metabolico — Crollo Capacità Lattacida/Endurance {d_info_end}:** A fronte di una buona forza massima delle dita "
                        f"({perc_conc:.1f}% BW), si osserva una caduta marcata della curva nei test di 30 secondi "
                        f"(Endurance 30s (Forza Media) a **{perc_end:.1f}% BW**, pari al **{ratio_end:.1f}%** della concentrica). "
                        f"L'atleta esaurisce precocemente le scorte glicolitiche locali sulle prese; inserire blocchi di ripetizioni sub-massimali e capacità lattacida specifica."
                    )
                elif perc_end >= (0.70 * perc_conc):
                    st.success(
                        f"**3. Check Metabolico — Ottima Resistenza Locale {d_info_end}:** L'atleta mantiene un'alta percentuale di espressione di forza "
                        f"(Endurance 30s (Forza Media) a **{perc_end:.1f}% BW**, pari al **{ratio_end:.1f}%** della concentrica) anche in regime di accumulo lattacido (Test 30s)."
                    )
                else:
                    st.info(
                        f"**3. Check Metabolico — Resistenza Intermedia {d_info_end}:** L'Endurance 30s (Forza Media) si attesta a **{perc_end:.1f}% BW** "
                        f"(pari al **{ratio_end:.1f}%** del massimale concentrico). Capacità anaerobica nella norma, con margini di progressione sulla capillarizzazione locale."
                    )
            elif perc_end > 0:
                st.info(f"3. Check Metabolico: Endurance 30s (Forza Media) registrata a {perc_end:.1f}% BW ({val_end:.1f} kg, test: {formatta_data_breve(data_end)}). Eseguire il test di Concentrica per calcolare la percentuale di decadimento.")
            else:
                st.caption("3. Check Metabolico: Nessun test Endurance 30s (Forza Media) registrato nello storico dell'atleta.")

            # 4. Check Equilibrio Stile di Presa (Mezza Crimpatura vs Stese)
            if stese_picco > 0 and val_conc > 0:
                ratio_presa = (stese_picco / val_conc) * 100
                d_info_presa = f"(Stese: {formatta_data_breve(d_stese)} | Concentrica: {formatta_data_breve(data_conc)})"
                if ratio_presa >= 85.0:
                    st.success(
                        f"**4. Equilibrio Stile di Presa — Bilanciamento Fisiologico Ottimale {d_info_presa}:** "
                        f"(Stese: {stese_picco:.1f} kg | Concentrica: {val_conc:.1f} kg). "
                        f"La forza a dita stese è il **{ratio_presa:.1f}%** della mezza crimpatura. "
                        f"Ottimo equilibrio tra flessore profondo (FDP) e superficiale (FDS), rischio infortuni ridotto."
                    )
                else:
                    st.warning(
                        f"**4. Equilibrio Stile di Presa — Dominanza Mezza Crimpatura {d_info_presa}:** "
                        f"(Stese: {stese_picco:.1f} kg | Concentrica: {val_conc:.1f} kg). "
                        f"La forza a dita stese è solo il **{ratio_presa:.1f}%** della mezza crimpatura (target > 85%). "
                        f"L'atleta è iper-specializzato sull'ingaggio del pollice/lumbricali. "
                        f"Si consiglia di integrare sospensioni a dita stese (drag) per rinforzare il Flessore Profondo (FDP) e scaricare le pulegge A2/A4."
                    )
            elif stese_picco > 0 or val_conc > 0:
                st.info("4. Equilibrio Stile di Presa: Rilevato solo uno tra i test di Dita Concentrica e Dita Stese; eseguire entrambi i test per valutare il bilanciamento FDP/FDS.")
            else:
                st.caption("4. Equilibrio Stile di Presa: Nessun dato per Dita Concentrica e Stese nello storico.")

            # 5. Check Sistema Aerobico (Critical Force vs Dita Concentrica)
            if val_cf > 0 and val_conc > 0:
                ratio_cf = (val_cf / val_conc) * 100
                d_info_cf = f"(Critical Force: {formatta_data_breve(data_cf)} | Concentrica: {formatta_data_breve(data_conc)})"
                if ratio_cf >= 45.0:
                    st.success(
                        f"**5. Check Sistema Aerobico — Efficienza Ossidativa Ottimale {d_info_cf}:** "
                        f"(Critical Force: {val_cf:.1f} kg | Concentrica: {val_conc:.1f} kg). "
                        f"La Critical Force è al **{ratio_cf:.1f}%** della forza massima. "
                        f"L'atleta ha un'eccellente capillarizzazione locale e smaltimento del lattato, ideale per le vie lunghe di continuità."
                    )
                else:
                    st.info(
                        f"**5. Check Sistema Aerobico — Carenza Ossidativa / Rischio Ghisa {d_info_cf}:** "
                        f"(Critical Force: {val_cf:.1f} kg | Concentrica: {val_conc:.1f} kg). "
                        f"La Critical Force è solo al **{ratio_cf:.1f}%** della forza massima (target > 45%). "
                        f"L'avambraccio si affida troppo al sistema anaerobico. È consigliato inserire allenamenti ARC "
                        f"(Aerobic Restoration and Capillarity) e continuità a bassa intensità per migliorare il recupero in via."
                    )
            elif val_cf > 0 or val_conc > 0:
                st.info("5. Check Sistema Aerobico: Rilevato solo uno tra i test di Critical Force e Dita Concentrica; eseguire entrambi i test per il calcolo del ratio aerobico.")
            else:
                st.caption("5. Check Sistema Aerobico: Nessun dato per Critical Force e Dita Concentrica nello storico.")

            # --- 6. ANALISI RFD (CONTACT STRENGTH SUI TEMPI DI CONTATTO REALI) ---
            cols_rfd = [c for c in df_atleta.columns if "rfd" in c.lower() and "dita" in c.lower()]
            if not cols_rfd:
                cols_rfd = [c for c in df_atleta.columns if "rfd" in c.lower() and not "pull" in c.lower()]
            rfd_picco, d_rfd = ottieni_ultimo_valore(df_atleta, cols_rfd)

            rfd_dx_val, rfd_sx_val = 0.0, 0.0
            if d_rfd:
                r_rfd = df_atleta[df_atleta['Data'].apply(formatta_data_breve) == str(formatta_data_breve(d_rfd))]
                if r_rfd.empty and 'DataStr' in df_atleta.columns:
                    r_rfd = df_atleta[df_atleta['DataStr'].apply(formatta_data_breve) == str(formatta_data_breve(d_rfd))]
                if not r_rfd.empty:
                    u_rfd = r_rfd.iloc[-1]
                    col_dx = next((c for c in cols_rfd if "dx" in c.lower()), None)
                    col_sx = next((c for c in cols_rfd if "sx" in c.lower()), None)
                    v_dx_r = pd.to_numeric(str(u_rfd.get(col_dx, 0)).replace(',', '.'), errors='coerce') if col_dx else 0.0
                    v_sx_r = pd.to_numeric(str(u_rfd.get(col_sx, 0)).replace(',', '.'), errors='coerce') if col_sx else 0.0
                    rfd_dx_val = float(v_dx_r) if pd.notna(v_dx_r) and v_dx_r > 0 else 0.0
                    rfd_sx_val = float(v_sx_r) if pd.notna(v_sx_r) and v_sx_r > 0 else 0.0

            rfd_picco = max(rfd_dx_val, rfd_sx_val, rfd_picco if rfd_picco else 0.0)
            if rfd_picco > 0:
                tempo_contatto = 0.20
                forza_contatto_200ms = rfd_picco * tempo_contatto
                perc_espressa_200ms = (forza_contatto_200ms / val_conc * 100) if val_conc > 0 else None

                if rfd_picco >= 180:
                    badge_rfd = "Elevata (Élite)"
                    diagnosi_rfd = "Reclutamento neuro-muscolare istantaneo: eccellente capacità di trattenere prese dinamiche e lanci al volo."
                elif rfd_picco >= 120:
                    badge_rfd = "Buona (Avanzato)"
                    diagnosi_rfd = "Buona reattività neurale: l'atleta esprime forza di contatto sufficiente sulla maggior parte dei movimenti balistici."
                else:
                    badge_rfd = "Latenza di Reclutamento (Motore Diesel)"
                    diagnosi_rfd = "La forza massimale è presente ma sale troppo lentamente: l'atleta rischia di perdere la presa nei primi 200ms prima di aver sviluppato la tensione utile."

                st.markdown("---")
                st.markdown("##### 6. Riquadro Dedicato: Valori RFD & Contact Strength in Chiaro")
                col_rfd1, col_rfd2, col_rfd3 = st.columns(3)
                with col_rfd1:
                    delta_lati = f"DX: {rfd_dx_val:.1f} | SX: {rfd_sx_val:.1f}" if (rfd_dx_val > 0 and rfd_sx_val > 0) else None
                    st.metric(
                        "Picco RFD Dita",
                        f"{rfd_picco:.1f} kg/s",
                        delta=delta_lati,
                        help="Rate of Force Development: velocità di incremento della forza delle dita su tacca."
                    )
                with col_rfd2:
                    st.metric(
                        "Forza a 200ms",
                        f"{forza_contatto_200ms:.1f} kg",
                        help="Forza scaricata sulla presa nella finestra di contatto reale dei lanci/dinamici (200 millisecondi = 0.2s)."
                    )
                with col_rfd3:
                    txt_pe = f"{perc_espressa_200ms:.1f}%" if perc_espressa_200ms is not None else "N/D"
                    st.metric(
                        "Efficienza di Contatto",
                        txt_pe,
                        help="Percentuale della forza concentrica massimale effettivamente sbloccata nei primi 200ms dall'impatto con la presa."
                    )

                asim_rfd_txt = ""
                if rfd_dx_val > 0 and rfd_sx_val > 0:
                    gap_rfd = (abs(rfd_dx_val - rfd_sx_val) / rfd_picco) * 100
                    ld_rfd = "DX" if rfd_dx_val < rfd_sx_val else "SX"
                    if gap_rfd > 15.0:
                        asim_rfd_txt = f" <br><b>Asimmetria Esplosiva:</b> {gap_rfd:.1f}% (lato debole: {ld_rfd}) — deficit di coordinazione neurale o di spinta sull'arto debole."

                st.markdown(
                    f"<div style='background-color: #f8fafc; border-left: 4px solid #8b5cf6; padding: 12px 16px; border-radius: 6px; margin-top: 10px; font-size: 0.92em; color: #1e293b; line-height: 1.5;'>"
                    f"<b>Diagnosi Contact Strength [{formatta_data_breve(d_rfd)}]:</b> {badge_rfd}<br>"
                    f"Nel tempo di contatto reale di un movimento dinamico (<b>200 ms</b>), l'atleta genera <b>{forza_contatto_200ms:.1f} kg</b>"
                    f"{f' ({perc_espressa_200ms:.1f}% della forza massima concentrica di {val_conc:.1f} kg)' if perc_espressa_200ms else ''}. "
                    f"{diagnosi_rfd}{asim_rfd_txt}"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.caption("6. Nessun test RFD (Forza Rapida Dita) disponibile nello storico dell'atleta.")

    # Esportazione Dossier Clinico Gemini AI
    with st.expander("🤖 Esportazione Fascicolo Clinico per Gemini AI", expanded=False):
        st.caption("Genera il fascicolo clinico completo pronto per la skill Climbing Performance Coach.")
        col_d1, col_d2 = st.columns([1, 4])
        with col_d1:
            btn_dossier = st.button("📄 Genera Fascicolo Atleta", type="primary", key="btn_genera_dossier_atleta")
        if btn_dossier or ('dossier_atleta_testo' in st.session_state and st.session_state.get('dossier_atleta_sel') == atleta_selezionato):
            if btn_dossier:
                st.session_state.dossier_atleta_testo = genera_dossier_ai(df, atleta_selezionato)
                st.session_state.dossier_atleta_sel = atleta_selezionato
            st.code(st.session_state.dossier_atleta_testo, language="markdown")
            st.download_button(
                label="⬇️ Scarica Fascicolo (.txt)",
                data=st.session_state.dossier_atleta_testo,
                file_name=f"Fascicolo_{atleta_selezionato.replace(' ', '_')}.txt",
                mime="text/plain",
                key="dl_dossier_singolo_atleta"
            )

    st.markdown("---")
    
    st.markdown("### I Tuoi Record Personali (All-Time)")
    st.markdown("<div class='coach-tip'><b>L'Occhio del Coach:</b> I record più importanti sono quelli relativi al tuo peso corporeo (% BW). Nel Bouldering moderno, un target d'élite è superare l'<b>80% BW</b> di trazione a dito singolo (Concentrica) e il <b>50-60% BW</b> di zavorra nel Pull-up. Un divario troppo alto tra le due evidenzia una debolezza nella trasmissione della forza sulla parete.</div>", unsafe_allow_html=True)
    
    st.markdown("#### Specifici (Dita, Trazione, Isometria)")
    colonne_specifiche = [
        ('Pull-Up 1RM Calcolata', 'Trazione (1RM)'), ('Pull-Up 1RM Reale', 'Trazione (1RM Reale)'),
        ('Concentrica', 'Dita Concentrica'), ('Eccentrica', 'Dita Eccentrica'), ('Stese', 'Dita Stese'),
        ('Vertical Pull 120°', 'Isometria Trazione 120°'), ('RFD Dita', 'Forza Esplosiva (RFD)'), ('Critical Force 7:3', 'Critical Force')
    ]
    cards_html_spec = []
    for col_db, label in colonne_specifiche:
        info = calcola_record_assoluto(col_db)
        if info["valore"] > 0:
            unita = "kg/s" if "RFD" in col_db else "kg"
            card = render_card(label, info, unit=unita)
            if card: cards_html_spec.append(card)
            
    if cards_html_spec: st.markdown(f'<div class="card-container">{"".join(cards_html_spec)}</div>', unsafe_allow_html=True)
    else: st.info("Nessun record specifico registrato.")
    
    st.markdown("---")
    with st.expander("Mostra Misurazioni Manuali e Test Generali (Panca, Squat, Corpo Libero)", expanded=False):
        colonne_generali = ['Panca', 'Squat', 'Deadlift', 'Push-up MAX rep', "Sit-up in 30''", 'Planck palla medica sec.', 'Box Jump', 'Squat contro parete']
        cards_html_gen = []
        for col in colonne_generali:
            try:
                info = calcola_record_assoluto(col)
                if info["valore"] > 0:
                    if "rep" in col.lower() or "up" in col.lower(): unita = "rep"
                    elif "sec" in col.lower() or "parete" in col.lower(): unita = "sec"
                    else: unita = "kg"
                    
                    card = render_card(col, info, unit=unita)
                    if card: cards_html_gen.append(card)
            except Exception:
                pass
                
        if cards_html_gen: st.markdown(f'<div class="card-container">{"".join(cards_html_gen)}</div>', unsafe_allow_html=True)
        else: st.info("Nessun record generale registrato (N/D).")

# --- LETTURA E CATEGORIZZAZIONE CHIRURGICA ---
cartella = os.path.join(CARTELLA_ARCHIVIO, f"{atleta_selezionato} ASSES")
file_forza = {}
file_endurance = {}

if os.path.exists(cartella):
    for root, dirs, files in os.walk(cartella):
        for file in files:
            if 'info.csv' in file.lower() or 'data_set_1' in file.lower(): continue
            if file.lower().endswith(".csv"):
                percorso_completo = os.path.join(root, file)
                col_base = individua_colonna_db(percorso_completo)
                
                data_t = "??/??/??"
                match1 = re.search(r'(\d{2})_(\d{2})_(\d{4})', file)
                if match1:
                    data_t = f"{match1.group(1)}/{match1.group(2)}/{match1.group(3)}"
                else:
                    match2 = re.search(r'(20\d{2})(\d{2})(\d{2})', file)
                    if match2:
                        data_t = f"{match2.group(3)}/{match2.group(2)}/{match2.group(1)}"
                    else:
                        try:
                            with open(percorso_completo, 'r', encoding='utf-8', errors='ignore') as f:
                                l1 = f.readline().strip()
                                l2 = f.readline().strip()
                                if l1.lower().startswith('date,') and ',' in l2:
                                    raw_d = l2.split(',')[0].strip()
                                    if ' ' in raw_d: raw_d = raw_d.split(' ')[0]
                                    dt_p = pd.to_datetime(raw_d, dayfirst=True, errors='coerce')
                                    if pd.notna(dt_p):
                                        data_t = dt_p.strftime('%d/%m/%Y')
                        except:
                            pass
                
                if data_t == "??/??/??":
                    try:
                        mtime = os.path.getmtime(percorso_completo)
                        data_t = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y")
                    except:
                        pass
                
                alias_pulito = file if col_base == "Test Sconosciuto" else col_base.replace(" - Picco Max", "")
                for k in ["Concentrica", "Eccentrica", "Stese", "Critical Force"]:
                    if k.lower() in alias_pulito.lower() and not alias_pulito.lower().startswith("dita"):
                        alias_pulito = f"Dita - {alias_pulito}"
                chiave_tendina = f"[{data_t}] {alias_pulito}"
                
                col_basso = col_base.lower()
                is_endurance = "endurance" in col_basso or "critical force" in col_basso or "30''" in col_basso
                
                if is_endurance:
                    file_endurance[chiave_tendina] = percorso_completo
                elif col_base != "Test Sconosciuto":
                    file_forza[chiave_tendina] = percorso_completo
                else:
                    if '30s' in file.lower() or '7-3' in file.lower() or 'cf' in file.lower(): file_endurance[chiave_tendina] = percorso_completo
                    else: file_forza[chiave_tendina] = percorso_completo

if False:
    st.markdown("### Laboratorio Forza (Curve Isometria & RFD)")
    st.markdown("<div class='coach-tip'><b>Pillola Biomeccanica:</b> Una linea che sale molto ripida nei primissimi decimi di secondo indica un eccellente <i>Tasso di Sviluppo della Forza (RFD)</i>. Questa è la famosa 'forza di contatto' che ti permette di tenere le prese in modo dinamico. Una curva tremolante in cima, invece, evidenzia una scarsa stiffness (rigidità) tendinea.</div>", unsafe_allow_html=True)
    
    if file_forza:
        # FIX ORDINAMENTO: Uso la funzione che estrae la data reale
        chiavi_ordinate = sorted(file_forza.keys(), key=estrai_data_per_ordinamento, reverse=True)
        alias_sel = st.selectbox("Seleziona una Curva di Forza (in ordine cronologico):", chiavi_ordinate)
        confronto_bilaterale = st.toggle("Sovrapponi Lato Opposto (Confronto DX/SX)", key="toggle_bilaterale_forza")
        if alias_sel:
            file_sel = file_forza[alias_sel]
            df_curva, col_peso, err_msg = leggi_curva_csv(file_sel)
            if df_curva is not None and col_peso in df_curva.columns:
                try:
                    picco_max = df_curva[col_peso].max()
                    val_picco = f"{picco_max:.1f} kg" if pd.notna(picco_max) else "N/D"
                    st.success(f"**Picco Rilevato:** {val_picco}")
                    
                    fig, ax = plt.subplots(figsize=fig_size)
                    if confronto_bilaterale:
                        alias_opp = None
                        if " DX" in alias_sel:
                            alias_opp = alias_sel.replace(" DX", " SX")
                        elif " SX" in alias_sel:
                            alias_opp = alias_sel.replace(" SX", " DX")
                            
                        if alias_opp and alias_opp in file_forza:
                            df_opp, col_peso_opp, _ = leggi_curva_csv(file_forza[alias_opp])
                            if df_opp is not None and col_peso_opp in df_opp.columns:
                                if " DX" in alias_sel:
                                    ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#3b82f6', linewidth=2, label='Lato Destro (DX)')
                                    ax.plot(df_opp['time_sec'], df_opp[col_peso_opp], color='#10b981', linewidth=2, label='Lato Sinistro (SX)')
                                else:
                                    ax.plot(df_opp['time_sec'], df_opp[col_peso_opp], color='#3b82f6', linewidth=2, label='Lato Destro (DX)')
                                    ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#10b981', linewidth=2, label='Lato Sinistro (SX)')
                                ax.legend()
                            else:
                                st.info("Test del lato opposto non trovato per questa specifica data.")
                                ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#8b5cf6', linewidth=2)
                        else:
                            st.info("Test del lato opposto non trovato per questa specifica data.")
                            ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#8b5cf6', linewidth=2)
                    else:
                        ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#8b5cf6', linewidth=2)
                    ax.set_ylabel("Forza (kg)"); ax.set_xlabel("Tempo (s)"); ax.grid(True, alpha=0.3)
                    st.pyplot(fig, use_container_width=True)
                except Exception:
                    st.info("Curva non disponibile per questo test (N/D).")
            else:
                st.info("Dati curva non disponibili (N/D).")
    else: st.warning("Nessun test di Forza Specifica trovato nel tuo archivio.")

if False:
    st.markdown("### Laboratorio Endurance (Sistemi Energetici)")
    st.markdown("<div class='coach-tip'><b>Fisiologia dell'Arrampicata:</b> Nel test <b>7:3 (Critical Force)</b> cerchiamo il <i>plateau metabolico</i>: la forza media che riesci a mantenere nell'ultimo blocco di ripetizioni. Nel test <b>30s</b>, un crollo repentino della forza (box rossi) indica una scarsa capillarizzazione: il muscolo si acidifica velocemente e le cellule non riescono a smaltire le scorie.</div>", unsafe_allow_html=True)
    
    def colore_percentuale(val):
        if pd.isna(val) or val == "": return ''
        try: 
            v = float(val)
            if v >= 90: return 'background-color: #dcfce7; color: #166534; font-weight: bold;' 
            elif v >= 80: return 'background-color: #fef08a; color: #854d0e; font-weight: bold;'
            elif v >= 70: return 'background-color: #fed7aa; color: #9a3412; font-weight: bold;'
            else: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold;'
        except: return ''
        
    def formatta_numero(val): return f"{val:.1f}" if isinstance(val, (int, float)) else val

    if file_endurance:
        # FIX ORDINAMENTO: Uso la funzione che estrae la data reale
        chiavi_ordinate = sorted(file_endurance.keys(), key=estrai_data_per_ordinamento, reverse=True)
        alias_sel = st.selectbox("Seleziona una Curva Metabolica (in ordine cronologico):", chiavi_ordinate)
        confronto_bilaterale = st.toggle("Sovrapponi Lato Opposto (Confronto DX/SX)", key="toggle_bilaterale_endurance")
        if alias_sel:
            file_sel = file_endurance[alias_sel]
            try:
                with open(file_sel, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
                start_idx = next((i for i, l in enumerate(lines) if l.lower().startswith('time,weight') or l.lower().startswith('time,force')), -1)
                
                if start_idx != -1:
                    df_curva = pd.read_csv(io.StringIO("".join(lines[start_idx:])))
                    col_peso = 'weight' if 'weight' in df_curva.columns else df_curva.columns[1]
                    df_curva['time_sec'] = pd.to_numeric(df_curva['time'], errors='coerce')
                    if df_curva['time_sec'].max() > 100000: df_curva['time_sec'] = (df_curva['time_sec'] - df_curva['time_sec'].iloc[0]) / 1_000_000
                    else: df_curva['time_sec'] = df_curva['time_sec'] - df_curva['time_sec'].iloc[0]
                    
                    fig, ax = plt.subplots(figsize=fig_size)
                    if confronto_bilaterale:
                        alias_opp = None
                        if " DX" in alias_sel:
                            alias_opp = alias_sel.replace(" DX", " SX")
                        elif " SX" in alias_sel:
                            alias_opp = alias_sel.replace(" SX", " DX")
                            
                        if alias_opp and alias_opp in file_endurance:
                            df_opp, col_peso_opp, _ = leggi_curva_csv(file_endurance[alias_opp])
                            if df_opp is not None and col_peso_opp in df_opp.columns:
                                if " DX" in alias_sel:
                                    ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#3b82f6', linewidth=1.5, label='Lato Destro (DX)')
                                    ax.plot(df_opp['time_sec'], df_opp[col_peso_opp], color='#10b981', linewidth=1.5, label='Lato Sinistro (SX)')
                                else:
                                    ax.plot(df_opp['time_sec'], df_opp[col_peso_opp], color='#3b82f6', linewidth=1.5, label='Lato Destro (DX)')
                                    ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#10b981', linewidth=1.5, label='Lato Sinistro (SX)')
                                ax.legend()
                            else:
                                st.info("Test del lato opposto non trovato per questa specifica data.")
                                ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#0ea5e9', linewidth=1.5)
                        else:
                            st.info("Test del lato opposto non trovato per questa specifica data.")
                            ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#0ea5e9', linewidth=1.5)
                    else:
                        ax.plot(df_curva['time_sec'], df_curva[col_peso], color='#0ea5e9', linewidth=1.5)
                    ax.set_ylabel("Forza (kg)"); ax.set_xlabel("Tempo (s)"); ax.grid(True, alpha=0.3)
                    st.pyplot(fig, use_container_width=True)
                    
                    nome = os.path.basename(file_sel).lower()
                    if "30" in nome or "endurance" in nome:
                        df_curva['Sec'] = np.floor(df_curva['time_sec']).astype(int)
                        df_30 = df_curva[(df_curva['Sec'] >= 0) & (df_curva['Sec'] < 30)].groupby('Sec')[col_peso].mean().reset_index()
                        df_30.columns = ['Intervallo (s)', 'Forza Media (kg)']
                        df_30['Intervallo (s)'] = df_30['Intervallo (s)'].apply(lambda x: f"{x}-{x+1}s")
                        picco_ass = df_30['Forza Media (kg)'].max()
                        df_30['% Max'] = round((df_30['Forza Media (kg)'] / picco_ass) * 100, 1)
                        for col in ['Forza Media (kg)', '% Max']: df_30[col] = df_30[col].apply(formatta_numero)
                        
                        try: styled_df = df_30.style.map(colore_percentuale, subset=['% Max'])
                        except AttributeError: styled_df = df_30.style.applymap(colore_percentuale, subset=['% Max'])
                        st.markdown(styled_df.to_html(index=False), unsafe_allow_html=True)
                        
                    elif "73" in nome or "7-3" in nome or "cf" in nome:
                        df_curva['Set'] = np.floor(df_curva['time_sec'] / 10).astype(int) + 1
                        df_73 = df_curva[df_curva['Set'] <= 25].groupby('Set')[col_peso].max().reset_index()
                        df_73.columns = ['Set', 'Picco (kg)']
                        picco_ass = df_73['Picco (kg)'].max()
                        df_73['% del Max'] = round((df_73['Picco (kg)'] / picco_ass) * 100, 1)
                        for col in ['Picco (kg)', '% del Max']: df_73[col] = df_73[col].apply(formatta_numero)
                        
                        try: styled_df = df_73.style.map(colore_percentuale, subset=['% del Max'])
                        except AttributeError: styled_df = df_73.style.applymap(colore_percentuale, subset=['% del Max'])
                        st.markdown(styled_df.to_html(index=False), unsafe_allow_html=True)
                else: st.error("Formato CSV non valido.")
            except Exception as e: st.error(f"Errore lettura curva: {e}")
    else: st.warning("Nessun test Endurance trovato nel tuo archivio.")

with tab4:
    st.markdown("### Storico Analitico (Progressioni)")
    st.markdown("<div class='coach-tip'><b>Come Leggere i Grafici:</b> La progressione in <i>Carico Assoluto (kg)</i> mostra la tua forza pura. Seleziona <i>Forza Relativa (% BW)</i> per capire se sei realmente più forte sulla parete, o se l'aumento dei carichi è solo una compensazione di un eventuale aumento di peso corporeo.</div>", unsafe_allow_html=True)
    
    # --- GRIGLIA MACRO-METRICHE STORICHE (MOBILE-FIRST) ---
    kpis = calcola_macro_kpi_storici(df_atleta)
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        v1, d1, dt1 = kpis["1rm"]
        st.metric(
            "Trazione 1RM",
            f"{v1:.1f} kg" if v1 is not None else "N/D",
            delta=f"{d1:+.1f} kg" if d1 is not None else None,
            help="Carico massimale teorico calcolato di trazione (ultimo test vs penultimo)."
        )
    with col_m2:
        vc, dc, lc, dtc = kpis["conc"]
        d_lbl_c = f"{dc:+.1f} kg ({lc})" if dc is not None else (f"Lato: {lc}" if lc else None)
        st.metric(
            "Dita Concentrica",
            f"{vc:.1f} kg" if vc is not None else "N/D",
            delta=d_lbl_c,
            help="Picco di forza concentrica massima dita su tacca (DX/SX vs penultimo test)."
        )
    with col_m3:
        ve, de, le, dte = kpis["ecc"]
        d_lbl_e = f"{de:+.1f} kg ({le})" if de is not None else (f"Lato: {le}" if le else None)
        st.metric(
            "Dita Eccentrica",
            f"{ve:.1f} kg" if ve is not None else "N/D",
            delta=d_lbl_e,
            help="Forza eccentrica dita/freno tendineo (DX/SX vs penultimo test)."
        )
    with col_m4:
        vnd, dnd, lnd, dtnd = kpis["end"]
        d_lbl_nd = f"{dnd:+.1f} kg ({lnd})" if dnd is not None else (f"Lato: {lnd}" if lnd else None)
        st.metric(
            "Endurance 30s",
            f"{vnd:.1f} kg" if vnd is not None else "N/D",
            delta=d_lbl_nd,
            help="Test di resistenza continua 30 secondi (ultimo test vs penultimo)."
        )
    st.markdown("---")
    
    # --- FUNZIONI DI FORMATTAZIONE ED ORDINAMENTO KINESIOLOGICO METRICHE ---
    def formatta_etichetta_metrica(raw):
        keywords = ["concentrica", "eccentrica", "stese", "critical force", "endurance"]
        raw_clean = raw.strip()
        if any(k in raw_clean.lower() for k in keywords):
            if not raw_clean.lower().startswith("dita"):
                return f"Dita - {raw_clean}"
        return raw_clean

    def priorita_metrica(label):
        l = label.lower()
        # 1°: Test Dita (voci che iniziano con "Dita - " o contengono "RFD Dita")
        if l.startswith("dita - ") or "rfd dita" in l or "dita" in l or "tacca" in l:
            return 1
        # 2°: Trazione (Vertical Pull, Pull-Up, Isometria)
        if "vertical pull" in l or "pull-up" in l or "pull up" in l or "trazion" in l or "isometria" in l:
            return 2
        # 4°: Test Secondari (Push-up, Sit-up, Salti, Campus, Squat parete) - valutato prima di Big Lifts per via di squat parete
        if "squat contro parete" in l or "squat parete" in l or "push-up" in l or "push up" in l or "sit-up" in l or "sit up" in l or "jump" in l or "salto" in l or "salti" in l or "campus" in l or "planck" in l or "plank" in l or "h.j." in l or "l.j." in l:
            return 4
        # 3°: Big Lifts (Panca, Squat, Deadlift)
        if "panca" in l or "squat" in l or "deadlift" in l or "stacco" in l:
            return 3
        # 5°: Antropometria (Peso, Addome, Braccio, Petto, Bacino, Coscia)
        if any(k in l for k in ["peso", "addome", "braccio", "petto", "bacino", "coscia", "circonferenza", "pliche"]):
            return 5
        return 6

    test_eseguiti = set()
    for col in df_atleta.columns:
        if col in ['Data', 'DataStr', 'Data_dt', 'Atleta', 'Gruppo']: continue
        if not df_atleta[col].dropna().empty: test_eseguiti.add(col.replace(' DX', '').replace(' SX', ''))
        
    if test_eseguiti:
        col_s1, col_s2 = st.columns([1, 1])
        
        # Mappatura UI -> Colonna originale grezza
        mappa_ui_to_raw = {}
        for raw in test_eseguiti:
            label_ui = formatta_etichetta_metrica(raw)
            if label_ui in mappa_ui_to_raw and mappa_ui_to_raw[label_ui] != raw:
                label_ui = f"{label_ui} ({raw})"
            mappa_ui_to_raw[label_ui] = raw
            
        # Ordinamento logico secondo i gruppi di priorità kinesiologici e alfabetico interno
        opzioni_ordinate = sorted(list(mappa_ui_to_raw.keys()), key=lambda x: (priorita_metrica(x), x))
        
        test_sel_ui = col_s1.selectbox("Seleziona Metrica da analizzare:", opzioni_ordinate)
        test_sel = mappa_ui_to_raw[test_sel_ui]
        modalita = col_s2.radio("Modalità di Visualizzazione:", ["Carico Assoluto (kg)", "Forza Relativa (% BW)"], horizontal=True)
        
        chiave_testo = next((k for k in TESTI_FISIOLOGIA.keys() if k.lower() in test_sel.lower()), None)
        if chiave_testo: st.markdown(f"<div class='bio-info-box'><b>Anatomia e Funzione:</b><br>{TESTI_FISIOLOGIA[chiave_testo].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
            
        fig = go.Figure()
        match_dx = [c for c in df_atleta.columns if c.replace(' DX', '') == test_sel and ' DX' in c]
        match_sx = [c for c in df_atleta.columns if c.replace(' SX', '') == test_sel and ' SX' in c]
        
        unita_misura = "% BW" if modalita == "Forza Relativa (% BW)" else "Forza (kg)"

        def plot_linea_plotly(col_nome, colore, label):
            df_plot = df_atleta.dropna(subset=[col_nome]).copy()
            if not df_plot.empty:
                y_vals = pd.to_numeric(df_plot[col_nome].astype(str).str.replace(',', '.'), errors='coerce')
                if modalita == "Forza Relativa (% BW)" and 'Peso Corporeo' in df_plot.columns:
                    pesi = pd.to_numeric(df_plot['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce')
                    y_vals = (y_vals / pesi) * 100
                fig.add_trace(go.Scatter(
                    x=df_plot['Data'],
                    y=y_vals,
                    mode='lines+markers',
                    name=label,
                    line=dict(color=colore, width=2.5),
                    marker=dict(size=8, color=colore),
                    hovertemplate=f"<b>%{{x|%d/%m/%Y}}</b><br>{label}: %{{y:.1f}} {unita_misura}<extra></extra>"
                ))
                return True
            return False
            
        if match_dx and match_sx:
            plot_linea_plotly(match_dx[0], '#3b82f6', 'Lato Destro (DX)')
            plot_linea_plotly(match_sx[0], '#10b981', 'Lato Sinistro (SX)')
        else:
            plot_linea_plotly(test_sel, '#3b82f6', test_sel_ui)

        fig.update_layout(
            title=dict(
                text=f"📈 Andamento Storico — {test_sel_ui} ({unita_misura})",
                font=dict(size=16)
            ),
            xaxis_title="Data Test",
            yaxis_title=unita_misura,
            hovermode='x unified',
            template='plotly_white',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=60, b=40),
            height=420 if dim_grafico == "Standard (Grande)" else 300,
            dragmode=False
        )
        fig.update_xaxes(
            type='date',
            tickformat='%d/%m/%Y',
            hoverformat='%d/%m/%Y',
            fixedrange=True,
            gridcolor='rgba(0,0,0,0.08)'
        )
        fig.update_yaxes(
            fixedrange=True,
            gridcolor='rgba(0,0,0,0.08)'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
        with st.expander("Tabella Dati Completa (Record evidenziati in DarkGoldenRod)", expanded=False):
            df_tab4 = df_atleta.drop(columns=['Data_dt', '_Data_Sort'], errors='ignore').dropna(axis=1, how='all').copy()
            if 'Data' in df_tab4.columns and pd.api.types.is_datetime64_any_dtype(df_tab4['Data']):
                df_tab4['Data'] = df_tab4['Data'].dt.strftime('%d/%m/%Y')
            colonne_numeriche = []
            for c in df_tab4.columns:
                if c in ['Data', 'DataStr', 'Atleta', 'Gruppo']:
                    continue
                s_num = pd.to_numeric(df_tab4[c].astype(str).str.replace(',', '.'), errors='coerce')
                if not s_num.dropna().empty:
                    df_tab4[c] = s_num
                    colonne_numeriche.append(c)
                    
            if colonne_numeriche:
                try:
                    styled_df_tab4 = df_tab4.style.highlight_max(subset=colonne_numeriche, color='#b8860b', axis=0).format(precision=1, na_rep="-")
                    st.dataframe(styled_df_tab4, width='stretch', hide_index=True)
                except Exception:
                    st.dataframe(prepara_df_visualizzazione(df_tab4), width='stretch', hide_index=True)
            else:
                st.dataframe(prepara_df_visualizzazione(df_tab4), width='stretch', hide_index=True)
    else: st.info("Nessun dato storico.")

with tab5:
    st.markdown("### Analisi Avanzata & Confronti Biomeccanici")
    df_bio = df_atleta.dropna(subset=['Peso Corporeo'])
    
    if not df_bio.empty:
        st.markdown("#### 1. Trazione (Motore) vs Dita (Trasmissione)")
        st.markdown("<div class='coach-tip'><b>Ottimizzazione:</b> Se il Motore (trazione) è molto forte ma la Trasmissione (dita) è bassa, la forza propulsiva viene persa appena la presa si riduce. Cerca di mantenere le due linee in proporzione equilibrata. (Valori in % BW)</div>", unsafe_allow_html=True)
        has_pull = 'Pull-Up 1RM Calcolata' in df_bio.columns or 'Pull-Up 1RM Reale' in df_bio.columns
        if has_pull and 'Concentrica DX' in df_bio.columns:
            col_pull_target = 'Pull-Up 1RM Calcolata' if 'Pull-Up 1RM Calcolata' in df_bio.columns else 'Pull-Up 1RM Reale'
            df_mvst = df_bio.dropna(subset=[col_pull_target, 'Concentrica DX', 'Concentrica SX']).copy()
            if not df_mvst.empty:
                # --- FIX: Sostituzione virgola con punto prima della conversione float ---
                s_conc_dx = pd.to_numeric(df_mvst['Concentrica DX'].astype(str).str.replace(',', '.'), errors='coerce')
                s_conc_sx = pd.to_numeric(df_mvst['Concentrica SX'].astype(str).str.replace(',', '.'), errors='coerce')
                
                s_traz = pd.Series(0, index=df_mvst.index)
                if 'Pull-Up 1RM Calcolata' in df_mvst.columns:
                    s_traz = pd.to_numeric(df_mvst['Pull-Up 1RM Calcolata'].astype(str).str.replace(',', '.'), errors='coerce')
                elif 'Pull-Up 1RM Reale' in df_mvst.columns:
                    s_traz = pd.to_numeric(df_mvst['Pull-Up 1RM Reale'].astype(str).str.replace(',', '.'), errors='coerce')
                
                s_peso = pd.to_numeric(df_mvst['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce')
                
                # Calcolo Percentuali
                df_mvst['Trasmissione %'] = (pd.concat([s_conc_dx, s_conc_sx], axis=1).max(axis=1) / s_peso) * 100
                df_mvst['Motore %'] = (s_traz / s_peso) * 100
                
                # Per l'integrata (Isometria Vertical Pull)
                s_iso_dx = pd.Series(0, index=df_mvst.index)
                s_iso_sx = pd.Series(0, index=df_mvst.index)
                if 'Vertical Pull 120° DX' in df_mvst.columns:
                    s_iso_dx = pd.to_numeric(df_mvst['Vertical Pull 120° DX'].astype(str).str.replace(',', '.'), errors='coerce')
                if 'Vertical Pull 120° SX' in df_mvst.columns:
                    s_iso_sx = pd.to_numeric(df_mvst['Vertical Pull 120° SX'].astype(str).str.replace(',', '.'), errors='coerce')
                
                df_mvst['Integrata %'] = (pd.concat([s_iso_dx, s_iso_sx], axis=1).max(axis=1) / s_peso) * 100

                fig_mvst = go.Figure()
                fig_mvst.add_trace(go.Scatter(
                    x=df_mvst['Data'],
                    y=df_mvst['Motore %'],
                    mode='lines+markers',
                    name='Motore (Trazione Pull-Up)',
                    line=dict(color='#3b82f6', width=2.5),
                    marker=dict(size=7),
                    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Motore: %{y:.1f}% BW<extra></extra>"
                ))
                fig_mvst.add_trace(go.Scatter(
                    x=df_mvst['Data'],
                    y=df_mvst['Trasmissione %'],
                    mode='lines+markers',
                    name='Trasmissione (Concentrica Max Dita)',
                    line=dict(color='#8b5cf6', width=2.5),
                    marker=dict(size=7),
                    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Trasmissione: %{y:.1f}% BW<extra></extra>"
                ))
                fig_mvst.update_layout(
                    title="Trazione (Motore) vs Dita (Trasmissione)",
                    xaxis_title="Data",
                    yaxis_title="% Bodyweight",
                    hovermode='x unified',
                    template='plotly_white',
                    height=400 if dim_grafico == "Standard (Grande)" else 300,
                    margin=dict(l=40, r=40, t=50, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    dragmode=False
                )
                fig_mvst.update_xaxes(type='date', tickformat='%d/%m/%Y', hoverformat='%d/%m/%Y', fixedrange=True, gridcolor='rgba(0,0,0,0.08)')
                fig_mvst.update_yaxes(fixedrange=True, gridcolor='rgba(0,0,0,0.08)')
                st.plotly_chart(fig_mvst, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("#### 2. Prevenzione Infortuni Strutturali")
        st.markdown("<div class='coach-tip'><b>Alert Clinico:</b> La forza Eccentrica (passiva) rappresenta il 'freno a mano' e la tolleranza limite dei tuoi tendini e pulegge. Se la forza Concentrica (il 'motore' attivo) la supera (o arriva al 95%), l'infortunio è statisticamente molto vicino. In tal caso, si scala il carico e si prescrivono isometrie Yielding per rinforzare i tessuti connettivi.</div>", unsafe_allow_html=True)
        if 'Concentrica DX' in df_bio.columns and 'Eccentrica DX' in df_bio.columns:
            df_inf = df_bio.dropna(subset=['Concentrica DX', 'Concentrica SX', 'Eccentrica DX', 'Eccentrica SX']).copy()
            if not df_inf.empty:
                ult_inf = df_inf.iloc[-1]
                v_c_dx = pd.to_numeric(str(ult_inf.get('Concentrica DX', 0)).replace(',', '.'), errors='coerce') or 0.0
                v_c_sx = pd.to_numeric(str(ult_inf.get('Concentrica SX', 0)).replace(',', '.'), errors='coerce') or 0.0
                v_e_dx = pd.to_numeric(str(ult_inf.get('Eccentrica DX', 0)).replace(',', '.'), errors='coerce') or 0.0
                v_e_sx = pd.to_numeric(str(ult_inf.get('Eccentrica SX', 0)).replace(',', '.'), errors='coerce') or 0.0
                max_conc = max(float(v_c_dx), float(v_c_sx))
                max_ecc = max(float(v_e_dx), float(v_e_sx))
                
                c1, c2 = st.columns(2)
                c1.metric("Max Concentrica (Attiva)", f"{max_conc:.1f} kg")
                c2.metric("Max Eccentrica (Passiva)", f"{max_ecc:.1f} kg")
                
                if max_conc >= max_ecc * 0.95: st.error("**ALLARME STRUTTURALE:** La forza attiva è vicina o supera la tolleranza passiva.")
                else: st.success("Margine di sicurezza strutturale nella norma.")

        st.markdown("#### 3. Zavorra Inerziale vs Forza Erogata")
        st.markdown("<div class='coach-tip'><b>Rapporto Peso/Potenza:</b> Questa visualizzazione a doppio asse è cruciale. Se la linea verde (Forza) sale, ma sale anche la linea rossa (Peso Corporeo), potresti non sentire reali benefici su roccia. Il miglioramento ideale vede la linea verde salire mentre la rossa resta stabile o scende leggermente.</div>", unsafe_allow_html=True)
        col_pull_fz = 'Pull-Up 1RM Calcolata' if 'Pull-Up 1RM Calcolata' in df_bio.columns else ('Pull-Up 1RM Reale' if 'Pull-Up 1RM Reale' in df_bio.columns else None)
        if col_pull_fz:
            df_fz = df_bio.dropna(subset=[col_pull_fz]).copy()
            if not df_fz.empty:
                s_fz = pd.to_numeric(df_fz[col_pull_fz].astype(str).str.replace(',', '.'), errors='coerce')
                s_bw = pd.to_numeric(df_fz['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce')
                fig_fz = go.Figure()
                fig_fz.add_trace(go.Scatter(
                    x=df_fz['Data'],
                    y=s_fz,
                    mode='lines+markers',
                    name='Forza Erogata (kg)',
                    line=dict(color='#10b981', width=2.5),
                    marker=dict(size=7),
                    yaxis='y1',
                    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Forza: %{y:.1f} kg<extra></extra>"
                ))
                fig_fz.add_trace(go.Scatter(
                    x=df_fz['Data'],
                    y=s_bw,
                    mode='lines+markers',
                    name='Peso Corporeo (kg)',
                    line=dict(color='#ef4444', width=2.5, dash='dash'),
                    marker=dict(size=7, symbol='square'),
                    yaxis='y2',
                    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Peso Corporeo: %{y:.1f} kg<extra></extra>"
                ))
                fig_fz.update_layout(
                    title="Zavorra Inerziale vs Forza Erogata",
                    dragmode=False,
                    xaxis=dict(
                        title=dict(text="Data"),
                        type='date',
                        tickformat='%d/%m/%Y',
                        hoverformat='%d/%m/%Y',
                        fixedrange=True,
                        gridcolor='rgba(0,0,0,0.08)'
                    ),
                    yaxis=dict(
                        title=dict(text="Forza (kg)", font=dict(color='#10b981')),
                        tickfont=dict(color='#10b981'),
                        fixedrange=True,
                        gridcolor='rgba(0,0,0,0.08)'
                    ),
                    yaxis2=dict(
                        title=dict(text="Peso Corporeo (kg)", font=dict(color='#ef4444')),
                        tickfont=dict(color='#ef4444'),
                        fixedrange=True,
                        overlaying='y',
                        side='right'
                    ),
                    hovermode='x unified',
                    template='plotly_white',
                    height=400 if dim_grafico == "Standard (Grande)" else 300,
                    margin=dict(l=40, r=40, t=50, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_fz, use_container_width=True, config={'displayModeBar': False})
