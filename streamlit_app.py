import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Dashboard Leads Aziendale", layout="wide")
st.title("📊 Analisi Performance Leads & Fatturato")

# --- FUNZIONI DI NORMALIZZAZIONE AVANZATA ---
def normalize_name(name):
    if pd.isna(name): return ""
    # Rimuove tutto ciò che non è una lettera o numero, mette in minuscolo
    s = re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip()
    # Ordina le parole alfabeticamente per gestire "Rossi Mario" e "Mario Rossi"
    parts = sorted(s.split())
    return " ".join(parts)

def super_clean_fatturato(name):
    if pd.isna(name): return ""
    s = str(name).upper()
    # 1. Rimuove codici tra parentesi quadre come [CI-704]
    s = re.sub(r'\[.*\]', '', s)
    # 2. Rimuove suffissi societari comuni
    s = re.sub(r'\b(S\.?R\.?L\.?|S\.?N\.?C\.?|S\.?P\.?A\.?|SAS|SS|S\.R\.L\.S\.)\b', '', s)
    # 3. Normalizzazione standard
    return normalize_name(s)

def clean_currency(value):
    if pd.isna(value): return 0.0
    if isinstance(value, str):
        # Toglie i punti delle migliaia e converte la virgola in punto
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
    st.divider()
    investimento = st.number_input("Investimento Pubblicitario (€)", min_value=0.0, value=1000.0)

# --- MOTORE DI ELABORAZIONE ---
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

    # Creazione Chiavi Univoche Normalizzate
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_name)
    df_o['key'] = df_o['Rag. Soc.'].apply(normalize_name)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_name)
    
    # Pulizia specifica per il Fatturato
    df_f['key'] = df_f['Descrizione conto'].apply(super_clean_fatturato)
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)

    # --- COSTRUZIONE TABELLA MASTER ---
    # Partiamo dai leads (escludendo contatti tecnici)
    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    
    # 1. Join con Lista Leads (Agente e Sorgente)
    df_l_unique = df_l.drop_duplicates(subset=['key'])
    master = pd.merge(master, df_l_unique[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # 2. Segnamo le conversioni (Sopralluogo e Cantiere)
    sopr_keys = set(df_s['key'].unique())
    cant_keys = set(df_c['key'].unique())
    master['Sopralluogo'] = master['key'].apply(lambda x: x in sopr_keys)
    master['Cantiere'] = master['key'].apply(lambda x: x in cant_keys)

    # 3. Logica Assegnazione Agente (Forzatura su De Lorenzi per i sopralluoghi)
    def assegna_agente(row):
        if pd.notna(row['Agente']) and row['Agente'] != "":
            return row['Agente']
        if row['Sopralluogo']:
            return "NEW DDL DI DE LORENZI DANIELE"
        return "DA ASSEGNARE / FUORI ZONA"

    master['Agente'] = master.apply(assegna_agente, axis=1)
    master['Sorgente'] = master['Sorgente'].fillna('Sconosciuta')

    # 4. Aggregazione Fatturato
    fatt_aggregato = df_f.groupby('key')['Valore_Netto'].sum().reset_index()
    master = pd.merge(master, fatt_aggregato, on='key', how='left').fillna({'Valore_Netto': 0})

    # --- GESTIONE VENDITE EXTRA (Clienti non in lista Leads) ---
    leads_presenti = set(master['key'].unique())
    df_extra = fatt_aggregato[~fatt_aggregato['key'].isin(leads_presenti)].copy()
    
    if not df_extra.empty:
        extra_rows = pd.DataFrame({
            'key': df_extra['key'],
            'Agente': 'VENDITE EXTRA / STORICI',
            'Sorgente': 'Diretto',
            'Sopralluogo': False,
            'Cantiere': True,
            'Valore_Netto': df_extra['Valore_Netto']
        })
        master = pd.concat([master, extra_rows], ignore_index=True)

    # --- DASHBOARD LAYOUT ---
    total_fatt = df_f['Valore_Netto'].sum()
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads Totali", len(master[master['Agente'] != 'VENDITE EXTRA / STORICI']))
    k2.metric("Sopralluoghi", int(master['Sopralluogo'].sum()))
    k3.metric("CPL Medio", f"{round(investimento/len(df_a), 2)} €")
    k4.metric("Fatturato Totale", f"{total_fatt:,.2f} €")

    st.divider()

    # Tabella Performance
    perf = master.groupby('Agente').agg(
        Leads=('key', 'count'),
        Sopralluoghi=('Sopralluogo', 'sum'),
        Cantieri=('Cantiere', 'sum'),
        Fatturato=('Valore_Netto', 'sum')
    ).reset_index()
    
    perf['% Conv.'] = ((perf['Sopralluoghi'] / perf['Leads']) * 100).round(1)
    perf = perf.sort_values(by='Fatturato', ascending=False)

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("Dettaglio Economico per Agente")
        st.dataframe(perf.style.format({'Fatturato': '{:,.2f} €'}), use_container_width=True)
    
    with col_b:
        st.subheader("Origine Leads")
        st.plotly_chart(px.pie(master, names='Sorgente', hole=0.4), use_container_width=True)

    st.subheader("Analisi Conversione")
    st.plotly_chart(px.bar(perf, x='Agente', y=['Leads', 'Sopralluoghi', 'Cantieri'], barmode='group'), use_container_width=True)

else:
    st.warning("Carica tutti i 6 file richiesti nella barra laterale per generare la dashboard.")
