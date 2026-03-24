import streamlit as st
import pandas as pd
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Domei Intelligence Pro", layout="wide")

# Funzione di pulizia per far combaciare i nomi (es. "Anselmi Elena" == "ANSELMI ELENA")
def normalize_key(text):
    if pd.isna(text): return ""
    return re.sub(r'[^a-z0-9]', '', str(text).lower().strip())

# --- CARICAMENTO DATI ---
st.sidebar.header("📁 Caricamento Database")
f_anal = st.sidebar.file_uploader("1. ANALISI (Leads)", type=['xlsx'])
f_list = st.sidebar.file_uploader("2. LISTA LEADS (Anagrafica)", type=['xlsx'])
f_sopr = st.sidebar.file_uploader("3. SOPRALLUOGHI", type=['xlsx'])
f_offe = st.sidebar.file_uploader("4. OFFERTE", type=['xlsx'])
f_cant = st.sidebar.file_uploader("5. CANTIERI", type=['xlsx'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant]):
    # Caricamento dei DataFrame
    df_a = pd.read_excel(f_anal)
    df_l = pd.read_excel(f_list)
    df_s = pd.read_excel(f_sopr)
    df_o = pd.read_excel(f_offe)
    df_c = pd.read_excel(f_cant)

    # 1. Normalizzazione delle chiavi di collegamento su tutti i file
    df_a['key'] = df_a['Cliente'].apply(normalize_key)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_key)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_key)
    df_o['key'] = df_o['Rag. Soc.'].apply(normalize_key)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_key)

    # 2. Creazione di una mappa globale degli Agenti
    # Uniamo le informazioni degli agenti da tutti i file per non perdere dati
    map_l = df_l.set_index('key')['Agente'].to_dict()
    map_s = df_s.set_index('key')['Creato da'].to_dict()
    map_o = df_o.set_index('key')['Creato da'].to_dict()
    map_c = df_c.set_index('key')['Creato da'].to_dict()

    def get_agente(row):
        k = row['key']
        # Priorità: 1. Lista Leads, 2. Cantieri, 3. Offerte, 4. Sopralluoghi
        return map_l.get(k) or map_c.get(k) or map_o.get(k) or map_s.get(k) or "NON ASSEGNATO"

    df_a['Agente_Assegnato'] = df_a.apply(get_agente, axis=1)

    # 3. Calcolo delle conversioni (Verifica presenza del lead negli altri file)
    set_sopr = set(df_s['key'].unique())
    set_offe = set(df_o['key'].unique())
    set_cant = set(df_c['key'].unique())

    df_a['Has_Sopralluogo'] = df_a['key'].isin(set_sopr)
    df_a['Has_Offerta'] = df_a['key'].isin(set_offe)
    df_a['Has_Contratto'] = df_a['key'].isin(set_cant)

    # --- DASHBOARD ---
    st.title("📊 Analisi Performance Commerciale")

    # Filtro Agente (ottimizzato per trovare "Daniele")
    lista_agenti = sorted([str(x) for x in df_a['Agente_Assegnato'].unique() if x])
    sel_agente = st.selectbox("Seleziona Agente", lista_agenti, 
                               index=lista_agenti.index(next(s for s in lista_agenti if "DANIELE" in s.upper())) if any("DANIELE" in s.upper() for s in lista_agenti) else 0)

    df_final = df_a[df_a['Agente_Assegnato'] == sel_agente]

    # Metriche principali
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads Totali", len(df_final))
    c2.metric("Sopralluoghi", df_final['Has_Sopralluogo'].sum())
    c3.metric("Offerte", df_final['Has_Offerta'].sum())
    c4.metric("Contratti", df_final['Has_Contratto'].sum())

    st.divider()

    # Visualizzazione Tabellare per Controllo
    st.subheader(f"Dettaglio Lead: {sel_agente}")
    st.dataframe(df_final[['Cliente', 'Has_Sopralluogo', 'Has_Offerta', 'Has_Contratto']].reset_index(drop=True), use_container_width=True)

else:
    st.info("👋 Carica i 5 file Excel nella barra laterale per generare le statistiche.")
