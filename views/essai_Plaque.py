import io
import os
from datetime import date, datetime
import pandas as pd
import streamlit as st

# Import Supabase & Audit log
from audit_log import enregistrer_modification
import projets_config

# Import pour la génération de PDF (ReportLab)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Import pour l'export Excel (OpenPyXL)
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# Variable globale pour la connexion Supabase
supabase = None


@st.cache_data(ttl=300)
def charger_essais_plaque(projet_id):
    """Charge les 30 derniers essais de plaque pour optimiser le temps de réponse et éviter le timeout 504."""
    if not supabase:
        return []
    try:
        response = (
            supabase.table("essai_plaque")
            .select("id, reference, date_essai, client, projet, emplacement, pk_profil, couche, nature_materiau, z1, z2, ev1, ev2, k_ratio, technicien, observations, points_mesure")
            .eq("projet_id", projet_id)
            .order("id", desc=True)
            .limit(30)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"Erreur lors du chargement des essais à la plaque : {e}")
        return []


def evaluer_conformite_couche(couche, ev2_val):
    """Vérifie la conformité des valeurs EV2 selon la couche sélectionnée."""
    conforme = True
    motif = []
    
    regles = {
        "Sous-couche et Couche de forme ferroviaire (LGV)": 80.0,
        "Remblais contigus aux Ouvrages d'Art (PRO)": 80.0,
        "Arase des terrassements / PST": 50.0,
        "Corps de remblai courant (avant PST)": 30.0,
        "Remblais de fouilles d'ouvrages d'art": 80.0,
        "Couche de forme des rétablissements / accès": 50.0,
        "Plateforme support d'étaiements / cintres": 80.0,
    }

    if couche in regles:
        seuil = regles[couche]
        if ev2_val < seuil:
            conforme = False
            motif.append(f"EV2 = {ev2_val} MPa < {seuil} MPa requis")

    return "Résultats conformes" if conforme else f"Résultats non conformes ({', '.join(motif)})"


def generer_pdf_pv(essai):
    """Génère le Procès-Verbal officiel au format PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=12, textColor=colors.HexColor('#1f4e78'), alignment=1, spaceAfter=10)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#595959'), alignment=1, spaceAfter=12)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1f4e78'), spaceBefore=10, spaceAfter=4)
    normal_style = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#262626'))
    bold_style = ParagraphStyle('BoldText', parent=normal_style, fontName='Helvetica-Bold')

    # En-tête avec Logo
    logo_path = "logo.png.jpg"
    header_text = (
        "<b>LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES (LPEE)</b><br/>"
        "<font size=8.5 color='#595959'>CENTRE TECHNIQUE REGIONAL DE CASABLANCA - SETTAT</font>"
    )
    
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=45, height=45)
            header_table = Table([[img, Paragraph(header_text, bold_style)]], colWidths=[55, 470])
            header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
            elements.append(header_table)
        except Exception:
            elements.append(Paragraph(header_text, bold_style))
    else:
        elements.append(Paragraph(header_text, bold_style))

    elements.append(Spacer(1, 10))

    # Informations du projet
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
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_infos)
    elements.append(Spacer(1, 10))

    # Points de mesure
    elements.append(Paragraph("Détail des Points de Mesure et Résultats (NF P 94-117-1)", section_style))
    points = essai.get('points_mesure', [])
    if not points:
        points = [{"z1": essai.get('z1', 0.53), "z2": essai.get('z2', 0.52), "pk_point": essai.get('pk_profil', '-')}]

    table_pts_data = [["Point / PK", "Z1 1er chrg (mm)", "Z2 2ème chrg (mm)", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]]
    for idx, pt in enumerate(points):
        z1_v = float(pt.get("z1", 0.53))
        z2_v = float(pt.get("z2", 0.52))
        ev1_v = round(112.5 / (z1_v * 2), 2) if z1_v > 0 else 0.0
        ev2_v = round(90.0 / (z2_v * 2), 2) if z2_v > 0 else 0.0
        k_v = round(ev2_v / ev1_v, 2) if ev1_v > 0 else 0.0
        
        table_pts_data.append([
            str(pt.get("pk_point", f"P{idx+1}")),
            f"{z1_v:.2f}", f"{z2_v:.2f}", f"{ev1_v:.2f}", f"{ev2_v:.2f}", f"{k_v:.2f}"
        ])

    t_pts = Table(table_pts_data, colWidths=[105, 90, 90, 80, 80, 80])
    t_pts.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f4e78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#bfbfbf')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_pts)
    elements.append(Spacer(1, 10))

    # Conclusion / Commentaires
    elements.append(Paragraph("Commentaire", section_style))
    commentaire_auto = evaluer_conformite_couche(essai.get('couche', ''), float(essai.get('ev2', 0)))
    t_obs = Table([[Paragraph(commentaire_auto, normal_style)]], colWidths=[525])
    t_obs.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#d9d9d9')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_obs)
    elements.append(Spacer(1, 15))

    # Signatures
    sig_style = ParagraphStyle('SigStyle', parent=normal_style, alignment=1)
    data_sig = [[
        Paragraph("<b>Responsable d'essai</b><br/><br/>O. IKKEN", sig_style),
        Paragraph("<b>Chef du laboratoire</b><br/><br/>H. BAALLAL", sig_style)
    ]]
    t_sig = Table(data_sig, colWidths=[262.5, 262.5])
    elements.append(t_sig)

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("PROCÈS-VERBAL D'ESSAI À LA PLAQUE (NF P 94-117-1)", title_style))
    elements.append(Paragraph(f"Référence : <b>{essai.get('reference', '-')}</b> | Date : {essai.get('date_essai', '-')}", subtitle_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generer_excel_synthese(df, mois_str, empl_str, couche_str, nom_projet):
    """Génère le fichier de synthèse Excel mis en forme."""
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Synthèse Plaque"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=13, bold=True, color="1F4E78")
    normal_font = Font(name="Calibri", size=10)
    thin_border = Border(left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
                         top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'))

    ws['A1'] = "LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES — CENTRE TECHNIQUE RÉGIONAL"
    ws['A1'].font = title_font
    ws.merge_cells('A1:G1')
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ["Date Essai", "Couche", "Emplacement", "PK / Profil", "EV1 (MPa)", "EV2 (MPa)", "K (EV2/EV1)"]
    for col_num, header_title in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num, value=header_title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    row_idx = 6
    for _, row in df.iterrows():
        ws.cell(row=row_idx, column=1, value=str(row.get('date_essai', ''))).alignment = Alignment(horizontal='center')
        ws.cell(row=row_idx, column=2, value=str(row.get('couche', '')))
        ws.cell(row=row_idx, column=3, value=str(row.get('emplacement', '')))
        ws.cell(row=row_idx, column=4, value=str(row.get('pk_profil', ''))).alignment = Alignment(horizontal='center')
        ws.cell(row=row_idx, column=5, value=float(row.get('ev1', 0) or 0)).number_format = '#,##0.00'
        ws.cell(row=row_idx, column=6, value=float(row.get('ev2', 0) or 0)).number_format = '#,##0.00'
        ws.cell(row=row_idx, column=7, value=float(row.get('k_ratio', 0) or 0)).number_format = '#,##0.00'
        
        for c in range(1, 8):
            ws.cell(row=row_idx, column=c).font = normal_font
            ws.cell(row=row_idx, column=c).border = thin_border
        row_idx += 1

    wb.save(output)
    output.seek(0)
    return output.getvalue()


def show(supabase_client):
    """Fonction d'affichage principale appelée par Streamlit."""
    global supabase
    supabase = supabase_client

    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")

    user_raw = st.session_state.get("username") or st.session_state.get("user") or "Agent LPEE"
    if isinstance(user_raw, dict):
        user_raw = user_raw.get("email") or user_raw.get("name") or "Agent LPEE"
    current_user = str(user_raw).upper()

    user_info_projet = st.session_state.get("user") or {}
    projet_id_actif = projets_config.projet_actif(user_info_projet)
    if not projet_id_actif:
        st.error("⚠️ Aucun projet autorisé. Veuillez contacter un administrateur.")
        return

    st.caption(f"📁 Projet actif : **{projets_config.nom_projet(projet_id_actif)}**")

    tab_saisie, tab_pv, tab_synthese = st.tabs(["📝 Saisie & Historique", "📄 PV / PDF", "📊 Synthèse"])

    # -------------------------------------------------------------
    # TAB 1: SAISIE & HISTORIQUE
    # -------------------------------------------------------------
    with tab_saisie:
        editing_item = st.session_state.get("edit_plaque_item", None)

        if editing_item:
            st.info(f"✏️ **Mode Modification** - Essai ID #{editing_item['id']}")
            default_ref = editing_item.get("reference", "260/26/PLQ/01")
            default_date = datetime.strptime(editing_item["date_essai"], "%Y-%m-%d").date() if isinstance(editing_item.get("date_essai"), str) else date.today()
            default_client = editing_item.get("client", "TGCC")
            default_projet = editing_item.get("projet", "LGV CASA SUD")
            default_empl = editing_item.get("emplacement", "")
            default_pk = editing_item.get("pk_profil", "")
            default_couche = editing_item.get("couche", "Sous-couche et Couche de forme ferroviaire (LGV)")
            default_mat = editing_item.get("nature_materiau", "")
            default_tech = editing_item.get("technicien", current_user)
            default_obs = editing_item.get("observations", "")
            default_points = editing_item.get("points_mesure") or [{"z1": float(editing_item.get("z1", 0.53)), "z2": float(editing_item.get("z2", 0.52)), "pk_point": default_pk}]
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

        st.subheader("1. Informations Générales")
        col0, col1, col2 = st.columns(3)
        with col0:
            reference = st.text_input("Référence de l'essai", value=default_ref)
        with col1:
            date_essai = st.date_input("Date de l'essai", value=default_date)
            client = st.text_input("Client", value=default_client)
            projet = st.text_input("Chantier / Projet", value=default_projet)
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
            couche = st.selectbox("Couche / Ouvrage testé", couche_options, index=couche_idx)
            emplacement = st.text_input("Emplacement / Zone", value=default_empl)
            pk_profil = st.text_input("PK / Profil Global", value=default_pk)

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            nature_materiau = st.text_input("Nature du matériau", value=default_mat)
        with col_m2:
            technicien = st.text_input("Technicien LPEE", value=default_tech)

        st.markdown("---")
        st.subheader("2. Points de Mesure")

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
            st.markdown(f"**Point N° {i+1}**")
            p_col0, p_col1, p_col2 = st.columns(3)
            default_pk_p = default_points[i].get("pk_point", default_pk) if i < len(default_points) else default_pk
            default_z1_v = default_points[i]["z1"] if i < len(default_points) else 0.53
            default_z2_v = default_points[i]["z2"] if i < len(default_points) else 0.52

            with p_col0:
                pk_p = st.text_input(f"PK/Profil [P{i+1}]", value=str(default_pk_p), key=f"pk_pt_{i}")
            with p_col1:
                z1_p = st.number_input(f"Z1 - 1er chrg (mm) [P{i+1}]", min_value=0.01, max_value=10.0, value=float(default_z1_v), step=0.01, format="%.2f", key=f"z1_pt_{i}")
            with p_col2:
                z2_p = st.number_input(f"Z2 - 2ème chrg (mm) [P{i+1}]", min_value=0.01, max_value=10.0, value=float(default_z2_v), step=0.01, format="%.2f", key=f"z2_pt_{i}")

            points_data.append({"z1": z1_p, "z2": z2_p, "pk_point": pk_p})

        st.markdown("---")
        st.subheader("📈 Résultats Calculés Automatiquement")

        points_results = []
        commentaires_points = []
        for i, p in enumerate(points_data):
            z1_v, z2_v = p["z1"], p["z2"]
            ev1_i = round(112.5 / (z1_v * 2), 2) if z1_v > 0 else 0.0
            ev2_i = round(90.0 / (z2_v * 2), 2) if z2_v > 0 else 0.0
            k_ratio_i = round(ev2_i / ev1_i, 2) if ev1_i > 0 else 0.0

            commentaires_points.append(f"Point {p['pk_point']} : EV2 = {ev2_i} MPa, K = {k_ratio_i}.")
            points_results.append({"ev1": ev1_i, "ev2": ev2_i, "k_ratio": k_ratio_i})

            r_col1, r_col2, r_col3 = st.columns(3)
            r_col1.metric(f"EV1 [Point {i+1}]", f"{ev1_i:.2f} MPa")
            r_col2.metric(f"EV2 [Point {i+1}]", f"{ev2_i:.2f} MPa")
            r_col3.metric(f"Coefficient K [Point {i+1}]", f"{k_ratio_i:.2f}")

        ev1_main = points_results[0]["ev1"]
        ev2_main = points_results[0]["ev2"]
        k_main = points_results[0]["k_ratio"]

        if not default_obs:
            default_obs = "\n".join(commentaires_points)

        observations = st.text_area("Commentaire / Remarques", value=default_obs)

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            label_btn = "🔄 Mettre à jour l'essai" if editing_item else "💾 Enregistrer l'essai"
            if st.button(label_btn, type="primary", use_container_width=True):
                safe_payload = {
                    "reference": str(reference),
                    "date_essai": str(date_essai),
                    "client": str(client),
                    "projet": str(projet),
                    "emplacement": str(emplacement),
                    "pk_profil": str(pk_profil),
                    "couche": str(couche),
                    "nature_materiau": str(nature_materiau),
                    "z1": float(points_data[0]["z1"]),
                    "z2": float(points_data[0]["z2"]),
                    "ev1": float(ev1_main),
                    "ev2": float(ev2_main),
                    "k_ratio": float(k_main),
                    "technicien": str(technicien),
                    "observations": str(observations),
                    "projet_id": projet_id_actif,
                    "points_mesure": [
                        {"z1": float(pt["z1"]), "z2": float(pt["z2"]), "pk_point": str(pt["pk_point"])}
                        for pt in points_data
                    ]
                }

                try:
                    if editing_item:
                        anciennes_vals = {k: editing_item.get(k) for k in safe_payload}
                        supabase.table("essai_plaque").update(safe_payload).eq("id", editing_item["id"]).execute()
                        try:
                            enregistrer_modification(supabase, "essai_plaque", editing_item["id"], "MODIFICATION", anciennes_vals, safe_payload)
                        except Exception:
                            pass
                        st.success(f"✅ Essai #{editing_item['id']} mis à jour !")
                        st.session_state["edit_plaque_item"] = None
                    else:
                        supabase.table("essai_plaque").insert(safe_payload).execute()
                        st.success("✅ Essai enregistré avec succès !")
                    
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement : {e}")

        with btn_col2:
            if editing_item and st.button("❌ Annuler", use_container_width=True):
                st.session_state["edit_plaque_item"] = None
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Historique des Essais Enregistrés")
        data_plaque = charger_essais_plaque(projet_id_actif)
        if data_plaque:
            df_hist = pd.DataFrame(data_plaque)[["id", "reference", "date_essai", "client", "emplacement", "couche", "ev2", "technicien"]]
            df_hist.columns = ["ID", "Référence", "Date", "Client", "Emplacement", "Couche", "EV2 (MPa)", "Technicien"]
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun essai enregistré pour ce projet.")

    # -------------------------------------------------------------
    # TAB 2: PV PDF
    # -------------------------------------------------------------
    with tab_pv:
        st.subheader("📄 Génération de PV Officiel PDF")
        data_plaque = charger_essais_plaque(projet_id_actif)
        if data_plaque:
            opts = {f"ID #{item['id']} - Réf: {item.get('reference', '-')} ({item.get('date_essai', '')})": item for item in data_plaque}
            choix_item = st.selectbox("Sélectionner l'essai :", options=list(opts.keys()))
            essai_sel = opts[choix_item]

            pdf_bytes = generer_pdf_pv(essai_sel)
            nom_pdf = f"PV_Essai_Plaque_{str(essai_sel.get('reference', essai_sel['id'])).replace('/', '_')}.pdf"
            
            st.download_button(
                label="📥 Télécharger le PV (PDF)",
                data=pdf_bytes,
                file_name=nom_pdf,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        else:
            st.info("Aucun essai disponible pour la génération de PV.")

    # -------------------------------------------------------------
    # TAB 3: SYNTHÈSE EXCEL
    # -------------------------------------------------------------
    with tab_synthese:
        st.subheader("📊 Synthèse & Filtres Avancés")
        data_plaque = charger_essais_plaque(projet_id_actif)
        if data_plaque:
            df_synth = pd.DataFrame(data_plaque)
            df_synth['date_datetime'] = pd.to_datetime(df_synth['date_essai'], errors='coerce')
            df_synth['mois'] = df_synth['date_datetime'].dt.strftime('%Y-%m')

            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                choix_mois = st.selectbox("Période (Mois)", ["Tous"] + sorted([m for m in df_synth['mois'].dropna().unique()], reverse=True))
            with f_col2:
                choix_empl = st.selectbox("Emplacement", ["Tous"] + sorted([str(e) for e in df_synth['emplacement'].dropna().unique()]))
            with f_col3:
                choix_couche = st.selectbox("Type de couche", ["Tous"] + sorted([str(c) for c in df_synth['couche'].dropna().unique()]))

            df_filt = df_synth.copy()
            if choix_mois != "Tous":
                df_filt = df_filt[df_filt['mois'] == choix_mois]
            if choix_empl != "Tous":
                df_filt = df_filt[df_filt['emplacement'] == choix_empl]
            if choix_couche != "Tous":
                df_filt = df_filt[df_filt['couche'] == choix_couche]

            if not df_filt.empty:
                nom_p = projets_config.nom_projet(projet_id_actif)
                excel_bytes = generer_excel_synthese(df_filt, choix_mois, choix_empl, choix_couche, nom_p)
                st.download_button(
                    label="📥 Télécharger la Synthèse (Excel)",
                    data=excel_bytes,
                    file_name=f"Synthese_Essais_Plaque_{choix_mois}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
                st.dataframe(df_filt[["reference", "date_essai", "emplacement", "couche", "ev1", "ev2", "k_ratio"]], use_container_width=True, hide_index=True)
            else:
                st.info("Aucun essai ne correspond aux critères de recherche.")
        else:
            st.info("Aucun essai enregistré.")
