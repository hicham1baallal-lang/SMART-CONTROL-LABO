import streamlit as st
import pandas as pd
from datetime import date, datetime
from audit_log import enregistrer_modification, afficher_historique_modifications
import projets_config

# Import pour la génération du PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
import os

# Import pour la génération Excel avancée
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def evaluer_conformite_couche(couche, ev2_val):
    """Évalue automatiquement si les résultats sont conformes ou non selon le type de couche."""
    conforme = True
    motif = []

    if couche == "Sous-couche et Couche de forme ferroviaire (LGV)":
        if ev2_val < 80.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < 80 MPa requis")
    elif couche == "Remblais contigus aux Ouvrages d'Art (PRO)":
        if ev2_val < 80.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < 80 MPa requis")
    elif couche == "Arase des terrassements / PST":
        if ev2_val < 50.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < 50 MPa requis")
    elif couche == "Corps de remblai courant (avant PST)":
        if ev2_val < 30.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < 30 MPa requis")
    elif couche == "Remblais de fouilles d'ouvrages d'art":
        if ev2_val < 80.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < 80 MPa requis")
    elif couche == "Couche de forme des rétablissements / accès":
        if ev2_val <= 50.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa non supérieur à 50 MPa requis")
    elif couche == "Plateforme support d'étaiements / cintres":
        if ev2_val <= 80.0:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa non supérieur à 80 MPa requis")

    if conforme:
        return "Résultats conforme"
    else:
        return f"Résultats non conforme ({', '.join(motif)})"


def generer_pdf_pv(essai):
    """Génère un Procès-Verbal (PV) professionnel sur format A4 avec le logo, le centre régional et la hiérarchie des titres."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=12,
        textColor=colors.HexColor('#1f4e78'),
        alignment=1,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontSize=9.5,
        textColor=colors.HexColor('#595959'),
        alignment=1,
        spaceAfter=12
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1f4e78'),
        spaceBefore=10,
        spaceAfter=4
    )
    
    normal_style = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#262626'))
    bold_style = ParagraphStyle('BoldText', parent=normal_style, fontName='Helvetica-Bold')

    logo_path = "logo.png.jpg"
    
    org_style = ParagraphStyle(
        'OrgStyle',
        parent=bold_style,
        alignment=0,
        fontSize=14,
        textColor=colors.HexColor('#1f4e78')
    )
    
    header_text = (
        "<b>LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES (LPEE)</b><br/>"
        "<font size=8.5 color='#595959'>CENTRE TECHNIQUE REGIONALE DE CASABLANCA -SETTAT BENIMELLAL</font>"
    )
    
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=45, height=45)
            img.hAlign = 'LEFT'
            txt_header = Paragraph(header_text, org_style)
            header_table = Table([[img, txt_header]], colWidths=[55, 470])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            elements.append(header_table)
        except Exception:
            elements.append(Paragraph(header_text, org_style))
    else:
        elements.append(Paragraph(header_text, org_style))

    elements.append(Spacer(1, 6))
    elements.append(Spacer(1, 4))

    data_infos = [
        [Paragraph("Client / Organisme :", bold_style), Paragraph(str(essai.get('client', '-')), normal_style),
         Paragraph("Chantier / Projet :", bold_style), Paragraph(str(essai.get('projet', '-')), normal_style)],
        [Paragraph("Emplacement / Zone :", bold_style), Paragraph(str(essai.get('emplacement', '-')), normal_style),
         Paragraph("PK / Profil :", bold_style), Paragraph(str(essai.get('pk_profil', '-')), normal_style)],
        [Paragraph("Couche / Ouvrage :", bold_style), Paragraph(str(essai.get('couche', '-')), normal_style),
         Paragraph("Nature du matériau :", bold_style), Paragraph(str(essai.get('nature_materiau', '-')), normal_style)],
        [Paragraph("Technicien :", bold_style), Paragraph(str(essai.get('technicien', '-')), normal_style),
         Paragraph("", normal_style), Paragraph("", normal_style)]
    ]
    
    t_infos = Table(data_infos, colWidths=[115, 147.5, 115, 147.5])
    t_infos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f2f2f2')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#d9d9d9')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_infos)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Détail des Points de Mesure et Résultats (NF P 94-117-1)", section_style))
    
    points = essai.get('points_mesure', [])
    if not points:
        points = [{"z1": essai.get('z1', 0), "z2": essai.get('z2', 0), "pk_point": essai.get('pk_profil', '-')}]

    table_pts_data = [["Point / PK", "Z1 1er chrg (mm)", "Z2 2ème chrg (mm)", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]]
    
    for idx, pt in enumerate(points):
        z1_v = float(pt.get("z1", 0.53))
        z2_v = float(pt.get("z2", 0.52))
        ev1_v = round(112.5 / (z1_v * 2), 2) if z1_v > 0 else 0.0
        ev2_v = round(90.0 / (z2_v * 2), 2) if z2_v > 0 else 0.0
        k_v = round(ev2_v / ev1_v, 2) if ev1_v > 0 else 0.0
        
        table_pts_data.append([
            str(pt.get("pk_point", f"P{idx+1}")),
            f"{z1_v:.2f}",
            f"{z2_v:.2f}",
            f"{ev1_v:.2f}",
            f"{ev2_v:.2f}",
            f"{k_v:.2f}"
        ])

    t_pts = Table(table_pts_data, colWidths=[105, 90, 90, 80, 80, 80])
    t_pts.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f4e78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#bfbfbf')),
    ]))
    elements.append(t_pts)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Commentaire", section_style))
    
    couche_nom = essai.get('couche', '')
    ev2_principal = float(essai.get('ev2', 0))
    commentaire_automatique = evaluer_conformite_couche(couche_nom, ev2_principal)
    
    t_obs = Table([[Paragraph(commentaire_automatique, normal_style)]], colWidths=[525])
    t_obs.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#d9d9d9')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_obs)
    elements.append(Spacer(1, 15))

    sig_style = ParagraphStyle('SigStyle', parent=normal_style, alignment=1)
    data_sig = [
        [
            Paragraph("<b>Responsable d'essai</b><br/><br/>O. IKKEN", sig_style), 
            Paragraph("<b>Chef du laboratoire</b><br/><br/>H. BAALLAL", sig_style)
        ]
    ]
    t_sig = Table(data_sig, colWidths=[262.5, 262.5])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_sig)

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("PROCÈS-VERBAL D'ESSAI À LA PLAQUE (NF P 94-117-1)", title_style))
    elements.append(Paragraph(f"Référence : <b>{essai.get('reference', '-')}</b> | Date : {essai.get('date_essai', '-')}", subtitle_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generer_excel_synthese(df, mois_str, empl_str, couche_str, nom_projet):
    """Génère un classeur Excel formaté simulant le modèle de synthèse demandé."""
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Synthèse Plaque"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=13, bold=True, color="1F4E78")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="595959")
    bold_font = Font(name="Calibri", size=10, bold=True)
    normal_font = Font(name="Calibri", size=10)
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    double_bottom_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='double', color='1F4E78')
    )

    ws['A1'] = "LABORATOIRE LPEE — CENTRE TECHNIQUE RÉGIONAL"
    ws['A1'].font = title_font
    ws.merge_cells('A1:G1')
    ws['A1'].alignment = Alignment(horizontal='center')

    ws['A2'] = "Norme : NF P 94-117-1 (Plaque Ø 600 mm)"
    ws['A2'].font = bold_font
    ws.merge_cells('A2:G2')
    ws['A2'].alignment = Alignment(horizontal='center')

    ws['A3'] = f"Projet : {nom_projet} | Filtres -> Mois: {mois_str} | Emplacement: {empl_str} | Couche: {couche_str}"
    ws['A3'].font = subtitle_font
    ws.merge_cells('A3:G3')
    ws['A3'].alignment = Alignment(horizontal='center')

    ws['A4'] = f"SYNTHÈSE DES ESSAIS DE PORTANCE À LA PLAQUE — MENSUEL - {mois_str}"
    ws['A4'].font = bold_font
    ws.merge_cells('A4:G4')
    ws['A4'].alignment = Alignment(horizontal='center')

    headers = ["Date Essai", "Couche", "Emplacement", "PK / Profil", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]
    for col_num, header_title in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col_num)
        cell.value = header_title
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    row_idx = 7
    ev1_vals, ev2_vals, k_vals = [], [], []

    for _, row in df.iterrows():
        ws.cell(row=row_idx, column=1, value=str(row.get('date_essai', ''))).alignment = Alignment(horizontal='center')
        ws.cell(row=row_idx, column=2, value=str(row.get('couche', ''))).alignment = Alignment(horizontal='left')
        ws.cell(row=row_idx, column=3, value=str(row.get('emplacement', ''))).alignment = Alignment(horizontal='left')
        ws.cell(row=row_idx, column=4, value=str(row.get('pk_profil', ''))).alignment = Alignment(horizontal='center')

        ev1_v = float(row.get('ev1', 0) or 0)
        ev2_v = float(row.get('ev2', 0) or 0)
        k_v = float(row.get('k_ratio', 0) or 0)

        ev1_vals.append(ev1_v)
        ev2_vals.append(ev2_v)
        k_vals.append(k_v)

        c_ev1 = ws.cell(row=row_idx, column=5, value=ev1_v)
        c_ev1.number_format = '#,##0.00'
        c_ev1.alignment = Alignment(horizontal='right')

        c_ev2 = ws.cell(row=row_idx, column=6, value=ev2_v)
        c_ev2.number_format = '#,##0.00'
        c_ev2.alignment = Alignment(horizontal='right')

        c_k = ws.cell(row=row_idx, column=7, value=k_v)
        c_k.number_format = '#,##0.00'
        c_k.alignment = Alignment(horizontal='right')
        c_k.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

        for c in range(1, 8):
            ws.cell(row=row_idx, column=c).font = normal_font
            ws.cell(row=row_idx, column=c).border = thin_border

        row_idx += 1

    if len(df) > 0:
        avg_ev1 = sum(ev1_vals) / len(ev1_vals)
        avg_ev2 = sum(ev2_vals) / len(ev2_vals)
        avg_k = sum(k_vals) / len(k_vals)

        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
        m_cell = ws.cell(row=row_idx, column=1, value="MOYENNE DES ESSAIS")
        m_cell.font = bold_font
        m_cell.alignment = Alignment(horizontal='right', vertical='center')

        for c in range(1, 5):
            ws.cell(row=row_idx, column=c).border = double_bottom_border

        c_avg1 = ws.cell(row=row_idx, column=5, value=avg_ev1)
        c_avg1.font = bold_font
        c_avg1.number_format = '#,##0.00'
        c_avg1.alignment = Alignment(horizontal='right')
        c_avg1.border = double_bottom_border

        c_avg2 = ws.cell(row=row_idx, column=6, value=avg_ev2)
        c_avg2.font = bold_font
        c_avg2.number_format = '#,##0.00'
        c_avg2.alignment = Alignment(horizontal='right')
        c_avg2.border = double_bottom_border

        c_avgk = ws.cell(row=row_idx, column=7, value=avg_k)
        c_avgk.font = bold_font
        c_avgk.number_format = '#,##0.00'
        c_avgk.alignment = Alignment(horizontal='right')
        c_avgk.border = double_bottom_border

        row_idx += 2

        ws.cell(row=row_idx, column=1, value="RÉSUMÉ STATISTIQUE QUALITÉ").font = bold_font
        row_idx += 1

        stat_headers = ["Indicateur", "EV1 (MPa)", "EV2 (MPa)", "Ratio K (EV2/EV1)"]
        for col_num, sh in enumerate(stat_headers, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = sh
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border
        row_idx += 1

        stats_data = [
            ("Valeur Minimale", min(ev1_vals), min(ev2_vals), min(k_vals)),
            ("Valeur Maximale", max(ev1_vals), max(ev2_vals), max(k_vals)),
            ("Moyenne Générale", avg_ev1, avg_ev2, avg_k),
            ("Nombre d'essais", len(ev1_vals), len(ev2_vals), len(k_vals))
        ]

        for label, v1, v2, vk in stats_data:
            ws.cell(row=row_idx, column=1, value=label).font = bold_font
            ws.cell(row=row_idx, column=1).border = thin_border
            
            for col_idx, val in enumerate([v1, v2, vk], 2):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = normal_font
                c.number_format = '#,##0.00' if label != "Nombre d'essais" else '#,##0'
                c.alignment = Alignment(horizontal='right')
                c.border = thin_border
            row_idx += 1

        row_idx += 3
        ws.cell(row=row_idx, column=1, value="Responsable d'essai").font = bold_font
        ws.cell(row=row_idx, column=6, value="Chef du Laboratoire").font = bold_font

    wb.save(output)
    output.seek(0)
    return output.getvalue()


def show(supabase):
    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")

    user_raw = (
        st.session_state.get("username") or 
        st.session_state.get("user") or 
        st.session_state.get("user_name") or 
        "Agent LPEE"
    )

    if isinstance(user_raw, dict):
        user_raw = user_raw.get("email") or user_raw.get("name") or "Agent LPEE"

    current_user = str(user_raw).upper()

    user_role = str(st.session_state.get("role", "")).upper()
    is_admin = st.session_state.get("is_admin", False) or user_role == "ADMIN"
    is_baallal_admin = current_user.strip() == "BAALLAL" and is_admin

    user_info_projet = st.session_state.get("user") or {}
    projet_id_actif = projets_config.projet_actif(user_info_projet)
    if not projet_id_actif:
        st.error("⚠️ Aucun projet ne vous est autorisé. Contactez un administrateur.")
        return
    st.caption(f"📁 Projet actif : **{projets_config.nom_projet(projet_id_actif)}**")

    tab_saisie, tab_pv, tab_synthese = st.tabs(["📝 Saisie & Historique", "PV/PDF", "Synthèse"])

    with tab_saisie:
        editing_item = st.session_state.get("edit_plaque_item", None)

        if editing_item:
            st.info(f"✏️ **Mode Modification** - Essai ID #{editing_item['id']}")
            
            default_ref = editing_item.get("reference") or editing_item.get("ref_essai") or editing_item.get("ref") or "260/26/PLQ/01"
            default_date = datetime.strptime(editing_item["date_essai"], "%Y-%m-%d").date() if isinstance(editing_item.get("date_essai"), str) else date.today()
            default_client = editing_item.get("client", "TGCC")
            default_projet = editing_item.get("projet", "LGV CASA SUD")
            default_empl = editing_item.get("emplacement", "")
            default_pk = editing_item.get("pk_profil", editing_item.get("pkl", ""))
            default_couche = editing_item.get("couche", "Sous-couche et Couche de forme ferroviaire (LGV)")
            default_mat = editing_item.get("nature_materiau", "")
            default_tech = editing_item.get("technicien", current_user)
            default_obs = editing_item.get("observations", "")
            
            saved_points = editing_item.get("points_mesure")
            if not saved_points or not isinstance(saved_points, list):
                default_points = [{"z1": float(editing_item.get("z1", 0.53)), "z2": float(editing_item.get("z2", 0.52)), "pk_point": default_pk}]
            else:
                default_points = saved_points
        else:
            default_ref = "260/26/PLQ/01"
            default_date = date.today()
            default_client = "TGCC"
            default_projet = "LGV CASA SUD"
            default_empl = "Voie B"
            default_pk = "PK 1+200"
            default_couche = "Sous-couche et Couche de forme ferroviaire (LGV)"
            default_mat = "GNT 0/31.5 Classée B2"
            default_tech = current_user
            default_obs = ""
            default_points = [{"z1": 0.53, "z2": 0.52, "pk_point": "PK 1+200"}]

        st.subheader("📝 " + ("Modifier l'essai" if editing_item else "Saisie d'un nouvel essai"))

        col0, col1, col2 = st.columns(3)

        with col0:
            reference = st.text_input("Référence de l'essai", value=default_ref, key="plaque_reference")
        with col1:
            date_essai = st.date_input("Date de l'essai", value=default_date, key="plaque_date")
            client = st.text_input("Client / Organisme", value=default_client, key="plaque_client")
            projet = st.text_input("Chantier / Projet", value=default_projet, key="plaque_projet")
        with col2:
            couche_options = [
                "Sous-couche et Couche de forme ferroviaire (LGV)",
                "Remblais contigus aux Ouvrages d'Art (PRO)",
                "Arase des terrassements / PST",
                "Corps de remblai courant (avant PST)",
                "Remblais de fouilles d'ouvrages d'art",
                "Couche de forme des rétablissements / accès",
                "Plateforme support d'étaiements / cintres",
                "Autre"
            ]
            couche_idx = couche_options.index(default_couche) if default_couche in couche_options else 0
            couche = st.selectbox("Couche / Ouvrage testé", couche_options, index=couche_idx, key="plaque_couche")
            emplacement = st.text_input("Emplacement / Zone", value=default_empl, key="plaque_empl")
            pk_profil = st.text_input("PK / Profil Global", value=default_pk, key="plaque_pk")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            nature_materiau = st.text_input("Nature du matériau", value=default_mat, key="plaque_mat")
        with col_m2:
            technicien = st.text_input("Technicien LPEE", value=default_tech, key="plaque_tech")

        st.markdown("---")
        st.subheader("2. Points de Mesure d'essai à la plaque")

        if "plaque_points_count" not in st.session_state or editing_item:
            st.session_state["plaque_points_count"] = len(default_points)

        col_add, col_rem, _ = st.columns([1, 1, 3])
        with col_add:
            if st.button("➕ Ajouter un point"):
                st.session_state["plaque_points_count"] += 1
        with col_rem:
            if st.session_state["plaque_points_count"] > 1:
                if st.button("➖ Supprimer un point"):
                    st.session_state["plaque_points_count"] -= 1

        points_data = []
        for i in range(st.session_state["plaque_points_count"]):
            st.markdown(f"**Point de mesure N° {i+1}**")
            p_col0, p_col1, p_col2 = st.columns([1, 1, 1])
            
            default_pk_point = default_points[i].get("pk_point", default_pk) if i < len(default_points) else default_pk
            default_z1_val = default_points[i]["z1"] if i < len(default_points) else 0.53
            default_z2_val = default_points[i]["z2"] if i < len(default_points) else 0.52

            with p_col0:
                pk_point = st.text_input(f"Num/PK/Profil [Point {i+1}]", value=str(default_pk_point), key=f"plaque_pk_point_{i}")
            with p_col1:
                z1 = st.number_input(f"Z1 - 1er chrg (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z1_val), step=0.01, format="%.2f", key=f"plaque_z1_{i}")
            with p_col2:
                z2 = st.number_input(f"Z2 - 2ème chrg (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z2_val), step=0.01, format="%.2f", key=f"plaque_z2_{i}")
            
            points_data.append({"z1": z1, "z2": z2, "pk_point": pk_point})

        st.markdown("---")
        st.subheader("📈 Résultats Calculés Automatiquement")

        points_results = []
        commentaires_points = []
        
        for i, p in enumerate(points_data):
            z1_val = p["z1"]
            z2_val = p["z2"]
            ev1_i = round(112.5 / (z1_val * 2), 2) if z1_val > 0 else 0.0
            ev2_i = round(90.0 / (z2_val * 2), 2) if z2_val > 0 else 0.0
            k_ratio_i = round(ev2_i / ev1_i, 2) if ev1_i > 0 else 0.0

            comm_pt = f"Point {p['pk_point']} : EV2 = {ev2_i} MPa, K = {k_ratio_i}."
            commentaires_points.append(comm_pt)
            points_results.append({"ev1": ev1_i, "ev2": ev2_i, "k_ratio": k_ratio_i})

            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric(f"EV1 [Point {i+1}]", f"{ev1_i:.2f} MPa")
            res_col2.metric(f"EV2 [Point {i+1}]", f"{ev2_i:.2f} MPa")
            res_col3.metric(f"Coefficient K [Point {i+1}]", f"{k_ratio_i:.2f}")

        active_z1 = points_data[0]["z1"]
        active_z2 = points_data[0]["z2"]
        ev1 = points_results[0]["ev1"]
        ev2 = points_results[0]["ev2"]
        k_ratio = points_results[0]["k_ratio"]

        default_obs_systematique = "\n".join(commentaires_points)
        if not default_obs and not editing_item:
            default_obs = default_obs_systematique
        elif editing_item and not default_obs:
            default_obs = default_obs_systematique

        observations = st.text_area("Commentaire / Remarques", value=default_obs, key="plaque_obs")

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            button_label = "🔄 Mettre à jour l'essai" if editing_item else "💾 Enregistrer l'essai"
            if st.button(button_label, key="btn_enregistrer_plaque", type="primary", use_container_width=True):
                
                try:
                    query_doublon = supabase.table("essai_plaque").select("id").eq("projet_id", projet_id_actif).eq("reference", reference)
                    if editing_item:
                        query_doublon = query_doublon.neq("id", editing_item["id"])
                    res_doublon = query_doublon.execute()
                    if res_doublon.data and len(res_doublon.data) > 0:
                        st.error(f"🚫 **BLOCAGE** : La référence d'essai **'{reference}'** existe déjà dans ce projet !")
                        st.stop()
                except Exception:
                    pass

                payload = {
                    "reference": reference,
                    "date_essai": str(date_essai),
                    "client": client,
                    "projet": projet,
                    "emplacement": emplacement,
                    "pk_profil": pk_profil,
                    "couche": couche,
                    "nature_materiau": nature_materiau,
                    "z1": float(active_z1),
                    "z2": float(active_z2),
                    "points_mesure": points_data,
                    "ev1": float(ev1),
                    "ev2": float(ev2),
                    "k_ratio": float(k_ratio),
                    "technicien": technicien,
                    "observations": observations
                }

                try:
                    sample_query = supabase.table("essai_plaque").select("*").limit(1).execute()
                    if sample_query.data and len(sample_query.data) > 0:
                        valid_columns = set(sample_query.data[0].keys())
                        safe_payload = {k: v for k, v in payload.items() if k in valid_columns}
                    else:
                        safe_payload = payload

                    safe_payload["projet_id"] = projet_id_actif

                    if editing_item:
                        anciennes_valeurs_plaque = {k: editing_item.get(k) for k in safe_payload}
                        supabase.table("essai_plaque").update(safe_payload).eq("id", editing_item["id"]).eq("projet_id", projet_id_actif).execute()
                        enregistrer_modification(supabase, "essai_plaque", editing_item["id"], "MODIFICATION", anciennes_valeurs_plaque, safe_payload)
                        st.success(f"✅ Essai #{editing_item['id']} mis à jour avec succès !")
                        st.session_state["edit_plaque_item"] = None
                    else:
                        res_ins_plaque = supabase.table("essai_plaque").insert(safe_payload).execute()
                        if res_ins_plaque.data:
                            nouvel_id_plaque = res_ins_plaque.data[0].get("id")
                            enregistrer_modification(supabase, "essai_plaque", nouvel_id_plaque, "CREATION", nouvelles_valeurs=safe_payload)
                        st.success("✅ Essai enregistré avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement : {e}")

        with btn_col2:
            if editing_item and st.button("❌ Annuler", use_container_width=True):
                st.session_state["edit_plaque_item"] = None
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Historique des Essais Enregistrés")
        try:
            res = supabase.table("essai_plaque").select("*").eq("projet_id", projet_id_actif).order("id", desc=True).execute()
            if res.data and len(res.data) > 0:
                clean_rows = []
                for row in res.data:
                    ref_val = row.get("reference") or row.get("ref_essai") or row.get("ref") or "-"
                    clean_rows.append({
                        "ID": row.get("id"),
                        "Référence": ref_val,
                        "Date": row.get("date_essai"),
                        "Client": row.get("client"),
                        "Emplacement": row.get("emplacement"),
                        "Couche": row.get("couche"),
                        "EV2 (MPa)": row.get("ev2"),
                        "Technicien": row.get("technicien")
                    })
                st.dataframe(pd.DataFrame(clean_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun essai enregistré.")
        except Exception as e:
            st.warning(f"Erreur historique : {e}")

    with tab_pv:
        st.subheader("📄 Génération de PV et Synthèse PDF")
        try:
            res_pv = supabase.table("essai_plaque").select("*").eq("projet_id", projet_id_actif).order("id", desc=True).execute()
            if res_pv.data and len(res_pv.data) > 0:
                options_essais = {f"ID #{item['id']} - Réf: {item.get('reference', 'Sans réf')} ({item.get('date_essai', '')})": item for item in res_pv.data}
                choix_essai_str = st.selectbox("Sélectionner l'essai à éditer en PV :", options=list(options_essais.keys()))
                essai_selectionne = options_essais[choix_essai_str]

                st.markdown("---")
                st.markdown("### 🔍 Aperçu rapide des données")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.write(f"**Référence :** {essai_selectionne.get('reference', '-')}")
                    st.write(f"**Date :** {essai_selectionne.get('date_essai', '-')}")
                    st.write(f"**Client :** {essai_selectionne.get('client', '-')}")
                    st.write(f"**Projet :** {essai_selectionne.get('projet', '-')}")
                with col_p2:
                    st.write(f"**Emplacement :** {essai_selectionne.get('emplacement', '-')}")
                    st.write(f"**Couche :** {essai_selectionne.get('couche', '-')}")
                    st.write(f"**Technicien :** {essai_selectionne.get('technicien', '-')}")

                st.markdown("### 📥 Téléchargement du PV")
                pdf_bytes = generer_pdf_pv(essai_selectionne)
                nom_fichier = f"PV_Essai_Plaque_{str(essai_selectionne.get('reference', essai_selectionne.get('id'))).replace('/', '_')}.pdf"
                
                st.download_button(
                    label="📥 Télécharger le Procès-Verbal (PDF)",
                    data=pdf_bytes,
                    file_name=nom_fichier,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
            else:
                st.info("Aucun essai disponible pour générer un PV.")
        except Exception as e:
            st.warning(f"Erreur lors du chargement des PV : {e}")

    with tab_synthese:
        st.subheader("📊 Synthèse & Filtres Avancés (Téléchargement Excel)")
        try:
            res_synth = supabase.table("essai_plaque").select("*").eq("projet_id", projet_id_actif).order("id", desc=True).execute()
            if res_synth.data and len(res_synth.data) > 0:
                df_synth = pd.DataFrame(res_synth.data)
                df_synth['date_datetime'] = pd.to_datetime(df_synth['date_essai'], errors='coerce')
                df_synth['mois'] = df_synth['date_datetime'].dt.strftime('%Y-%m')

                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    mois_options = ["Tous"] + sorted([m for m in df_synth['mois'].dropna().unique().tolist()], reverse=True)
                    choix_mois = st.selectbox("Période (Mois)", mois_options, key="filtre_mois")
                with f_col2:
                    empl_options = ["Tous"] + sorted([str(e) for e in df_synth['emplacement'].dropna().unique().tolist()])
                    choix_empl = st.selectbox("Emplacement", empl_options, key="filtre_emplacement")
                with f_col3:
                    couche_options_filt = ["Tous"] + sorted([str(c) for c in df_synth['couche'].dropna().unique().tolist()])
                    choix_couche = st.selectbox("Type de couche", couche_options_filt, key="filtre_couche")

                df_filtered = df_synth.copy()
                if choix_mois != "Tous":
                    df_filtered = df_filtered[df_filtered['mois'] == choix_mois]
                if choix_empl != "Tous":
                    df_filtered = df_filtered[df_filtered['emplacement'] == choix_empl]
                if choix_couche != "Tous":
                    df_filtered = df_filtered[df_filtered['couche'] == choix_couche]

                st.markdown("---")
                col_m, col_btn = st.columns([2, 1])
                with col_m:
                    st.metric("Nombre d'essais correspondants", len(df_filtered))
                with col_btn:
                    if not df_filtered.empty:
                        nom_projet_actif = projets_config.nom_projet(projet_id_actif)
                        excel_bytes = generer_excel_synthese(df_filtered, choix_mois, choix_empl, choix_couche, nom_projet_actif)
                        st.download_button(
                            label="📥 Télécharger la Synthèse Excel",
                            data=excel_bytes,
                            file_name=f"Synthese_Essais_Plaque_{choix_mois}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )

                if not df_filtered.empty:
                    clean_synth_rows = []
                    for _, row in df_filtered.iterrows():
                        ref_val = row.get("reference") or row.get("ref_essai") or row.get("ref") or "-"
                        clean_synth_rows.append({
                            "ID": row.get("id"),
                            "Référence": ref_val,
                            "Date": row.get("date_essai"),
                            "Client": row.get("client"),
                            "Emplacement": row.get("emplacement"),
                            "Couche": row.get("couche"),
                            "EV2 (MPa)": row.get("ev2"),
                            "Technicien": row.get("technicien")
                        })
                    st.dataframe(pd.DataFrame(clean_synth_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("Aucun essai ne correspond aux critères de filtre sélectionnés.")
            else:
                st.info("Aucun essai enregistré pour ce projet.")
        except Exception as e:
            st.warning(f"Erreur lors du chargement de la synthèse : {e}")
