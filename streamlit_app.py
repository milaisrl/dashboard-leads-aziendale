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
        width: 100%;
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

def get_gsheet_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database")
    except Exception:
        return None

# --- 3. INIZIALIZZAZIONE SESSION STATE ---
if 'db_budget' not in st.session_state:
    st.session_state.db_budget = pd.DataFrame(columns=["Agente", "Mese", "Budget"])

# --- 4. HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    else:
        st.header("DOMEI")
with col_title:
    st.title("Business Intelligence & Marginalità")

# --- 5. SIDEBAR CARICAMENTO ---
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

    master = dfs['a'][dfs['a']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO").astype(str)
    master['Sopralluogo'] = master['key'].isin(dfs['s']['key'].unique())
    master['Cantiere'] = master['key'].isin(dfs['c']['key'].unique())
    
    t_perf, t_mkt, t_bud, t_marg = st.tabs(["📊 Performance", "📢 Marketing", "💰 Budget", "🏗️ Marginalità"])

    # --- TAB PERFORMANCE ---
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

    # --- TAB MARKETING ---
    with t_mkt:
        m_sum = master.groupby('Sorgente').agg({'key':'count', 'Cantiere':'sum'}).reset_index()
        m_sum.columns = ['Sorgente', 'Leads', 'Contratti']
        col_m1, col_m2 = st.columns([1,1])
        with col_m1:
            # CORRETTO: px.colors.qualitative.Greys (con la 's')
            st.plotly_chart(px.pie(m_sum, values='Leads', names='Sorgente', hole=.4, color_discrete_sequence=px.colors.qualitative.Prism), use_container_width=True)
        with col_m2:
            st.dataframe(m_sum, use_container_width=True)

    # --- TAB BUDGET (SICURA E AUTOMATICA) ---
    with t_bud:
        st.subheader("Gestione Investimenti Marketing")
        mesi_disp = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        mese_sel = st.selectbox("Seleziona Mese/Anno:", mesi_disp)
        
        # Agenti reali filtrati (escluso NON ASSEGNATO)
        agenti_reali = sorted([a for a in master['Agente'].unique() if a != "NON ASSEGNATO"])
        
        # Recupero dati esistenti nel session state
        input_data = []
        for ag in agenti_reali:
            esistente = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == ag) & (st.session_state.db_budget['Mese'] == mese_sel)]
            valore = esistente['Budget'].values[0] if not esistente.empty else 0.0
            input_data.append({"Agente": ag, "Mese": mese_sel, "Budget": valore})
        
        df_input = pd.DataFrame(input_data)
        
        st.info(f"Modifica i budget per gli agenti attivi nel mese di **{mese_sel}**.")
        
        edited_df = st.data_editor(df_input, column_config={
            "Agente": st.column_config.Column(disabled=True),
            "Mese": st.column_config.Column(disabled=True),
            "Budget": st.column_config.NumberColumn(format="€ %.2f")
        }, use_container_width=True, key=f"editor_{mese_sel}")

        if st.button("💾 Salva Budget in Memoria"):
            # Aggiorniamo il database interno
            temp_db = st.session_state.db_budget[st.session_state.db_budget['Mese'] != mese_sel]
            st.session_state.db_budget = pd.concat([temp_db, edited_df], ignore_index=True)
            st.success("Dati aggiornati per i calcoli di marginalità!")

    # --- TAB MARGINALITÀ ---
    with t_marg:
        st.subheader("Riepilogo Marginalità per Cantiere")
        df_c = dfs['c'][['key', 'Rag. Soc.', 'Mese_Anno', 'Totale']].copy()
        df_c['Valore'] = df_c['Totale'].apply(clean_currency)
        df_m = pd.merge(df_c, master[['key', 'Agente']].drop_duplicates('key'), on='key', how='left')
        
        # Calcolo quota marketing dinamico
        def calc_quota(r):
            match = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == r['Agente']) & (st.session_state.db_budget['Mese'] == r['Mese_Anno'])]
            if not match.empty:
                n_contratti = len(df_m[(df_m['Agente'] == r['Agente']) & (df_m['Mese_Anno'] == r['Mese_Anno'])])
                return match['Budget'].values[0] / n_contratti if n_contratti > 0 else 0
            return 0

        df_m['Quota_Mkt'] = df_m.apply(calc_quota, axis=1)
        st.dataframe(df_m[['Rag. Soc.', 'Agente', 'Mese_Anno', 'Valore', 'Quota_Mkt']], use_container_width=True)

else:
    st.info("👋 Benvenuto in Domei Intelligence. Carica i 6 file per iniziare.")
