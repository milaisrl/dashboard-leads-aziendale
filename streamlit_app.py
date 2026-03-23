import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF
import io

# Configurazione Pagina
st.set_page_config(page_title="CRM & Marketing Analytics ULTRA", layout="wide")

# --- 1. FUNZIONE GENERAZIONE PDF ---
def genera_pdf(nome_agente, dati_agente, periodo):
    pdf = FPDF()
    pdf.add_page()
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
    
    pdf.set_font("Arial", "", 11)
    metriche = [
        ("Leads Assegnati", f"{dati_agente['Leads']}"),
        ("Sopralluoghi Effettuati", f"{dati_agente['Sopralluoghi']}"),
        ("Tasso Conversione Lead/Sopr", f"{dati_agente['Conv_Perc']}%"),
        ("Ticket Medio Vendita", f"{dati_agente['Ticket_Medio']:,.2f} EUR"),
        ("Fatturato Totale", f"{dati_agente['Fatturato']:,.2f} EUR"),
        ("ROI su Budget Marketing", f"{dati_agente['ROI']}x")
    ]
    
    for m, v in metriche:
        pdf.cell(95, 10, f" {m}", 1)
        pdf.cell(95, 10, f"{v} ", 1, 1, 'R')
        
    pdf.set_y(-30)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(190, 10, "Documento generato da CRM Analytics - Riservato", 0, 0, 'C')
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 2. SIDEBAR BUDGET ---
with st.sidebar:
    st.header("💰 Investimenti Marketing")
    if 'budget_agenti' not in st.session_state:
        st.session_state.budget_agenti = pd.DataFrame([
            {"Agente": "NEW DDL DI DE LORENZI DANIELE", "Mese": "2026-03", "Budget": 1000.0}
        ])
    st.session_state.budget_agenti = st.data_editor(st.session_state.budget_agenti, num_rows="dynamic")

# --- 3. UTILITIES ---
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

# --- 4. ENGINE CARICAMENTO ---
st.title("🚀 Marketing & Sales Intelligence")

with st.expander("📁 Caricamento Database Storico"):
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

    # Chiavi e Normalizzazione Soldi
    dfs['anal']['key'] = dfs['anal']['Cliente'].apply(normalize_name)
    dfs['list']['key'] = dfs['list']['Ragione_sociale'].apply(normalize_name)
    dfs['sopr']['key'] = dfs['sopr']['Rag. Soc.'].apply(normalize_name)
    dfs['offe']['key'] = dfs['offe']['Rag. Soc.'].apply(normalize_name)
    dfs['fatt']['key'] = dfs['fatt']['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in dfs['fatt'].columns else 'Totale'
    dfs['fatt']['Valore_Netto'] = dfs['fatt'][col_soldi].apply(clean_currency)
    dfs['offe']['Valore_Offerta'] = dfs['offe']['Totale'].apply(clean_currency)

    # UNIFICAZIONE MASTER
    master = dfs['anal'][dfs['anal']['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, dfs['list'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    
    # Marcatori Fasi
    master['Sopralluogo'] = master['key'].isin(dfs['sopr']['key'].unique())
    master['Ha_Offerta'] = master['key'].isin(dfs['offe']['key'].unique())
    master['Valore_Offerto'] = master['key'].map(dfs['offe'].groupby('key')['Valore_Offerta'].sum()).fillna(0)
    master['Fatturato'] = master['key'].map(dfs['fatt'].groupby('key')['Valore_Netto'].sum()).fillna(0)
    
    # Recupero Agente Orfano
    sopr_map = dfs['sopr'].drop_duplicates('key').set_index('key')['Creato da'].to_dict()
    master['Agente'] = master.apply(lambda r: r['Agente'] if pd.notna(r['Agente']) and r['Agente']!="" else sopr_map.get(r['key'], "DA ASSEGNARE"), axis=1)
    master['Sorgente'] = master['Sorgente'].fillna("Sconosciuta")

    # --- 5. DASHBOARD GENERALE & MARKETING ROI ---
    st.header("🌍 Analisi Globale Sorgenti Marketing")
    
    marketing_stats = master.groupby('Sorgente').agg(
        Leads=('key', 'count'),
        Sopralluoghi=('Sopralluogo', 'sum'),
        Fatturato_Reale=('Fatturato', 'sum')
    ).reset_index()
    marketing_stats['Efficacia_%'] = (marketing_stats['Sopralluoghi'] / marketing_stats['Leads'] * 100).round(1)
    
    c_m1, c_m2 = st.columns([2, 1])
    with c_m1:
        st.subheader("Fatturato Generato per Canale")
        st.plotly_chart(px.bar(marketing_stats, x='Sorgente', y='Fatturato_Reale', color='Sorgente', text_auto='.2s'), use_container_width=True)
    with c_m2:
        st.subheader("Qualità Leads per Sorgente")
        st.dataframe(marketing_stats[['Sorgente', 'Leads', 'Efficacia_%']], use_container_width=True)

    # --- 6. PERFORMANCE AGENTE ---
    st.divider()
    st.header("👤 Focus Performance Agente")
    
    periodi = sorted(master['Mese_Anno'].dropna().unique(), reverse=True)
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        ag_scelto = st.selectbox("Seleziona Agente", sorted(master['Agente'].unique()))
    with col_a2:
        per_scelto = st.selectbox("Seleziona Periodo", ["STORICO TOTALE"] + periodi)

    # Filtro Agente
    df_ag = master[master['Agente'] == ag_scelto]
    if per_scelto != "STORICO TOTALE":
        df_ag = df_ag[df_ag['Mese_Anno'] == per_scelto]

    # Metriche Qualità
    l_tot = len(df_ag)
    s_tot = int(df_ag['Sopralluogo'].sum())
    f_tot = df_ag['Fatturato'].sum()
    ticket_medio = round(f_tot / df_ag[df_ag['Fatturato']>0].shape[0], 2) if (df_ag['Fatturato']>0).any() else 0
    tasso_prev = round((df_ag['Ha_Offerta'].sum() / s_tot * 100), 1) if s_tot > 0 else 0
    
    # Budget e ROI
    b_df = st.session_state.budget_agenti
    bud = b_df[b_df['Agente']==ag_scelto]['Budget'].sum() if per_scelto=="STORICO TOTALE" else b_df[(b_df['Agente']==ag_scelto) & (b_df['Mese']==per_scelto)]['Budget'].sum()
    roi = round(f_tot / bud, 2) if bud > 0 else 0

    # Layout KPI Agente
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Leads", l_tot)
    k2.metric("Sopralluoghi", s_tot)
    k3.metric("Tasso Prev.", f"{tasso_prev}%")
    k4.metric("Ticket Medio", f"{ticket_medio:,.0f} €")
    k5.metric("ROI", f"{roi}x")

    # PDF & Dettaglio
    dati_pdf = {'Leads': l_tot, 'Sopralluoghi': s_tot, 'Conv_Perc': round(s_tot/l_tot*100,1) if l_tot>0 else 0, 'Fatturato': f_tot, 'Budget': bud, 'ROI': roi, 'Ticket_Medio': ticket_medio}
    st.download_button("📥 Scarica Report PDF Agente", genera_pdf(ag_scelto, dati_pdf, per_scelto), f"Report_{ag_scelto}.pdf", "application/pdf")
    
    st.subheader("Elenco Pratiche in Corso")
    st.dataframe(df_ag[['Data_Ref', 'key', 'Sorgente', 'Sopralluogo', 'Ha_Offerta', 'Fatturato']], use_container_width=True)

else:
    st.info("👋 Carica i 6 file storici per sbloccare l'Intelligence Marketing e Sales.")
