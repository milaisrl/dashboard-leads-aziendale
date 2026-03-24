import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")
DATA_START = pd.to_datetime("2025-12-01")

def clean_key(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# --- LOGO ---
try: st.image("logo.png", width=200)
except: st.title("🏠 Domei Intelligence")

# --- CARICAMENTO ---
with st.sidebar:
    st.header("📁 Carica Database")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Lettura
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # 1. Pulizia Date e Filtro Lead (La base di tutto)
    # Usiamo la colonna 'Data Inizio' per il file ANALISI
    df_a['Data_DT'] = pd.to_datetime(df_a['Data Inizio'], errors='coerce')
    df_a_filtered = df_a[df_a['Data_DT'] >= DATA_START].copy()
    
    # 2. Creazione Chiavi Univoche
    df_a_filtered['key'] = df_a_filtered['Cliente'].apply(clean_key)
    df_l['key'] = df_l['Ragione_sociale'].apply(clean_key)
    
    # Creiamo set di chiavi per Sopralluoghi, Offerte e Cantieri (senza filtri data qui, 
    # perché un lead di dicembre può avere un cantiere a febbraio)
    set_sopr = set(df_s['Rag. Soc.'].apply(clean_key).unique())
    set_offe = set(df_o['Rag. Soc.'].apply(clean_key).unique())
    set_cant = set(df_c['Rag. Soc.'].apply(clean_key).unique())

    # 3. Mappatura Agente da LISTA LEADS
    map_agente = df_l.set_index('key')['Agente'].to_dict()
    df_a_filtered['Agente'] = df_a_filtered['key'].map(map_agente).fillna("NON ASSEGNATO")

    # 4. Selezione Agente
    agenti = sorted([str(x) for x in df_a_filtered['Agente'].unique()])
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    
    # Filtriamo il dataframe finale
    df_final = df_a_filtered[df_a_filtered['Agente'] == sel_agente].copy()

    # 5. CONTEGGIO REALE (Per riga di lead)
    # Verifichiamo per ogni lead se ha generato le fasi successive
    df_final['Ha_Sopr'] = df_final['key'].apply(lambda x: 1 if x in set_sopr else 0)
    df_final['Ha_Offe'] = df_final['key'].apply(lambda x: 1 if x in set_offe else 0)
    df_final['Ha_Cant'] = df_final['key'].apply(lambda x: 1 if x in set_cant else 0)

    # Metriche Finali
    n_leads = len(df_final)
    n_sopr = df_final['Ha_Sopr'].sum()
    n_offe = df_final['Ha_Offe'].sum()
    n_cant = df_final['Ha_Cant'].sum()

    # --- UI ---
    st.markdown(f"### Performance Reali: **{sel_agente}** (Dal 01/12/2025)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads", n_leads)
    c2.metric("Sopralluoghi", int(n_sopr))
    c3.metric("Offerte", int(n_offe))
    c4.metric("Contratti", int(n_cant))

    # Funnel con ordine logico decrescente
    fig = go.Figure(go.Funnel(
        y = ["Leads", "Sopralluoghi", "Offerte", "Contratti"],
        x = [n_leads, n_sopr, n_offe, n_cant],
        textinfo = "value+percent initial",
        marker = {"color": ["#002147", "#003366", "#004080", "#0052A5"]}
    ))
    st.plotly_chart(fig, use_container_width=True)

    # Tabella di Verifica
    with st.expander("📝 Verifica i nomi dei Lead e le conversioni"):
        st.dataframe(df_final[['Cliente', 'Ha_Sopr', 'Ha_Offe', 'Ha_Cant']])

else:
    st.info("Carica i file per correggere il funnel.")
