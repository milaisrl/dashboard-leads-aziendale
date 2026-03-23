import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")
st.title("📊 Analisi Performance Leads (Deep Match)")

# --- FUNZIONE DI PULIZIA AVANZATA ---
def normalize_name(name):
    if pd.isna(name): return ""
    # Rimuove tutto ciò che non è una lettera, spazi extra e mette in minuscolo
    s = re.sub(r'[^a-zA-Z\s]', '', str(name)).lower().strip()
    # Divide il nome in parole e le ordina alfabeticamente
    # Esempio: "Rossi Mario" e "Mario Rossi" diventano entrambi "mario rossi"
    parts = sorted(s.split())
    return " ".join(parts)

def clean_currency(value):
    if pd.isna(value): return 0.0
    if isinstance(value, str):
        value = value.replace('.', '').replace(',', '.')
    try: return float(value)
    except: return 0.0

# --- SIDEBAR ---
with st.sidebar:
    st.header("Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])
    investimento = st.number_input("Investimento (€)", min_value=0.0, value=1000.0)

# --- ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        return df.dropna(how='all')

    # Caricamento
    df_a = load(f_anal)
    df_l = load(f_list)
    df_s = load(f_sopr)
    df_o = load(f_offe)
    df_c = load(f_cant)
    df_f = load(f_fatt)

    # CREAZIONE CHIAVI NORMALIZZATE
    # Usiamo i nomi delle colonne che abbiamo visto nei tuoi file
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_name)
    df_o['key'] = df_o['Rag. Soc.'].apply(normalize_name)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_name)
    
    # Pulizia particolare per il Fatturato (rimuove i codici cliente [CI-xxx])
    df_f['key'] = df_f['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)

    # --- COSTRUZIONE TABELLA MASTER ---
    # Partiamo dai lead dell'analisi (escludendo i contatti tecnici)
    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    
    # 1. Recuperiamo Agente e Sorgente dalla LISTA LEADS
    # Rimuoviamo i duplicati dalla lista leads per evitare di moltiplicare le righe
    df_l_unique = df_l.drop_duplicates(subset=['key'])
    master = pd.merge(master, df_l_unique[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # 2. Assegnazione Sopralluoghi
    sopr_keys = set(df_s['key'].unique())
    master['Sopralluogo'] = master['key'].apply(lambda x: x in sopr_keys)

    # --- LOGICA DI RECUPERO AGENTE ---
    # Se il cliente ha fatto un sopralluogo, forziamo l'agente a De Lorenzi se non trovato
    def assegna_agente(row):
        if pd.notna(row['Agente']) and row['Agente'] != "":
            return row['Agente']
        if row['Sopralluogo']:
            return "NEW DDL DI DE LORENZI DANIELE"
        return "DA ASSEGNARE / FUORI ZONA"

    master['Agente'] = master.apply(assegna_agente, axis=1)
    master['Sorgente'] = master['Sorgente'].fillna('Sconosciuta')

    # 3. Aggancio Fatturato
    fatt_sum = df_f.groupby('key')['Valore_Netto'].sum().reset_index()
    master = pd.merge(master, fatt_sum, on='key', how='left').fillna(0)

    # --- DASHBOARD ---
    st.header("📈 Risultati Mensili")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads Totali", len(master))
    k2.metric("Sopralluoghi", int(master['Sopralluogo'].sum()))
    k3.metric("Costo/Lead", f"{round(investimento/len(master), 2)} €")
    k4.metric("Fatturato", f"{df_f['Valore_Netto'].sum():,.2f} €")

    st.divider()
    
    # Tabella Performance
    perf = master.groupby('Agente').agg(
        Leads=('key', 'count'),
        Sopralluoghi=('Sopralluogo', 'sum'),
        Fatturato=('Valore_Netto', 'sum')
    ).reset_index()
    
    perf['% Conv.'] = ((perf['Sopralluoghi'] / perf['Leads']) * 100).round(1)
    
    c_graf1, c_graf2 = st.columns(2)
    with c_graf1:
        st.plotly_chart(px.bar(perf, x='Agente', y='Leads', title="Leads per Agente"), use_container_width=True)
    with c_graf2:
        st.plotly_chart(px.pie(master, names='Sorgente', title="Origine dei Leads"), use_container_width=True)

    st.subheader("Dettaglio Analisi")
    st.dataframe(perf.sort_values(by='Leads', ascending=False), use_container_width=True)

else:
    st.info("Carica i 6 file per avviare l'analisi.")
