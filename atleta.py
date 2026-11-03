import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import re
from datetime import datetime
import numpy as np

def prepara_df_visualizzazione(df_in):
    df_out = df_in.copy()
    for col in df_out.columns:
        if df_out[col].dtype == 'object':
            df_out[col] = df_out[col].apply(lambda x: "" if pd.isna(x) else str(x).strip())
    return df_out

CARTELLA_ARCHIVIO = "Archivio_CSV"

# --- CONNESSIONE CLOUD SICURA ---
@st.cache_data(ttl=60)
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

    div[data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    footer { display: none !important; }

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
    df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce')

atleti_lista = sorted(df['Atleta'].dropna().unique().tolist()) if 'Atleta' in df.columns else []

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
        st.markdown("<div style='text-align: center; margin-top: 2.5rem; margin-bottom: 1.5rem;'>", unsafe_allow_html=True)
        st.title("🧗 Vetrina Atleta")
        st.caption("Piattaforma di consultazione dati personali Tindeq")
        st.markdown("</div>", unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            st.markdown("#### 🔐 Accesso Riservato")
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
        st.title("🧗 Vetrina Atleta — Vista Admin")
        col_sel_at, col_sz = st.columns([2, 1])
        with col_sel_at:
            atleta_selezionato = st.selectbox("👤 Seleziona Profilo Atleta:", atleti_lista, key="sel_coach_atleta")
        with col_sz:
            dim_grafico = st.radio("📏 Dimensione Grafici:", ["Compatta (Piccola)", "Standard (Grande)"], horizontal=True, key="sel_dim_grafico")
    else:
        atleta_selezionato = st.session_state.nome_atleta_esatto
        st.title(f"🧗 Vetrina Atleta — {atleta_selezionato}")
        dim_grafico = "Standard (Grande)"

with col_top_out:
    st.write("")
    st.caption(f"👤 **{st.session_state.nome_utente}** ({st.session_state.ruolo})")
    if st.button("🚪 Esci / Logout", key="btn_logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.ruolo = None
        st.session_state.nome_utente = None
        st.session_state.nome_atleta_esatto = None
        st.rerun()

fig_size = (10, 4) if dim_grafico == "Standard (Grande)" else (8, 2.5)
df_atleta = df[df['Atleta'] == atleta_selezionato].sort_values(by='Data_dt').copy()

# ==============================================================================
# 3. KPI BASE IN CIMA (Pull-Up 1RM, Asimmetria %, Endurance 30s)
# ==============================================================================
val_1rm, delta_1rm = None, None
if 'Pull-Up 1RM Calcolata' in df_atleta.columns:
    s_1rm = pd.to_numeric(df_atleta['Pull-Up 1RM Calcolata'].astype(str).str.replace(',', '.'), errors='coerce').dropna()
    if not s_1rm.empty:
        val_1rm = s_1rm.iloc[-1]
        if len(s_1rm) > 1: delta_1rm = val_1rm - s_1rm.iloc[-2]
elif 'Pull-Up 1RM Reale' in df_atleta.columns:
    s_1rm = pd.to_numeric(df_atleta['Pull-Up 1RM Reale'].astype(str).str.replace(',', '.'), errors='coerce').dropna()
    if not s_1rm.empty:
        val_1rm = s_1rm.iloc[-1]
        if len(s_1rm) > 1: delta_1rm = val_1rm - s_1rm.iloc[-2]

val_asim, delta_asim, lato_debole, nome_test_asim = None, None, "", ""
for c_dx, c_sx, t_label in [
    ('Concentrica DX', 'Concentrica SX', 'Concentrica'),
    ('Vertical Pull 120° DX', 'Vertical Pull 120° SX', 'Vertical Pull 120°'),
    ('Eccentrica DX', 'Eccentrica SX', 'Eccentrica'),
    ("Endurance 30'' DX - Picco Max", "Endurance 30'' SX - Picco Max", "Endurance 30'")
]:
    if c_dx in df_atleta.columns and c_sx in df_atleta.columns:
        s_coppia = df_atleta.dropna(subset=[c_dx, c_sx])
        if not s_coppia.empty:
            v_dx_list = pd.to_numeric(s_coppia[c_dx].astype(str).str.replace(',', '.'), errors='coerce').tolist()
            v_sx_list = pd.to_numeric(s_coppia[c_sx].astype(str).str.replace(',', '.'), errors='coerce').tolist()
            if v_dx_list and v_sx_list and v_dx_list[-1] > 0 and v_sx_list[-1] > 0:
                diff_u = abs(v_dx_list[-1] - v_sx_list[-1])
                max_u = max(v_dx_list[-1], v_sx_list[-1])
                val_asim = (diff_u / max_u) * 100
                lato_debole = "DX" if v_dx_list[-1] < v_sx_list[-1] else "SX"
                nome_test_asim = t_label
                if len(v_dx_list) > 1 and v_dx_list[-2] > 0 and v_sx_list[-2] > 0:
                    diff_pen = abs(v_dx_list[-2] - v_sx_list[-2])
                    max_pen = max(v_dx_list[-2], v_sx_list[-2])
                    asim_pen = (diff_pen / max_pen) * 100
                    delta_asim = val_asim - asim_pen
                break

val_end, delta_end = None, None
lato_end = ""
for c in ["Endurance 30'' DX - Forza Media", "Endurance 30'' SX - Forza Media"]:
    if c in df_atleta.columns:
        s_end = pd.to_numeric(df_atleta[c].astype(str).str.replace(',', '.'), errors='coerce').dropna()
        if not s_end.empty and (s_end.iloc[-1] > 0):
            val_end = s_end.iloc[-1]
            lato_end = "DX" if "DX" in c else "SX"
            if len(s_end) > 1 and s_end.iloc[-2] > 0:
                delta_end = val_end - s_end.iloc[-2]
            break

val_conc, delta_conc, lato_conc = None, None, ""
cols_c = [c for c in ['Concentrica DX', 'Concentrica SX'] if c in df_atleta.columns]
if cols_c:
    s_conc_df = df_atleta.dropna(subset=cols_c, how='all')
    if not s_conc_df.empty:
        r_ult = s_conc_df.iloc[-1]
        v_dx = pd.to_numeric(str(r_ult.get('Concentrica DX', 0)).replace(',', '.'), errors='coerce')
        v_sx = pd.to_numeric(str(r_ult.get('Concentrica SX', 0)).replace(',', '.'), errors='coerce')
        val_dx = v_dx if (pd.notna(v_dx) and v_dx > 0) else 0.0
        val_sx = v_sx if (pd.notna(v_sx) and v_sx > 0) else 0.0
        if val_dx > 0 or val_sx > 0:
            val_conc = max(val_dx, val_sx)
            lato_conc = "DX" if val_dx >= val_sx else "SX"
            if len(s_conc_df) > 1:
                r_pen = s_conc_df.iloc[-2]
                p_dx = pd.to_numeric(str(r_pen.get('Concentrica DX', 0)).replace(',', '.'), errors='coerce')
                p_sx = pd.to_numeric(str(r_pen.get('Concentrica SX', 0)).replace(',', '.'), errors='coerce')
                pen_dx = p_dx if (pd.notna(p_dx) and p_dx > 0) else 0.0
                pen_sx = p_sx if (pd.notna(p_sx) and p_sx > 0) else 0.0
                max_pen = max(pen_dx, pen_sx)
                if max_pen > 0:
                    delta_conc = val_conc - max_pen

st.markdown("#### ⚡ Metriche Chiave dell'Ultima Sessione")
col_k1, col_k2, col_k3, col_k4 = st.columns(4)
with col_k1:
    txt_1rm = f"{val_1rm:.1f} kg" if val_1rm is not None else "N/D"
    d_1rm_txt = f"{delta_1rm:+.1f} kg" if delta_1rm is not None else None
    st.metric(
        "🏋️ Pull-Up 1RM",
        txt_1rm,
        delta=d_1rm_txt,
        help="Il tuo massimale teorico calcolato sull'ultimo test."
    )

with col_k2:
    titolo_asim = f"⚖️ Asimmetria ({nome_test_asim})" if nome_test_asim else "⚖️ Asimmetria"
    if val_asim is not None:
        txt_asim = f"{val_asim:.1f}%"
        d_asim_txt = f"{delta_asim:+.1f}% ({lato_debole} debole)" if delta_asim is not None else f"Lato debole: {lato_debole}"
        d_color = "inverse" if val_asim > 10 else "normal"
        st.metric(
            titolo_asim,
            txt_asim,
            delta=d_asim_txt,
            delta_color=d_color,
            help="Differenza percentuale di forza tra braccio destro e sinistro. Sotto il 10% è considerata fisiologica."
        )
    else:
        st.metric(
            titolo_asim,
            "N/D",
            help="Differenza percentuale di forza tra braccio destro e sinistro. Sotto il 10% è considerata fisiologica."
        )

with col_k3:
    txt_end = f"{val_end:.1f} kg" if val_end is not None else "N/D"
    d_end_txt = f"{delta_end:+.1f} kg" if delta_end is not None else None
    titolo_end = f"⏱️ Endurance 30s ({lato_end})" if lato_end else "⏱️ Endurance 30s"
    st.metric(
        titolo_end,
        txt_end,
        delta=d_end_txt,
        help="Forza media mantenuta per 30 secondi continui. Il delta indica la differenza col test precedente."
    )

with col_k4:
    txt_conc = f"{val_conc:.1f} kg" if val_conc is not None else "N/D"
    d_conc_txt = f"{delta_conc:+.1f} kg ({lato_conc})" if delta_conc is not None else (f"Lato: {lato_conc}" if lato_conc else None)
    st.metric(
        "🖐️ Forza Max Dita",
        txt_conc,
        delta=d_conc_txt,
        help="Picco massimale di forza delle dita su tacca (test Concentrica, valore massimo tra DX e SX). Il delta indica la variazione rispetto al test precedente."
    )

st.markdown("---")

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

tab1, tab4, tab5 = st.tabs(["🏆 Record & Best", "📈 Storico Analitico", "🧬 Analisi Avanzata"])

with tab1:
    st.markdown("### 🥇 I Tuoi Record Personali (All-Time)")
    st.markdown("<div class='coach-tip'><b>💡 L'Occhio del Coach:</b> I record più importanti sono quelli relativi al tuo peso corporeo (% BW). Nel Bouldering moderno, un target d'élite è superare l'<b>80% BW</b> di trazione a dito singolo (Concentrica) e il <b>50-60% BW</b> di zavorra nel Pull-up. Un divario troppo alto tra le due evidenzia una debolezza nella trasmissione della forza sulla parete.</div>", unsafe_allow_html=True)
    
    st.markdown("#### 🧗 Specifici (Dita, Trazione, Isometria)")
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
    with st.expander("🏋️ Mostra Misurazioni Manuali e Test Generali (Panca, Squat, Corpo Libero)", expanded=False):
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
    st.markdown("### 💪 Laboratorio Forza (Curve Isometria & RFD)")
    st.markdown("<div class='coach-tip'><b>💡 Pillola Biomeccanica:</b> Una linea che sale molto ripida nei primissimi decimi di secondo indica un eccellente <i>Tasso di Sviluppo della Forza (RFD)</i>. Questa è la famosa 'forza di contatto' che ti permette di tenere le prese in modo dinamico. Una curva tremolante in cima, invece, evidenzia una scarsa stiffness (rigidità) tendinea.</div>", unsafe_allow_html=True)
    
    if file_forza:
        # FIX ORDINAMENTO: Uso la funzione che estrae la data reale
        chiavi_ordinate = sorted(file_forza.keys(), key=estrai_data_per_ordinamento, reverse=True)
        alias_sel = st.selectbox("Seleziona una Curva di Forza (in ordine cronologico):", chiavi_ordinate)
        confronto_bilaterale = st.toggle("⚖️ Sovrapponi Lato Opposto (Confronto DX/SX)", key="toggle_bilaterale_forza")
        if alias_sel:
            file_sel = file_forza[alias_sel]
            df_curva, col_peso, err_msg = leggi_curva_csv(file_sel)
            if df_curva is not None and col_peso in df_curva.columns:
                try:
                    picco_max = df_curva[col_peso].max()
                    val_picco = f"{picco_max:.1f} kg" if pd.notna(picco_max) else "N/D"
                    st.success(f"**⚡ Picco Rilevato:** {val_picco}")
                    
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
                    st.info("ℹ️ Curva non disponibile per questo test (N/D).")
            else:
                st.info("ℹ️ Dati curva non disponibili (N/D).")
    else: st.warning("Nessun test di Forza Specifica trovato nel tuo archivio.")

if False:
    st.markdown("### 🔬 Laboratorio Endurance (Sistemi Energetici)")
    st.markdown("<div class='coach-tip'><b>💡 Fisiologia dell'Arrampicata:</b> Nel test <b>7:3 (Critical Force)</b> cerchiamo il <i>plateau metabolico</i>: la forza media che riesci a mantenere nell'ultimo blocco di ripetizioni. Nel test <b>30s</b>, un crollo repentino della forza (box rossi) indica una scarsa capillarizzazione: il muscolo si acidifica velocemente e le cellule non riescono a smaltire le scorie.</div>", unsafe_allow_html=True)
    
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
        confronto_bilaterale = st.toggle("⚖️ Sovrapponi Lato Opposto (Confronto DX/SX)", key="toggle_bilaterale_endurance")
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
    st.markdown("### 📈 Storico Analitico (Progressioni)")
    st.markdown("<div class='coach-tip'><b>💡 Come Leggere i Grafici:</b> La progressione in <i>Carico Assoluto (kg)</i> mostra la tua forza pura. Seleziona <i>Forza Relativa (% BW)</i> per capire se sei realmente più forte sulla parete, o se l'aumento dei carichi è solo una compensazione di un eventuale aumento di peso corporeo.</div>", unsafe_allow_html=True)
    
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
        if chiave_testo: st.markdown(f"<div class='bio-info-box'><b>ℹ️ Anatomia e Funzione:</b><br>{TESTI_FISIOLOGIA[chiave_testo].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
            
        fig, ax = plt.subplots(figsize=fig_size)
        match_dx = [c for c in df_atleta.columns if c.replace(' DX', '') == test_sel and ' DX' in c]
        match_sx = [c for c in df_atleta.columns if c.replace(' SX', '') == test_sel and ' SX' in c]
        
        def plot_linea(col_nome, colore, label):
            df_plot = df_atleta.dropna(subset=[col_nome])
            if not df_plot.empty:
                y_vals = pd.to_numeric(df_plot[col_nome].astype(str).str.replace(',', '.'), errors='coerce')
                if modalita == "Forza Relativa (% BW)" and 'Peso Corporeo' in df_plot.columns:
                    pesi = pd.to_numeric(df_plot['Peso Corporeo'].astype(str).str.replace(',', '.'), errors='coerce')
                    y_vals = (y_vals / pesi) * 100
                ax.plot(df_plot['Data'], y_vals, marker='o', color=colore, label=label, linewidth=2)
                return df_plot, y_vals
            return None, None
            
        if match_dx and match_sx:
            df_dx, y_dx = plot_linea(match_dx[0], '#3b82f6', 'Lato Destro (DX)')
            df_sx, y_sx = plot_linea(match_sx[0], '#10b981', 'Lato Sinistro (SX)')
            ax.set_ylabel("% BW" if modalita == "Forza Relativa (% BW)" else "Forza (kg)")
            ax.legend(); ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            st.pyplot(fig, use_container_width=True)
        else:
            plot_linea(test_sel, '#3b82f6', test_sel_ui)
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            st.pyplot(fig, use_container_width=True)
            
        with st.expander("📋 Tabella Dati Completa (Record evidenziati in DarkGoldenRod)", expanded=False):
            df_tab4 = df_atleta.drop(columns=['Data_dt', '_Data_Sort'], errors='ignore').dropna(axis=1, how='all').copy()
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
    st.markdown("### 🧬 Analisi Avanzata & Confronti Biomeccanici")
    df_bio = df_atleta.dropna(subset=['Peso Corporeo'])
    
    if not df_bio.empty:
        st.markdown("#### 1. Trazione (Motore) vs Dita (Trasmissione)")
        st.markdown("<div class='coach-tip'><b>💡 Ottimizzazione:</b> Se il Motore (trazione) è molto forte ma la Trasmissione (dita) è bassa, la forza propulsiva viene persa appena la presa si riduce. Cerca di mantenere le due linee in proporzione equilibrata. (Valori in % BW)</div>", unsafe_allow_html=True)
        if 'Pull-Up 1RM Calcolata' in df_bio.columns and 'Concentrica DX' in df_bio.columns:
            df_mvst = df_bio.dropna(subset=['Pull-Up 1RM Calcolata', 'Concentrica DX', 'Concentrica SX'])
            if not df_mvst.empty:
                df_mvst['Motore %'] = (pd.to_numeric(df_mvst['Pull-Up 1RM Calcolata']) / pd.to_numeric(df_mvst['Peso Corporeo'])) * 100
                df_mvst['Trasmissione %'] = (df_mvst[['Concentrica DX', 'Concentrica SX']].astype(float).max(axis=1) / pd.to_numeric(df_mvst['Peso Corporeo'])) * 100
                fig, ax = plt.subplots(figsize=fig_size)
                ax.plot(df_mvst['Data'], df_mvst['Motore %'], label='Motore (Trazione Pull-Up)', marker='o', color='#3b82f6')
                ax.plot(df_mvst['Data'], df_mvst['Trasmissione %'], label='Trasmissione (Concentrica Max Dita)', marker='o', color='#8b5cf6')
                ax.set_ylabel("% Bodyweight"); ax.legend(); ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45, ha='right')
                st.pyplot(fig, use_container_width=True)
        
        st.markdown("#### 2. Prevenzione Infortuni Strutturali")
        st.markdown("<div class='coach-tip'><b>🚨 Alert Clinico:</b> La forza Eccentrica (passiva) rappresenta il 'freno a mano' e la tolleranza limite dei tuoi tendini e pulegge. Se la forza Concentrica (il 'motore' attivo) la supera (o arriva al 95%), l'infortunio è statisticamente molto vicino. In tal caso, si scala il carico e si prescrivono isometrie Yielding per rinforzare i tessuti connettivi.</div>", unsafe_allow_html=True)
        if 'Concentrica DX' in df_bio.columns and 'Eccentrica DX' in df_bio.columns:
            df_inf = df_bio.dropna(subset=['Concentrica DX', 'Concentrica SX', 'Eccentrica DX', 'Eccentrica SX'])
            if not df_inf.empty:
                ult_inf = df_inf.iloc[-1]
                max_conc = max(float(ult_inf['Concentrica DX']), float(ult_inf['Concentrica SX']))
                max_ecc = max(float(ult_inf['Eccentrica DX']), float(ult_inf['Eccentrica SX']))
                
                c1, c2 = st.columns(2)
                c1.metric("Max Concentrica (Attiva)", f"{max_conc} kg")
                c2.metric("Max Eccentrica (Passiva)", f"{max_ecc} kg")
                
                if max_conc >= max_ecc * 0.95: st.error("⚠️ **ALLARME STRUTTURALE:** La forza attiva è vicina/supera la tolleranza passiva.")
                else: st.success("✅ Margine di sicurezza strutturale nella norma.")

        st.markdown("#### 3. Zavorra Inerziale vs Forza Erogata")
        st.markdown("<div class='coach-tip'><b>💡 Rapporto Peso/Potenza:</b> Questa visualizzazione a doppio asse è cruciale. Se la linea verde (Forza) sale, ma sale anche la linea rossa (Peso Corporeo), potresti non sentire reali benefici su roccia. Il miglioramento ideale vede la linea verde salire mentre la rossa resta stabile o scende leggermente.</div>", unsafe_allow_html=True)
        if 'Pull-Up 1RM Calcolata' in df_bio.columns:
            df_fz = df_bio.dropna(subset=['Pull-Up 1RM Calcolata'])
            if not df_fz.empty:
                fig, ax1 = plt.subplots(figsize=fig_size)
                ax2 = ax1.twinx()
                ax1.plot(df_fz['Data'], pd.to_numeric(df_fz['Pull-Up 1RM Calcolata']), marker='o', linestyle='-', label='Forza Erogata (kg)', color='#10b981')
                ax2.plot(df_fz['Data'], pd.to_numeric(df_fz['Peso Corporeo']), marker='s', linestyle='--', label='Peso Corporeo (kg)', color='#ef4444')
                ax1.set_ylabel('Forza (kg)', color='#10b981'); ax2.set_ylabel('Peso Corporeo (kg)', color='#ef4444')
                ax1.grid(True, alpha=0.3)
                plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
                st.pyplot(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 4. Profilo Biomeccanico Atleta (Spider Radar Chart)")
    
    # 1. Estrazione Date Uniche dei test di forza o endurance
    colonne_test_radar = [
        c for c in df_atleta.columns 
        if c not in ['Data', 'DataStr', 'Data_dt', 'Atleta', 'Gruppo', 'Peso Corporeo', 
                     'Braccio (cm)', 'Petto (cm)', 'Addome (cm)', 'Bacino (cm)', 'Coscia (cm)', '_Data_Sort']
    ]
    df_con_test = df_atleta[df_atleta[colonne_test_radar].notna().any(axis=1)].copy()
    date_test = df_con_test['Data'].dropna().unique().tolist()
    if not date_test:
        date_test = df_atleta['Data'].dropna().unique().tolist()
        
    if date_test:
        # 2. Slider Interattivo
        if len(date_test) > 1:
            data_sel = st.select_slider(
                "Scorri la linea del tempo (Evoluzione del Profilo):",
                options=date_test,
                value=date_test[-1],
                key="slider_tempo_radar"
            )
        else:
            data_sel = date_test[0]
            st.caption(f"📅 Rilevazione disponibile: **{data_sel}**")
            
        # 3. Filtro Dinamico fino alla data selezionata inclusa
        if 'Data_dt' in df_atleta.columns and pd.notna(df_atleta['Data_dt']).any():
            dt_limite = pd.to_datetime(data_sel)
            df_radar_filt = df_atleta[df_atleta['Data_dt'] <= dt_limite].copy()
        else:
            df_radar_filt = df_atleta[df_atleta['Data'] <= data_sel].copy()
            
        # Calcolo massimali storici fino a data_sel per le 4 macro-aree (normalizzate su base 100)
        # 1. Trazione Max: target 60% BW = 100 punti
        rec_pull = calcola_record_assoluto('Pull-Up 1RM Calcolata', df_target=df_radar_filt)
        if rec_pull['valore'] == 0:
            rec_pull = calcola_record_assoluto('Pull-Up 1RM Reale', df_target=df_radar_filt)
        score_pull = 0.0
        if rec_pull['valore'] > 0 and rec_pull['bw'] > 0:
            pct_pull = (rec_pull['valore'] / rec_pull['bw']) * 100
            score_pull = min(100.0, max(0.0, (pct_pull / 60.0) * 100))
            
        # 2. Dita Concentrica: target 80% BW = 100 punti
        rec_dita = calcola_record_assoluto('Concentrica', df_target=df_radar_filt)
        score_dita = 0.0
        if rec_dita['valore'] > 0 and rec_dita['bw'] > 0:
            pct_dita = (rec_dita['valore'] / rec_dita['bw']) * 100
            score_dita = min(100.0, max(0.0, (pct_dita / 80.0) * 100))
            
        # 3. Endurance 30s: target 70% BW = 100 punti (o valore max / 50kg)
        rec_end = calcola_record_assoluto("Endurance 30''", df_target=df_radar_filt)
        score_end = 0.0
        if rec_end['valore'] > 0:
            if rec_end['bw'] > 0:
                pct_end = (rec_end['valore'] / rec_end['bw']) * 100
                score_end = min(100.0, max(0.0, (pct_end / 70.0) * 100))
            else:
                score_end = min(100.0, max(0.0, (rec_end['valore'] / 50.0) * 100))
                
        # 4. Esplosività RFD: target 150 kg/s = 100 punti
        rec_rfd = calcola_record_assoluto('RFD Dita', df_target=df_radar_filt)
        score_rfd = 0.0
        if rec_rfd['valore'] > 0:
            score_rfd = min(100.0, max(0.0, (rec_rfd['valore'] / 150.0) * 100))
            
        macro_categorie = ['Trazione (Upper Body)', 'Forza Dita Max', 'Endurance 30s', 'Esplosività RFD']
        punteggi = [round(score_pull, 1), round(score_dita, 1), round(score_end, 1), round(score_rfd, 1)]
        
        # 4. Aggiornamento UI: Radar Chart e Diagnosi Profilo Atleta
        col_rad1, col_rad2 = st.columns([1, 1])
        with col_rad1:
            N = len(macro_categorie)
            angoli = [n / float(N) * 2 * np.pi for n in range(N)]
            punteggi_plot = punteggi + punteggi[:1]
            angoli_plot = angoli + angoli[:1]
            
            fig_r, ax_r = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
            ax_r.set_theta_offset(np.pi / 2)
            ax_r.set_theta_direction(-1)
            plt.xticks(angoli, macro_categorie, color='#0f172a', size=10, weight='bold')
            ax_r.set_rlabel_position(0)
            plt.yticks([25, 50, 75, 100], ['25%', '50%', '75%', '100%'], color='#64748b', size=8)
            plt.ylim(0, 100)
            ax_r.plot(angoli_plot, punteggi_plot, linewidth=2.5, linestyle='solid', color='#2563eb')
            ax_r.fill(angoli_plot, punteggi_plot, color='#3b82f6', alpha=0.25)
            ax_r.scatter(angoli, punteggi, color='#1d4ed8', s=50, zorder=5)
            st.pyplot(fig_r, use_container_width=True)
            
        with col_rad2:
            st.markdown(f"##### 🧭 Diagnosi del Profilo Atleta *(fino al {data_sel})*")
            validi = [(macro_categorie[i], punteggi[i]) for i in range(len(macro_categorie)) if punteggi[i] > 0]
            if validi:
                best_cat, best_val = max(validi, key=lambda x: x[1])
                worst_cat, worst_val = min(validi, key=lambda x: x[1])
                
                st.success(f"🎯 **Punto di Forza:** **{best_cat}** ({best_val:.0f}/100)")
                if 'Endurance' in best_cat:
                    st.caption("Spiccata attitudine alla continuità: eccellente per vie lunghe e tiri ad alto numero di movimenti.")
                elif 'Dita' in best_cat or 'RFD' in best_cat:
                    st.caption("Profilo da boulderista potente: grande tenuta sulle prese piccole e capacità di contatto dinamico esplosivo.")
                else:
                    st.caption("Grande motore di tirata nell'upper body: ideale per compressioni, strapiombi accentuati e movimenti a grande escursione.")
                    
                if worst_val < best_val - 15:
                    st.warning(f"⚠️ **Area di Priorità Allenante:** **{worst_cat}** ({worst_val:.0f}/100)")
                    st.caption("Rappresenta l'anello debole della catena cinetica fino a questo punto temporale. Focalizzare i richiami della fase di condizionamento su questo distretto.")
                else:
                    st.info("⚖️ **Profilo Armonico:** Tutte le macro-aree presentano uno sviluppo equilibrato senza evidenti asimmetrie prestazionali.")
            else:
                st.info(f"Nessun test registrato fino alla data **{data_sel}**. Sposta il cursore verso date più recenti per visualizzare l'evoluzione.")
    else:
        st.info("Nessun dato di test registrato per generare il Profilo Radar.")