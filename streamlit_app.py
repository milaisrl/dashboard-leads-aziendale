import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE E LOGO ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# Visualizzazione Logo
try:
    st.image("logo.png", width=200)
except:
    st.title("🏠 Domei Intelligence") # Fallback se il file manca

# --- 2. FUNZIONI TECNICHE ---
def normalize_key(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# --- 3. SIDEBAR: CARICAMENTO E FILTRI ---
with st.sidebar:
    st.header("📁 Database")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx'])
    f_cant = st.file_uploader("5. CANTIERI", type=['xlsx'])

    st.divider()
    st.header("📅 Periodo di Analisi")
    opzione_tempo = st.radio("Seleziona intervallo:", ["Mensile", "Trimestrale", "Annuale", "Tutto lo storico"])

# --- 4. LOGICA DI ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Lettura
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # Conversione Date (Assumendo colonna 'Data' o 'Data Inizio')
    for df in [df_a, df_s, df_o, df_c]:
        col_data = next((c for c in df.columns if 'Data' in c), None)
        if col_data:
            df[col_data] = pd.to_datetime(df[col_data], errors='coerce')

    # Filtro Temporale
    oggi = datetime.now()
    if opzione_tempo == "Mensile":
        inizio = oggi.replace(day=1)
    elif opzione_tempo == "Trimestrale":
        inizio = oggi - timedelta(days=90)
    elif opzione_tempo == "Annuale":
        inizio = oggi.replace(month=1, day=1)
    else:
        inizio = datetime(2000, 1, 1)

    # Applichiamo il filtro (sul file Analisi che genera i Lead)
    col_data_a = next((c for c in df_a.columns if 'Data' in c), df_a.columns[0])
    df_a = df_a[df_a[col_data_a] >= inizio]

    # Matching e Agenti (Logica rinforzata)
    df_a['key'] = df_a['Cliente'].apply(normalize_key)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_key)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_key)
    df_o['key'] = df_o['Rag. Soc.'].apply(normalize_key)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_key)

    map_agente = df_l.set_index('key')['Agente'].to_dict()
    df_a['Agente'] = df_a['key'].map(map_agente).fillna("NON ASSEGNATO")

    # Flag Conversioni
    df_a['S'] = df_a['key'].isin(set(df_s['key']))
    df_a['O'] = df_a['key'].isin(set(df_o['key']))
    df_a['C'] = df_a['key'].isin(set(df_c['key']))

    # --- 5. VISUALIZZAZIONE ---
    # Selezione Agente
    agenti = sorted(df_a['Agente'].unique())
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    df_final = df_a[df_a['Agente'] == sel_agente]

    # Metriche
    tot_l = len(df_final)
    tot_s = df_final['S'].sum()
    tot_o = df_final['O'].sum()
    tot_c = df_final['C'].sum()

    st.subheader(f"Performance di {sel_agente}")
    
    # GRAFICO FUNNEL
    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [tot_l, tot_s, tot_o, tot_c],
        textinfo = "value+percent initial",
        marker = {"color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]}
    ))
    fig.update_layout(title_text="Funnel di Conversione", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Dettaglio Tabellare
    with st.expander("🔍 Vedi Elenco Clienti Dettagliato"):
        st.dataframe(df_final[['Cliente', 'S', 'O', 'C']], use_container_width=True)

else:
    st.info("Carica i 5 file Excel per visualizzare il Funnel e le statistiche.")
