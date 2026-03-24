import streamlit as st
import pandas as pd
import plotly.express as px
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

def clean_name(text):
    if pd.isna(text): return ""
    # Portiamo tutto in minuscolo, rimuoviamo spazi extra e punteggiatura
    t = str(text).lower().strip()
    t = re.sub(r'[^a-z0-9 ]', '', t)
    return t

# --- CARICAMENTO DATI ---
with st.sidebar:
    st.header("📁 Carica i File Aggiornati")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx'])
    f_sopr = st.file_uploader("3. ORDINI SOPRALLUOGO", type=['xlsx'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx'])

if f_anal and f_sopr and f_cant and f_list:
    # Caricamento con gestione nomi colonne specifica per i tuoi file
    df_a = pd.read_excel(f_anal) # Colonna: 'Cliente'
    df_l = pd.read_excel(f_list) # Colonna: 'Ragione_sociale' e 'Agente'
    df_s = pd.read_excel(f_sopr) # Colonna: 'Rag. Soc.'
    df_c = pd.read_excel(f_cant) # Colonna: 'Rag. Soc.'

    # Creazione Chiavi di Collegamento Pulite
    df_a['key'] = df_a['Cliente'].apply(clean_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(clean_name)
    df_s['key'] = df_s['Rag. Soc.'].apply(clean_name)
    df_c['key'] = df_c['Rag. Soc.'].apply(clean_name)

    # Arricchimento Analisi con Agente dalla Lista Leads
    # Usiamo drop_duplicates per evitare di moltiplicare le righe se un lead appare due volte
    df_leads_info = df_l[['key', 'Agente', 'Sorgente']].drop_duplicates('key')
    master = pd.merge(df_a, df_leads_info, on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO")

    # --- CALCOLO PERFORMANCE ---
    # Liste univoche di chi ha fatto sopralluogo o contratto
    set_sopralluoghi = set(df_s['key'].unique())
    set_contratti = set(df_c['key'].unique())

    master['Ha_Sopralluogo'] = master['key'].isin(set_sopralluoghi)
    master['Ha_Contratto'] = master['key'].isin(set_contratti)

    # --- INTERFACCIA ---
    st.title("📊 Dashboard Domei Intelligence")
    
    agente_sel = st.selectbox("Seleziona Agente", sorted(master['Agente'].unique()))
    df_filtered = master[master['Agente'] == agente_sel]

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Leads Totali", len(df_filtered))
    with m2:
        n_sopr = df_filtered['Ha_Sopralluogo'].sum()
        st.metric("Sopralluoghi", int(n_sopr))
    with m3:
        n_cont = df_filtered['Ha_Contratto'].sum()
        st.metric("Contratti", int(n_cont))

    st.divider()
    
    col_sx, col_dx = st.columns(2)
    with col_sx:
        fig_sorg = px.pie(df_filtered, names='Sorgente', title="Provenienza Leads")
        st.plotly_chart(fig_sorg, use_container_width=True)
    
    with col_dx:
        # Tabella di controllo per vedere chi "matcha"
        st.subheader("Dettaglio Conversioni")
        st.dataframe(df_filtered[[ 'Cliente', 'Ha_Sopralluogo', 'Ha_Contratto']].head(20))

else:
    st.warning("Carica tutti i file richiesti per attivare i calcoli.")
