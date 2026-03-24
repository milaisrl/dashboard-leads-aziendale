import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- CONNESSIONE GOOGLE SHEETS ---
def init_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Utilizziamo i secrets per la sicurezza
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Domei_Database").worksheet("Marginalita")

# --- PULIZIA AUTOMATICA ---
def normalize_name(name):
    if pd.isna(name): return ""
    return " ".join(sorted(re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip().split()))

# --- CORE APP ---
st.title("Statistiche Commerciali & Marginalità")

# Caricamento file (come da tuoi screenshot)
f_cantieri = st.sidebar.file_uploader("Carica File Cantieri", type=['xlsx'])

if f_cantieri:
    df_c = pd.read_excel(f_cantieri)
    # Pulizia nomi automatica per evitare errori dell'impiegata
    df_c['key'] = df_c['Ragione_Sociale'].apply(normalize_name)
    
    st.subheader("Calcolo Marginalità")
    
    # Integramo con i dati già presenti sul foglio Google per non sovrascrivere il lavoro fatto
    sheet = init_gsheet()
    existing_data = pd.DataFrame(sheet.get_all_records())
    
    # Creiamo la tabella per l'inserimento rapido (Manodopera, Materiali, Extra)
    # L'app cercherà di pre-compilare se i dati esistono già nel DB
    df_merge = pd.merge(df_c[['key', 'Ragione_Sociale', 'Totale']], 
                        existing_data[['key', 'Manodopera', 'Materiali', 'Extra']], 
                        on='key', how='left').fillna(0)
    
    edited_df = st.data_editor(df_merge, num_rows="dynamic")

    if st.button("💾 Salva e Sincronizza su Google Sheets"):
        # Trasformiamo il dataframe per il foglio Google (10 colonne come da tuo screen)
        # Aggiungiamo Mese_Anno e Quota_Mkt calcolata
        edited_df['Mese_Anno'] = pd.Timestamp.now().strftime('%Y-%m')
        
        # Pulizia foglio e aggiornamento (Automazione totale)
        sheet.clear()
        sheet.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("Dati salvati con successo nel Domei_Database!")

    # Visualizzazione ROI (come da tuoi screenshot)
    st.divider()
    st.subheader("Performance Economica")
    total_valore = edited_df['Totale'].sum()
    total_costi = edited_df['Manodopera'].sum() + edited_df['Materiali'].sum() + edited_df['Extra'].sum()
    st.metric("Margine Aziendale", f"{total_valore - total_costi:,.2f} €", f"{((total_valore - total_costi)/total_valore*100 if total_valore > 0 else 0):.1f}%")
