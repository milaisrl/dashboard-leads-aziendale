import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E LOGO ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")
DATA_LIMITE_ASSOLUTA = pd.to_datetime("2025-12-01")

def clean_simple(text):
    if pd.isna(text): return ""
    return str(text).lower().strip()

# Visualizzazione Logo
col_l, col_r = st.columns([1, 3])
with col_l:
    try: st.image("logo.png", use_container_width=True)
    except: st.title("🏠 Domei")

# --- 2. SELETTORE PERIODO ---
with col_r:
    st.write("") # Spaziatore
    opzione_tempo = st.segmented_control(
        "Intervallo di Analisi:",
        ["Ultimi 30 giorni", "Ultimi 90 giorni", "Tutto (dal 01/12/25)"],
        default="Tutto (dal 01/12/25)"
    )

# --- 3. CARICAMENTO ---
with st.sidebar:
    st.header("📁 Database")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx'])
    f_cant = st.file_uploader("5. CANTIERI", type=['xlsx'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Caricamento
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # Definizione Data Inizio in base alla scelta
    oggi = pd.Timestamp.now()
    if "30" in opzione_tempo:
        data_inizio_scelta = oggi - timedelta(days=30)
    elif "90" in opzione_tempo:
        data_inizio_scelta = oggi - timedelta(days=90)
    else:
        data_inizio_scelta = DATA_LIMITE_ASSOLUTA

    # La data finale non può comunque essere precedente al 01/12/2025
    data_filtro = max(data_inizio_scelta, DATA_LIMITE_ASSOLUTA)

    # 4. Filtro Leads
    df_a['Data_DT'] = pd.to_datetime(df_a['Data Inizio'], errors='coerce')
    df_a_filtered = df_a[df_a['Data_DT'] >= data_filtro].copy()
    
    # 5. Mappatura Agenti
    df_l['key_clean'] = df_l['Ragione_sociale'].apply(clean_simple)
    map_agente = df_l.set_index('key_clean')['Agente'].to_dict()
    
    df_a_filtered['key_clean'] = df_a_filtered['Cliente'].apply(clean_simple)
    df_a_filtered['Agente'] = df_a_filtered['key_clean'].map(map_agente).fillna("NON ASSEGNATO")

    # Selezione Agente
    agenti = sorted([str(x) for x in df_a_filtered['Agente'].unique()])
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    df_final = df_a_filtered[df_a_filtered['Agente'] == sel_agente].copy()

    # 6. Matching Intelligente (Contiene)
    nomi_sopr = [clean_simple(n) for n in df_s['Rag. Soc.'].dropna()]
    nomi_offe = [clean_simple(n) for n in df_o['Rag. Soc.'].dropna()]
    nomi_cant = [clean_simple(n) for n in df_c['Rag. Soc.'].dropna()]

    def check_presence(nome_lead, lista_operativa):
        if not nome_lead: return 0
        for n_op in lista_operativa:
            if nome_lead in n_op or n_op in nome_lead: return 1
        return 0

    df_final['S'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_sopr))
    df_final['O'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_offe))
    df_final['C'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_cant))

    # 7. Visualizzazione
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads", len(df_final))
    c2.metric("Sopralluoghi", int(df_final['S'].sum()))
    c3.metric("Offerte", int(df_final['O'].sum()))
    c4.metric("Contratti", int(df_final['C'].sum()))

    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [len(df_final), df_final['S'].sum(), df_final['O'].sum(), df_final['C'].sum()],
        textinfo = "value+percent initial",
        marker = {"color": ["#002147", "#1D56A5", "#4A90E2", "#A6CEF7"]}
    ))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📝 Dettaglio Nominativi Periodo"):
        st.dataframe(df_final[['Data Inizio', 'Cliente', 'S', 'O', 'C']])

else:
    st.info("In attesa del caricamento file...")
