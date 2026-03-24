import streamlit as st
import pandas as pd
import re

# Funzione di pulizia profonda
def clean_string(s):
    if pd.isna(s): return ""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

# Caricamento file (Assicurati che i nomi coincidano con i tuoi caricatori)
if f_anal and f_sopr and f_cant and f_list:
    df_a = pd.read_excel(f_anal) #
    df_s = pd.read_excel(f_sopr) #
    df_c = pd.read_excel(f_cant) #
    df_l = pd.read_excel(f_list) #

    # 1. Creiamo set di chiavi pulite per sopralluoghi e cantieri
    # Usiamo un set per una ricerca ultra-veloce
    sopr_keys = set(df_s['Rag. Soc.'].apply(clean_string).unique())
    cant_keys = set(df_c['Rag. Soc.'].apply(clean_string).unique())

    # 2. Colleghiamo l'Agente ai Lead dell'analisi
    # Nota: Usiamo la Ragione_sociale della LISTA LEADS per trovare l'Agente
    agent_map = df_l.set_index(df_l['Ragione_sociale'].apply(clean_string))['Agente'].to_dict()

    def get_performance(row):
        nome_pulito = clean_string(row['Cliente'])
        # Cerchiamo se il nome dell'analisi esiste come sottostringa o match nei sopralluoghi
        has_sopr = any(nome_pulito in s or s in nome_pulito for s in sopr_keys if nome_pulito != "")
        has_cant = any(nome_pulito in c or c in nome_pulito for c in cant_keys if nome_pulito != "")
        agente = agent_map.get(nome_pulito, "NON ASSEGNATO")
        return pd.Series([has_sopr, has_cant, agente])

    # Applichiamo la logica riga per riga sul file Analisi
    master = df_a.copy()
    master[['Sopralluogo', 'Contratto', 'Agente_Reale']] = master.apply(get_performance, axis=1)

    # 3. Filtro per Daniele (usando una ricerca parziale sul nome agente)
    # Questo cattura sia "Daniele" che "NEW DDL DI DE LORENZI DANIELE"
    df_daniele = master[master['Agente_Reale'].str.contains("DANIELE", case=False, na=False)]

    # Visualizzazione Metriche
    c1, c2, c3 = st.columns(3)
    c1.metric("Leads Totali Daniele", len(df_daniele))
    c2.metric("Sopralluoghi", int(df_daniele['Sopralluogo'].sum()))
    c3.metric("Contratti", int(df_daniele['Contratto'].sum()))

    # TABELLA DI CONTROLLO: Per vedere chi manchi
    if st.checkbox("Vedi dettaglio Lead Daniele (Verifica se mancano nomi)"):
        st.write(df_daniele[['Cliente', 'Sopralluogo', 'Contratto', 'Agente_Reale']])
