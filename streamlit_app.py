import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF # Ricorda di aggiungerlo a requirements.txt
import io

st.set_page_config(page_title="CRM & Marketing Analytics", layout="wide")

# --- 1. GESTIONE BUDGET PUBBLICITARIO PER AGENTE ---
with st.sidebar:
    st.header("💰 Budget Pubblicitario")
    st.info("Assegna il valore pubblicitario mensile per ciascun agente.")
    
    # Inizializzazione tabella budget se non esiste
    if 'budget_agenti' not in st.session_state:
        st.session_state.budget_agenti = pd.DataFrame([
            {"Agente": "AGENTE A", "Mese": "2026-03", "Budget": 500.0},
            {"Agente": "AGENTE B", "Mese": "2026-03", "Budget": 300.0},
        ])
    
    # Editor dinamico per assegnare budget agli agenti
    edited_budget = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic")
    st.session_state.budget_agenti = edited_budget

# --- 2. FUNZIONE GENERAZIONE PDF ---
def genera_pdf(nome_agente, dati_agente, periodo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Report Performance: {nome_agente}", ln=True, align='C')
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 10, f"Periodo: {periodo}", ln=True, align='C')
    pdf.ln(10)
    
    # Tabella Dati
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(95, 10, "Metrica", 1, 0, 'C', True)
    pdf.cell(95, 10, "Valore", 1, 1, 'C', True)
    
    metriche = [
        ("Leads Assegnati", str(dati_agente['Leads'])),
        ("Sopralluoghi", str(dati_agente['Sopralluoghi'])),
        ("Conversione Lead/Sopr.", f"{dati_agente['Conv_Perc']}%"),
        ("Contratti (Fatturato > 0)", str(dati_agente['Contratti'])),
        ("Fatturato Totale", f"{dati_agente['Fatturato']:,.2f} EUR")
    ]
    
    for m, v in metriche:
        pdf.cell(95, 10, m, 1)
        pdf.cell(95, 10, v, 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 3. FUNZIONI DI PULIZIA (Invariate) ---
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

# --- 4. CARICAMENTO E UNIFICAZIONE ---
st.title("📊 CRM Analytics & Performance Agenti")

with st.expander("📁 Carica i File Storici"):
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    df_a, df_l, df_s, df_o, df_c, df_f = load(f_anal), load(f_list), load(f_sopr), load(f_offe), load(f_cant), load(f_fatt)

    # Elaborazione dati
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_s['key'] = df_s['Rag. Soc.'].apply(normalize_name)
    df_f['key'] = df_f['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)

    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, df_l.drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    master['Fatturato'] = master['key'].map(df_f.groupby('key')['Valore_Netto'].sum()).fillna(0)
    master['Agente'] = master['Agente'].fillna("DA ASSEGNARE")

    # --- 5. DASHBOARD AGENTE ---
    st.divider()
    st.subheader("👤 Analisi Singolo Agente")
    
    c1, c2 = st.columns(2)
    with c1:
        agente_scelto = st.selectbox("Seleziona Agente", master['Agente'].unique())
    with c2:
        periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
        periodo_scelto = st.selectbox("Seleziona Periodo", ["TUTTO LO STORICO"] + periodi)

    # Filtraggio dati agente
    df_agente = master[master['Agente'] == agente_scelto]
    if periodo_scelto != "TUTTO LO STORICO":
        df_agente = df_agente[df_agente['Mese_Anno'] == periodo_scelto]

    # Calcolo metriche per report
    leads_tot = len(df_agente)
    sopr_tot = int(df_agente['Sopralluogo'].sum())
    conv_perc = round((sopr_tot / leads_tot * 100), 2) if leads_tot > 0 else 0
    contratti = len(df_agente[df_agente['Fatturato'] > 0])
    fatt_agente = df_agente['Fatturato'].sum()

    # Visualizzazione KPI Agente
    ka1, ka2, ka3, ka4 = st.columns(4)
    ka1.metric("Leads Assegnati", leads_tot)
    ka2.metric("Sopralluoghi", sopr_tot, f"{conv_perc}% conv.")
    ka3.metric("Contratti", contratti)
    ka4.metric("Fatturato", f"{fatt_agente:,.2f} €")

    # Bottone PDF
    dati_per_pdf = {
        'Leads': leads_tot, 'Sopralluoghi': sopr_tot, 
        'Conv_Perc': conv_perc, 'Contratti': contratti, 'Fatturato': fatt_agente
    }
    
    pdf_file = genera_pdf(agente_scelto, dati_per_pdf, periodo_scelto)
    st.download_button(label="📄 Scarica Report PDF Agente", data=pdf_file, 
                       file_name=f"Report_{agente_scelto}_{periodo_scelto}.pdf", mime="application/pdf")

else:
    st.info("👋 Carica i file storici per sbloccare l'analisi per agente.")
