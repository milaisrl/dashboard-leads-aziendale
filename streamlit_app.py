import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")

st.title("📊 Analisi Leads & Performance")
st.markdown("Carica i file mensili estratti dal gestionale/CRM.")

# --- FUNZIONE PULIZIA NOMI ---
def clean_name(name):
    return str(name).strip().lower()

# --- SIDEBAR CARICAMENTO ---
with st.sidebar:
    st.header("Caricamento File")
    f_analisi = st.file_uploader("1. ANALISI (Leads ricevuti)", type=['xlsx', 'csv'])
    f_lista = st.file_uploader("2. LISTA LEADS (Agente/Sorgente)", type=['xlsx', 'csv'])
    f_sopralluoghi = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offerte = st.file_uploader("4. OFFERTE (Preventivi)", type=['xlsx', 'csv'])
    f_cantieri = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatturato = st.file_uploader("6. FATTURATO REALE", type=['xlsx', 'csv'])
    
    st.divider()
    investimento = st.number_input("Investimento Pubblicitario (€)", min_value=0.0, value=1000.0)

# --- LOGICA DI ELABORAZIONE ---
if all([f_analisi, f_lista, f_sopralluoghi, f_offerte, f_cantieri, f_fatturato]):
    
    def load(file):
        if file.name.endswith('.csv'): return pd.read_csv(file, sep=None, engine='python')
        return pd.read_excel(file)

    # Caricamento e pulizia immediata nomi colonne
    dfs = {
        'anal': load(f_analisi), 'list': load(f_lista), 
        'sopr': load(f_sopralluoghi), 'offe': load(f_offerte), 
        'cant': load(f_cantieri), 'fatt': load(f_fatturato)
    }
    for k in dfs: dfs[k].columns = dfs[k].columns.astype(str).str.strip()

    # Creazione chiavi di aggancio (sperando ci sia 'Cliente' in tutti)
    for k in dfs:
        col_name = 'Cliente' if 'Cliente' in dfs[k].columns else dfs[k].columns[0]
        dfs[k]['key'] = dfs[k][col_name].apply(clean_name)

    # 1. Filtro Analisi
    df_a = dfs['anal']
    tipo_col = 'Tipo' if 'Tipo' in df_a.columns else df_a.columns[0]
    df_a = df_a[df_a[tipo_col] != 'WF Contatto cliente']

    # 2. Arricchimento Leads (Join con Lista Leads)
    df_l = dfs['list']
    cols_l = ['key']
    if 'Agente' in df_l.columns: cols_l.append('Agente')
    if 'Sorgente' in df_l.columns: cols_l.append('Sorgente')
    
    master = pd.merge(df_a, df_l[cols_l], on='key', how='left')
    master['Agente'] = master['Agente'].fillna('FUORI ZONA')

    # 3. Aggancio conversioni
    master['Sopralluogo'] = master['key'].isin(dfs['sopr']['key'].unique())
    master['Contratto'] = master['key'].isin(dfs['cant']['key'].unique())

    # 4. Calcolo Fatturato per Agente (dal file Fatturato)
    # Assumiamo che nel file fatturato ci sia una colonna 'Importo'
    col_soldi = 'Importo' if 'Importo' in dfs['fatt'].columns else dfs['fatt'].select_dtypes(include='number').columns[0]
    fatt_per_cliente = dfs['fatt'].groupby('key')[col_soldi].sum().reset_index()
    master = pd.merge(master, fatt_per_cliente, on='key', how='left').fillna(0)

    # --- DISPLAY KPI ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads Totali", len(master))
    c2.metric("Sopralluoghi", master['Sopralluogo'].sum())
    c3.metric("CPL (Costo Lead)", f"{(investimento/len(master)):.2f} €")
    c4.metric("Fatturato Tot.", f"{dfs['fatt'][col_soldi].sum():,.2f} €")

    # --- GRAFICI ---
    st.divider()
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("Leads per Sorgente")
        fig1 = px.pie(master, names='Sorgente')
        st.plotly_chart(fig1, use_container_width=True)
        
    with g2:
        st.subheader("Conversione per Agente")
        # Raggruppiamo i dati per agente
        agente_df = master.groupby('Agente').agg(
            Leads=('key', 'count'),
            Sopralluoghi=('Sopralluogo', 'sum'),
            Fatturato=(col_soldi, 'sum')
        ).reset_index()
        fig2 = px.bar(agente_df, x='Agente', y=['Leads', 'Sopralluoghi'], barmode='group')
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Dettaglio Performance")
    # Calcolo Rapporto Lead/Sopralluogo
    agente_df['% Conv.'] = (agente_df['Sopralluoghi'] / agente_df['Leads'] * 100).round(1)
    st.dataframe(agente_df, use_container_width=True)

else:
    st.info("In attesa del caricamento di tutti i 6 file richiesti...")
