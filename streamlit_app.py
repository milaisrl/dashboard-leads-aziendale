import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")

st.title("📊 Analisi Leads & Performance Agenti")
st.markdown("Carica i file mensili per generare le statistiche.")

# --- SIDEBAR PER CARICAMENTO E INPUT ---
with st.sidebar:
    st.header("Caricamento Dati")
    file_analisi = st.file_uploader("1. ANALISI (Excel/CSV)", type=['xlsx', 'csv'])
    file_lista = st.file_uploader("2. LISTA LEADS (Excel/CSV)", type=['xlsx', 'csv'])
    file_sopralluoghi = st.file_uploader("3. SOPRALLUOGHI (Excel/CSV)", type=['xlsx', 'csv'])
    file_offerte = st.file_uploader("4. OFFERTE (Excel/CSV)", type=['xlsx', 'csv'])
    file_cantieri = st.file_uploader("5. CANTIERI/FATTURATO (Excel/CSV)", type=['xlsx', 'csv'])
    
    st.divider()
    investimento = st.number_input("Investimento Pubblicitario (€)", min_value=0.0, value=1000.0)

# Funzione per pulire i nomi e renderli confrontabili
def clean_name(name):
    return str(name).strip().lower()

# --- ELABORAZIONE DATI ---
if all([file_analisi, file_lista, file_sopralluoghi, file_offerte, file_cantieri]):
    # Caricamento (gestisce sia CSV che Excel)
    def load_df(file):
        if file.name.endswith('.csv'): return pd.read_csv(file)
        return pd.read_excel(file)

    df_a = load_df(file_analisi)
    df_l = load_df(file_lista)
    df_s = load_df(file_sopralluoghi)
    df_o = load_df(file_offerte)
    df_c = load_df(file_cantieri)

    # 1. Pulizia Analisi (Rimuovo WF Contatto)
    df_a = df_a[df_a['Tipo'] != 'WF Contatto cliente']
    
    # 2. Creazione Chiavi Univoche
    for df in [df_a, df_l, df_s, df_o, df_c]:
        if 'Cliente' in df.columns:
            df['key'] = df['Cliente'].apply(clean_name)

    # 3. Merge dei dati
    # Unisco Analisi con Lista Leads per avere Agente e Sorgente
    df_master = pd.merge(df_a, df_l[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # Identificazione Fuori Zona (Agente vuoto)
    df_master['Agente'] = df_master['Agente'].fillna('FUORI ZONA')
    
    # --- CALCOLO KPI ---
    tot_leads = len(df_master)
    leads_validi = len(df_master[df_master['Agente'] != 'FUORI ZONA'])
    cpl = investimento / tot_leads if tot_leads > 0 else 0
    
    # Calcolo Sopralluoghi e Conversioni
    sopralluoghi_nomi = df_s['key'].unique()
    df_master['Sopralluogo'] = df_master['key'].isin(sopralluoghi_nomi)
    
    # Fatturato
    tot_fatturato = df_c['Importo'].sum() if 'Importo' in df_c.columns else 0

    # --- VISUALIZZAZIONE ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totale Leads", tot_leads)
    col2.metric("Leads Fuori Zona", len(df_master[df_master['Agente'] == 'FUORI ZONA']))
    col3.metric("Costo per Lead (CPL)", f"{cpl:.2f} €")
    col4.metric("Fatturato Totale", f"{tot_fatturato:,.2f} €")

    st.divider()

    # Grafici
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Leads per Sorgente")
        fig_sor = px.pie(df_master, names='Sorgente', hole=0.4)
        st.plotly_chart(fig_sor, use_container_width=True)

    with c2:
        st.subheader("Performance Agenti (Leads vs Sopralluoghi)")
        agenti_stats = df_master.groupby('Agente').agg(
            Leads=('key', 'count'),
            Sopralluoghi=('Sopralluogo', 'sum')
        ).reset_index()
        fig_bar = px.bar(agenti_stats, x='Agente', y=['Leads', 'Sopralluoghi'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Tabella Riassuntiva Mensile")
    st.dataframe(agenti_stats, use_container_width=True)

else:
    st.info("👋 Benvenuto! Carica tutti i 5 file nella barra laterale per vedere l'analisi.")
