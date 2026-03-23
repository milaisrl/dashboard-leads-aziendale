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

def get_gsheet_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database")
    except Exception as e:
        return None

# --- 3. INIZIALIZZAZIONE SESSION STATE ---
if 'db_budget' not in st.session_state:
    st.session_state.db_budget = pd.DataFrame(columns=["Agente", "Mese", "Budget"])

# --- 4. SIDEBAR & CARICAMENTO ---
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

    # Normalizzazione chiavi
    for k in dfs:
        col_name = next((c for c in ['Cliente', 'Rag. Soc.', 'Ragione_sociale'] if c in dfs[k].columns), dfs[k].columns[0])
        dfs[k]['key'] = dfs[k][col_name].apply(normalize_name)

    # Arricchimento dati
    master = dfs['a'][dfs['a']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO").astype(str)
    master['Sopralluogo'] = master['key'].isin(dfs['s']['key'].unique())
    master['Cantiere'] = master['key'].isin(dfs['c']['key'].unique())
    
    # --- 5. TABS ---
    t_perf, t_mkt, t_bud, t_marg = st.tabs(["📊 Performance", "📢 Marketing", "💰 Budget", "🏗️ Marginalità"])

    # --- TAB PERFORMANCE ---
    with t_perf:
        col_f1, col_f2 = st.columns(2)
        with col_f1: ag_sel = st.selectbox("Agente", sorted(master['Agente'].unique()))
        with col_f2: per_sel = st.selectbox("Periodo", ["STORICO TOTALE"] + sorted(master['Mese_Anno'].dropna().unique(), reverse=True))
        
        df_ag = master[master['Agente'] == ag_sel]
        if per_sel != "STORICO TOTALE": df_ag = df_ag[df_ag['Mese_Anno'] == per_sel]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Leads", len(df_ag))
        c2.metric("Sopralluoghi", int(df_ag['Sopralluogo'].sum()))
        c3.metric("Contratti", int(df_ag['Cantiere'].sum()))
        c4.metric("Conversion", f"{round(df_ag['Cantiere'].sum()/len(df_ag)*100,1) if len(df_ag)>0 else 0}%")
        
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
            st.plotly_chart(px.pie(m_sum, values='Leads', names='Sorgente', hole=.4, color_discrete_sequence=px.colors.qualitative.Grey), use_container_width=True)
        with col_m2:
            st.dataframe(m_sum, use_container_width=True)

    # --- TAB BUDGET (LA TUA RICHIESTA) ---
    with t_bud:
        st.subheader("Configurazione Investimento Mensile")
        
        # 1. Scelta Mese/Anno
        mesi_disp = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        mese_sel = st.selectbox("Seleziona il mese per cui inserire i budget:", mesi_disp)
        
        # 2. Generazione lista agenti reali
        agenti_reali = sorted([a for a in master['Agente'].unique() if a != "NON ASSEGNATO"])
        
        # Preparazione DataFrame per l'editor
        current_budgets = st.session_state.db_budget[st.session_state.db_budget['Mese'] == mese_sel]
        
        input_data = []
        for ag in agenti_reali:
            # Cerchiamo se esiste già un valore salvato per questo mese/agente
            esistente = current_budgets[current_budgets['Agente'] == ag]['Budget'].values
            valore = esistente[0] if len(esistente) > 0 else 0.0
            input_data.append({"Agente": ag, "Mese": mese_sel, "Budget": valore})
        
        df_input = pd.DataFrame(input_data)
        
        st.info(f"Inserisci gli investimenti marketing per **{mese_sel}**. I nomi degli agenti sono bloccati per evitare errori.")
        
        # 3. L'Editor
        edited_df = st.data_editor(df_input, column_config={
            "Agente": st.column_config.Column(disabled=True),
            "Mese": st.column_config.Column(disabled=True),
            "Budget": st.column_config.NumberColumn(format="€ %.2f")
        }, use_container_width=True, key=f"editor_{mese_sel}")

        # 4. Salvataggio in Session State
        if st.button("💾 Conferma Budget per questo mese"):
            # Rimuoviamo i vecchi dati di quel mese e aggiungiamo i nuovi
            st.session_state.db_budget = pd.concat([
                st.session_state.db_budget[st.session_state.db_budget['Mese'] != mese_sel],
                edited_df
            ])
            st.success(f"Budget di {mese_sel} salvati in memoria!")

    # --- TAB MARGINALITÀ ---
    with t_marg:
        st.subheader("Analisi Profitti per Contratto")
        # Unione Contratti + Agenti
        df_c = dfs['c'][['key', 'Rag. Soc.', 'Mese_Anno', 'Totale']].copy()
        df_c['Valore'] = df_c['Totale'].apply(clean_currency)
        df_m = pd.merge(df_c, master[['key', 'Agente']].drop_duplicates('key'), on='key', how='left')
        
        # Calcolo Quota Marketing
        def get_quota(row):
            bud = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == row['Agente']) & 
                                             (st.session_state.db_budget['Mese'] == row['Mese_Anno'])]
            if not bud.empty:
                n_contratti = len(df_m[(df_m['Agente'] == row['Agente']) & (df_m['Mese_Anno'] == row['Mese_Anno'])])
                return bud['Budget'].values[0] / n_contratti if n_contratti > 0 else 0
            return 0

        df_m['Quota_Mkt'] = df_m.apply(get_quota, axis=1)
        
        st.write("Inserisci i costi vivi per ogni cantiere:")
        # Qui potresti aggiungere gspread per salvare/caricare manodopera e materiali
        st.data_editor(df_m[['Rag. Soc.', 'Agente', 'Valore', 'Quota_Mkt']], use_container_width=True)

else:
    st.warning("Carica tutti i 6 file per attivare la dashboard.")
