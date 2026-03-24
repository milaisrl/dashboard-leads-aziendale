import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os

# --- 1. CONFIGURAZIONE & CONNESSIONE ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

def init_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("Domei_Database").worksheet("Marginalita")
    except:
        return None

def normalize_name(name):
    if pd.isna(name): return ""
    return " ".join(sorted(re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip().split()))

# --- 2. SIDEBAR: RIPRISTINO CARICAMENTI ---
with st.sidebar:
    st.header("📁 Caricamento Dati")
    f_anal = st.file_uploader("1. ANALISI (Leads)", type=['xlsx', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS (Agenti/Sorgenti)", type=['xlsx', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'csv'])
    f_cant = st.file_uploader("4. CANTIERI (Marginalità)", type=['xlsx', 'csv'])

# --- 3. LOGICA DI ELABORAZIONE ---
if f_anal and f_list and f_sopr and f_cant:
    # Funzione interna per pulizia rapida
    def load(f):
        df = pd.read_csv(f, sep=None, engine='python') if f.name.endswith('.csv') else pd.read_excel(f)
        df.columns = df.columns.astype(str).str.strip()
        col_rag = next((c for c in df.columns if 'Rag' in c or 'Cliente' in c), df.columns[0])
        df['key'] = df[col_rag].apply(normalize_name)
        df['Rag_Soc_Pulita'] = df[col_rag]
        return df

    df_a = load(f_anal)
    df_l = load(f_list)
    df_s = load(f_sopr)
    df_c = load(f_cant)

    # Merge per Performance
    master = pd.merge(df_a, df_l.drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
    master['Agente'] = master['Agente'].fillna("NON ASSEGNATO")
    master['Sopralluogo'] = master['key'].isin(df_s['key'].unique())
    master['Contratto'] = master['key'].isin(df_c['key'].unique())

    # --- 4. TABS: PERFORMANCE + MARGINALITÀ ---
    t_perf, t_marg = st.tabs(["📊 Performance Commerciali", "🏗️ Gestione Marginalità"])

    with t_perf:
        # Ripristino filtri screenshot 1
        c1, c2 = st.columns(2)
        with c1: ag_sel = st.selectbox("Agente", sorted(master['Agente'].unique()))
        
        df_filter = master[master['Agente'] == ag_sel]
        
        # Metrics screenshot 1
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Leads Ricevuti", len(df_filter))
        m2.metric("Sopralluoghi", int(df_filter['Sopralluogo'].sum()))
        m3.metric("Contratti", int(df_filter['Contratto'].sum()))
        m4.metric("Closing Rate", f"{(df_filter['Contratto'].sum()/len(df_filter)*100 if len(df_filter)>0 else 0):.1f}%")

        st.divider()
        
        # Funnel & Pie screenshot 1, 2 e 3
        g1, g2 = st.columns([1, 1])
        with g1:
            st.subheader("Conversione (Funnel)")
            f_data = pd.DataFrame({
                'Fase': ['1. Leads', '2. Sopralluoghi', '3. Contratti'],
                'Valore': [len(df_filter), df_filter['Sopralluogo'].sum(), df_filter['Contratto'].sum()]
            })
            fig_f = px.funnel(f_data, x='Valore', y='Fase', color_discrete_sequence=['#000000'])
            st.plotly_chart(fig_f, use_container_width=True)
        
        with g2:
            st.subheader("Provenienza Leads")
            pie_data = df_filter.groupby('Sorgente').size().reset_index(name='Q')
            fig_p = px.pie(pie_data, values='Q', names='Sorgente', hole=0.4, 
                           color_discrete_sequence=px.colors.sequential.Greys_r)
            st.plotly_chart(fig_p, use_container_width=True)

    with t_marg:
        st.subheader("Database Marginalità (Sincronizzato Google Sheets)")
        
        # Caricamento dati da Google Sheet
        sheet = init_gsheet()
        if sheet:
            existing = pd.DataFrame(sheet.get_all_records())
            # Uniamo i dati del file Excel con i costi già salvati nel DB
            df_m = pd.merge(df_c[['key', 'Rag_Soc_Pulita', 'Totale']], 
                            existing[['key', 'Manodopera', 'Materiali', 'Extra']] if not existing.empty else pd.DataFrame(columns=['key','Manodopera','Materiali','Extra']), 
                            on='key', how='left').fillna(0)
            
            edited = st.data_editor(df_m, column_config={"key": None}, use_container_width=True)

            if st.button("💾 Salva e Aggiorna Google Sheets"):
                edited['Mese_Anno'] = pd.Timestamp.now().strftime('%Y-%m')
                sheet.clear()
                sheet.update([edited.columns.values.tolist()] + edited.values.tolist())
                st.success("Sincronizzazione eseguita!")
        else:
            st.error("Configura i Secrets per attivare il salvataggio su Google Sheets.")

else:
    st.warning("👋 Carica i 4 file richiesti nella sidebar per visualizzare la dashboard completa.")
