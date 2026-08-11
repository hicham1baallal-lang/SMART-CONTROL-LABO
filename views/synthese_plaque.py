import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def generate_excel_a4(df_filtered, filter_title="Synthèse Générale"):
    """
    Génère un fichier Excel professionnel mis en page pour impression A4 Portrait.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Synthèse Essais Plaque"

    # --- CONFIGURATION IMPRESSION ---
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # --- PALETTE DE COULEURS ET STYLES ---
    NAVY_HEADER = "1F4E79"
    BLUE_SUBHEADER = "2F5597"
    ICE_BLUE_BG = "F2F5F9"
    BORDER_COLOR = "D9D9D9"
    GREEN_OK = "E2EFDA"
    TEXT_GREEN = "276A3C"
    ORANGE_WARN = "FFF2CC"
    TEXT_ORANGE = "B25900"

    # --- 1. EN-TÊTE DU DOCUMENT ---
    # Ligne 1 : Nom du Laboratoire
    ws.merge_cells("A1:G1")
    ws["A1"] = "LABORATOIRE LPEE — CENTRE TECHNIQUE RÉGIONAL"
    ws["A1"].font = Font(name="Calibri", size=15, bold=True, color=NAVY_HEADER)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30 

    # Ligne 2 : Norme (Nouvelle ligne dédiée)
    ws.merge_cells("A2:G2")
    ws["A2"] = "Norme : NF P 94-117-1 (Plaque Ø 600 mm)"
    ws["A2"].font = Font(name="Calibri", size=13, bold=True, color="404040")
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 25

    # Ligne 3 : Projet / Client
    ws.merge_cells("A3:G3")
    ws["A3"] = "Projet : LGV CASA SUD  |  Client : TGCC"
    ws["A3"].font = Font(name="Calibri", size=12, bold=True, color=BLUE_SUBHEADER)
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 25

    # Ligne 4 : Titre dynamique
    ws.merge_cells("A4:G4")
    ws["A4"] = f"SYNTHÈSE DES ESSAIS DE PORTANCE À LA PLAQUE — {filter_title.upper()}"
    ws["A4"].font = Font(name="Calibri", size=11, italic=True, color="595959")
    ws["A4"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[4].height = 20
    
    # Ligne 5 : Espacement
    ws.row_dimensions[5].height = 10

    # --- STYLES DE TABLEAU ---
    font_th = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    fill_th = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    fill_zebra = PatternFill(start_color=ICE_BLUE_BG, end_color=ICE_BLUE_BG, fill_type="solid")
    thin_border = Border(left=Side(style='thin', color=BORDER_COLOR), right=Side(style='thin', color=BORDER_COLOR), 
                         top=Side(style='thin', color=BORDER_COLOR), bottom=Side(style='thin', color=BORDER_COLOR))

    # --- 2. EN-TÊTES DE TABLEAU (Ligne 6) ---
    headers = ["Date Essai", "Couche", "Emplacement", "PK / Profil", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]
    ws.row_dimensions[6].height = 30
    for col_idx, text in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col_idx, value=text)
        cell.font = font_th
        cell.fill = fill_th
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # --- 3. REMPLISSAGE DES DONNÉES ---
    start_row = 7
    for r_idx, (_, row) in enumerate(df_filtered.iterrows(), start=start_row):
        ws.row_dimensions[r_idx].height = 34
        is_even = (r_idx % 2 == 0)
        current_fill = fill_zebra if is_even else PatternFill(fill_type=None)
        k_val = float(row.get("k", 0.0) or 0.0)

        values = [str(row.get("date_essai", "") or ""), str(row.get("couche", "") or ""), 
                  str(row.get("emplacement", "") or ""), str(row.get("pk_profil", "") or ""),
                  float(row.get("ev1", 0.0) or 0.0), float(row.get("ev2", 0.0) or 0.0), k_val]

        for c_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Calibri", size=12)
            cell.border = thin_border
            cell.fill = current_fill
            if c_idx >= 5: cell.number_format = "#,##0.00" if c_idx < 7 else "0.00"
            if c_idx == 7:
                if k_val >= 1.5:
                    cell.fill = PatternFill(start_color=GREEN_OK, end_color=GREEN_OK, fill_type="solid")
                    cell.font = Font(name="Calibri", size=12, bold=True, color=TEXT_GREEN)
                else:
                    cell.fill = PatternFill(start_color=ORANGE_WARN, end_color=ORANGE_WARN, fill_type="solid")
                    cell.font = Font(name="Calibri", size=12, bold=True, color=TEXT_ORANGE)

    # --- LARGEURS ET SAUVEGARDE ---
    for col_letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
        ws.column_dimensions[col_letter].width = 16
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

def show(supabase):
    st.title("📊 Synthèse Essais à la Plaque")
    st.markdown("---")

    if not supabase:
        st.error("❌ Connexion Supabase indisponible.")
        return

    try:
        res = supabase.table("essai_plaque").select("*").order("date_essai", desc=True).execute()
        data = res.data if res else []
    except Exception as e:
        st.error(f"Erreur DB : {e}")
        return

    if not data:
        st.info("Aucun essai trouvé.")
        return

    df = pd.DataFrame(data)
    df['date_essai_dt'] = pd.to_datetime(df['date_essai'])

    # --- FILTRES ---
    col1, col2, col3 = st.columns(3)
    with col1:
        type_recap = st.selectbox("Période", ["Tous les essais", "Journalier", "Mensuel"])
    
    filtered_df = df.copy()
    filter_label = "Historique Complet"
    
    if type_recap == "Journalier":
        date_choisie = st.date_input("Date")
        filtered_df = df[df['date_essai_dt'].dt.date == date_choisie]
        filter_label = f"Journalier du {date_choisie}"
    
    # [Ajoutez vos logiques de filtres supplémentaires ici si nécessaire]

    # --- TABLEAU ET EXPORT ---
    st.dataframe(filtered_df, use_container_width=True)
    
    excel_data = generate_excel_a4(filtered_df, filter_title=filter_label)
    st.download_button(
        label="📄 Télécharger la Synthèse Excel",
        data=excel_data,
        file_name="Synthese_Essais.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
