import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Domei Intelligence", layout="wide")

# CSS per rendere l'app professionale e pronta per la stampa
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stMetric"] { background-color: #f8f9fa; border-left: 5px solid #FF4B4B; padding: 10px; }
    @media print {
        [data-testid="stSidebar"], .stButton, header { display: none !important; }
        .main { width: 100% !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNZIONI CORE (CONNESSIONE E PULIZIA) ---
def init_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Assicurati che il nome del file sia corretto
        return client.open("Domei_Database").worksheet("Marginalita")
    except Exception as e:
        st.error(f"Errore connessione Google Sheets: {e}")
        return None

def normalize_name(name):
    if pd.isna(name): return ""
    # Pulizia profonda: rimuove simboli, mette in ordine e pulisce spazi
    s = re.sub(r'[^a-zA-Z0-9\s]', '', str(name)).lower().strip()
    return " ".join(sorted(s.split()))

def smart_load(f):
    if f is None: return pd.DataFrame()
    try:
        if f.name.endswith('.csv'):
            return pd.read_csv(f, sep=None, engine='python')
        try:
            return pd.read_excel(f, engine='openpyxl')
        except:
            return pd.read_excel(f, engine='xlrd')
    except Exception as e:
        st.warning(f"Non riesco a leggere {f.name}. Errore: {e}")
        return pd.DataFrame()

# --- 3. SIDEBAR CARICAMENTO ---
with st.sidebar:
    st.header("📁 Caricamento Mensile")
    st.info("Carica i 6 file per sbloccare l'analisi.")
    f_anal = st.file_uploader("1. ANALISI", type=['xlsx', 'xls', 'csv'])
    f_list = st.file_uploader("2. LISTA LEADS", type=['xlsx', 'xls', 'csv'])
    f_sopr = st.file_uploader("3. SOPRALLUOGHI", type=['xlsx', 'xls', 'csv'])
    f_offe = st.file_uploader("4. OFFERTE", type=['xlsx', 'xls', 'csv'])
    f_cant = st.file_uploader("5. ORDINI CANTIERI", type=['xlsx', 'xls', 'csv'])
    f_fatt = st.file_uploader("6. FATTURATO", type=['xlsx', 'xls', 'csv'])

# --- 4. LOGICA DI ELABORAZIONE ---
if all([f_anal, f_list, f_sopr, f_offe, f_cant, f_fatt]):
    files = {"a": f_anal, "l": f_list, "s": f_sopr, "o": f_offe, "c": f_cant, "f": f_fatt}
    dfs = {k: smart_load(v) for k, v in files.items()}

    # Verifica se i file critici sono vuoti
    if dfs['a'].empty or dfs['c'].empty:
        st.error("Uno o più file critici (Analisi o Cantieri) sono vuoti o leggibili male.")
    else:
        # Normalizzazione nomi per il JOIN
        for k in dfs:
            if not dfs[k].empty:
                cols = dfs[k].columns.tolist()
                target = next((c for c in cols if any(x in c for x in ['Cliente', 'Rag', 'Soc', 'Nominativo'])), cols[0])
                dfs[k]['key'] = dfs[k][target].apply(normalize_name)
                dfs[k]['Nome_Visibile'] = dfs[k][target]

        # --- MEMORIA MENSILE (GOOGLE SHEETS) ---
        sheet = init_gsheet()
        db_cloud = pd.DataFrame()
        if sheet:
            try:
                records = sheet.get_all_records()
                db_cloud = pd.DataFrame(records)
            except:
                db_cloud = pd.DataFrame(columns=['key', 'Manodopera', 'Materiali', 'Extra'])
        
        # Protezione colonne mancanti nel DB Cloud
        for col in ['key', 'Manodopera', 'Materiali', 'Extra']:
            if col not in db_cloud.columns: db_cloud[col] = 0.0

        # Preparazione Tabella Marginalità
        # Cerchiamo la colonna del valore (Totale/Fatturato)
        val_col = next((c for c in dfs['c'].columns if any(x in c for x in ['Totale', 'Prezzo', 'Valore', 'Imponibile'])), dfs['c'].columns[0])
        
        df_base = dfs['c'][['key', 'Nome_Visibile']].copy()
        df_base['Valore_Contratto'] = dfs['c'][val_col].fillna(0)

        # Il MERGE magico: Prende i cantieri nuovi e "pesca" i costi vecchi dal Cloud
        df_marg_finale = pd.merge(
            df_base, 
            db_cloud[['key', 'Manodopera', 'Materiali', 'Extra']].drop_duplicates('key'), 
            on='key', how='left'
        ).fillna(0)

        # --- 5. INTERFACCIA TABS ---
        t_perf, t_marg = st.tabs(["📊 Performance", "🏗️ Marginalità & Storico"])

        with t_perf:
            st.subheader("Performance Commerciali")
            # Uniamo Analisi con Liste per avere Agenti e Sorgenti
            master = pd.merge(dfs['a'], dfs['l'].drop_duplicates('key')[['key', 'Agente', 'Sorgente']], on='key', how='left')
            master['Agente'] = master['Agente'].fillna("NON ASSEGNATO")
            
            sel_ag = st.selectbox("Seleziona Agente", sorted(master['Agente'].unique()))
            df_ag = master[master['Agente'] == sel_ag]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Leads", len(df_ag))
            c2.metric("Sopralluoghi", int(dfs['s']['key'].isin(df_ag['key']).sum()))
            c3.metric("Contratti", int(dfs['c']['key'].isin(df_ag['key']).sum()))
            
            # Grafico Sorgenti
            st.plotly_chart(px.pie(df_ag, names='Sorgente', title="Provenienza Leads"), use_container_width=True)

        with t_marg:
            st.subheader("Database Marginalità")
            st.caption("Modifica i costi qui sotto. I dati vengono salvati su Google Sheets e ricordati il mese prossimo.")
            
            # Tabella Editabile
            edited_df = st.data_editor(
                df_marg_finale, 
                column_config={"key": None, "Nome_Visibile": "Cliente", "Valore_Contratto": st.column_config.NumberColumn("Fatturato €", format="%.2f")},
                use_container_width=True
            )

            if st.button("💾 Salva e Aggiorna Storico"):
                if sheet:
                    # Pulizia e invio dati
                    final_save = edited_df.copy()
                    final_save['Ultimo_Update'] = pd.Timestamp.now().strftime('%d/%m/%Y')
                    sheet.clear()
                    sheet.update([final_save.columns.values.tolist()] + final_save.values.tolist())
                    st.success("Dati sincronizzati con il Cloud!")
                else:
                    st.error("Google Sheet non connesso. Controlla i Secrets.")

            # Calcolo ROI
            tot_f = edited_df['Valore_Contratto'].sum()
            tot_c = edited_df[['Manodopera', 'Materiali', 'Extra']].sum().sum()
            st.divider()
            r1, r2, r3 = st.columns(3)
            r1.metric("Fatturato Totale", f"{tot_f:,.2f} €")
            r2.metric("Margine (€)", f"{tot_f - tot_c:,.2f} €")
            r3.metric("Margine (%)", f"{( (tot_f - tot_c)/tot_f*100 if tot_f > 0 else 0):.1f}%")

else:
    st.title("Domei Business Intelligence")
    st.warning("👋 Benvenuto. Per favore, carica i 6 file richiesti nella sidebar per iniziare l'elaborazione dei dati.")
