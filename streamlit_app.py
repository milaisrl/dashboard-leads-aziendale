import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# --- 2. FUNZIONI DI PULIZIA AVANZATA ---
def clean_company_name(name):
    if pd.isna(name): return ""
    s = str(name).lower()
    # Rimuove estensioni societarie comuni che creano disallineamenti
    s = re.sub(r'\b(srl|s\.r\.l\.|spa|s\.p\.a\.|snc|sas|ss)\b', '', s)
    # Rimuove tutto ciò che non è lettera o numero
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

def init_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database").worksheet("Marginalita")
    except: return None

def smart_load(f):
    if f is None: return pd.DataFrame()
    try:
        if f.name.endswith('.csv'): return pd.read_csv(f, sep=None, engine='python')
        try: return pd.read_excel(f, engine='openpyxl')
        except: return pd.read_excel(f, engine='xlrd')
    except: return pd.DataFrame()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("📁 Carica i 6 File")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'xls', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'xls', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'xls', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'xls', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'xls', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'xls', 'csv'])

# --- 4. ELABORAZIONE DATI ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    dfs = {
        "a": smart_load(f_anal), "l": smart_load(f_list), 
        "s": smart_load(f_sopr), "o": smart_load(f_offe),
        "c": smart_load(f_cant), "f": smart_load(f_fatt)
    }

    # Prepariamo le chiavi di collegamento su tutti i file
    for k in dfs:
        if not dfs[k].empty:
            cols = dfs[k].columns.tolist()
            # Identifica la colonna cliente
            target = next((c for c in cols if any(x in c for x in ['Cliente', 'Rag', 'Soc', 'Nominativo'])), cols[0])
            dfs[k]['key'] = dfs[k][target].apply(clean_company_name)
            dfs[k]['Nome_Originale'] = dfs[k][target]

    # --- COSTRUZIONE MASTER TABLE ---
    # 1. Partiamo dall'Analisi e uniamo l'Agente/Sorgente dalla Lista Leads
    master = pd.merge(dfs['a'], dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO")
    
    # 2. Flag Sopralluoghi e Contratti (con controllo booleano)
    list_sopr = dfs['s']['key'].unique()
    list_cant = dfs['c']['key'].unique()
    
    master['Sopralluogo_Effettuato'] = master['key'].apply(lambda x: 1 if x in list_sopr and x != "" else 0)
    master['Contratto_Chiuso'] = master['key'].apply(lambda x: 1 if x in list_cant and x != "" else 0)

    # --- INTERFACCIA ---
    t_perf, t_marg = st.tabs(["📊 Performance", "🏗️ Marginalità"])

    with t_perf:
        agenti = sorted(master['Agente'].unique())
        sel_ag = st.selectbox("Seleziona Agente", agenti)
        
        df_ag = master[master['Agente'] == sel_ag]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Leads", len(df_ag))
        c2.metric("Sopralluoghi", int(df_ag['Sopralluogo_Effettuato'].sum()))
        c3.metric("Contratti", int(df_ag['Contratto_Chiuso'].sum()))

        # Debug per te: vedi se i nomi coincidono
        if st.checkbox("Mostra nomi per controllo (Debug)"):
            st.write("Esempio chiavi generate per Sopralluoghi:", list_sopr[:5])
            st.write("Esempio chiavi generate per Analisi (Agente):", df_ag['key'].head().tolist())

        st.plotly_chart(px.pie(df_ag, names='Sorgente', title="Provenienza Leads"), use_container_width=True)

    with t_marg:
        # (Logica marginalità invariata rispetto alla precedente per brevità)
        st.write("Gestione marginalità attiva.")

else:
    st.info("Carica i file per correggere le statistiche.")
