import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Dashboard Consegne", layout="wide", page_icon="🚚")

# --- FUNZIONE ETL (ESTRAZIONE E PULIZIA DATI) ---
@st.cache_data
def elabora_corse(file_path):
    xls = pd.ExcelFile(file_path)
    df_finali = []

    for sheet in xls.sheet_names:
        df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None)
        if df_raw.empty or len(df_raw) < 5:
            continue
            
        vettore = str(df_raw.iloc[2, 5]).strip()
        data_consegna_raw = str(df_raw.iloc[2, 11])
        data_consegna = data_consegna_raw.replace("DATA CONSEGNA:", "").strip() if "DATA CONSEGNA" in data_consegna_raw else np.nan
        
        df = df_raw.iloc[5:].copy()
        # Mappiamo tutte le colonne presenti nel file originale
        df.columns = ['Vuoto', 'Data_Bordero', 'Ora', 'Can', 'Cod_PDV', 'Des_PDV', 'Prv', 'Plt', 'Plt_Resi', 'Ora_Cons', 'Note_Cons', 'Note']
        
        df['Bordero'] = df['Data_Bordero'].apply(lambda x: x if isinstance(x, str) and str(x).startswith("ID:") else np.nan)
        df['Data_Preparazione'] = pd.to_datetime(df['Data_Bordero'], format='%d/%m/%Y', errors='coerce')
        
        df['Bordero'] = df['Bordero'].ffill()
        df['Data_Preparazione'] = df['Data_Preparazione'].ffill()
        
        df['Vettore'] = vettore
        df['Data_Consegna'] = data_consegna
        df['Controllo'] = 'ok'
        
        df['Cod_PDV'] = pd.to_numeric(df['Cod_PDV'], errors='coerce')
        df['Plt'] = pd.to_numeric(df['Plt'], errors='coerce')
        
        df_clean = df.dropna(subset=['Cod_PDV', 'Plt']).copy()
        
        if not df_clean.empty:
            df_finali.append(df_clean)

    if not df_finali:
        return pd.DataFrame()

    df_completo = pd.concat(df_finali, ignore_index=True)

    # Creiamo la tabella finale aggiungendo l'orario
    df_output = pd.DataFrame({
        'Preparata': False, 
        'bordero': df_completo['Bordero'],
        'Ora Partenza': df_completo['Ora'].fillna(""), # Aggiunta colonna orario
        'negozio': df_completo['Cod_PDV'].astype(int),
        'descrizione': df_completo['Des_PDV'],
        'data CONSEGNA': df_completo['Data_Consegna'],
        'Name': df_completo['Vettore'],
        'data PREPARAZIONE': df_completo['Data_Preparazione'].dt.strftime('%Y-%m-%d'),
        'controllo': df_completo['Controllo'],
        'Totale': df_completo['Plt']
    })

    return df_output


# --- INTERFACCIA UTENTE (UI) ---
st.title("🚚 Dashboard Operativa Consegne")
st.markdown("Carica il file Excel grezzo per pulirlo, spuntare le corse preparate e visualizzare le analisi avanzate.")

uploaded_file = st.file_uploader("📂 Scegli il file Excel (dettaglioCorse.xls)", type=["xls", "xlsx"])

if uploaded_file is not None:
    try:
        with st.spinner("Elaborazione e pulizia in corso..."):
            df = elabora_corse(uploaded_file)
        
        if df.empty:
            st.error("Il file sembra essere vuoto o non ha il formato atteso.")
        else:
            # --- BARRA LATERALE (FILTRI E RICERCA) ---
            st.sidebar.header("🔍 Cerca e Filtra")
            
            # Ricerca Testuale 
            testo_ricerca = st.sidebar.text_input("Cerca parola libera (es. codice borderò):", "")
            
            # Liste per i filtri a tendina
            lista_vettori = ["Tutti"] + list(df['Name'].dropna().unique())
            lista_date = ["Tutte"] + list(df['data CONSEGNA'].dropna().unique())
            
            # Ordiniamo alfabeticamente le destinazioni per trovarle più facilmente
            lista_destinazioni = ["Tutte"] + sorted(list(df['descrizione'].dropna().astype(str).unique()))
            
            # Filtri a tendina
            vettore = st.sidebar.selectbox("Seleziona Vettore", lista_vettori)
            destinazione = st.sidebar.selectbox("Seleziona Destinazione", lista_destinazioni) # Nuovo Filtro
            data_cons = st.sidebar.selectbox("Data Consegna", lista_date)

            # --- APPLICAZIONE FILTRI ---
            df_filtrato = df.copy()
            
            if testo_ricerca:
                df_filtrato = df_filtrato[
                    df_filtrato['descrizione'].astype(str).str.contains(testo_ricerca, case=False, na=False) |
                    df_filtrato['bordero'].astype(str).str.contains(testo_ricerca, case=False, na=False) |
                    df_filtrato['Ora Partenza'].astype(str).str.contains(testo_ricerca, case=False, na=False)
                ]
                
            if vettore != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['Name'] == vettore]
            if destinazione != "Tutte":
                df_filtrato = df_filtrato[df_filtrato['descrizione'] == destinazione]
            if data_cons != "Tutte":
                df_filtrato = df_filtrato[df_filtrato['data CONSEGNA'] == data_cons]

            # --- METRICHE PRINCIPALI ---
            st.markdown("### 📊 Riepilogo Attuale")
            tot_pallet = df_filtrato['Totale'].sum()
            tot_viaggi = df_filtrato['bordero'].nunique()
            corse_totali = len(df_filtrato)

            col1, col2, col3 = st.columns(3)
            col1.metric(label="Totale Pallet", value=f"{tot_pallet:.1f}")
            col2.metric(label="Viaggi (Borderò)", value=tot_viaggi)
            col3.metric(label="Righe di Consegna", value=corse_totali)

            # --- TABELLA INTERATTIVA EDITABILE ---
            st.markdown("### 📋 Distinta di Carico (Spunta le corse)")
            
            # Blocchiamo la modifica di tutte le colonne tranne "Preparata"
            colonne_bloccate = ["bordero", "Ora Partenza", "negozio", "descrizione", "data CONSEGNA", "Name", "data PREPARAZIONE", "controllo", "Totale"]
            
            edited_df = st.data_editor(
                df_filtrato,
                column_config={
                    "Preparata": st.column_config.CheckboxColumn(
                        "Pronta?",
                        help="Clicca per confermare che questa corsa è stata preparata",
                        default=False,
                    )
                },
                disabled=colonne_bloccate, 
                use_container_width=True,
                hide_index=True
            )

            # Pulsante Download
            csv_da_scaricare = edited_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Scarica Tabella in CSV (con spunte salvate)",
                data=csv_da_scaricare,
                file_name="consegne_aggiornate.csv",
                mime="text/csv",
            )

            st.divider()

            # --- SEZIONE QUERY E GRAFICI ---
            st.markdown("### 📈 Analisi Avanzate e Grafici")
            
            tipo_query = st.selectbox(
                "Scegli quale interrogazione eseguire sui dati attualmente filtrati:",
                [
                    "1. Volumi totali (Pallet) per Vettore",
                    "2. Top 10 Negozi che ricevono più merce",
                    "3. Numero di Viaggi (Borderò) per Vettore",
                    "4. Stato Avanzamento Lavori (Merce Preparata vs Da Preparare)"
                ]
            )

            col_tab, col_grafico = st.columns([1, 2])

            if tipo_query == "1. Volumi totali (Pallet) per Vettore":
                dati_agg = edited_df.groupby('Name')['Totale'].sum().reset_index().rename(columns={'Name':'Vettore'})
                dati_agg = dati_agg.sort_values(by='Totale', ascending=False)
                with col_tab:
                    st.dataframe(dati_agg, hide_index=True, use_container_width=True)
                with col_grafico:
                    st.bar_chart(data=dati_agg, x='Vettore', y='Totale', use_container_width=True)

            elif tipo_query == "2. Top 10 Negozi che ricevono più merce":
                dati_agg = edited_df.groupby('descrizione')['Totale'].sum().reset_index().rename(columns={'descrizione':'Negozio'})
                dati_agg = dati_agg.sort_values(by='Totale', ascending=False).head(10)
                with col_tab:
                    st.dataframe(dati_agg, hide_index=True, use_container_width=True)
                with col_grafico:
                    st.bar_chart(data=dati_agg, x='Negozio', y='Totale', use_container_width=True)

            elif tipo_query == "3. Numero di Viaggi (Borderò) per Vettore":
                dati_agg = edited_df.groupby('Name')['bordero'].nunique().reset_index().rename(columns={'Name':'Vettore', 'bordero':'Numero Viaggi'})
                dati_agg = dati_agg.sort_values(by='Numero Viaggi', ascending=False)
                with col_tab:
                    st.dataframe(dati_agg, hide_index=True, use_container_width=True)
                with col_grafico:
                    st.bar_chart(data=dati_agg, x='Vettore', y='Numero Viaggi', use_container_width=True)
            
            elif tipo_query == "4. Stato Avanzamento Lavori (Merce Preparata vs Da Preparare)":
                dati_agg = edited_df.groupby('Preparata')['Totale'].sum().reset_index()
                dati_agg['Stato'] = dati_agg['Preparata'].apply(lambda x: 'Pronta' if x else 'Da Preparare')
                with col_tab:
                    st.dataframe(dati_agg[['Stato', 'Totale']], hide_index=True, use_container_width=True)
                with col_grafico:
                    st.bar_chart(data=dati_agg, x='Stato', y='Totale', color='Stato', use_container_width=True)

    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione del file: {e}")
else:
    st.info("👆 Carica il file tramite il box qui sopra per iniziare.")