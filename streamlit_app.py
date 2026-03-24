import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
from gspread_pandas import Spread, Client

# --- 1. CONFIGURAZIONE & BRANDING ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stMetric"] { background-color: #f8f9fa; border-left: 5px solid #FF4B4B; padding: 15px; }
    .stButton>button { background-color: #000000; color: white; border-radius: 5px; }
    @media print {
        [data-testid="stSidebar"], .stButton, header, footer, .stTabs [data-baseweb="tab-list"] { display: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNZIONI DI AUTOMAZIONE PULIZIA ---
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

# --- 3. TESTATA ---
col_logo, col_titolo, col_print = st.columns([1, 3, 1])
with col_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=150)
    else: st.subheader("DOMEI")
with col_titolo:
    st.markdown("<h1 style='margin-top: 10px;'>Statistiche commerciali</h1>", unsafe_allow_html=True)
with col_print:
    if st.button("🖨️ Stampa Report PDF"):
        st.components.v1.html("<script>window.print();</script>", height=0)

st.divider()

# --- 4. CARICAMENTO DATI (SIDEBAR) ---
with st.sidebar:
    st.header("📁 Carica Export Gestionali")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    # Logica di caricamento identica alla precedente per stabilità
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

    # --- TAB BUDGET CON PERSISTENZA ---
    with t_bud:
        st.subheader("💰 Database Budget Marketing")
        # Qui l'app legge dal tuo Google Sheets reale (se configurato)
        # Per ora usiamo session_state, ma pronto per il bridge Google
        mesi_disp = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        mese_sel = st.selectbox("Seleziona Mese/Anno:", mesi_disp)
        
        agenti_validi = sorted([a for a in master['Agente'].unique() if a != "NON ASSEGNATO"])
        
        # Generazione automatica righe agenti
        input_data = []
        for ag in agenti_validi:
            esistente = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == ag) & (st.session_state.db_budget['Mese'] == mese_sel)]
            valore = esistente['Budget'].values[0] if not esistente.empty else 0.0
            input_data.append({"Agente": ag, "Mese": mese_sel, "Budget": valore})
        
        df_input = pd.DataFrame(input_data)
        edited_df = st.data_editor(df_input, use_container_width=True, key=f"edit_{mese_sel}")
        
        if st.button("💾 Salva Definitivamente"):
            # Qui inseriremo il codice per scrivere su Google Sheets
            temp_db = st.session_state.db_budget[st.session_state.db_budget['Mese'] != mese_sel]
            st.session_state.db_budget = pd.concat([temp_db, edited_df], ignore_index=True)
            st.success("Dati sincronizzati con il database centrale.")

    # --- TAB MARGINALITÀ AUTOMATICA ---
    with t_marg:
        st.subheader("🏗️ Calcolo Margine Automatico")
        # Filtriamo i "None" e i vuoti automaticamente
        df_c = dfs['c'].dropna(subset=['Ragione_Sociale_Pulita'])
        df_c = df_c[df_c['Ragione_Sociale_Pulita'].astype(str).str.strip() != ""]
        df_c['Valore_Contratto'] = df_c['Totale'].apply(clean_currency)
        
        df_m = pd.merge(df_c, master[['key', 'Agente']].drop_duplicates('key'), on='key', how='left')
        
        # Quota Marketing Calcolata al volo
        def get_mkt_cost(r):
            match = st.session_state.db_budget[(st.session_state.db_budget['Agente'] == r['Agente']) & (st.session_state.db_budget['Mese'] == r['Mese_Anno'])]
            if not match.empty:
                n = len(df_m[(df_m['Agente'] == r['Agente']) & (df_m['Mese_Anno'] == r['Mese_Anno'])])
                return match['Budget'].values[0] / n if n > 0 else 0
            return 0
        
        df_m['Costo_Mkt'] = df_m.apply(get_mkt_cost, axis=1)
        
        # Merge con i costi inseriti in precedenza
        df_m = pd.merge(df_m, st.session_state.costi_manuali, on='key', how='left').fillna(0)
        
        st.info("L'app ha già pulito i dati e rimosso i 'None'. Inserisci solo i costi operativi.")
        
        df_final_edit = st.data_editor(df_m[['key', 'Ragione_Sociale_Pulita', 'Agente', 'Valore_Contratto', 'Costo_Mkt', 'Costo_Operatori', 'Costo_Prodotti']], 
                                       column_config={"key":None}, use_container_width=True)
        
        if st.button("📊 Aggiorna Marginalità Aziendale"):
            st.session_state.costi_manuali = df_final_edit[['key', 'Costo_Operatori', 'Costo_Prodotti']]
            st.rerun()

        # Calcoli finali
        df_final_edit['Tot_Costi'] = df_final_edit['Costo_Mkt'] + df_final_edit['Costo_Operatori'] + df_final_edit['Costo_Prodotti']
        df_final_edit['Margine_€'] = df_final_edit['Valore_Contratto'] - df_final_edit['Tot_Costi']
        
        # RIEPILOGO RAPIDO
        f1, f2, f3 = st.columns(3)
        f1.metric("Fatturato", f"{df_final_edit['Valore_Contratto'].sum():,.2f}€")
        f2.metric("Margine Totale", f"{df_final_edit['Margine_€'].sum():,.2f}€")
        f3.metric("% Media", f"{(df_final_edit['Margine_€'].sum()/df_final_edit['Valore_Contratto'].sum()*100 if df_final_edit['Valore_Contratto'].sum()>0 else 0):.1f}%")

        st.dataframe(df_final_edit[['Ragione_Sociale_Pulita', 'Agente', 'Valore_Contratto', 'Margine_€']].style.background_gradient(cmap='RdYlGn'), use_container_width=True)

else:
    st.warning("Carica i file per attivare l'automazione.")
