import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")

st.title("📊 Analisi Performance Leads")

# --- FUNZIONI DI SUPPORTO ---
def clean_name(name):
    if pd.isna(name): return ""
    return str(name).strip().lower()

def clean_currency(value):
    if pd.isna(value): return 0.0
    if isinstance(value, str):
        # Toglie i punti delle migliaia e cambia la virgola in punto decimale
        value = value.replace('.', '').replace(',', '.')
    try:
        return float(value)
    except:
        return 0.0

# --- SIDEBAR ---
with st.sidebar:
    st.header("Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS (Sorgenti)", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])
    st.divider()
    investimento = st.number_input("Investimento Pubblicitario (€)", min_value=0.0, value=1000.0)

# --- ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load(file):
        if file.name.endswith('.csv'): 
            df = pd.read_csv(file, sep=None, engine='python')
        else:
            df = pd.read_excel(file)
        return df.dropna(how='all') # Rimuove righe totalmente vuote

    df_a = load(f_anal)
    df_l = load(f_list)
    df_s = load(f_sopr)
    df_o = load(f_offe)
    df_c = load(f_cant)
    df_f = load(f_fatt)

    # Pulizia nomi colonne (rimuove spazi extra)
    for df in [df_a, df_l, df_s, df_o, df_c, df_f]:
        df.columns = df.columns.astype(str).str.strip()

    # Creazione chiavi di ricerca basate sui nomi reali delle colonne dei tuoi file
    df_a['key'] = df_a['Cliente'].apply(clean_name)
    df_a = df_a[df_a['Tipo'] != 'WF Contatto cliente'] # Filtro richiesto

    df_l['key'] = df_l['Ragione_sociale'].apply(clean_name)
    
    for df in [df_s, df_o, df_c]:
        df['key'] = df['Rag. Soc.'].apply(clean_name)

    # Gestione speciale per il file Fatturato (pulisce nomi come "AZIENDA [CI-123]")
    col_conto = 'Descrizione conto'
    df_f['key'] = df_f[col_conto].apply(lambda x: clean_name(str(x).split('[')[0]))
    
    # Identifica colonna soldi (Imponibile o Totale)
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Pulito'] = df_f[col_soldi].apply(clean_currency)

    # --- INCROCIO DATI (MERGE) ---
    # Uniamo Analisi con Lista Leads per avere Agente e Sorgente
    master = pd.merge(df_a, df_l[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna('FUORI ZONA')
    master['Sorgente'] = master['Sorgente'].fillna('Sconosciuta')
    
    # Verifichiamo passaggi successivi
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    master['Offerta'] = master['key'].isin(df_o['key'].unique())
    master['Cantiere'] = master['key'].isin(df_c['key'].unique())

    # Aggreghiamo il fatturato reale per cliente
    fatt_per_cliente = df_f.groupby('key')['Valore_Pulito'].sum().reset_index()
    master = pd.merge(master, fatt_per_cliente, on='key', how='left').fillna(0)

    # --- VISUALIZZAZIONE KPI ---
    num_leads = len(master)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads Ricevuti", num_leads)
    c2.metric("Sopralluoghi Fatti", int(master['Sopralluogo'].sum()))
    
    cpl = round(investimento / num_leads, 2) if num_leads > 0 else 0
    c3.metric("Costo per Lead (CPL)", f"{cpl} €")
    
    tot_fatt = df_f['Valore_Pulito'].sum()
    c4.metric("Fatturato Totale", f"{tot_fatt:,.2f} €")

    st.divider()

    # --- GRAFICI ---
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Distribuzione per Sorgente")
        st.plotly_chart(px.pie(master, names='Sorgente', hole=0.3), use_container_width=True)
    
    with g2:
        st.subheader("Performance Agenti (Volume)")
        perf = master.groupby('Agente').agg(
            Leads=('key', 'count'),
            Sopralluoghi=('Sopralluogo', 'sum'),
            Fatturato=('Valore_Pulito', 'sum')
        ).reset_index()
        st.plotly_chart(px.bar(perf, x='Agente', y=['Leads', 'Sopralluoghi'], barmode='group'), use_container_width=True)

    # --- TABELLA ANALISI ECONOMICA ---
    st.subheader("💰 Analisi Economica Dettagliata per Agente")
    
    # Calcolo rapporti richiesti
    perf['Conv. Lead/Sopr (%)'] = ((perf['Sopralluoghi'] / perf['Leads']) * 100).round(1)
    perf['Fatturato / Lead (€)'] = (perf['Fatturato'] / perf['Leads']).round(2)
    
    # Ordiniamo per fatturato decrescente
    perf = perf.sort_values(by='Fatturato', ascending=False)
    
    st.dataframe(perf.style.format({
        'Fatturato': '{:,.2f} €',
        'Fatturato / Lead (€)': '{:,.2f} €'
    }), use_container_width=True)

else:
    st.info("👋 In attesa del caricamento dei 6 file richiesti nella barra laterale.")
