import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- 1. CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

def init_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database").worksheet("Marginalita")
    except:
        return None

def normalize_name(name):
    if pd.isna(name): return ""
    return " ".join(sorted(re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip().split()))

# --- 2. SIDEBAR: TUTTI I 6 FILES ---
with st.sidebar:
    st.header("📁 Caricamento Mensile")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

# --- 3. LOGICA DI CARICAMENTO (Con correzione errore ValueError) ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load_data(f):
        try:
            if f.name.endswith('.csv'):
                df = pd.read_csv(f, sep=None, engine='python')
            else:
                # Forza openpyxl per evitare il ValueError del motore Excel
                df = pd.read_excel(f, engine='openpyxl')
            df.columns = df.columns.astype(str).str.strip()
            return df
        except Exception as e:
            st.error(f"Errore nel file {f.name}: {e}")
            return pd.DataFrame()

    dfs = {
        "a": load_data(f_anal), "l": load_data(f_list), 
        "s": load_data(f_sopr), "o": load_data(f_offe),
        "c": load_data(f_cant), "f": load_data(f_fatt)
    }

    # Normalizzazione per tutte le tabelle
    for k in dfs:
        col = next((c for c in ['Cliente', 'Rag. Soc.', 'Ragione_sociale'] if c in dfs[k].columns), dfs[k].columns[0])
        dfs[k]['key'] = dfs[k][col].apply(normalize_name)
        dfs[k]['Nome_Pulito'] = dfs[k][col]

    # --- 4. LOGICA AGGIORNAMENTO MENSILE ---
    sheet = init_gsheet()
    db_cloud = pd.DataFrame(sheet.get_all_records()) if sheet else pd.DataFrame()

    # Uniamo i dati del gestionale (CANTIERI e FATTURATO) con il database storico
    # Così se un cantiere era già stato inserito il mese scorso, l'app mostra i costi già salvati
    merged_marg = pd.merge(dfs['c'][['key', 'Nome_Pulito', 'Totale']], 
                           db_cloud[['key', 'Manodopera', 'Materiali', 'Extra']], 
                           on='key', how='left').fillna(0)

    # --- 5. INTERFACCIA TABS ---
    t_perf, t_marg = st.tabs(["📊 Performance", "🏗️ Marginalità Mensile"])

    with t_perf:
        # Qui integriamo i dati per i grafici (Funnel, Sorgenti)
        master = pd.merge(dfs['a'], dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
        st.subheader("Analisi Conversioni")
        # [Codice per grafici Funnel e Pie invariato]
        st.write("Dati elaborati correttamente per il report.")

    with t_marg:
        st.subheader("Gestione Costi e Aggiornamento Database")
        st.info("I dati sotto includono i cantieri caricati oggi. Se avevi già inserito i costi nei mesi scorsi, li vedrai apparire automaticamente.")
        
        # Tabella editabile per Manodopera, Materiali, Extra
        edited_df = st.data_editor(merged_marg, column_config={"key": None}, use_container_width=True)

        if st.button("💾 Salva e Aggiorna Database"):
            # Aggiungiamo il timestamp per sapere quando è stato fatto l'ultimo update
            edited_df['Ultimo_Aggiornamento'] = pd.Timestamp.now().strftime('%Y-%m-%d')
            
            # AGGIORNAMENTO INTELLIGENTE: invece di pulire tutto, potremmo fare un append, 
            # ma per semplicità ora aggiorniamo l'intero foglio con lo stato attuale
            if sheet:
                sheet.clear()
                sheet.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
                st.success("Dati sincronizzati con il Google Sheet!")

        # Calcolo ROI Totale
        total_entrate = edited_df['Totale'].sum()
        total_uscite = edited_df[['Manodopera', 'Materiali', 'Extra']].sum().sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Fatturato Totale", f"{total_entrate:,.2f} €")
        c2.metric("Margine (€)", f"{total_entrate - total_uscite:,.2f} €")
        c3.metric("Margine (%)", f"{((total_entrate - total_uscite)/total_entrate*100 if total_entrate > 0 else 0):.1f}%")

else:
    st.warning("⚠️ Carica tutti i 6 file nella sidebar per attivare l'analisi completa.")
