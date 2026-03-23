import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF
import io

# Configurazione Pagina
st.set_page_config(page_title="CRM & Marketing Analytics PRO", layout="wide")

# --- 1. FUNZIONE GENERAZIONE PDF MIGLIORATA ---
def genera_pdf(nome_agente, dati_agente, periodo):
    pdf = FPDF()
    pdf.add_page()
    
    # Gestione Logo
    try:
        pdf.image("logo.png", x=10, y=8, w=40) 
    except:
        pdf.set_font("Arial", "I", 8)
        pdf.cell(190, 5, "[Logo Aziendale]", ln=True, align='L')

    pdf.set_font("Arial", "B", 18)
    pdf.ln(10)
    pdf.cell(190, 10, "REPORT PERFORMANCE AGENTE", ln=True, align='C')
    
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(190, 10, f"{nome_agente.upper()}", ln=True, align='C')
    
    pdf.set_font("Arial", "I", 11)
    pdf.cell(190, 7, f"Periodo: {periodo}", ln=True, align='C')
    pdf.ln(15)
    
    # Tabella KPI
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(95, 12, "Indicatore (KPI)", 1, 0, 'C', True)
    pdf.cell(95, 12, "Risultato", 1, 1, 'C', True)
    
    pdf.set_font("Arial", "", 12)
    # Sostituiamo il simbolo € con EUR per evitare errori di codifica nel PDF standard
    metriche = [
        ("Leads Assegnati", f"{dati_agente['Leads']}"),
        ("Sopralluoghi Effettuati", f"{dati_agente['Sopralluoghi']}"),
        ("Tasso di Conversione", f"{dati_agente['Conv_Perc']}%"),
        ("Fatturato Generato", f"{dati_agente['Fatturato']:,.2f} EUR"),
        ("Budget Marketing", f"{dati_agente['Budget']:,.2f} EUR"),
        ("ROI (Ritorno Investimento)", f"{dati_agente['ROI']}x")
    ]
    
    for m, v in metriche:
        pdf.cell(95, 10, f" {m}", 1)
        pdf.cell(95, 10, f"{v} ", 1, 1, 'R')
        
    pdf.set_y(-30)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(190, 10, "Documento ad uso interno - Generato da CRM Analytics", 0, 0, 'C')
        
    # Usiamo 'latin-1' ma gestiamo i caratteri speciali
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 2. SIDEBAR BUDGET ---
with st.sidebar:
    st.header("💰 Gestione Budget")
    if 'budget_agenti' not in st.session_state:
        st.session_state.budget_agenti = pd.DataFrame([
            {"Agente": "NEW DDL DI DE LORENZI DANIELE", "Mese": "2026-03", "Budget": 1000.0}
        ])
    
    st.session_state.budget_agenti = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic")

# --- 3. PULIZIA ---
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

# --- 4. CARICAMENTO ---
st.title("📊 Dashboard Analitica & Performance")

with st.expander("📁 Caricamento File Storici"):
    files = {
        "anal": st.file_uploader("1. ANALISI", type=['xlsx', 'csv']),
        "list": st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv']),
        "sopr": st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv']),
        "offe": st.file_uploader("4. OFFERTE", type=['xlsx', 'csv']),
        "cant": st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv']),
        "fatt": st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])
    }

if all(files.values()):
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    dfs = {k: load(v) for k, v in files.items()}

    # Chiavi
    dfs['anal']['key'] = dfs['anal']['Cliente'].apply(normalize_name)
    dfs['list']['key'] = dfs['list']['Ragione_sociale'].apply(normalize_name)
    dfs['sopr']['key'] = dfs['sopr']['Rag. Soc.'].apply(normalize_name)
    dfs['fatt']['key'] = dfs['fatt']['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in dfs['fatt'].columns else 'Totale'
    dfs['fatt']['Valore_Netto'] = dfs['fatt'][col_soldi].apply(clean_currency)

    # UNIFICAZIONE AGENTE (Cruciale per i PDF)
    master = dfs['anal'][dfs['anal']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['list'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # Segniamo i sopralluoghi
    sopr_keys = set(dfs['sopr']['key'].unique())
    master['Sopralluogo'] = master['key'].apply(lambda x: x in sopr_keys)
    
    # RECUPERO AGENTE: Se c'è un sopralluogo, cerchiamo chi l'ha creato nel file Sopralluoghi
    sopr_agente_map = dfs['sopr'].drop_duplicates('key').set_index('key')['Creato da'].to_dict()
    
    def recupera_agente(row):
        if pd.notna(row['Agente']) and row['Agente'] != "":
            return row['Agente']
        # Se l'agente è vuoto ma c'è un sopralluogo, prendi chi ha inserito il sopralluogo
        return sopr_agente_map.get(row['key'], "DA ASSEGNARE")

    master['Agente'] = master.apply(recupera_agente, axis=1)
    
    # Fatturato
    fatt_cli = dfs['fatt'].groupby('key')['Valore_Netto'].sum()
    master['Fatturato'] = master['key'].map(fatt_cli).fillna(0)

    # --- 5. INTERFACCIA ---
    st.divider()
    periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
    
    col1, col2 = st.columns(2)
    with col1:
        agente_scelto = st.selectbox("👤 Seleziona Agente", sorted(master['Agente'].unique()))
    with col2:
        periodo_agente = st.selectbox("📅 Seleziona Periodo", ["STORICO TOTALE"] + periodi)

    # Filtro
    df_ag = master[master['Agente'] == agente_scelto]
    if periodo_agente != "STORICO TOTALE":
        df_ag = df_ag[df_ag['Mese_Anno'] == periodo_agente]

    # Metriche
    l_tot = len(df_ag)
    s_tot = int(df_ag['Sopralluogo'].sum())
    c_perc = round((s_tot / l_tot * 100), 1) if l_tot > 0 else 0
    f_tot = df_ag['Fatturato'].sum()

    # Budget & ROI
    b_df = st.session_state.budget_agenti
    if periodo_agente == "STORICO TOTALE":
        bud = b_df[b_df['Agente'] == agente_scelto]['Budget'].sum()
    else:
        bud = b_df[(b_df['Agente'] == agente_scelto) & (b_df['Mese'] == periodo_agente)]['Budget'].sum()
    
    roi = round(f_tot / bud, 2) if bud > 0 else 0

    # Display
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Leads", l_tot)
    m2.metric("Sopralluoghi", s_tot, f"{c_perc}% conv.")
    m3.metric("Fatturato", f"{f_tot:,.2f} €")
    m4.metric("ROI", f"{roi}x")

    # PDF Button
    dati_pdf = {'Leads': l_tot, 'Sopralluoghi': s_tot, 'Conv_Perc': c_perc, 'Fatturato': f_tot, 'Budget': bud, 'ROI': roi}
    try:
        pdf_file = genera_pdf(agente_scelto, dati_pdf, periodo_agente)
        st.download_button("📥 Scarica Report PDF", pdf_file, f"Report_{agente_scelto}.pdf", "application/pdf")
    except Exception as e:
        st.error(f"Errore generazione PDF: {e}")

    st.subheader("Dettaglio Operativo")
    st.dataframe(df_ag[['Data_Ref', 'key', 'Sorgente', 'Sopralluogo', 'Fatturato']], use_container_width=True)

else:
    st.info("Carica i 6 file per iniziare.")
