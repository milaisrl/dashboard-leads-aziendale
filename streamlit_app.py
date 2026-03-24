import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from thefuzz import process, fuzz # Serve per accoppiare i nomi scritti in modo diverso

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Domei Business Intelligence", layout="wide")

# Funzione di pulizia stringhe
def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).lower().strip()
    text = re.sub(r'\b(srl|s\.r\.l\.|spa|s\.p\.a\.|snc|sas|ss|ditta)\b', '', text)
    return re.sub(r'[^a-z0-9]', '', text)

# Funzione per trovare il match tra i nomi (Fuzzy Match)
def get_match_score(name, list_to_check):
    if not name or len(list_to_check) == 0: return 0
    # Cerca il nome più simile nella lista e restituisce il punteggio di somiglianza
    _, score = process.extractOne(name, list_to_check, scorer=fuzz.token_sort_ratio)
    return score

# --- CARICAMENTO FILE ---
with st.sidebar:
    st.header("📁 Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
    f_sopr = st.file_uploader("2. SOPRALLUOGHI", type=['xlsx'])
    f_cant = st.file_uploader("3. CANTIERI (Contratti)", type=['xlsx'])
    # Altri file omessi per brevità, aggiungili come i precedenti

if f_anal and f_sopr and f_cant:
    # Lettura file
    df_a = pd.read_excel(f_anal)
    df_s = pd.read_excel(f_sopr)
    df_c = pd.read_excel(f_cant)

    # Identificazione colonne Nome (cerca automaticamente la colonna più probabile)
    def find_name_col(df):
        cols = df.columns.tolist()
        return next((c for c in cols if any(x in c.lower() for x in ['cliente', 'rag', 'nominativo'])), cols[0])

    col_a = find_name_col(df_a)
    col_s = find_name_col(df_s)
    col_c = find_name_col(df_c)

    # Pulizia nomi per il matching
    df_a['key'] = df_a[col_a].apply(clean_text)
    list_s = df_s[col_s].apply(clean_text).unique().tolist()
    list_c = df_c[col_c].apply(clean_text).unique().tolist()

    # --- LOGICA DEI CONTATORI (Il cuore del problema) ---
    # Usiamo una soglia di somiglianza (85%) per decidere se è lo stesso cliente
    with st.spinner("Sincronizzazione nomi in corso..."):
        df_a['Sopralluogo_Match'] = df_a['key'].apply(lambda x: 1 if get_match_score(x, list_s) > 85 else 0)
        df_a['Contratto_Match'] = df_a['key'].apply(lambda x: 1 if get_match_score(x, list_c) > 85 else 0)

    # --- DASHBOARD ---
    st.title("📊 Statistiche Commerciali")
    
    # Filtro Agente (Cerca colonna Agente nell'Analisi)
    col_ag = next((c for c in df_a.columns if 'agente' in c.lower()), None)
    if col_ag:
        agente = st.selectbox("Seleziona Agente", sorted(df_a[col_ag].unique()))
        df_filtered = df_a[df_a[col_ag] == agente]
    else:
        df_filtered = df_a

    c1, c2, c3 = st.columns(3)
    c1.metric("Leads", len(df_filtered))
    c2.metric("Sopralluoghi", int(df_filtered['Sopralluogo_Match'].sum()))
    c3.metric("Contratti", int(df_filtered['Contratto_Match'].sum()))

    # Debug Tabella
    if st.checkbox("Mostra dati sincronizzati (Verifica Match)"):
        st.write(df_filtered[[col_a, 'Sopralluogo_Match', 'Contratto_Match']].head(20))

else:
    st.info("Carica i file ANALISI, SOPRALLUOGHI e CANTIERI per vedere i dati.")
