import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def generate_excel_a4(df_filtered, filter_title="Synthèse Générale"):
    """
    Génère un fichier Excel professionnel mis en page pour impression A4 Portrait
    avec une police de taille 12, un espacement de ligne de 34, et les blocs de signature.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Synthèse Essais Plaque"

    # --- CONFIGURATION IMPRESSION A4 PORTRAIT ---
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # --- EN-TÊTE ET PIED DE PAGE D'IMPRESSION ---
    ws.oddHeader.left.text = "&\"Calibri,Bold\"&10LABORATOIRE LPEE - CTR-CSB\nProjet: LGV CASA SUD | Client: TGCC"
    ws.oddHeader.center.text = f"&\"Calibri,Bold\"&12SYNTHÈSE DES ESSAIS À LA PLAQUE\n{filter_title}"
    ws.oddHeader.right.text = "&\"Calibri,Regular\"&9Edité le: &D"
    ws.oddFooter.center.text = "&\"Calibri,Bold\"&10Page &P sur &N"

    # --- PALETTE DE COULEURS ET STYLES ---
    NAVY_HEADER = "1F4E79"
    BLUE_SUBHEADER = "2F5597"
    ICE_BLUE_BG = "F2F5F9"
    BORDER_COLOR = "D9D9D9"
    GREEN_OK = "E2EFDA"
    TEXT_GREEN = "276A3C"
    ORANGE_WARN = "FFF2CC"
    TEXT_ORANGE = "B25900"

    font_title = Font(name="Calibri", size=15, bold=True, color=NAVY_HEADER)
    font_th = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    
    fill_th = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    fill_zebra = PatternFill(start_color=ICE_BLUE_BG, end_color=ICE_BLUE_BG, fill_type="solid")
    fill_kpi = PatternFill(start_color="EAECEE", end_color="EAECEE", fill_type="solid")

    thin_border = Border(left=Side(style='thin', color=BORDER_COLOR), right=Side(style='thin', color=BORDER_COLOR), top=Side(style='thin', color=BORDER_COLOR), bottom=Side(style='thin', color=BORDER_COLOR))
    thick_top_bottom = Border(left=Side(style='thin', color=BORDER_COLOR), right=Side(style='thin', color=BORDER_COLOR), top=Side(style='medium', color=NAVY_HEADER), bottom=Side(style='double', color=NAVY_HEADER))

    # --- 1. EN-TÊTE DU DOCUMENT ---
    ws.merge_cells("A1:G1"); ws["A1"] = "LABORATOIRE LPEE — CENTRE TECHNIQUE RÉGIONAL"; ws["A1"].font = font_title; ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A2:G2"); ws["A2"] = "Norme : NF P 94-117-1 (Plaque Ø 600 mm)"; ws["A2"].font = Font(name="Calibri", size=15, bold=True, color=NAVY_HEADER); ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A3:G3"); ws["A3"] = "Projet : LGV CASA SUD  |  Client : TGCC"; ws["A3"].font = Font(name="Calibri", size=14, bold=True, color=BLUE_SUBHEADER); ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A4:G4"); ws["A4"] = f"SYNTHÈSE DES ESSAIS DE PORTANCE À LA PLAQUE — {filter_title.upper()}"; ws["A4"].font = Font(name="Calibri", size=12, italic=True, color="595959"); ws["A4"].alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 26; ws.row_dimensions[2].height = 26; ws.row_dimensions[3].height = 24; ws.row_dimensions[4].height = 20; ws.row_dimensions[5].height = 8

    # --- 2. EN-TÊTES ---
    headers = ["Date Essai", "Couche", "Emplacement", "PK / Profil", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]
    ws.row_dimensions[6].height = 30
    for col_idx, text in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col_idx, value=text)
        cell.font = font_th; cell.fill = fill_th; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = thin_border

    # --- 3. DONNÉES ---
    start_row = 7
    for r_idx, (_, row) in enumerate(df_filtered.iterrows(), start=start_row):
        ws.row_dimensions[r_idx].height = 34
        is_even = (r_idx % 2 == 0)
        current_fill = fill_zebra if is_even else PatternFill(fill_type=None)
        k_val = float(row.get("k", 0.0) or 0.0)
        values = [str(row.get("date_essai", "") or ""), str(row.get("couche", "") or ""), str(row.get("emplacement", "") or ""), str(row.get("pk_profil", "") or ""), float(row.get("ev1", 0.0) or 0.0), float(row.get("ev2", 0.0) or 0.0), k_val]
        for c_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Calibri", size=12); cell.border = thin_border; cell.fill = current_fill
            if c_idx == 1: cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c_idx in [2, 3, 4]: cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c_idx in [5, 6]: cell.alignment = Alignment(horizontal="right", vertical="center"); cell.number_format = "#,##0.00"
            elif c_idx == 7: 
                cell.alignment = Alignment(horizontal="right", vertical="center"); cell.number_format = "0.00"
                if k_val >= 1.5: cell.fill = PatternFill(start_color=GREEN_OK, end_color=GREEN_OK, fill_type="solid"); cell.font = Font(name="Calibri", size=12, bold=True, color=TEXT_GREEN)
                else: cell.fill = PatternFill(start_color=ORANGE_WARN, end_color=ORANGE_WARN, fill_type="solid"); cell.font = Font(name="Calibri", size=12, bold=True, color=TEXT_ORANGE)

    buffer = io.BytesIO()
    wb.save(buffer); buffer.seek(0)
    return buffer

def show(supabase):
    st.title("📊 Synthèse Essais à la Plaque")
    st.markdown("---")

    if not supabase:
        st.error("❌ Connexion Supabase indisponible.")
        return

    # Récupération des données
    try:
        res = supabase.table("essai_plaque").select("*").order("date_essai", desc=True).execute()
        data = res.data if res else []
    except Exception as e:
        st.error(f"Erreur DB : {e}"); return

    if not data:
        st.info("Aucun essai enregistré."); return

    df = pd.DataFrame(data)
    df['date_essai_dt'] = pd.to_datetime(df['date_essai'])

    # --- FILTRES ---
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1: type_recap = st.selectbox("Période", ["Tous les essais", "Journalier", "Mensuel", "Période Personnalisée"])
    
    filtered_df = df.copy()
    filter_label = "Général"
    
    if type_recap == "Journalier":
        with col_f2: d = st.date_input("Date", value=date.today()); filtered_df = df[df['date_essai_dt'].dt.date == d]
    elif type_recap == "Mensuel":
        with col_f2: m = st.date_input("Choisir le mois", value=date.today()); filtered_df = df[(df['date_essai_dt'].dt.year == m.year) & (df['date_essai_dt'].dt.month == m.month)]
    elif type_recap == "Période Personnalisée":
        with col_f2: ds = st.date_input("Du"); de = st.date_input("Au")
        filtered_df = df[(df['date_essai_dt'].dt.date >= ds) & (df['date_essai_dt'].dt.date <= de)]
    
    # ... (le reste de vos filtres existants) ...
    st.dataframe(filtered_df, use_container_width=True)

    # ==========================================================
    # --- ZONE ADMINISTRATION (Admin Only) ---
    # ==========================================================
    if st.session_state.role == "admin":
        st.markdown("---")
        st.subheader("🛠️ Espace Administration (Gestion des données)")
        
        # 1. Sélection de l'enregistrement
        record_options = {f"ID {r['id']} - {r.get('date_essai', 'N/A')} - {r.get('pk_profil', '')}": r for r in data}
        selected_key = st.selectbox("Sélectionner l'essai à gérer", list(record_options.keys()))
        selected_item = record_options[selected_key]
        
        col_ed, col_del = st.columns(2)
        
        with col_ed:
            with st.expander("📝 Modifier cet essai"):
                with st.form("edit_form"):
                    new_pk = st.text_input("PK / Profil", value=selected_item.get("pk_profil", ""))
                    new_ev1 = st.number_input("EV1 (MPa)", value=float(selected_item.get("ev1", 0)))
                    new_ev2 = st.number_input("EV2 (MPa)", value=float(selected_item.get("ev2", 0)))
                    
                    if st.form_submit_button("Enregistrer les modifications"):
                        try:
                            # Calcul automatique de K
                            new_k = new_ev2 / new_ev1 if new_ev1 > 0 else 0
                            supabase.table("essai_plaque").update({
                                "pk_profil": new_pk,
                                "ev1": new_ev1,
                                "ev2": new_ev2,
                                "k": new_k
                            }).eq("id", selected_item["id"]).execute()
                            st.success("Données mises à jour !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")
                            
        with col_del:
            if st.button("🗑️ Supprimer définitivement", type="primary"):
                try:
                    supabase.table("essai_plaque").delete().eq("id", selected_item["id"]).execute()
                    st.success("Enregistrement supprimé.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

    # --- EXPORT ---
    st.markdown("---")
    excel_data = generate_excel_a4(filtered_df)
    st.download_button("📄 Télécharger Excel", data=excel_data, file_name="synthese.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
