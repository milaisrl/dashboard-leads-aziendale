import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF
import io

# Configurazione Pagina
st.set_page_config(page_title="CRM & Marketing Analytics PRO", layout="wide")

# --- 1. FUNZIONE GENERAZIONE PDF ---
def genera_pdf(nome_agente, dati_agente, periodo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Report Performance: {nome_agente}", ln=True, align='C')
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 10, f"Periodo: {periodo}", ln=True, align='C')
    pdf.ln(10)
    
    # Tabella Performance
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(95, 10, "Metrica", 1, 0, 'C', True)
    pdf.cell(95, 10, "Valore", 1, 1, 'C', True)
    
    metriche = [
        ("Leads Assegnati", str(dati_agente['Leads'])),
        ("Sopralluoghi", str(dati_agente['Sopralluoghi'])),
        ("Conversione Lead/Sopr.", f"{dati_agente['Conv_Perc']}%"),
        ("Fatturato Totale", f"{dati_agente['Fatturato']:,.2f} EUR"),
        ("Budget Pubblicitario", f"{dati_agente['Budget']:,.2f} EUR"),
        ("ROI (Ritorno)", f"{dati_agente['ROI']}x")
    ]
    
    for m, v in metriche:
        pdf.cell(95, 10, m, 1)
        pdf.cell(95, 10, v, 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 2. GESTIONE BUDGET PUBBLICITARIO NELLA SIDEBAR ---
with st.sidebar:
    st.header("💰 Gestione Budget Agenti")
    st.info("Assegna il valore pubblicitario per agente e mese.")
    
    if 'budget_agenti' not in st.session_state:
        # Esempio di struttura, aggiungi qui i tuoi agenti reali
        st.session_state.budget_agenti = pd.DataFrame([
            {"Agente": "AGENTE TEST", "Mese": "2026-03", "Budget": 500.0}
        ])
    
    edited_budget = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic")
    st.session_state.budget_agenti = edited_budget

# --- 3. FUNZIONI DI PULIZIA DATI ---
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
st.title("📊 Dashboard Analitica & Performance")

with st.expander("📁 Carica i File Storici (Analisi, Leads, Sopralluoghi, Offerte, Cantieri, Fatturato)"):
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

    # Chiavi e Merge
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

    # --- 5. DASHBOARD AGENTE & REPORTING ---
    st.divider()
    st.header("👤 Performance per Agente")
    
    periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
    
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        agente_scelto = st.selectbox("Seleziona Agente", master['Agente'].unique())
    with c_sel2:
        periodo_agente = st.selectbox("Seleziona Periodo", ["TUTTO LO STORICO"] + periodi)

    # Filtraggio Dati
    df_agente = master[master['Agente'] == agente_scelto]
    if periodo_agente != "TUTTO LO STORICO":
        df_agente = df_agente[df_agente['Mese_Anno'] == periodo_agente]

    # Metriche Base
    leads_tot = len(df_agente)
    sopr_tot = int(df_agente['Sopralluogo'].sum())
    conv_perc = round((sopr_tot / leads_tot * 100), 2) if leads_tot > 0 else 0
    fatt_agente = df_agente['Fatturato'].sum()

    # Recupero Budget e ROI
    if periodo_agente == "TUTTO LO STORICO":
        budget_agente = st.session_state.budget_agenti[st.session_state.budget_agenti['Agente'] == agente_scelto]['Budget'].sum()
    else:
        budget_agente = st.session_state.budget_agenti[
            (st.session_state.budget_agenti['Agente'] == agente_scelto) & 
            (st.session_state.budget_agenti['Mese'] == periodo_agente)
        ]['Budget'].sum()

    roi_agente = round(fatt_agente / budget_agente, 2) if budget_agente > 0 else 0

    # Visualizzazione KPI
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads Ricevuti", leads_tot)
    k2.metric("Sopralluoghi", sopr_tot, f"{conv_perc}%")
    k3.metric("Fatturato Prodotto", f"{fatt_agente:,.2f} €")
    k4.metric("ROI Pubblicitario", f"{roi_agente}x")

    # Grafico Funnel Agente
    fig_funnel = px.funnel(
        pd.DataFrame({'Fase': ['Leads', 'Sopralluoghi'], 'Quantità': [leads_tot, sopr_tot]}),
        x='Quantità', y='Fase', title=f"Conversione {agente_scelto}"
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

    # --- 6. ESPORTAZIONE PDF ---
    dati_report = {
        'Leads': leads_tot, 'Sopralluoghi': sopr_tot, 'Conv_Perc': conv_perc,
        'Fatturato': fatt_agente, 'Budget': budget_agente, 'ROI': roi_agente
    }
    
    btn_pdf = genera_pdf(agente_scelto, dati_report, periodo_agente)
    st.download_button(
        label="📥 Scarica Statistica Agente (PDF)",
        data=btn_pdf,
        file_name=f"Report_{agente_scelto}_{periodo_agente}.pdf",
        mime="application/pdf"
    )

    # --- 7. DETTAGLIO TABELLARE ---
    st.subheader("📋 Dettaglio Leads Assegnati")
    st.dataframe(df_agente[['Data_Ref', 'key', 'Sorgente', 'Sopralluogo', 'Fatturato']], use_container_width=True)

else:
    st.info("👋 In attesa dei file storici. Caricali per attivare i report.")
