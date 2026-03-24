import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

def init_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database").worksheet("Marginalita")
    except: return None

def normalize_name(name):
    if pd.isna(name): return ""
    return " ".join(sorted(re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip().split()))

# --- SIDEBAR ---
with st.sidebar:
    st.header("📁 Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'xls', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'xls', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'xls', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'xls', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'xls', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'xls', 'csv'])

# --- LOGICA DI CARICAMENTO ROBUSTA ---
def smart_load(f):
    if f is None: return pd.DataFrame()
    try:
        if f.name.endswith('.csv'):
            return pd.read_csv(f, sep=None, engine='python')
        try:
            # Prova formato moderno .xlsx
            return pd.read_excel(f, engine='openpyxl')
        except:
            # Prova formato vecchio .xls
            return pd.read_excel(f, engine='xlrd')
    except Exception as e:
        st.error(f"Impossibile leggere {f.name}. Verifica che non sia protetto da password.")
        return pd.DataFrame()

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    dfs = {
        "a": smart_load(f_anal), "l": smart_load(f_list), 
        "s": smart_load(f_sopr), "o": smart_load(f_offe),
        "c": smart_load(f_cant), "f": smart_load(f_fatt)
    }

    # Controllo che i dati non siano vuoti prima di procedere
    valid = True
    for k, v in dfs.items():
        if v.empty:
            st.error(f"Il file {k} caricato sembra vuoto o non leggibile.")
            valid = False
    
    if valid:
        # Normalizzazione chiavi
        for k in dfs:
            cols = dfs[k].columns.tolist()
            # Cerchiamo una colonna sensata per il nome cliente
            target_col = next((c for c in cols if any(x in c for x in ['Cliente', 'Rag', 'Soc', 'Nominativo'])), cols[0])
            dfs[k]['key'] = dfs[k][target_col].apply(normalize_name)
            dfs[k]['Nome_Pulito'] = dfs[k][target_col]

        # --- LOGICA AGGIORNAMENTO MENSILE (MEMORIA) ---
        sheet = init_gsheet()
        # Scarichiamo lo storico da Google Sheets
        try:
            db_cloud = pd.DataFrame(sheet.get_all_records())
        except:
            db_cloud = pd.DataFrame(columns=['key', 'Manodopera', 'Materiali', 'Extra'])

        # Costruiamo la tabella per l'impiegata
        # Prendiamo i cantieri dal file Excel e "attacchiamo" i costi se già esistono nel cloud
        current_cantieri = dfs['c'].copy()
        # Se il file cantieri ha una colonna Totale/Prezzo, usiamola
        val_col = next((c for c in current_cantieri.columns if 'Tot' in c or 'Valore' in c), None)
        current_cantieri['Valore_Contratto'] = current_cantieri[val_col] if val_col else 0.0

        merged_marg = pd.merge(
            current_cantieri[['key', 'Nome_Pulito', 'Valore_Contratto']], 
            db_cloud[['key', 'Manodopera', 'Materiali', 'Extra']], 
            on='key', how='left'
        ).fillna(0)

        # --- TABS ---
        t_perf, t_marg = st.tabs(["📊 Performance Commerciali", "🏗️ Marginalità & Storico"])

        with t_perf:
            st.subheader("Analisi Conversione")
            # Qui inseriremo i grafici Funnel come prima
            st.write("Caricamento completato. Seleziona l'altro Tab per inserire i costi.")

        with t_marg:
            st.info("💡 Qui puoi aggiornare i costi. I dati salvati verranno ricordati il mese prossimo.")
            edited_df = st.data_editor(merged_marg, column_config={"key": None}, use_container_width=True)

            if st.button("💾 Salva/Aggiorna Database"):
                if sheet:
                    # Preparazione per Google Sheets
                    final_to_save = edited_df.copy()
                    final_to_save['Data_Update'] = pd.Timestamp.now().strftime('%d/%m/%Y')
                    sheet.clear()
                    sheet.update([final_to_save.columns.values.tolist()] + final_to_save.values.tolist())
                    st.success("Dati sincronizzati con successo!")
                else:
                    st.error("Connessione a Google Sheets non riuscita.")

else:
    st.info("Per favore carica tutti i 6 file richiesti per procedere.")
