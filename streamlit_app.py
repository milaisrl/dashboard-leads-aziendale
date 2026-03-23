import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURAZIONE PAGINA & BRANDING ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# Stile CSS Custom per rispecchiare il Brand Manual (Nero e Rosso Domei)
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-left: 5px solid #000000;
        padding: 15px;
        border-radius: 5px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f1f1;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #000000 !important;
        color: white !important;
    }
    .stButton>button {
        background-color: #000000;
        color: white;
        border: none;
        padding: 10px 25px;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #FF4B4B;
        color: white;
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
        return client.open("Domei_Database").worksheet("Marginalita")
    except Exception as e:
        st.sidebar.error(f"Errore Cloud: {e}")
        return None

# --- 3. INIZIALIZZAZIONE ---
if 'budget_agenti' not in st.session_state:
    st.session_state.budget_agenti = pd.DataFrame([{"Agente": "ESEMPIO", "Mese": "2026-03", "Budget": 0.0}])

# --- 4. HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=140)
    else:
        st.markdown("### DOMEI")

with col_title:
    st.title("Business Intelligence & Marginalità")
    st.write("Controllo vendite, ROI marketing e gestione profitti")

st.divider()

# --- 5. SIDEBAR CARICAMENTO ---
with st.sidebar:
    st.header("📁 Importazione File")
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
           "o": load_and_clean(f_offe), "c": load_and_clean(f_cant), "f": load_and_clean(f_fatt)}

    for k in dfs:
        col_name = 'Cliente' if 'Cliente' in dfs[k] else 'Rag. Soc.' if 'Rag. Soc.' in dfs[k] else \
                   'Ragione_sociale' if 'Ragione_sociale' in dfs[k] else 'Descrizione conto'
        dfs[k]['key'] = dfs[k][col_name].apply(normalize_name)

    dfs['c']['Valore_Contratto'] = dfs['c']['Totale'].apply(clean_currency)
    dfs['f']['Valore_Netto'] = dfs['f']['Imponibile in EUR' if 'Imponibile in EUR' in dfs['f'].columns else 'Totale'].apply(clean_currency)

    master = dfs['a'][dfs['a']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    sopr_map = dfs['s'].drop_duplicates('key').set_index('key')['Creato da'].to_dict()
    master['Agente'] = master.apply(lambda r: r['Agente'] if pd.notna(r['Agente']) and str(r['Agente']).strip() != "" else sopr_map.get(r['key'], "NON ASSEGNATO"), axis=1)
    # Assicuriamoci che tutti i valori in Agente siano stringhe per l'ordinamento
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO").astype(str)
    
    master['Sopralluogo'] = master['key'].isin(dfs['s']['key'].unique())
    master['Cantiere'] = master['key'].isin(dfs['c']['key'].unique())
    master['Fatturato'] = master['key'].map(dfs['f'].groupby('key')['Valore_Netto'].sum()).fillna(0)

    # --- 6. NAVIGAZIONE TABS ---
    t_perf, t_mkt, t_bud, t_marg = st.tabs(["📊 Performance Sales", "📢 Canali Marketing", "💰 Gestione Budget", "🏗️ Analisi Margini"])

    with t_perf:
        st.subheader("🎯 Analisi Performance")
        c1, c2 = st.columns(2)
        with c1:
            # Lista pulita e ordinata di agenti
            lista_agenti = sorted([str(x) for x in master['Agente'].unique() if x is not None])
            ag_sel = st.selectbox("Agente", lista_agenti)
        with c2:
            periodi = ["STORICO TOTALE"] + sorted([str(x) for x in master['Mese_Anno'].dropna().unique()], reverse=True)
            per_sel = st.selectbox("Periodo", periodi)

        df_ag = master[master['Agente'] == ag_sel]
        if per_sel != "STORICO TOTALE":
            df_ag = df_ag[df_ag['Mese_Anno'] == per_sel]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Leads Ricevuti", len(df_ag))
        k2.metric("Sopralluoghi", int(df_ag['Sopralluogo'].sum()))
        k3.metric("Contratti", int(df_ag['Cantiere'].sum()))
        k4.metric("Closing Rate", f"{round(df_ag['Cantiere'].sum()/len(df_ag)*100, 1) if len(df_ag)>0 else 0}%")

        st.divider()
        g1, g2 = st.columns([2, 3])
        with g1:
            st.write("**Conversione (Funnel)**")
            f_data = pd.DataFrame({'Fase':['Leads','Sopralluoghi','Contratti'], 'V':[len(df_ag), df_ag['Sopralluogo'].sum(), df_ag['Cantiere'].sum()]})
            st.plotly_chart(px.funnel(f_data, x='V', y='Fase', color_discrete_sequence=['#000000']), use_container_width=True)
        with g2:
            st.write("**Provenienza Leads**")
            sorg = df_ag.groupby('Sorgente').size().reset_index(name='Q')
            st.plotly_chart(px.bar(sorg, x='Sorgente', y='Q', color_discrete_sequence=['#FF4B4B']), use_container_width=True)

    with t_mkt:
        st.subheader("Efficacia Canali")
        mkt_sum = master.groupby('Sorgente').agg({'key':'count', 'Cantiere':'sum', 'Fatturato':'sum'}).reset_index()
        mkt_sum.columns = ['Sorgente', 'Leads', 'Contratti', 'Fatturato']
        st.plotly_chart(px.pie(mkt_sum, values='Leads', names='Sorgente', title="Volume Leads", color_discrete_sequence=px.colors.sequential.Greys), use_container_width=True)
        st.dataframe(mkt_sum, use_container_width=True)

    with t_bud:
        st.header("💰 Budget Marketing")
        st.session_state.budget_agenti = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic", use_container_width=True)

    with t_marg:
        st.header("🏗️ Analisi Margini (Cloud Sync)")
        
        if st.button("🔄 Recupera Dati Salvati"):
            sheet = get_gsheet_client()
            if sheet:
                st.session_state.cloud_data = pd.DataFrame(sheet.get_all_records())
                st.success("Dati sincronizzati!")
        
        df_marg = pd.merge(dfs['c'][['key', 'Rag. Soc.', 'Mese_Anno', 'Valore_Contratto']], master[['key', 'Agente']], on='key', how='left')
        count_c = df_marg.groupby(['Agente', 'Mese_Anno']).size().reset_index(name='N')
        bud_map = pd.merge(st.session_state.budget_agenti, count_c, left_on=['Agente','Mese'], right_on=['Agente','Mese_Anno'], how='left')
        bud_map['Quota_Mkt'] = (bud_map['Budget'] / bud_map['N']).fillna(0)
        
        df_final = pd.merge(df_marg, bud_map[['Agente', 'Mese', 'Quota_Mkt']], left_on=['Agente','Mese_Anno'], right_on=['Agente','Mese'], how='left')
        
        if 'cloud_data' in st.session_state and not st.session_state.cloud_data.empty:
            df_final = pd.merge(df_final, st.session_state.cloud_data[['key', 'Manodopera', 'Materiali', 'Extra']], on='key', how='left', suffixes=('', '_cloud'))
            for c in ['Manodopera', 'Materiali', 'Extra']:
                if f'{c}_cloud' in df_final.columns:
                    df_final[c] = df_final[f'{c}_cloud'].fillna(0.0)
                else:
                    df_final[c] = 0.0
        else:
            for c in ['Manodopera', 'Materiali', 'Extra']: df_final[c] = 0.0

        edit_cols = ['key', 'Rag. Soc.', 'Agente', 'Valore_Contratto', 'Quota_Mkt', 'Manodopera', 'Materiali', 'Extra']
        df_edit = st.data_editor(df_final[edit_cols], use_container_width=True)
        
        df_edit['Tot_Costi'] = df_edit['Quota_Mkt'] + df_edit['Manodopera'] + df_edit['Materiali'] + df_edit['Extra']
        df_edit['Margine_€'] = df_edit['Valore_Contratto'] - df_edit['Tot_Costi']
        df_edit['Margine_%'] = (df_edit['Margine_€'] / df_edit['Valore_Contratto'] * 100).round(1)

        if st.button("💾 SALVA SU CLOUD"):
            sheet = get_gsheet_client()
            if sheet:
                sheet.clear()
                sheet.update([df_edit.columns.values.tolist()] + df_edit.values.tolist())
                st.success("Dati salvati!")

        st.divider()
        st.dataframe(df_edit.style.background_gradient(subset=['Margine_%'], cmap='RdYlGn'), use_container_width=True)

else:
    st.info("👋 Benvenuto. Carica i 6 file nella barra laterale per attivare Domei Intelligence.")
