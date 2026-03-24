import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")
DATA_START = pd.to_datetime("2025-12-01")

def clean_simple(text):
    if pd.isna(text): return ""
    return str(text).lower().strip()

# --- LOGO ---
try: st.image("logo.png", width=200)
except: st.title("🏠 Domei Intelligence")

# --- CARICAMENTO ---
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

    # 1. Filtro temporale sui LEADS (quelli nati dal 1 Dicembre)
    df_a['Data_DT'] = pd.to_datetime(df_a['Data Inizio'], errors='coerce')
    df_a_filtered = df_a[df_a['Data_DT'] >= DATA_START].copy()
    
    # 2. Mappatura Agenti (dalla lista leads)
    df_l['key_clean'] = df_l['Ragione_sociale'].apply(clean_simple)
    map_agente = df_l.set_index('key_clean')['Agente'].to_dict()
    
    df_a_filtered['key_clean'] = df_a_filtered['Cliente'].apply(clean_simple)
    df_a_filtered['Agente'] = df_a_filtered['key_clean'].map(map_agente).fillna("NON ASSEGNATO")

    # 3. Selezione Agente
    agenti = sorted([str(x) for x in df_a_filtered['Agente'].unique()])
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    df_final = df_a_filtered[df_a_filtered['Agente'] == sel_agente].copy()

    # 4. LOGICA DI MATCHING "INTELLIGENTE" (Contiene)
    # Creiamo liste di nomi dai file operativi
    nomi_sopr = [clean_simple(n) for n in df_s['Rag. Soc.'].dropna()]
    nomi_offe = [clean_simple(n) for n in df_o['Rag. Soc.'].dropna()]
    nomi_cant = [clean_simple(n) for n in df_c['Rag. Soc.'].dropna()]

    def check_presence(nome_lead, lista_operativa):
        if not nome_lead: return 0
        # Se il nome del lead è contenuto in una qualsiasi riga del file operativo (o viceversa)
        for n_op in lista_operativa:
            if nome_lead in n_op or n_op in nome_lead:
                return 1
        return 0

    # Applichiamo il controllo
    with st.spinner('Calcolando conversioni...'):
        df_final['S'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_sopr))
        df_final['O'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_offe))
        df_final['C'] = df_final['key_clean'].apply(lambda x: check_presence(x, nomi_cant))

    # 5. METRICHE
    n_leads = len(df_final)
    n_sopr = df_final['S'].sum()
    n_offe = df_final['O'].sum()
    n_cant = df_final['C'].sum()

    # --- VISUALIZZAZIONE ---
    st.markdown(f"### Performance: **{sel_agente}** (Dal 01/12/2025)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads", n_leads)
    c2.metric("Sopralluoghi", int(n_sopr))
    c3.metric("Offerte", int(n_offe))
    c4.metric("Contratti", int(n_cant))

    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [n_leads, n_sopr, n_offe, n_cant],
        textinfo = "value+percent initial",
        marker = {"color": ["#002147", "#1D56A5", "#4A90E2", "#A6CEF7"]}
    ))
    st.plotly_chart(fig, use_container_width=True)

    # TABELLA DI CONTROLLO
    st.subheader("Dettaglio Analisi Nominativi")
    st.write("Se vedi uno '0' dove dovrebbe esserci '1', significa che il nome è scritto in modo troppo diverso nei due file.")
    st.dataframe(df_final[['Cliente', 'S', 'O', 'C']].rename(columns={'S':'Sopralluogo','O':'Offerta','C':'Contratto'}))

else:
    st.info("Carica i file per generare il funnel corretto.")
