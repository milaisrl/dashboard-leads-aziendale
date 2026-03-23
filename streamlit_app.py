import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")

st.title("📊 Analisi Leads & Performance")

# --- FUNZIONI DI PULIZIA ---
def clean_name(name):
    return str(name).strip().lower()

def clean_currency(value):
    if isinstance(value, str):
        # Toglie punti (migliaia) e cambia virgola in punto (decimali)
        value = value.replace('.', '').replace(',', '.')
    try:
        return float(value)
    except:
        return 0.0

# --- SIDEBAR ---
with st.sidebar:
    st.header("Caricamento File")
    f_anal = st.file_uploader("1. ANALISI (Foglio 1)", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])
    st.divider()
    investimento = st.number_input("Investimento Pubblicitario (€)", min_value=0.0, value=1000.0)

# --- ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load(file):
        if file.name.endswith('.csv'): return pd.read_csv(file, sep=None, engine='python')
        return pd.read_excel(file)

    # Caricamento
    df_a = load(f_anal)
    df_l = load(f_list)
    df_s = load(f_sopr)
    df_o = load(f_offe)
    df_c = load(f_cant)
    df_f = load(f_fatt)

    # Pulizia nomi colonne
    for df in [df_a, df_l, df_s, df_o, df_c, df_f]:
        df.columns = df.columns.astype(str).str.strip()

    # Identificazione colonne chiave per ogni file
    # ANALISI: usa 'Cliente'
    df_a['key'] = df_a['Cliente'].apply(clean_name) if 'Cliente' in df_a.columns else df_a[df_a.columns[5]].apply(clean_name)
    df_a = df_a[df_a['Tipo'] != 'WF Contatto cliente']

    # LISTA LEADS: usa 'Ragione_sociale'
    df_l['key'] = df_l['Ragione_sociale'].apply(clean_name) if 'Ragione_sociale' in df_l.columns else df_l[df_l.columns[2]].apply(clean_name)

    # SOPRALLUOGHI, OFFERTE, CANTIERI: usano 'Rag. Soc.'
    for df in [df_s, df_o, df_c]:
        col = 'Rag. Soc.' if 'Rag. Soc.' in df.columns else df.columns[6]
        df['key'] = df[col].apply(clean_name)

    # FATTURATO: usa 'Descrizione conto' e pulizia soldi
    col_f_cli = 'Descrizione conto' if 'Descrizione conto' in df_f.columns else df_f.columns[5]
    df_f['key'] = df_f[col_f_cli].apply(lambda x: clean_name(str(x).split('[')[0])) # Toglie il codice [CI-...]
    
    col_f_soldi = 'Totale' if 'Totale' in df_f.columns else 'Imponibile in EUR'
    df_f['Valore'] = df_f[col_f_soldi].apply(clean_currency)

    # --- MERGE ---
    # Unisco Analisi con Lista Leads per Agente e Sorgente
    master = pd.merge(df_a, df_l[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna('FUORI ZONA')
    
    # Marcatori conversioni
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    master['Offerta'] = master['key'].isin(df_o['key'].unique())
    master['Cantiere'] = master['key'].isin(df_c['key'].unique())

    # Fatturato reale dal file Fatturato
    fatt_aggregato = df_f.groupby('key')['Valore'].sum().reset_index()
    master = pd.merge(master, fatt_aggregato, on='key', how='left').fillna(0)

    # --- DASHBOARD ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads Totali", len(master))
    c2.metric("Sopralluoghi", master['Sopralluogo'].sum())
    c3.metric("Cantieri Chiusi", master['Cantiere'].sum())
    c4.metric("Fatturato Totale", f"{df_f['Valore'].sum():,.2f} €")

    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Leads per Sorgente")
        st.plotly_chart(px.pie(master, names='Sorgente'), use_container_width=True)
    
    with col_g2:
        st.subheader("Performance Agenti")
        perf = master.groupby('Agente').agg(
            Leads=('key', 'count'),
            Sopralluoghi=('Sopralluogo', 'sum'),
            Fatturato=('Valore', 'sum')
        ).reset_index()
        st.plotly_chart(px.bar(perf, x='Agente', y=['Leads', 'Sopralluoghi'], barmode='group'), use_container_width=True)

    st.subheader("Analisi Economica per Agente")
    perf['CPL Medio'] = (investimento / len(master)).round(2)
    perf['Fatturato per Lead'] = (perf['Fatturato'] / perf['Leads']).round(2)
    st.dataframe(perf, use_container_width=True)

else:
    st.info("Carica i 6 file per visualizzare l'analisi completa.")
