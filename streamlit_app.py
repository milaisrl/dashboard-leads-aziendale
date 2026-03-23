import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURAZIONE PAGINA & BRANDING ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-left: 5px solid #FF4B4B;
        padding: 15px;
        border-radius: 5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #000000 !important;
        color: white !important;
    }
    .stButton>button {
        background-color: #000000;
        color: white;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNZIONI TECNICHE ---
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

# --- 3. INIZIALIZZAZIONE SESSION STATE ---
if 'db_budget' not in st.session_state:
    st.session_state.db_budget = pd.DataFrame(columns=["Agente", "Mese", "Budget"])

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📁 Caricamento File")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load_and_clean(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        d_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if d_col:
            df['Data_Ref'] = pd.to_datetime(df[d_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df

    dfs = {"a": load_and_clean(f_anal), "l": load_and_clean(f_list), "s": load_and_clean(f_sopr), 
           "c": load_and_clean(f_cant), "f": load_and_clean(f_fatt)}

    for k in dfs:
        col_name = next((c for c in ['Cliente', 'Rag. Soc.', 'Ragione_sociale'] if c in dfs[k].columns), dfs[k].columns[0])
        dfs[k]['key'] = dfs[k][col_name].apply(normalize_name)
        dfs[k]['Ragione_Sociale_Pulita'] = dfs[k][col_name]

    master = dfs['a'][dfs['a']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO").astype(str)
    master['Sopralluogo'] = master['key'].isin(dfs['s']['key'].unique())
    master['Cantiere'] = master['key'].isin(dfs['c']['key'].unique())
    
    t_perf, t_mkt, t_bud, t_marg = st.tabs(["📊 Performance", "📢 Marketing", "💰 Budget", "🏗️ Marginalità"])

    # [Tab Performance e Marketing rimosse per brevità, restano uguali]
    with t_perf:
        c1, c2 = st.columns(2)
        with c1: ag_sel = st.selectbox("Agente", sorted(master['Agente'].unique()))
        with c2: per_sel = st.selectbox("Periodo", ["STORICO TOTALE"] + sorted(master['Mese_Anno'].dropna().unique(), reverse=True))
        df_ag = master[master['Agente'] == ag_sel]
        if per_sel != "STORICO TOTALE": df_ag = df_ag[df_ag['Mese_Anno'] == per_sel]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Leads", len(df_ag))
        m2.metric("Sopralluoghi", int(df_ag['Sopralluogo'].sum()))
        m3.metric("Contratti", int(df_ag['Cantiere'].sum()))
        m4.metric("Conversion", f"{round(df_ag['Cantiere'].sum()/len(df_ag)*100,1) if len(df_ag)>0 else 0}%")
        g1, g2 = st.columns([2,3])
        with g1:
            f_dat = pd.DataFrame({'Fase':['Leads','Sopr.','Contr.'], 'V':[len(df_ag), df_ag['Sopralluogo'].sum(), df_ag['Cantiere'].sum()]})
            fig = px.funnel(f_dat, x='V', y='Fase')
            fig.update_traces(marker=dict(color=['#000000','#444444','#FF4B4B']))
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            sorg = df_ag.groupby('Sorgente').size().reset_index(name='Q')
            st.plotly_chart(px.bar(sorg, x='Sorgente', y='Q', color_discrete_sequence=['#FF4B4B']), use_container_width=True)

    with t_mkt:
        m_sum = master.groupby('Sorgente').agg({'key':'count', 'Cantiere':'sum'}).reset_index()
        m_sum.columns = ['Sorgente', 'Leads', 'Contratti']
        col_m1, col_m2 = st.columns([1,1])
        with col_m1:
            st.plotly_chart(px.pie(m_sum, values='Leads', names='Sorgente', hole=.4, color_discrete_sequence=px.colors.qualitative.Prism), use_container_width=True)
        with col_m2:
            st.dataframe(m_sum, use_container_width=True)

    with t_bud:
        st.subheader("Gestione Investimenti Marketing")
        mesi_disp = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        mese_sel = st.selectbox("Seleziona Mese/Anno:", mesi_disp)
        agenti_reali = sorted([a for a in master['Agente'].unique() if a != "NON ASSEGNATO"])
        input_data = []
        for ag in agenti_reali:
            esistente = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == ag) & (st.session_state.db_budget['Mese'] == mese_sel)]
            valore = esistente['Budget'].values[0] if not esistente.empty else 0.0
            input_data.append({"Agente": ag, "Mese": mese_sel, "Budget": valore})
        df_input = pd.DataFrame(input_data)
        edited_df = st.data_editor(df_input, column_config={"Agente": st.column_config.Column(disabled=True), "Mese": st.column_config.Column(disabled=True), "Budget": st.column_config.NumberColumn(format="€ %.2f")}, use_container_width=True, key=f"editor_{mese_sel}")
        if st.button("💾 Salva Budget"):
            temp_db = st.session_state.db_budget[st.session_state.db_budget['Mese'] != mese_sel]
            st.session_state.db_budget = pd.concat([temp_db, edited_df], ignore_index=True)
            st.success("Dati budget salvati!")

    # --- TAB MARGINALITÀ AGGIORNATA ---
    with t_marg:
        st.subheader("🏗️ Analisi Marginalità per Cantiere")
        
        # Preparazione dati: prendiamo i contratti e filtriamo i "None"
        df_c = dfs['c'][['key', 'Ragione_Sociale_Pulita', 'Mese_Anno', 'Totale']].copy()
        df_c = df_c.dropna(subset=['Ragione_Sociale_Pulita']) # Punto 1: Escludiamo i None
        df_c = df_c[df_c['Ragione_Sociale_Pulita'].str.strip() != ""] 
        
        df_c['Valore_Contratto'] = df_c['Totale'].apply(clean_currency)
        df_m = pd.merge(df_c, master[['key', 'Agente']].drop_duplicates('key'), on='key', how='left')
        
        # Calcolo quota marketing
        def calc_quota(r):
            match = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == r['Agente']) & (st.session_state.db_budget['Mese'] == r['Mese_Anno'])]
            if not match.empty:
                n_contratti = len(df_m[(df_m['Agente'] == r['Agente']) & (df_m['Mese_Anno'] == r['Mese_Anno'])])
                return match['Budget'].values[0] / n_contratti if n_contratti > 0 else 0
            return 0
        
        df_m['Costo_Mkt'] = df_m.apply(calc_quota, axis=1)
        
        # Punto 2: Aggiunta colonne per inserimento costi
        if 'costi_manuali' not in st.session_state:
            st.session_state.costi_manuali = pd.DataFrame(columns=['key', 'Costo_Operatori', 'Costo_Prodotti'])
        
        df_m = pd.merge(df_m, st.session_state.costi_manuali, on='key', how='left').fillna(0)
        
        st.write("Inserisci i costi operatori e prodotti per calcolare il margine reale:")
        
        # Editor per i costi
        cols_to_edit = ['key', 'Ragione_Sociale_Pulita', 'Agente', 'Valore_Contratto', 'Costo_Mkt', 'Costo_Operatori', 'Costo_Prodotti']
        df_edited = st.data_editor(df_m[cols_to_edit], column_config={
            "key": None, # Nascondiamo la chiave tecnica
            "Ragione_Sociale_Pulita": st.column_config.Column("Cliente", disabled=True),
            "Agente": st.column_config.Column(disabled=True),
            "Valore_Contratto": st.column_config.NumberColumn("Fatturato €", format="%.2f", disabled=True),
            "Costo_Mkt": st.column_config.NumberColumn("Quota Mkt €", format="%.2f", disabled=True),
            "Costo_Operatori": st.column_config.NumberColumn("Costo Operatori €", format="%.2f"),
            "Costo_Prodotti": st.column_config.NumberColumn("Costo Prodotti €", format="%.2f")
        }, use_container_width=True)
        
        # Punto 3: Calcolo delle marginalità
        df_edited['Tot_Costi'] = df_edited['Costo_Mkt'] + df_edited['Costo_Operatori'] + df_edited['Costo_Prodotti']
        df_edited['Margine_€'] = df_edited['Valore_Contratto'] - df_edited['Tot_Costi']
        df_edited['Margine_%'] = (df_edited['Margine_€'] / df_edited['Valore_Contratto'] * 100).fillna(0)
        
        # Salvataggio dei costi inseriti
        if st.button("💾 Calcola e Salva Marginalità"):
            st.session_state.costi_manuali = df_edited[['key', 'Costo_Operatori', 'Costo_Prodotti']]
            st.success("Margini calcolati!")
        
        st.divider()
        st.subheader("📈 Risultati Finanziari")
        # Visualizzazione formattata con colori per il margine
        st.dataframe(df_edited[['Ragione_Sociale_Pulita', 'Valore_Contratto', 'Tot_Costi', 'Margine_€', 'Margine_%']].style.format({
            'Valore_Contratto': '{:.2f} €',
            'Tot_Costi': '{:.2f} €',
            'Margine_€': '{:.2f} €',
            'Margine_%': '{:.1f} %'
        }).background_gradient(subset=['Margine_%'], cmap='RdYlGn', vmin=0, vmax=50), use_container_width=True)

else:
    st.info("👋 Carica i file per analizzare la marginalità.")
