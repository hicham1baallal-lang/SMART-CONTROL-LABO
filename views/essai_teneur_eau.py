import datetime
import io
import os
import pandas as pd
import streamlit as st
from fpdf import FPDF

# ==========================================
# FONCTION DE CLASSIFICATION SELON LE GTR (CLASSES A & B)
# ==========================================
def evaluer_etat_hydrique_gtr(w_mesure, w_opn, classe_gtr="Classe B", sous_classe="B2"):
    """
    Détermine l'état hydrique (th, h, m, s, ts) et la conformité selon les seuils du GTR (Classes A et B).
    """
    if w_opn is None or w_opn <= 0:
        return "N/A", "N/A", 0.0

    ratio = w_mesure / w_opn

    if "Classe A" in str(classe_gtr):
        if sous_classe == "A1":
            seuil_th, seuil_h, seuil_m, seuil_s = 1.25, 1.10, 0.90, 0.70
        elif sous_classe == "A2":
            seuil_th, seuil_h, seuil_m, seuil_s = 1.30, 1.10, 0.90, 0.70
        elif sous_classe in ["A3", "A4"]:
            seuil_th, seuil_h, seuil_m, seuil_s = 1.40, 1.20, 0.90, 0.70
        else:
            seuil_th, seuil_h, seuil_m, seuil_s = 1.25, 1.10, 0.90, 0.70
    else:  # Classe B
        if sous_classe == "B6":
            seuil_th, seuil_h, seuil_m, seuil_s = 1.30, 1.10, 0.90, 0.70
        elif sous_classe == "B2":
            seuil_th, seuil_h, seuil_m, seuil_s = 1.25, 1.10, 0.90, 0.50
        else:  # B1, B3, B4, B5
            seuil_th, seuil_h, seuil_m, seuil_s = 1.25, 1.10, 0.90, 0.60

    if ratio >= seuil_th:
        etat_hydrique = "Très Humide (th)"
        conforme = False
    elif ratio >= seuil_h:
        etat_hydrique = "Humide (h)"
        conforme = False
    elif ratio >= seuil_m:
        etat_hydrique = "Moyen (m)"
        conforme = True
    elif ratio >= seuil_s:
        etat_hydrique = "Sec (s)"
        conforme = False
    else:
        etat_hydrique = "Très Sec (ts)"
        conforme = False

    observation = "Conforme" if conforme else "Non Conforme"
    return etat_hydrique, observation, ratio


# ==========================================
# CLASSE DE GÉNÉRATION DU PV EN PDF AVEC LOGO LPEE
# ==========================================
class LPEETeneurEauPDF(FPDF):
    def header(self):
        logo_path = "logo.png.jpg"
        if os.path.exists(logo_path):
            try:
                self.image(logo_path, 10, 8, 25)
            except Exception:
                pass

        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, "LABORATOIRE PUBLIC D'ESSAIS ET D'ETUDES - LPEE", 0, 1, "C")
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 5, "CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT-BENI MELLAL (CTR-CSB)", 0, 1, "C")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "Laboratoire de Contrôle Externe - LGV CASA SUD", 0, 1, "C")
        self.ln(3)
        self.line(10, 26, 200, 26)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"CTR-CSB - Page {self.page_no()}/{{nb}}", 0, 0, "C")


def generate_pv_teneur_eau_pdf(header_info, points_data):
    pdf = LPEETeneurEauPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- TITRE DU RAPPORT ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "PROCES VERBAL", 0, 1, "C")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Détermination de la teneur en eau pondérale des matériaux par étuvage (NM EN 1097-5)", 0, 1, "C")
    pdf.ln(5)

    # N° RAPPORT
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"Rapport d'Essai n° : {header_info.get('num_rapport') or 'N/A'}", 0, 1, "R")
    pdf.ln(4)

    # --- SECTION I : IDENTIFICATION DU MATÉRIAU ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 8, " I - Identification du matériau testé", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 9)

    type_p = header_info.get('type_proctor') or 'OPN'
    
    pdf.cell(95, 7, f"  Nature du matériau : {header_info.get('nature_materiau') or ''}", 1, 0, "L")
    pdf.cell(95, 7, f"  Type de Proctor : {type_p}", 1, 1, "L")

    pdf.cell(95, 7, f"  Lieu de prélèvement : {header_info.get('lieu_prelevement') or ''}", 1, 0, "L")
    pdf.cell(95, 7, f"  Teneur en eau {type_p} (%) : {header_info.get('w_opn') or ''} %", 1, 1, "L")

    pdf.cell(95, 7, f"  Prélèvement effectué le : {header_info.get('date_prelevement') or ''}", 1, 0, "L")
    pdf.cell(95, 7, f"  PK / Section : {header_info.get('pk_zone') or ''}", 1, 1, "L")
    pdf.ln(8)

    # --- SECTION II : RÉSULTATS DES ESSAIS ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 8, " II - Résultats des essais", 1, 1, "L", fill=True)

    headers = ["Référence", "Date Prél.", "PK / Localisation", "w (%)", f"w {type_p} (%)", "w / wOPN", "État Hydrique (GTR)", "Observation"]
    widths = [22, 20, 38, 16, 20, 18, 34, 22]

    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, 1, 0, "C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    nb_samples = max(len(points_data), 1)
    row_height = 10 if nb_samples <= 4 else (8 if nb_samples <= 8 else 6)

    for p in points_data:
        w_m = float(p.get('w_mesure')) if p.get('w_mesure') is not None else 0.0
        w_o = float(p.get('w_opn')) if p.get('w_opn') is not None else 1.0
        ratio = p.get('ratio_w') if p.get('ratio_w') is not None else (w_m / w_o if w_o > 0 else 0.0)

        pdf.cell(widths[0], row_height, str(p.get("ref_ech") or ""), 1, 0, "C")
        pdf.cell(widths, row_height, str(p.get("date_prel") or p.get("created_at") or "")[:10], 1, 0, "C")
        pdf.cell(widths, row_height, str(p.get("pk") or ""), 1, 0, "C")
        pdf.cell(widths, row_height, f"{w_m:.1f}", 1, 0, "C")
        pdf.cell(widths, row_height, f"{w_o:.1f}", 1, 0, "C")
        pdf.cell(widths, row_height, f"{ratio:.2f}", 1, 0, "C")
        pdf.cell(widths[6], row_height, str(p.get("etat_hydrique") or ""), 1, 0, "C")
        pdf.cell(widths[7], row_height, str(p.get("observation") or "Conforme"), 1, 1, "C")

    if pdf.get_y() < 220:
        pdf.set_y(220)
    else:
        pdf.ln(10)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(63, 6, "Réception du client", 0, 0, "C")
    pdf.cell(64, 6, "Le Coordinateur des Essais", 0, 0, "C")
    pdf.cell(63, 6, "Le Chef de Laboratoire Externe", 0, 1, "C")

    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(63, 5, "(Nom, Visa, Date)", 0, 0, "C")
    pdf.cell(64, 5, "B. ELAMRI", 0, 0, "C")
    pdf.cell(63, 5, "H. BAALLAL", 0, 1, "C")

    return bytes(pdf.output())


# ==========================================
# MODULE VUE STREAMLIT : TENEUR EN EAU
# ==========================================
def show(supabase_client, can_edit=False, is_admin=False):
    user_name = str(st.session_state.get("user_name", st.session_state.get("username", ""))).upper()
    user_role = str(st.session_state.get("role", st.session_state.get("user_role", ""))).upper()
    
    is_baallal = ("BAALLAL" in user_name) or ("BAALLAL" in user_role)
    user_is_admin = is_admin or ("ADMIN" in user_role) or is_baallal
    user_can_edit = can_edit or user_is_admin or ("LABO" in user_role)

    st.title("💧 Essai de Teneur en Eau (NM EN 1097-5 / GTR)")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    is_editing_mode = st.session_state.get("teneur_eau_edit_mode", False)
    if is_editing_mode:
        st.warning(f"✏️ **Mode Modification** activé pour le PV : `{st.session_state.get('teneur_eau_edit_num_rapport')}`")

    tabs = st.tabs(["➕ Saisie & Modification PV", "📋 PVS / Historique, Consultation & Administration", "📊 Synthèse"])

    # ---------------------------------------------------------
    # TAB 1 : SAISIE & MODIFICATION PV
    # ---------------------------------------------------------
    with tabs[0]:
        if not user_can_edit:
            st.warning("🔒 Mode lecture seule. Vous n'avez pas les droits de modification.")

        st.subheader("1. Informations Générales du PV")
        col_h1, col_h2, col_h3 = st.columns(3)

        default_seq = st.session_state.get("edit_num_pv_seq", 371)
        default_lieu = st.session_state.get("edit_lieu", "Zone T4 Axe V3G et V6G")
        default_pk = st.session_state.get("edit_pk", "pk 8+540 à pk 8+600")
        default_w_opn = float(st.session_state.get("edit_w_opn", 12.0))

        with col_h1:
            st.markdown("**N° Rapport d'essai**")
            c_prefix, c_num = st.columns([2.5, 1.5])
            with c_prefix:
                fixed_prefix = st.text_input("Préfixe fixe", value="25/260/LGV/CS/", disabled=True, key="fixed_prefix")
            with c_num:
                num_pv_seq = st.number_input("N° PV", value=default_seq, step=1, key="num_pv_seq", disabled=not user_can_edit or is_editing_mode)

            num_rapport = f"{fixed_prefix}{num_pv_seq}"
            st.info(f"Rapport : **{num_rapport}**")

            classe_gtr = st.selectbox(
                "Classe GTR du matériau",
                ["Classe A (Sols Fins)", "Classe B (Sols Sableux et Graveleux)"],
                index=1,
                disabled=not user_can_edit
            )

        with col_h2:
            lieu_prelevement = st.text_input("Lieu de prélèvement / Zone", value=default_lieu, disabled=not user_can_edit)
            pk_zone = st.text_input("PK / Section", value=default_pk, disabled=not user_can_edit)

            if "Classe A" in classe_gtr:
                sous_classes_options = ["A1", "A2", "A3", "A4"]
                default_idx = 1
            else:
                sous_classes_options = ["B1", "B2", "B3", "B4", "B5", "B6"]
                default_idx = 1

            sous_classe_gtr = st.selectbox(
                "Sous-classe GTR",
                sous_classes_options,
                index=default_idx,
                disabled=not user_can_edit
            )

        with col_h3:
            date_prelevement = st.date_input("Date de prélèvement", value=datetime.date.today(), disabled=not user_can_edit)
            type_proctor = st.selectbox("Type de Proctor", ["OPN", "OPM"], disabled=not user_can_edit)
            w_opn = st.number_input(f"Teneur en eau {type_proctor} (%)", value=default_w_opn, step=0.1, disabled=not user_can_edit)

        nature_mat_complete = f"{classe_gtr.split()[0]} - Sous-classe {sous_classe_gtr}"

        st.markdown("---")
        st.subheader("2. Mesures & Prélèvements")

        if "teneur_eau_samples" not in st.session_state:
            st.session_state["teneur_eau_samples"] = [
                {"pk": pk_zone, "couche": 1, "m_humide": 238.1, "m_seche": 217.0, "m_tare": 38.0},
                {"pk": pk_zone, "couche": 1, "m_humide": 239.0, "m_seche": 217.5, "m_tare": 38.5},
            ]

        col_b1, col_b2, col_b3 = st.columns()
        with col_b1:
            if st.button("➕ Ajouter un échantillon", disabled=not user_can_edit):
                st.session_state["teneur_eau_samples"].append({
                    "pk": pk_zone, "couche": 1, "m_humide": 200.0, "m_seche": 180.0, "m_tare": 30.0
                })
                st.rerun()

        with col_b2:
            if st.button("➖ Supprimer le dernier", disabled=not user_can_edit or len(st.session_state["teneur_eau_samples"]) <= 1):
                st.session_state["teneur_eau_samples"].pop()
                st.rerun()

        samples_calculated = []
        to_delete_idx = None

        for i, sample in enumerate(st.session_state["teneur_eau_samples"]):
            computed_ref = f"{num_pv_seq}/{i+1}"

            with st.expander(f"📍 Échantillon N° {i+1} : {computed_ref}", expanded=True):
                c1, c2, c3, c4, c5, c6 = st.columns()
                with c1:
                    st.text_input("Référence", value=computed_ref, key=f"ref_{i}", disabled=True)
                with c2:
                    pk_item = st.text_input("PK / Localisation", value=sample["pk"], key=f"pk_{i}", disabled=not user_can_edit)
                with c3:
                    m_h = st.number_input("Masse Humide + Tare (g)", value=float(sample["m_humide"]), step=0.1, key=f"mh_{i}", disabled=not user_can_edit)
                with c4:
                    m_s = st.number_input("Masse Sèche + Tare (g)", value=float(sample["m_seche"]), step=0.1, key=f"ms_{i}", disabled=not user_can_edit)
                with c5:
                    m_t = st.number_input("Masse Tare (g)", value=float(sample["m_tare"]), step=0.1, key=f"mt_{i}", disabled=not user_can_edit)
                with c6:
                    st.markdown("&nbsp;")
                    if st.button("🗑️", key=f"del_{i}", help="Supprimer cet échantillon", disabled=not user_can_edit or len(st.session_state["teneur_eau_samples"]) <= 1):
                        to_delete_idx = i

                m_eau = m_h - m_s
                m_seche_nette = m_s - m_t
                w_mesure = (m_eau / m_seche_nette * 100) if m_seche_nette > 0 else 0.0

                etat_hydrique, obs, ratio_w = evaluer_etat_hydrique_gtr(
                    w_mesure, w_opn, classe_gtr=classe_gtr, sous_classe=sous_classe_gtr
                )

                st.caption(f"📊 **w mesurée** = `{w_mesure:.1f} %` | **Ratio w/wOPN** = `{ratio_w:.2f}` | **État Hydrique (GTR)** = `{etat_hydrique}` | **Observation** = `{obs}`")

                samples_calculated.append({
                    "ref_ech": computed_ref,
                    "date_prel": str(date_prelevement),
                    "pk": pk_item,
                    "couche": sample.get("couche", 1),
                    "m_humide": m_h,
                    "m_seche": m_s,
                    "m_tare": m_t,
                    "w_mesure": round(w_mesure, 1),
                    "w_opn": w_opn,
                    "ratio_w": round(ratio_w, 2),
                    "etat_hydrique": etat_hydrique,
                    "observation": obs
                })

        if to_delete_idx is not None:
            st.session_state["teneur_eau_samples"].pop(to_delete_idx)
            st.rerun()

        st.markdown("---")

        header_data = {
            "num_rapport": num_rapport,
            "nature_materiau": nature_mat_complete,
            "lieu_prelevement": lieu_prelevement,
            "pk_zone": pk_zone,
            "date_prelevement": str(date_prelevement),
            "type_proctor": type_proctor,
            "w_opn": w_opn
        }

        pdf_bytes = generate_pv_teneur_eau_pdf(header_data, samples_calculated)

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            st.download_button(
                label="📄 Télécharger le PV Officiel (PDF)",
                data=pdf_bytes,
                file_name=f"PV_Teneur_en_eau_{num_pv_seq}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col_act2:
            btn_label = "🔄 Mettre à jour dans Supabase" if is_editing_mode else "💾 Enregistrer dans Supabase"
            if st.button(btn_label, type="primary", use_container_width=True, disabled=not user_can_edit):
                if not supabase_client:
                    st.error("❌ Connexion Supabase indisponible.")
                else:
                    try:
                        if not is_editing_mode:
                            refs_to_check = [s["ref_ech"] for s in samples_calculated]
                            check_samples = supabase_client.table("essai_teneur_eau").select("ref_ech").in_("ref_ech", refs_to_check).execute()

                            if check_samples.data:
                                existing_refs = [item["ref_ech"] for item in check_samples.data]
                                st.error(f"⛔ **Saisie bloquée** : Les références suivantes existent déjà : **{', '.join(existing_refs)}**.")
                                st.stop()

                        supabase_client.table("pv_teneur_eau").upsert(header_data).execute()

                        if is_editing_mode:
                            supabase_client.table("essai_teneur_eau").delete().eq("num_rapport", num_rapport).execute()

                        for item in samples_calculated:
                            item_to_insert = item.copy()
                            item_to_insert["num_rapport"] = num_rapport
                            item_to_insert.pop("ratio_w", None)
                            supabase_client.table("essai_teneur_eau").insert(item_to_insert).execute()

                        st.success(f"✅ PV **{num_rapport}** enregistré/mis à jour avec succès !")

                        if is_editing_mode:
                            st.session_state["teneur_eau_edit_mode"] = False
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'enregistrement : {e}")

    # ---------------------------------------------------------
    # TAB 2 : PVS / HISTORIQUE, CONSULTATION & ADMINISTRATION
    # ---------------------------------------------------------
    with tabs:
        st.subheader("📋 PVS / Historique, Consultation & Administration")

        if not supabase_client:
            st.info("💡 Client Supabase non configuré.")
        else:
            try:
                pv_res = supabase_client.table("pv_teneur_eau").select("*").order("created_at", desc=True).execute()

                if pv_res.data:
                    pv_list = pv_res.data

                    st.markdown("#### 🔎 Recherche de PV")
                    search_query = st.text_input("Rechercher par N° de Rapport, Lieu ou PK :", "").strip().lower()

                    if search_query:
                        filtered_pv_list = [
                            pv for pv in pv_list
                            if search_query in str(pv.get("num_rapport") or "").lower()
                            or search_query in str(pv.get("lieu_prelevement") or "").lower()
                            or search_query in str(pv.get("pk_zone") or "").lower()
                        ]
                    else:
                        filtered_pv_list = pv_list

                    if not filtered_pv_list:
                        st.warning("Aucun PV ne correspond à votre recherche.")
                    else:
                        pv_options = {pv["num_rapport"]: pv for pv in filtered_pv_list if pv.get("num_rapport")}

                        if pv_options:
                            selected_num_rapport = st.selectbox(
                                "Sélectionner un PV dans la liste :",
                                options=list(pv_options.keys())
                            )

                            if selected_num_rapport:
                                selected_pv = pv_options[selected_num_rapport]

                                samples_res = supabase_client.table("essai_teneur_eau") \
                                    .select("*") \
                                    .eq("num_rapport", selected_num_rapport) \
                                    .order("ref_ech", desc=False) \
                                    .execute()

                                samples_data = samples_res.data if samples_res.data else []

                                with st.expander(f"📄 Détails du PV : {selected_num_rapport}", expanded=True):
                                    c_info1, c_info2 = st.columns(2)
                                    with c_info1:
                                        st.markdown(f"**Nature du matériau :** {selected_pv.get('nature_materiau') or 'N/A'}")
                                        st.markdown(f"**Lieu de prélèvement :** {selected_pv.get('lieu_prelevement') or 'N/A'}")
                                        st.markdown(f"**PK / Section :** {selected_pv.get('pk_zone') or 'N/A'}")
                                    with c_info2:
                                        st.markdown(f"**Date de prélèvement :** {selected_pv.get('date_prelevement') or 'N/A'}")
                                        st.markdown(f"**Type de Proctor :** {selected_pv.get('type_proctor') or 'OPN'}")
                                        st.markdown(f"**w Proctor (%) :** {selected_pv.get('w_opn') or 'N/A'} %")

                                    st.markdown("#### Liste des échantillons :")
                                    if samples_data:
                                        df_samples = pd.DataFrame(samples_data)
                                        display_cols = [c for c in ["ref_ech", "pk", "m_humide", "m_seche", "m_tare", "w_mesure", "w_opn", "etat_hydrique", "observation"] if c in df_samples.columns]
                                        st.dataframe(df_samples[display_cols], use_container_width=True)
                                    else:
                                        st.warning("Aucun échantillon rattaché à ce PV.")

                                col_act1, col_act2, col_act3 = st.columns()

                                with col_act1:
                                    pdf_reprint = generate_pv_teneur_eau_pdf(selected_pv, samples_data)
                                    st.download_button(
                                        label="📥 Télécharger en PDF",
                                        data=pdf_reprint,
                                        file_name=f"PV_Teneur_en_eau_{selected_num_rapport.replace('/', '_')}.pdf",
                                        mime="application/pdf",
                                        type="primary",
                                        use_container_width=True
                                    )

                                with col_act2:
                                    can_modify_baallal = user_is_admin or ("BAALLAL" in user_name) or ("BAALLAL" in user_role)
                                    if st.button("✏️ Modifier ce PV", disabled=not can_modify_baallal, use_container_width=True, help="Modification réservée aux administrateurs"):
                                        try:
                                            seq_val = int(selected_num_rapport.split('/')[-1])
                                        except Exception:
                                            seq_val = 371

                                        st.session_state["teneur_eau_edit_mode"] = True
                                        st.session_state["teneur_eau_edit_num_rapport"] = selected_num_rapport
                                        st.session_state["edit_num_pv_seq"] = seq_val
                                        st.session_state["edit_lieu"] = selected_pv.get("lieu_prelevement", "")
                                        st.session_state["edit_pk"] = selected_pv.get("pk_zone", "")
                                        st.session_state["edit_w_opn"] = selected_pv.get("w_opn", 12.0)

                                        if samples_data:
                                            st.session_state["teneur_eau_samples"] = [
                                                {
                                                    "pk": s.get("pk") or selected_pv.get("pk_zone", ""),
                                                    "couche": s.get("couche") or 1,
                                                    "m_humide": s.get("m_humide") or 200.0,
                                                    "m_seche": s.get("m_seche") or 180.0,
                                                    "m_tare": s.get("m_tare") or 30.0
                                                } for s in samples_data
                                            ]
                                        st.success("PV chargé dans l'onglet 'Saisie & Modification'.")
                                        st.rerun()

                                with col_act3:
                                    can_delete_baallal = user_is_admin or ("BAALLAL" in user_name) or ("BAALLAL" in user_role)
                                    
                                    confirm_key = f"confirm_delete_{selected_num_rapport.replace('/', '_')}"
                                    is_confirming = st.session_state.get(confirm_key, False)

                                    if not is_confirming:
                                        if st.button("🗑️ Supprimer ce PV", disabled=not can_delete_baallal, use_container_width=True, help="Supprimer définitivement ce PV"):
                                            st.session_state[confirm_key] = True
                                            st.rerun()
                                    else:
                                        st.warning(f"⚠️ Confirmer la suppression de {selected_num_rapport} ?")
                                        c_yes, c_no = st.columns(2)
                                        with c_yes:
                                            if st.button("✅ Oui", key=f"yes_{selected_num_rapport.replace('/', '_')}", use_container_width=True):
                                                try:
                                                    supabase_client.table("essai_teneur_eau").delete().eq("num_rapport", selected_num_rapport).execute()
                                                    supabase_client.table("pv_teneur_eau").delete().eq("num_rapport", selected_num_rapport).execute()
                                                    st.session_state[confirm_key] = False
                                                    st.success(f"✅ PV `{selected_num_rapport}` supprimé.")
                                                    st.rerun()
                                                except Exception as err:
                                                    st.error(f"Erreur : {err}")
                                        with c_no:
                                            if st.button("❌ Non", key=f"no_{selected_num_rapport.replace('/', '_')}", use_container_width=True):
                                                st.session_state[confirm_key] = False
                                                st.rerun()

                else:
                    st.info("Aucun PV enregistré dans la base de données.")

            except Exception as e:
                st.error(f"❌ Erreur lors de la récupération des données : {e}")

        st.markdown("---")
        st.subheader("📋 Base de données brute des mesures (essai_teneur_eau)")
        if supabase_client:
            try:
                res = supabase_client.table("essai_teneur_eau").select("*").order("created_at", desc=True).execute()
                if res.data:
                    df = pd.DataFrame(res.data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Aucune donnée d'échantillon enregistrée.")
            except Exception as e:
                st.error(f"Erreur de chargement de la table brute : {e}")

    # ---------------------------------------------------------
    # TAB 3 : SYNTHÈSE + EXPORT EXCEL
    # ---------------------------------------------------------
    with tabs:
        st.subheader("📊 Synthèse des Essais de Teneur en Eau")

        if not supabase_client:
            st.info("💡 Client Supabase non configuré.")
        else:
            try:
                res_synth = supabase_client.table("essai_teneur_eau").select("*").execute()
                res_pv = supabase_client.table("pv_teneur_eau").select("*").execute()

                if res_synth.data:
                    df_synth = pd.DataFrame(res_synth.data)
                    df_pv = pd.DataFrame(res_pv.data) if res_pv.data else pd.DataFrame()

                    if not df_pv.empty and "num_rapport" in df_synth.columns and "num_rapport" in df_pv.columns:
                        df_merged = pd.merge(df_synth, df_pv[["num_rapport", "lieu_prelevement", "nature_materiau"]], on="num_rapport", how="left")
                    else:
                        df_merged = df_synth.copy()
                        if "lieu_prelevement" not in df_merged.columns:
                            df_merged["lieu_prelevement"] = "N/A"
                        if "nature_materiau" not in df_merged.columns:
                            df_merged["nature_materiau"] = "N/A"

                    date_col = "date_prel" if "date_prel" in df_merged.columns else "created_at"
                    if date_col in df_merged.columns:
                        df_merged["mois"] = pd.to_datetime(df_merged[date_col], errors="coerce").dt.to_period("M").astype(str)
                    else:
                        df_merged["mois"] = "N/A"

                    st.markdown("#### 🎛️ Filtres de Synthèse")
                    f_col1, f_col2, f_col3 = st.columns(3)

                    mois_options = ["Tous"] + sorted([str(m) for m in df_merged["mois"].dropna().unique().tolist() if m != "nan" and m != "NaT"])
                    with f_col1:
                        filtre_mois = st.selectbox("Période (Mois)", mois_options)

                    emplacement_options = ["Tous"] + sorted([str(e) for e in df_merged["lieu_prelevement"].dropna().unique().tolist() if e != "nan"])
                    with f_col2:
                        filtre_emplacement = st.selectbox("Emplacement", emplacement_options)

                    couche_options = ["Tous"] + sorted([str(c) for c in df_merged["couche"].dropna().unique().tolist() if c != "nan"]) if "couche" in df_merged.columns else ["Tous"]
                    with f_col3:
                        filtre_couche = st.selectbox("Type de couche", couche_options)

                    df_filtered = df_merged.copy()
                    if filtre_mois != "Tous":
                        df_filtered = df_filtered[df_filtered["mois"] == filtre_mois]
                    if filtre_emplacement != "Tous":
                        df_filtered = df_filtered[df_filtered["lieu_prelevement"] == filtre_emplacement]
                    if filtre_couche != "Tous":
                        df_filtered = df_filtered[df_filtered["couche"].astype(str) == filtre_couche]

                    st.markdown("---")
                    
                    tot_essais = len(df_filtered)
                    conformes = len(df_filtered[df_filtered["observation"] == "Conforme"]) if "observation" in df_filtered.columns else 0
                    taux_conformite = (conformes / tot_essais * 100) if tot_essais > 0 else 0

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Échantillons Filtrés", tot_essais)
                    m2.metric("Échantillons Conformes", conformes)
                    m3.metric("Taux de Conformité", f"{taux_conformite:.1f}%")

                    st.markdown("#### 📋 Données filtrées")
                    st.dataframe(df_filtered, use_container_width=True)

                    # --- EXPORT EXCEL ---
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df_filtered.to_excel(writer, sheet_name='Synthese_Teneur_Eau', index=False)
                    excel_buffer.seek(0)

                    st.download_button(
                        label="📥 Télécharger la synthèse en Excel (.xlsx)",
                        data=excel_buffer,
                        file_name=f"synthese_teneur_eau_{datetime.date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )

                else:
                    st.info("Aucune donnée disponible pour la synthèse.")

            except Exception as e:
                st.error(f"❌ Erreur lors du chargement de la synthèse : {e}")
