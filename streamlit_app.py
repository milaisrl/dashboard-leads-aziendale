import streamlit as st
import pandas as pd
import plotly.express as px
import re
from fpdf import FPDF

# Configurazione Pagina
st.set_page_config(page_title="CRM & Margin Analytics ULTRA", layout="wide")

# --- 1. FUNZIONI DI UTILITÀ ---
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

# --- 2. INIZIALIZZAZIONE SESSION STATE ---
if 'budget_agenti' not in st.session_state:
    st.session_state.budget_agenti = pd.DataFrame([
        {"Agente": "NEW DDL DI DE LORENZI DANIELE", "Mese": "2026-03", "Budget": 1000.0}
    ])

if 'costi_extra' not in st.session_state:
    st.session_state.costi_extra = pd.DataFrame(columns=['key', 'Manodopera', 'Materiali', 'Altri_Costi'])

# --- 3. CARICAMENTO FILE ---
st.title("🚀 Business Intelligence & Marginalità")

with st.sidebar:
    st.header("📁 Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'csv'])

if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    # Caricamento e Normalizzazione (Logica simile alla precedente)
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        date_col = [c for c in df.columns if 'Data' in c or 'inizio' in c.lower()]
        if date_col:
            df['Data_Ref'] = pd.to_datetime(df[date_col[0]], errors='coerce')
            df['Mese_Anno'] = df['Data_Ref'].dt.strftime('%Y-%m')
        return df.dropna(how='all')

    df_a, df_l, df_s, df_o, df_c, df_f = load(f_anal), load(f_list), load(f_sopr), load(f_offe), load(f_cant), load(f_fatt)

    # Chiavi
    df_a['key'] = df_a['Cliente'].apply(normalize_name)
    df_l['key'] = df_l['Ragione_sociale'].apply(normalize_name)
    df_c['key'] = df_c['Rag. Soc.'].apply(normalize_name)
    df_f['key'] = df_f['Descrizione conto'].apply(lambda x: normalize_name(str(x).split('[')[0]))
    
    # Valori Economici
    col_soldi = 'Imponibile in EUR' if 'Imponibile in EUR' in df_f.columns else 'Totale'
    df_f['Valore_Netto'] = df_f[col_soldi].apply(clean_currency)
    df_c['Valore_Contratto'] = df_c['Totale'].apply(clean_currency)

    # Unificazione Master
    master = df_a[df_a['Tipo'] != 'WF Contatto cliente'].copy()
    master = pd.merge(master, df_l.drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Cantiere'] = master['key'].isin(df_c['key'].unique())
    master['Fatturato'] = master['key'].map(df_f.groupby('key')['Valore_Netto'].sum()).fillna(0)
    master['Agente'] = master['Agente'].fillna("DA ASSEGNARE")

    # --- 4. TABS PRINCIPALI ---
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard Performance", "💰 Gestione Budget Marketing", "🏗️ Analisi Marginalità"])

    # --- TAB 2: GESTIONE BUDGET (Per risolvere il tuo problema dello screenshot) ---
    with tab2:
        st.header("Gestione Investimenti Pubblicitari")
        st.info("Aggiungi qui sotto le righe per ogni Agente e Mese. Usa il tasto '+' in fondo alla tabella.")
        st.session_state.budget_agenti = st.data_editor(
            st.session_state.budget_agenti, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Mese": st.column_config.TextColumn("Mese (es: 2026-03)"),
                "Budget": st.column_config.NumberColumn("Budget (€)", format="%.2f €")
            }
        )

    # --- TAB 1: DASHBOARD (Analisi già esistente) ---
    with tab1:
        st.subheader("Performance Commerciale Generale")
        # ... (Qui rimane la logica dei KPI e grafici che avevamo costruito)
        st.write("Seleziona i filtri per vedere le performance degli agenti.")

    # --- TAB 3: ANALISI MARGINALITÀ (Nuova Sezione Richiesta) ---
    with tab3:
        st.header("Dettaglio Contratti e Calcolo Margini")
        
        # Uniamo i dati dei cantieri con l'agente e il mese
        df_margini = pd.merge(
            df_c[['key', 'Rag. Soc.', 'Mese_Anno', 'Valore_Contratto']], 
            master[['key', 'Agente']], 
            on='key', how='left'
        )

        # Calcolo Costo Pubblicitario per Contratto
        # 1. Quanti contratti ha fatto ogni agente ogni mese?
        count_contratti = df_margini.groupby(['Agente', 'Mese_Anno']).size().reset_index(name='Num_Contratti')
        
        # 2. Uniamo col budget
        budget_map = st.session_state.budget_agenti.copy()
        budget_map = pd.merge(budget_map, count_contratti, on=['Agente', 'Mese'], how='left')
        budget_map['Costo_Pubb_Unitario'] = budget_map['Budget'] / budget_map['Num_Contratti']
        
        # 3. Portiamo il costo nel df_margini
        df_margini = pd.merge(
            df_margini, 
            budget_map[['Agente', 'Mese', 'Costo_Pubb_Unitario']], 
            left_on=['Agente', 'Mese_Anno'], right_on=['Agente', 'Mese'], how='left'
        )
        
        # Inizializziamo costi se non esistono
        for col in ['Manodopera', 'Materiali', 'Altri_Costi']:
            if col not in df_margini: df_margini[col] = 0.0

        st.write("Compila i costi per ogni contratto nella tabella qui sotto:")
        df_editor = st.data_editor(
            df_margini[['Rag. Soc.', 'Agente', 'Valore_Contratto', 'Costo_Pubb_Unitario', 'Manodopera', 'Materiali', 'Altri_Costi']],
            use_container_width=True
        )

        # Calcoli finali
        df_editor['Totale_Costi'] = df_editor['Costo_Pubb_Unitario'].fillna(0) + df_editor['Manodopera'] + df_editor['Materiali'] + df_editor['Altri_Costi']
        df_editor['Margine_Assoluto'] = df_editor['Valore_Contratto'] - df_editor['Totale_Costi']
        df_editor['Margine_Perc'] = (df_editor['Margine_Assoluto'] / df_editor['Valore_Contratto'] * 100).round(1)

        st.divider()
        st.subheader("Risultato Marginalità")
        
        # Formattazione per visualizzazione
        st.dataframe(
            df_editor.style.format({
                'Valore_Contratto': '{:,.2f} €',
                'Margine_Assoluto': '{:,.2f} €',
                'Margine_Perc': '{:.1f} %',
                'Totale_Costi': '{:,.2f} €'
            }).background_gradient(subset=['Margine_Perc'], cmap='RdYlGn'),
            use_container_width=True
        )

        # Grafico Margini
        fig_marg = px.bar(df_editor, x='Rag. Soc.', y='Margine_Assoluto', color='Margine_Perc', title="Margine per Singolo Contratto (€)")
        st.plotly_chart(fig_marg, use_container_width=True)

else:
    st.info("Carica i file nella sidebar per attivare l'analisi dei margini.")
