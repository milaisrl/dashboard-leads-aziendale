import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import datetime

# --- 1. CONFIGURAZIONE E LOGO ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# Visualizzazione Logo
col_logo, _ = st.columns([1, 4])
with col_logo:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.title("🏠 Domei Intelligence")

# --- 2. COSTANTI E FUNZIONI ---
DATA_INIZIO_STORICA = pd.to_datetime("2025-12-01")

def normalize_key(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# --- 3. SIDEBAR: CARICAMENTO E FILTRI ---
with st.sidebar:
    st.header("📁 Database Excel")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx'])

    st.divider()
    st.header("📅 Periodo di Analisi")
    st.info(f"Analisi bloccata dal: {DATA_INIZIO_STORICA.strftime('%d/%m/%Y')}")
    
    opzione_tempo = st.selectbox("Seleziona intervallo:", 
                                ["Tutto (dal 01/12/25)", "Ultimi 30 giorni", "Ultimi 90 giorni"])

# --- 4. LOGICA DI ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Lettura
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # Conversione Date e Filtro Hard al 01/12/2025
    def filter_date(df):
        col_data = next((c for c in df.columns if 'Data' in c), None)
        if col_data:
            df[col_data] = pd.to_datetime(df[col_data], errors='coerce')
            return df[df[col_data] >= DATA_INIZIO_STORICA]
        return df

    df_a = filter_date(df_a)
    df_s = filter_date(df_s)
    df_o = filter_date(df_o)
    df_c = filter_date(df_c)

    # Ulteriore filtro basato sulla scelta utente
    oggi = pd.Timestamp.now()
    if opzione_tempo == "Ultimi 30 giorni":
        df_a = df_a[df_a.iloc[:,0] >= (oggi - pd.Timedelta(days=30))]
    elif opzione_tempo == "Ultimi 90 giorni":
        df_a = df_a[df_a.iloc[:,0] >= (oggi - pd.Timedelta(days=90))]

    # Matching e Agenti
    df_a['key'] = df_a['Cliente'].apply(normalize_key)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_key)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_key)
    df_o['key'] = df_o['Rag. Soc.'].apply(normalize_key)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_key)

    # Mappa agenti cross-file (per non perdere Daniele)
    map_agente = df_l.set_index('key')['Agente'].to_dict()
    df_a['Agente'] = df_a['key'].map(map_agente).fillna("NON ASSEGNATO")

    # Flag Conversioni
    df_a['S'] = df_a['key'].isin(set(df_s['key']))
    df_a['O'] = df_a['key'].isin(set(df_o['key']))
    df_a['C'] = df_a['key'].isin(set(df_c['key']))

    # --- 5. VISUALIZZAZIONE ---
    agenti = sorted([str(x) for x in df_a['Agente'].unique()])
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    df_final = df_a[df_a['Agente'] == sel_agente]

    # Metriche
    tot_l = len(df_final)
    tot_s = df_final['S'].sum()
    tot_o = df_final['O'].sum()
    tot_c = df_final['C'].sum()

    # Layout Dashboard
    st.markdown(f"### Performance di **{sel_agente}**")
    
    col_met1, col_met2, col_met3 = st.columns(3)
    col_met1.metric("Leads", tot_l)
    col_met2.metric("Sopralluoghi", int(tot_s), f"{int(tot_s/tot_l*100 if tot_l>0 else 0)}% conv.")
    col_met3.metric("Contratti", int(tot_c), f"{int(tot_c/tot_l*100 if tot_l>0 else 0)}% conv.")

    st.divider()

    # FUNNEL GRAFICO
    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [tot_l, tot_s, tot_o, tot_c],
        textinfo = "value+percent initial",
        marker = {"color": ["#11305D", "#1D56A5", "#4A90E2", "#A6CEF7"]} # Colori professionali blu/azzurro
    ))
    fig.update_layout(title_text="Funnel di Conversione", height=450, font=dict(size=14))
    st.plotly_chart(fig, use_container_width=True)

    # TABELLA DETTAGLIO
    with st.expander("🔍 Analisi dettagliata nominativi (Periodo Selezionato)"):
        st.dataframe(
            df_final[['Cliente', 'S', 'O', 'C']].rename(columns={'S':'Sopralluogo', 'O':'Offerta', 'C':'Contratto'}),
            use_container_width=True
        )

else:
    st.warning("⚠️ Caricare tutti i file richiesti per visualizzare l'analisi dal 1 Dicembre 2025.")
