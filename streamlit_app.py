import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence Pro", layout="wide")
DATA_LIMITE_SISTEMA = pd.to_datetime("2025-12-01")

def clean_key(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# Funzione di caricamento robusta
def load_data(file_obj):
    if file_obj is None:
        return None
    try:
        # Prova prima Excel, se fallisce prova CSV
        if file_obj.name.endswith('.csv'):
            return pd.read_csv(file_obj)
        else:
            return pd.read_excel(file_obj)
    except Exception as e:
        st.error(f"Errore nel caricamento di {file_obj.name}: {e}")
        return None

# Logo
try: st.image("logo.png", width=200)
except: st.title("🏠 Domei Intelligence")

# --- 2. SELETTORI IN ALTO ---
st.write("---")
col_p1, col_p2 = st.columns([2, 2])
with col_p1:
    opzione_tempo = st.selectbox(
        "Seleziona intervallo di analisi:",
        ["Tutto lo storico (dal 01/12/25)", "Ultimi 30 giorni", "Ultimi 90 giorni"],
        key="temp_select"
    )

# --- 3. SIDEBAR PER CARICAMENTO ---
with st.sidebar:
    st.header("📁 Carica i 6 File")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO DARVEL", type=['xlsx', 'csv'])

# --- 4. ELABORAZIONE ---
if f_anal and f_list and f_sopr and f_offe and f_cant and f_fatt:
    # Caricamento individuale per evitare NameError in riga unica
    df_a = load_data(f_anal)
    df_l = load_data(f_list)
    df_s = load_data(f_sopr)
    df_o = load_data(f_offe)
    df_c = load_data(f_cant)
    df_f = load_data(f_fatt)

    if all(df is not None for df in [df_a, df_l, df_s, df_o, df_c, df_f]):
        
        # Logica Data
        oggi = pd.Timestamp.now()
        if "30" in opzione_tempo: data_inizio = oggi - timedelta(days=30)
        elif "90" in opzione_tempo: data_inizio = oggi - timedelta(days=90)
        else: data_inizio = DATA_LIMITE_SISTEMA
        data_inizio = max(data_inizio, DATA_LIMITE_SISTEMA)

        # Pulizia e Date
        for df in [df_s, df_o, df_c, df_f]:
            col_d = next((c for c in df.columns if any(x in c for x in ['Data', 'Giorno', 'Documento'])), df.columns[0])
            df['DT_LOGIC'] = pd.to_datetime(df[col_d], errors='coerce', dayfirst=True)

        # Filtri Temporali
        df_s_p = df_s[df_s['DT_LOGIC'] >= data_inizio]
        df_o_p = df_o[df_o['DT_LOGIC'] >= data_inizio]
        df_c_p = df_c[df_c['DT_LOGIC'] >= data_inizio]
        df_f_p = df_f[df_f['DT_LOGIC'] >= data_inizio].copy()

        # Rilevamento Colonna Soldi (Fatturato)
        col_soldi = next((c for c in df_f_p.columns if any(x in c.lower() for x in ['imponibile', 'totale', 'importo', 'netto'])), None)
        if col_soldi:
            df_f_p[col_soldi] = pd.to_numeric(df_f_p[col_soldi].astype(str).str.replace('.','').str.replace(',','.').str.replace('€','').str.strip(), errors='coerce').fillna(0)
        
        # Chiavi Match
        df_l['key'] = df_l['Ragione_sociale'].apply(clean_key)
        set_s = set(df_s_p['Rag. Soc.'].apply(clean_key).unique())
        set_o = set(df_o_p['Rag. Soc.'].apply(clean_key).unique())
        set_c = set(df_c_p['Rag. Soc.'].apply(clean_key).unique())
        
        col_cli_f = next((c for c in df_f_p.columns if any(x in c.lower() for x in ['ragione', 'cliente'])), df_f_p.columns[1])
        df_f_p['key'] = df_f_p[col_cli_f].apply(clean_key)
        map_soldi = df_f_p.groupby('key')[col_soldi].sum().to_dict() if col_soldi else {}

        # Selezione Agente
        agenti = sorted([str(x) for x in df_l['Agente'].unique() if pd.notna(x)])
        with col_p2:
            sel_agente = st.selectbox("👤 Agente:", agenti, key="agente_select")

        # Calcoli
        leads_agente = df_l[df_l['Agente'] == sel_agente].copy()
        leads_agente['S'] = leads_agente['key'].isin(set_s)
        leads_agente['O'] = leads_agente['key'].isin(set_o)
        leads_agente['C'] = leads_agente['key'].isin(set_c)
        leads_agente['Soldi'] = leads_agente['key'].map(map_soldi).fillna(0)

        # --- UI FINALE ---
        st.divider()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Leads", len(leads_agente))
        m2.metric("Sopralluoghi", int(leads_agente['S'].sum()))
        m3.metric("Offerte", int(leads_agente['O'].sum()))
        m4.metric("Contratti", int(leads_agente['C'].sum()))
        m5.metric("Fatturato Reale", f"€ {leads_agente['Soldi'].sum():,.2f}")

        fig = go.Figure(go.Funnel(
            y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
            x = [len(leads_agente), leads_agente['S'].sum(), leads_agente['O'].sum(), leads_agente['C'].sum()],
            textinfo = "value+percent initial",
            marker = {"color": ["#002147", "#1D56A5", "#4A90E2", "#A6CEF7"]}
        ))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📝 Dettaglio Clienti e Incassi"):
            st.dataframe(leads_agente[leads_agente['S'] | leads_agente['O'] | leads_agente['C'] | (leads_agente['Soldi'] > 0)][['Ragione_sociale', 'S', 'O', 'C', 'Soldi']])

else:
    st.info("👋 Carica i 6 file richiesti nella sidebar per visualizzare i dati.")
