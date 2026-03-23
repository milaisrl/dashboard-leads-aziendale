import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="CRM & Marketing Analytics", layout="wide")

# --- 1. GESTIONE BUDGET STORICO ---
# In un'app reale questi dati andrebbero su un database. 
# Per ora, li gestiamo con una tabella modificabile nella sidebar.
with st.sidebar:
    st.header("💰 Archivio Spese Pubblicitarie")
    st.info("Inserisci il budget speso per ogni mese per calcolare il CPL storico.")
    
    # Creiamo una tabella predefinita per i mesi
    if 'budget_data' not in st.session_state:
        st.session_state.budget_data = pd.DataFrame([
            {"Mese": "2025-10", "Budget": 1000.0},
            {"Mese": "2025-11", "Budget": 1000.0},
            {"Mese": "2025-12", "Budget": 1000.0},
            {"Mese": "2026-01", "Budget": 1000.0},
            {"Mese": "2026-02", "Budget": 1000.0},
            {"Mese": "2026-03", "Budget": 1000.0},
        ])
    
    edited_budget = st.data_editor(st.session_state.budget_data, num_rows="dynamic")
    st.session_state.budget_data = edited_budget

# --- 2. FUNZIONI DI PULIZIA ---
def normalize_name(name):
    if pd.isna(name): return ""
    s = re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip()
    return " ".join(sorted(s.split()))

def clean_currency(value):
    if pd.isna(value): return 0.0
    if isinstance(value, str):
        value = value.replace('.', '').replace(',', '.')
    try: return float(value)
    except: return 0.0

# --- 3. CARICAMENTO E UNIFICAZIONE ---
st.title("📊 Dashboard Analitica Globale vs Mensile")

with st.expander("📁 Carica i File Storici (Analisi, Leads, Sopralluoghi, Offerte, Cantieri, Fatturato)"):
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        # Cerchiamo una colonna data per il raggruppamento temporale
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    # Caricamento
    df_a = load(f_anal)
    df_l = load(f_list)
    df_s = load(f_sopr)
    df_o = load(f_offe)
    df_c = load(f_cant)
    df_f = load(f_fatt)

    # Chiavi e Pulizia
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_name)
    
    # Fatturato con pulizia specifica
    df_f['key'] = df_f['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)

    # Merge Master
    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, df_l.drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # Marcatori
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    master['Fatturato'] = master['key'].map(df_f.groupby('key')['Valore_Netto'].sum()).fillna(0)
    master['Agente'] = master['Agente'].fillna("NEW DDL DI DE LORENZI DANIELE" if master['Sopralluogo'].any() else "DA ASSEGNARE")

    # --- 4. SELETTORE PERIODO ---
    periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
    scelta = st.selectbox("Seleziona Periodo di Analisi", ["TUTTO LO STORICO"] + periodi)

    if scelta == "TUTTO LO STORICO":
        df_view = master
        budget_tot = st.session_state.budget_data['Budget'].sum()
    else:
        df_view = master[master['Mese_Anno'] == scelta]
        budget_tot = st.session_state.budget_data[st.session_state.budget_data['Mese'] == scelta]['Budget'].sum()

    # --- 5. VISUALIZZAZIONE KPI ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Leads nel Periodo", len(df_view))
    m2.metric("Sopralluoghi", int(df_view['Sopralluogo'].sum()))
    
    cpl = round(budget_tot / len(df_view), 2) if len(df_view) > 0 else 0
    m3.metric("CPL (Costo per Lead)", f"{cpl} €")
    
    fatt_periodo = df_view['Fatturato'].sum() if scelta != "TUTTO LO STORICO" else df_f['Valore_Netto'].sum()
    m4.metric("Fatturato Periodo", f"{fatt_periodo:,.2f} €")

    # --- 6. GRAFICI ---
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("Performance Agenti")
        perf_agente = df_view.groupby('Agente').agg({'key': 'count', 'Sopralluogo': 'sum', 'Fatturato': 'sum'}).reset_index()
        st.plotly_chart(px.bar(perf_agente, x='Agente', y='key', title="Volume Leads"), use_container_width=True)
    
    with c_right:
        st.subheader("Trend Mensile (Leads vs Budget)")
        trend = master.groupby('Mese_Anno').size().reset_index(name='Leads')
        st.plotly_chart(px.line(trend, x='Mese_Anno', y='Leads', title="Andamento Temporale"), use_container_width=True)

    st.subheader("Dettaglio Analisi Economica")
    st.dataframe(perf_agente.style.format({'Fatturato': '{:,.2f} €'}), use_container_width=True)

else:
    st.info("👋 Carica i file storici per generare l'analisi globale e mensile.")
