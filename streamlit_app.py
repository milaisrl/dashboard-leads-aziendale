import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF

# --- 1. CONFIGURAZIONE PAGINA & BRANDING DOMEI ---
st.set_page_config(page_title="Domei Business Intelligence", layout="wide")

# CSS per allineare l'interfaccia al Brand Manual (Nero e Rosso Arancio)
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    div[data-testid="stMetricValue"] { color: #000000; font-family: 'Arial'; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f1f1f1; border-radius: 4px 4px 0px 0px; gap: 1px; }
    .stTabs [aria-selected="true"] { background-color: #000000 !important; color: white !important; }
    .stButton>button { background-color: #000000; color: white; border-radius: 0px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #FF4B4B; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNZIONI TECNICHE ---
def get_gsheet_client():
    """Connessione a Google Sheets tramite Secrets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database").worksheet("Marginalita")
    except Exception as e:
        st.error(f"Errore connessione Cloud: {e}")
        return None

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
if 'budget_agenti' not in st.session_state:
    st.session_state.budget_agenti = pd.DataFrame([{"Agente": "AGENTE TEST", "Mese": "2026-03", "Budget": 0.0}])

if 'df_cloud' not in st.session_state:
    st.session_state.df_cloud = pd.DataFrame(columns=['key', 'Manodopera', 'Materiali', 'Extra'])

# --- 4. TESTATA ---
col_l, col_t = st.columns([1, 4])
with col_l:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=150)
    else:
        st.title("DOMEI")
with col_t:
    st.title("Business Intelligence & Controllo Margini")
    st.write("Analisi integrata Sales & Marketing secondo Brand Guideline")

st.divider()

# --- 5. CARICAMENTO FILE (SIDEBAR) ---
with st.sidebar:
    st.header("📁 Importazione Dati")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load_df(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    dfs = { "a": load_df(f_anal), "l": load_df(f_list), "s": load_df(f_sopr), 
            "o": load_df(f_offe), "c": load_df(f_cant), "f": load_df(f_fatt) }

    # Normalizzazione e Chiavi
    for k in dfs: dfs[k]['key'] = (dfs[k]['Cliente'] if 'Cliente' in dfs[k] else 
                                  dfs[k]['Rag. Soc.'] if 'Rag. Soc.' in dfs[k] else 
                                  dfs[k]['Ragione_sociale'] if 'Ragione_sociale' in dfs[k] else
                                  dfs[k]['Descrizione conto']).apply(normalize_name)

    # Valori Economici
    dfs['c']['Valore_Contratto'] = dfs['c']['Totale'].apply(clean_currency)
    dfs['f']['Valore_Netto'] = dfs['f']['Imponibile in EUR' if 'Imponibile in EUR' in dfs['f'].columns else 'Totale'].apply(clean_currency)

    # Master Data Construction
    master = dfs['a'][dfs['a']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # Recupero Agente da Sopralluogo
    sopr_map = dfs['s'].drop_duplicates('key').set_index('key')['Creato da'].to_dict()
    master['Agente'] = master.apply(lambda r: r['Agente'] if pd.notna(r['Agente']) and r['Agente']!="" else sopr_map.get(r['key'], "DA ASSEGNARE"), axis=1)
    
    master['Sopralluogo'] = master['key'].isin(dfs['s']['key'].unique())
    master['Cantiere'] = master['key'].isin(dfs['c']['key'].unique())
    master['Fatturato'] = master['key'].map(dfs['f'].groupby('key')['Valore_Netto'].sum()).fillna(0)

    # --- 6. TABS ---
    tab_p, tab_m, tab_b, tab_marg = st.tabs(["📊 Sales Performance", "📢 ROI Marketing", "💰 Budget", "🏗️ MARGINALITÀ"])

    with tab_p:
        st.subheader("Performance Agenti")
        ag_sel = st.selectbox("Agente", sorted(master['Agente'].unique()))
        df_ag = master[master['Agente'] == ag_sel]
        k1, k2, k3 = st.columns(3)
        k1.metric("Leads", len(df_ag))
        k2.metric("Sopralluoghi", int(df_ag['Sopralluogo'].sum()))
        k3.metric("Fatturato", f"{df_ag['Fatturato'].sum():,.2f} €")
        st.plotly_chart(px.funnel(pd.DataFrame({'Fase':['Leads','Sopr.'], 'Val':[len(df_ag), df_ag['Sopralluogo'].sum()]}), x='Val', y='Fase', color_discrete_sequence=['#000000']))

    with tab_m:
        st.subheader("Efficacia Canali Marketing")
        mkt = master.groupby('Sorgente').agg({'key':'count', 'Fatturato':'sum'}).reset_index()
        st.plotly_chart(px.bar(mkt, x='Sorgente', y='Fatturato', title="Fatturato per Sorgente", color_discrete_sequence=['#FF4B4B']))

    with tab_b:
        st.subheader("Gestione Investimenti")
        st.session_state.budget_agenti = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic", use_container_width=True)

    with tab_marg:
        st.header("Analisi Margini (Sincronizzato Cloud)")
        
        # Caricamento da Cloud
        if st.button("🔄 Sincronizza Dati da Cloud"):
            client_sheet = get_gsheet_client()
            if client_sheet:
                st.session_state.df_cloud = pd.DataFrame(client_sheet.get_all_records())
                st.success("Dati scaricati da Google Sheets!")

        # Calcolo Quota Marketing
        df_c_m = pd.merge(dfs['c'][['key', 'Rag. Soc.', 'Mese_Anno', 'Valore_Contratto']], master[['key', 'Agente']], on='key', how='left')
        count_m = df_c_m.groupby(['Agente', 'Mese_Anno']).size().reset_index(name='N')
        bud_m = pd.merge(st.session_state.budget_agenti, count_m, left_on=['Agente','Mese'], right_on=['Agente','Mese_Anno'], how='left')
        bud_m['Quota_Mkt'] = (bud_m['Budget'] / bud_m['N']).fillna(0)
        
        # Merge finale per tabella margini
        final_marg = pd.merge(df_c_m, bud_m[['Agente', 'Mese', 'Quota_Mkt']], left_on=['Agente','Mese_Anno'], right_on=['Agente','Mese'], how='left')
        
        # Unione con i costi storici salvati su Cloud
        final_marg = pd.merge(final_marg, st.session_state.df_cloud[['key', 'Manodopera', 'Materiali', 'Extra']], on='key', how='left')
        for c in ['Manodopera', 'Materiali', 'Extra']: final_marg[c] = final_marg[c].fillna(0.0)

        # Editor
        df_edit = st.data_editor(
            final_marg[['key', 'Rag. Soc.', 'Agente', 'Valore_Contratto', 'Quota_Mkt', 'Manodopera', 'Materiali', 'Extra']],
            use_container_width=True, key="main_editor"
        )

        # Calcolo Totali
        df_edit['Margine_€'] = df_edit['Valore_Contratto'] - (df_edit['Quota_Mkt'] + df_edit['Manodopera'] + df_edit['Materiali'] + df_edit['Extra'])
        df_edit['Margine_%'] = (df_edit['Margine_€'] / df_edit['Valore_Contratto'] * 100).round(1)

        if st.button("💾 SALVA MODIFICHE SU CLOUD"):
            client_sheet = get_gsheet_client()
            if client_sheet:
                client_sheet.clear()
                client_sheet.update([df_edit.columns.values.tolist()] + df_edit.values.tolist())
                st.success("Database Domei aggiornato!")

        st.subheader("Riepilogo Marginalità")
        st.dataframe(df_edit.style.background_gradient(subset=['Margine_%'], cmap='RdYlGn'), use_container_width=True)

else:
    st.warning("In attesa dei file storici Domei...")
