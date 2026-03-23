import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
from fpdf import FPDF

# 1. CONFIGURAZIONE PAGINA E STILE DOMEI
st.set_page_config(page_title="Domei - Business Intelligence", layout="wide")

# CSS Personalizzato per richiamare la Brand Identity
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { border-left: 5px solid #FF4B4B; padding-left: 10px; background-color: #f9f9f9; }
    h1, h2, h3 { color: #000000; font-family: 'Arial'; }
    .stButton>button { background-color: #000000; color: white; border-radius: 0px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI DI UTILITÀ ---
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

# --- INIZIALIZZAZIONE DATI ---
if 'budget_agenti' not in st.session_state:
    st.session_state.budget_agenti = pd.DataFrame([
        {"Agente": "NEW DDL DI DE LORENZI DANIELE", "Mese": "2026-03", "Budget": 1000.0}
    ])

# --- TESTATA BRANDIZZATA ---
col_logo, col_titolo = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=160)
    else:
        st.subheader("DOMEI")

with col_titolo:
    st.title("Business Intelligence & Marginalità")
    st.write("Performance Analysis | Sales Tracking | Margin Control")

st.divider()

# --- SIDEBAR CARICAMENTO ---
with st.sidebar:
    st.header("📁 Database Files")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    # Caricamento dati
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    df_a, df_l, df_s, df_o, df_c, df_f = load(f_anal), load(f_list), load(f_sopr), load(f_offe), load(f_cant), load(f_fatt)

    # Normalizzazione Chiavi
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_name)
    df_f['key'] = df_f['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    
    # Pulizia Valori
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)
    df_c['Valore_Contratto'] = df_c['Totale'].apply(clean_currency)

    # UNIFICAZIONE MASTER
    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, df_l.drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Cantiere'] = master['key'].isin(df_c['key'].unique())
    master['Fatturato'] = master['key'].map(df_f.groupby('key')['Valore_Netto'].sum()).fillna(0)
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    
    # Assegnazione automatica agente da sopralluogo
    sopr_map = df_s.drop_duplicates('key').set_index('key')['Creato da'].to_dict()
    master['Agente'] = master.apply(lambda r: r['Agente'] if pd.notna(r['Agente']) and r['Agente']!="" else sopr_map.get(r['key'], "DA ASSEGNARE"), axis=1)

    # --- TABS ---
    tab_perf, tab_mkt, tab_bud, tab_marg = st.tabs(["📊 Performance Sales", "📢 ROI Marketing", "💰 Gestione Budget", "🏗️ Marginalità"])

    # TAB PERFORMANCE (Focus Agenti)
    with tab_perf:
        periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        c1, c2 = st.columns(2)
        with c1: ag_sel = st.selectbox("Seleziona Agente", sorted(master['Agente'].unique()))
        with c2: per_sel = st.selectbox("Periodo", ["STORICO TOTALE"] + periodi)

        df_ag = master[master['Agente'] == ag_sel]
        if per_sel != "STORICO TOTALE": df_ag = df_ag[df_ag['Mese_Anno'] == per_sel]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Leads", len(df_ag))
        k2.metric("Sopralluoghi", int(df_ag['Sopralluogo'].sum()))
        k3.metric("Fatturato", f"{df_ag['Fatturato'].sum():,.2f} €")
        
        # Grafico Funnel
        fig_f = px.funnel(pd.DataFrame({'Fase':['Leads','Sopralluoghi','Cantieri'], 'Q':[len(df_ag), df_ag['Sopralluogo'].sum(), df_ag['Cantiere'].sum()]}), x='Q', y='Fase', color_discrete_sequence=['#000000'])
        st.plotly_chart(fig_f, use_container_width=True)

    # TAB MARKETING (Analisi Sorgenti)
    with tab_mkt:
        st.subheader("Analisi Efficacia Canali Acquisizione")
        mkt_df = master.groupby('Sorgente').agg({'key':'count', 'Sopralluogo':'sum', 'Fatturato':'sum'}).reset_index()
        mkt_df.columns = ['Sorgente', 'Leads', 'Sopralluoghi', 'Fatturato']
        st.plotly_chart(px.bar(mkt_df, x='Sorgente', y='Fatturato', color_discrete_sequence=['#FF4B4B'], title="Fatturato per Sorgente"), use_container_width=True)
        st.dataframe(mkt_df, use_container_width=True)

    # TAB BUDGET (Gestione Spese)
    with tab_bud:
        st.header("Inserimento Investimenti Mensili")
        st.session_state.budget_agenti = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic", use_container_width=True)

    # TAB MARGINALITÀ (Il tuo nuovo "Conto Economico")
    with tab_marg:
        st.header("Controllo Margini su Cantieri Chiusi")
        df_marg = pd.merge(df_c[['key', 'Rag. Soc.', 'Mese_Anno', 'Valore_Contratto']], master[['key', 'Agente']], on='key', how='left')
        
        # Ripartizione Budget Marketing
        count_c = df_marg.groupby(['Agente', 'Mese_Anno']).size().reset_index(name='N')
        bud_map = pd.merge(st.session_state.budget_agenti, count_c, left_on=['Agente','Mese'], right_on=['Agente','Mese_Anno'], how='left')
        bud_map['Quota_Mkt'] = bud_map['Budget'] / bud_map['N']
        
        df_marg = pd.merge(df_marg, bud_map[['Agente', 'Mese', 'Quota_Mkt']], left_on=['Agente','Mese_Anno'], right_on=['Agente','Mese'], how='left')
        
        for c in ['Manodopera', 'Materiali', 'Extra']: 
            if c not in df_marg: df_marg[c] = 0.0

        st.write("Inserisci i costi tecnici per ogni contratto:")
        df_edit = st.data_editor(df_marg[['Rag. Soc.', 'Agente', 'Valore_Contratto', 'Quota_Mkt', 'Manodopera', 'Materiali', 'Extra']], use_container_width=True)
        
        df_edit['Margine_€'] = df_edit['Valore_Contratto'] - (df_edit['Quota_Mkt'].fillna(0) + df_edit['Manodopera'] + df_edit['Materiali'] + df_edit['Extra'])
        df_edit['Margine_%'] = (df_edit['Margine_€'] / df_edit['Valore_Contratto'] * 100).round(1)
        
        st.subheader("Riepilogo Utili")
        st.dataframe(df_edit.style.background_gradient(subset=['Margine_%'], cmap='RdYlGn'), use_container_width=True)

else:
    st.warning("👋 Carica i file per generare la dashboard DOMEI.")
