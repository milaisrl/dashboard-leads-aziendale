import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E LOGO ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")
DATA_MINIMA = pd.to_datetime("2025-12-01")

try:
    st.image("logo.png", width=200)
except:
    st.title("🏠 Domei Intelligence")

# --- 2. SELETTORE PERIODO (Sempre visibile in alto) ---
st.write("### Analisi Performance")
col_p1, col_p2 = st.columns([2, 2])
with col_p1:
    opzione_tempo = st.selectbox(
        "Seleziona l'intervallo temporale:",
        ["Tutto lo storico (dal 01/12/25)", "Ultimi 30 giorni", "Ultimi 90 giorni"]
    )

# --- 3. CARICAMENTO ---
with st.sidebar:
    st.header("📁 Carica i tuoi Excel")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS (Anagrafica)", type=['xlsx'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx'])
    f_cant = st.file_uploader("5. CANTIERI", type=['xlsx'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Lettura
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # Definizione Data Inizio
    oggi = pd.Timestamp.now()
    if "30" in opzione_tempo: data_inizio = oggi - timedelta(days=30)
    elif "90" in opzione_tempo: data_inizio = oggi - timedelta(days=90)
    else: data_inizio = DATA_MINIMA
    
    # Protezione: non andare mai prima del 01/12/25
    data_inizio = max(data_inizio, DATA_MINIMA)

    # --- 4. FILTRO PER AGENTE (Basato sui file operativi) ---
    # Prendiamo tutti gli agenti unici che appaiono nei vari file
    tutti_agenti = sorted(list(set(df_l['Agente'].dropna().unique()) | set(df_s['Creato da'].dropna().unique())))
    with col_p2:
        sel_agente = st.selectbox("👤 Seleziona l'Agente da analizzare:", tutti_agenti)

    # --- 5. LOGICA DI CONTEGGIO PURA (Senza incroci rischiosi) ---
    # Funzione per filtrare ogni DF per data e agente
    def filtra(df, col_data, col_agente, data_limite, agente_nome):
        df[col_data] = pd.to_datetime(df[col_data], errors='coerce')
        # Filtro Data
        temp = df[df[col_data] >= data_limite]
        # Filtro Agente (cerchiamo il nome dell'agente nel campo dedicato)
        # Usiamo 'str.contains' per gestire nomi parziali o maiuscole
        cognome_agente = agente_nome.split()[-1].upper()
        return temp[temp[col_agente].astype(str).str.upper().str.contains(cognome_agente, na=False)]

    # Conteggi reali estratti dai singoli file
    leads_periodo = filtra(df_l, 'Agente', 'Agente', data_inizio, sel_agente) # Qui usiamo un'altra logica per i leads
    # Nota: Per i LEADS usiamo il file LISTA LEADS o ANALISI? 
    # Usiamo LISTA LEADS filtrato per agente (i lead totali assegnati)
    n_leads = len(df_l[df_l['Agente'] == sel_agente])
    
    # Per Sopralluoghi, Offerte e Cantieri usiamo la colonna 'Creato da' e la data del file
    n_sopr = len(filtra(df_s, 'Data', 'Creato da', data_inizio, sel_agente))
    n_offe = len(filtra(df_o, 'Data', 'Creato da', data_inizio, sel_agente))
    n_cant = len(filtra(df_c, 'Data', 'Creato da', data_inizio, sel_agente))

    # --- 6. VISUALIZZAZIONE ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Leads Totali", n_leads)
    m2.metric("Sopralluoghi", n_sopr)
    m3.metric("Offerte", n_offe)
    m4.metric("Contratti", n_cant)

    # Funnel
    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [n_leads, n_sopr, n_offe, n_cant],
        textinfo = "value+percent initial",
        marker = {"color": ["#11305D", "#1D56A5", "#4A90E2", "#A6CEF7"]}
    ))
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Tabella Dettaglio (per verifica immediata)
    st.write(f"### Dettaglio attività di {sel_agente} nel periodo")
    tab1, tab2, tab3 = st.tabs(["Sopralluoghi", "Offerte", "Cantieri"])
    with tab1:
        st.dataframe(filtra(df_s, 'Data', 'Creato da', data_inizio, sel_agente)[['Data', 'Rag. Soc.', 'Comune']], use_container_width=True)
    with tab2:
        st.dataframe(filtra(df_o, 'Data', 'Creato da', data_inizio, sel_agente)[['Data', 'Rag. Soc.', 'Totale']], use_container_width=True)
    with tab3:
        st.dataframe(filtra(df_c, 'Data', 'Creato da', data_inizio, sel_agente)[['Data', 'Rag. Soc.', 'Totale']], use_container_width=True)

else:
    st.warning("Carica tutti i file per visualizzare i dati corretti.")
