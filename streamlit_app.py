import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# --- CONNESSIONE GOOGLE SHEETS (DB) ---
def init_gsheet():
    # Usa le credenziali salvate nei Secrets di Streamlit Cloud
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    # Apre il file che abbiamo visto nello screenshot
    return client.open("Domei_Database").worksheet("Marginalita")

# --- FUNZIONE PULIZIA (L'arma segreta contro gli errori manuali) ---
def normalize_name(name):
    if pd.isna(name): return ""
    # Rimuove spazi doppi, caratteri speciali e mette in ordine alfabetico le parole
    # Così "Rossi Luigi" e "Luigi Rossi " diventano la stessa chiave
    return " ".join(sorted(re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip().split()))

# --- INTERFACCIA ---
st.title("Statistiche Commerciali & Marginalità")

with st.sidebar:
    f_cantieri = st.file_uploader("Carica File Cantieri", type=['xlsx'])

if f_cantieri:
    # 1. Lettura dati dal file Excel caricato
    df_c = pd.read_excel(f_cantieri)
    df_c.columns = df_c.columns.astype(str).str.strip()
    
    # Cerchiamo la colonna ragione sociale (gestisce diverse varianti nel nome colonna)
    col_rag = next((c for c in df_c.columns if 'Rag' in c or 'Cliente' in c), df_c.columns[0])
    df_c['key'] = df_c[col_rag].apply(normalize_name)
    df_c['Rag_Soc_Pulita'] = df_c[col_rag]

    # 2. Recupero dati storici dal Google Sheet
    try:
        sheet = init_gsheet()
        existing_data = pd.DataFrame(sheet.get_all_records())
        if not existing_data.empty:
            # Uniamo i dati caricati con quelli già salvati (per non perdere Manodopera/Materiali già inseriti)
            df_final = pd.merge(df_c[['key', 'Rag_Soc_Pulita', 'Totale']], 
                                existing_data[['key', 'Manodopera', 'Materiali', 'Extra']], 
                                on='key', how='left').fillna(0)
        else:
            df_final = df_c[['key', 'Rag_Soc_Pulita', 'Totale']].copy()
            for col in ['Manodopera', 'Materiali', 'Extra']: df_final[col] = 0.0
    except Exception as e:
        st.error(f"Errore connessione DB: {e}")
        df_final = df_c[['key', 'Rag_Soc_Pulita', 'Totale']].copy()

    # 3. Tabella Editabile (L'unico punto dove l'impiegata deve intervenire)
    st.subheader("Inserimento Costi di Cantiere")
    edited_df = st.data_editor(df_final, column_config={"key": None}, use_container_width=True)

    # 4. Salvataggio
    if st.button("💾 Salva e Sincronizza su Google Sheets"):
        # Preparazione dati per le 10 colonne dello screenshot
        # key, Rag. Soc., Agente, Valore_Contratto, Quota_Mkt, Manodopera, Materiali, Extra, Mese_Anno
        output_df = edited_df.copy()
        output_df['Mese_Anno'] = pd.Timestamp.now().strftime('%Y-%m')
        
        # Aggiorna il foglio
        sheet.clear()
        sheet.update([output_df.columns.values.tolist()] + output_df.values.tolist())
        st.success("Sincronizzazione completata!")

    # 5. Visualizzazione Risultati (ROI)
    total_fatt = edited_df['Totale'].sum()
    total_costi = edited_df[['Manodopera', 'Materiali', 'Extra']].sum().sum()
    
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Fatturato Caricato", f"{total_fatt:,.2f} €")
    m2.metric("Costi Totali", f"{total_costi:,.2f} €")
    m3.metric("Margine Operativo", f"{total_fatt - total_costi:,.2f} €", f"{((total_fatt-total_costi)/total_fatt*100 if total_fatt>0 else 0):.1f}%")

else:
    st.info("👋 In attesa del file Excel dei Cantieri per generare la tabella di marginalità.")
