import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime

# --- 1. CONFIGURAZIONE E COSTANTI ---
st.set_page_config(page_title="Domei Intelligence Pro", layout="wide")
DATA_START_REPORT = pd.to_datetime("2025-12-01")

def clean_name(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# Visualizzazione Logo
try:
    st.image("logo.png", width=200)
except:
    st.title("🏠 Domei Intelligence")

# --- 2. CARICAMENTO DATI (TUTTI I 6 FILE) ---
with st.sidebar:
    st.header("📁 Database Integrato")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS (Anagrafica)", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO DARVEL", type=['xlsx', 'csv'])
    
    st.divider()
    periodo_scelto = st.selectbox("Intervallo Analisi", ["Dal 01/12/2025 ad oggi", "Ultimi 30 giorni"])

# --- 3. ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    # Lettura (gestione automatica csv/xlsx)
    def load_df(f):
        if f.name.endswith('.csv'): return pd.read_csv(f)
        return pd.read_excel(f)

    df_a = load_df(f_anal)
    df_l = load_df(f_list)
    df_s = load_df(f_sopr)
    df_o = load_df(f_offe)
    df_c = load_df(f_cant)
    df_f = load_df(f_fatt)

    # Normalizzazione Date
    for df in [df_s, df_o, df_c, df_f]:
        col_d = next((c for c in df.columns if 'Data' in c or 'Giorno' in c), df.columns[0])
        df['Date_DT'] = pd.to_datetime(df[col_d], errors='coerce')

    # Filtro temporale per i risultati (non per i lead!)
    start_date = DATA_START_REPORT if "01/12" in periodo_scelto else (pd.Timestamp.now() - pd.Timedelta(days=30))
    
    df_s_p = df_s[df_s['Date_DT'] >= start_date]
    df_o_p = df_o[df_o['Date_DT'] >= start_date]
    df_c_p = df_c[df_c['Date_DT'] >= start_date]
    df_f_p = df_f[df_f['Date_DT'] >= start_date]

    # Matching Keys
    df_l['key'] = df_l['Ragione_sociale'].apply(clean_name)
    set_s = set(df_s_p['Rag. Soc.'].apply(clean_name).unique())
    set_o = set(df_o_p['Rag. Soc.'].apply(clean_name).unique())
    set_c = set(df_c_p['Rag. Soc.'].apply(clean_name).unique())
    
    # Mappa Fatturato (Totale imponibile per cliente dal 1 Dicembre)
    df_f_p['key'] = df_f_p.iloc[:, 1].apply(clean_name) # Assumendo Cliente in seconda colonna
    # Cerchiamo colonna importo (Imponibile)
    col_imp = next((c for c in df_f_p.columns if 'Imponibile' in c or 'Totale' in c), df_f_p.columns[-1])
    map_fatturato = df_f_p.groupby('key')[col_imp].sum().to_dict()

    # --- 4. ANALISI PER AGENTE ---
    # Usiamo LISTA LEADS come base per gli agenti
    agenti = sorted([str(x) for x in df_l['Agente'].unique() if pd.notna(x)])
    sel_agente = st.selectbox("👤 Seleziona Agente", agenti)
    
    # Lead dell'agente (tutti, anche quelli vecchi di maggio)
    leads_agente = df_l[df_l['Agente'] == sel_agente].copy()
    
    # Calcolo Metriche
    leads_agente['S'] = leads_agente['key'].isin(set_s)
    leads_agente['O'] = leads_agente['key'].isin(set_o)
    leads_agente['C'] = leads_agente['key'].isin(set_c)
    leads_agente['Fatt'] = leads_agente['key'].map(map_fatturato).fillna(0)

    n_l = len(leads_agente)
    n_s = leads_agente['S'].sum()
    n_o = leads_agente['O'].sum()
    n_c = leads_agente['C'].sum()
    val_fatt = leads_agente['Fatt'].sum()

    # --- 5. DASHBOARD ---
    st.header(f"Report Performance: {sel_agente}")
    st.caption(f"Analisi dei risultati dal {start_date.strftime('%d/%m/%Y')} su tutto il database Leads")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Leads Totali", n_l)
    m2.metric("Sopralluoghi", int(n_s))
    m3.metric("Offerte", int(n_o))
    m4.metric("Contratti", int(n_c))
    m5.metric("Fatturato Reale", f"€ {val_fatt:,.2f}")

    st.divider()

    # Funnel Grafico
    fig = go.Figure(go.Funnel(
        y = ["Leads Assegnati", "Sopralluoghi", "Offerte", "Contratti"],
        x = [n_l, n_s, n_o, n_c],
        textinfo = "value+percent initial",
        marker = {"color": ["#11305D", "#1D56A5", "#4A90E2", "#A6CEF7"]}
    ))
    st.plotly_chart(fig, use_container_width=True)

    # Tabella Dettaglio
    with st.expander("🔍 Dettaglio Clienti e Incassi (Periodo Selezionato)"):
        df_display = leads_agente[leads_agente['S'] | leads_agente['O'] | leads_agente['C'] | (leads_agente['Fatt'] > 0)]
        st.dataframe(df_display[['Ragione_sociale', 'S', 'O', 'C', 'Fatt']].rename(
            columns={'S':'Sopralluogo', 'O':'Offerta', 'C':'Cantiere', 'Fatt':'Fatturato €'}
        ), use_container_width=True)

else:
    st.warning("⚠️ Caricare tutti i 6 file richiesti per sbloccare l'analisi economica completa.")
