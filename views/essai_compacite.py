import datetime
import pandas as pd
import streamlit as st
from fpdf import FPDF

# ==========================================
# UTILITAIRE NETTOYAGE TEXTE UTF-8 POUR FPDF (HELVETICA)
# ==========================================
def clean_text(text):
    """
    Nettoie et convertit une chaîne UTF-8 pour la rendre compatible avec le codage latin-1 de FPDF.
    """
    if text is None:
        return ""
    text_str = str(text)
    text_str = text_str.replace("–", "-").replace("—", "-").replace("’", "'").replace("³", "3")
    return text_str.encode("latin-1", "replace").decode("latin-1")


# ==========================================
# TABLEAU DE RÉFÉRENCE MATÉRIAUX & EXIGENCES CCTP
# ==========================================
REFERENTIEL_MATERIAUX = {
    "GNT 0/31,5 - sous-couche LGV": {"exigence_str": "q1", "exigence_mc": 98.0, "exigence_fc": 95.0},
    "GNT / Grave 0/60 - couche de forme LGV": {"exigence_str": "q3", "exigence_mc": 98.5, "exigence_fc": 96.0},
    "GNT - PST": {"exigence_str": "95 % OPM", "exigence_mc": 95.0, "exigence_fc": 95.0},
    "GNT / matériaux Type 1 ou Type 2 - remblais contigus OA": {"exigence_str": "q4 (zones courantes) / q3 (partie sup.)", "exigence_mc": 98.5, "exigence_fc": 96.0},
    "Sols de remblai courant": {"exigence_str": "q4", "exigence_mc": 95.0, "exigence_fc": 92.0},
    "Sols en place - assise des remblais": {"exigence_str": "95 % OPM", "exigence_mc": 95.0, "exigence_fc": 95.0},
    "Sols réutilisables / D2-D3 - remblais de fouilles": {"exigence_str": ">= 95 % OPM", "exigence_mc": 95.0, "exigence_fc": 95.0},
    "GNA/GNB 0/31,5 - couche de base": {"exigence_str": ">= 98 % OPM", "exigence_mc": 98.0, "exigence_fc": 98.0},
    "GNF 0/40 - couche de fondation": {"exigence_str": "Critère stat : 95% >= 95% OPM & 100% >= 95% OPM", "exigence_mc": 95.0, "exigence_fc": 95.0},
    "Autre / Saisie Personnalisée": {"exigence_str": "Personnalisée", "exigence_mc": 95.0, "exigence_fc": 92.0}
}


# ==========================================
# FONCTION DE CALCUL ET ÉVALUATION COMPACITÉ
# ==========================================
def evaluer_compacite(density_seche, density_ref, type_mesure="mc", exigence_mc=95.0, exigence_fc=92.0):
    if density_ref <= 0:
        return 0.0, "N/A"

    ic = (density_seche / density_ref) * 100.0
    seuil = exigence_mc if type_mesure == "mc" else exigence_fc
    conforme = ic >= seuil
    
    observation = "Conforme" if conforme else "Non Conforme"
    return round(ic, 1), observation


# ==========================================
# CLASSE DE GÉNÉRATION DU PV EN PDF (FORMAT LPEE - OPTIMISÉ A4)
# ==========================================
class LPEECompacitePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 5, clean_text("LABORATOIRE PUBLIC D'ESSAIS ET D'ETUDES - LPEE"), 0, 1, "C")
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 4, clean_text("CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT-BENI MELLAL (CTR-CSB)"), 0, 1, "C")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 4, clean_text("Laboratoire de Contrôle Externe - LGV CASA SUD"), 0, 1, "C")
        self.ln(2)
        self.line(10, 24, 200, 24)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, clean_text(f"CTR-CSB - Page {self.page_no()}/{{nb}}"), 0, 0, "C")


def generate_pv_compacite_pdf(header_info, points_data):
    pdf = LPEECompacitePDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- TITRE DU RAPPORT ---
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, clean_text("PROCES VERBAL DE CONTROLE DE COMPACITE"), 0, 1, "C")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, clean_text("Références de normes : NF P 94-093 / NF P 94-061-2"), 0, 1, "C")
    pdf.ln(3)

    # N° RAPPORT & DOSSIER
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(100, 5, clean_text(f"N° Dossier : {header_info.get('num_dossier', 'N/A')}"), 0, 0, "L")
    pdf.cell(90, 5, clean_text(f"Rapport d'Essai n° : {header_info.get('num_rapport', 'N/A')}"), 0, 1, "R")
    pdf.ln(3)

    # --- SECTION I : IDENTIFICATION DU PROJET & DU MATÉRIAU ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(190, 7, clean_text(" I - Informations Générales & Matériau"), 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 8.5)

    pdf.cell(95, 6, clean_text(f"  Client : {header_info.get('client', 'TGCC')}"), 1, 0, "L")
    pdf.cell(95, 6, clean_text(f"  Date du prélèvement : {header_info.get('date_prelevement', '')}"), 1, 1, "L")

    pdf.cell(190, 6, clean_text(f"  Lieu de prélèvement : {header_info.get('lieu_prelevement', '')}"), 1, 1, "L")

    type_mat_str = clean_text(header_info.get('type_materiau', '')[:48])
    pdf.cell(95, 6, f"  Type de materiau : {type_mat_str}", 1, 0, "L")
    pdf.cell(95, 6, clean_text(f"  Densité Proctor OPN/OPM : {header_info.get('densite_opn', '2.09')} t/m3"), 1, 1, "L")

    pdf.cell(95, 6, clean_text(f"  Teneur en eau opt. : {header_info.get('w_opn', '6.3')} %"), 1, 0, "L")
    exig_str = clean_text(header_info.get('exigence_str', ''))
    pdf.cell(95, 6, clean_text(f"  Exigence CCTP : {exig_str} (mc > {header_info.get('exigence_mc', 95)}% | fc > {header_info.get('exigence_fc', 92)}%)"), 1, 1, "L")
    pdf.ln(6)

    # --- SECTION II : RÉSULTATS DES ESSAIS DE COMPACITÉ ---
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(190, 7, clean_text(" II - Résultats des Essais de Compacité"), 1, 1, "L", fill=True)

    headers = ["Réf", "Désignation", "D. Sèche", "D. Réf", "w (%)", "% > 20mm", "IC (%)", "Commentaire"]
    widths = [10, 68, 18, 22, 16, 18, 16, 22]

    pdf.set_font("Helvetica", "B", 7.5)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 7, clean_text(h), 1, 0, "C")
    pdf.ln()

    # Corps du tableau avec hauteur adaptable
    pdf.set_font("Helvetica", "", 7.5)
    nb_samples = max(len(points_data), 1)
    row_height = 8 if nb_samples <= 6 else 6.5

    for p in points_data:
        desig = f"{p.get('designation', '')} ({p.get('type_mesure', 'mc')})"
        
        pdf.cell(widths[0], row_height, clean_text(str(p.get("ref_num", ""))), 1, 0, "C")
        pdf.cell(widths[1], row_height, clean_text(desig[:45]), 1, 0, "L")
        pdf.cell(widths[2], row_height, f"{float(p.get('densite_seche', 0.0)):.3f}", 1, 0, "C")
        pdf.cell(widths[3], row_height, f"{float(p.get('densite_ref', 0.0)):.3f}", 1, 0, "C")
        pdf.cell(widths[4], row_height, f"{float(p.get('w_mesure', 0.0)):.1f}%", 1, 0, "C")
        pdf.cell(widths[5], row_height, f"{float(p.get('refus_20mm', 0.0)):.1f}", 1, 0, "C")
        pdf.cell(widths[6], row_height, f"{float(p.get('ic', 0.0)):.1f}%", 1, 0, "C")
        pdf.cell(widths[7], row_height, clean_text(str(p.get("observation", "Conforme"))), 1, 1, "C")

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.cell(0, 4, clean_text("Légende : fc = fond de couche de la couche compactée | mc = moyenne sur toute l'épaisseur de la couche compactée"), 0, 1, "L")

    # --- BLOC SIGNATURES ---
    if pdf.get_y() < 220:
        pdf.set_y(220)
    else:
        pdf.ln(8)

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(63, 5, clean_text("REÇU PAR LE CLIENT"), 0, 0, "C")
    pdf.cell(64, 5, clean_text("LE COORDINATEUR DES ESSAIS"), 0, 0, "C")
    pdf.cell(63, 5, clean_text("LE CHEF DU LABORATOIRE"), 0, 1, "C")

    pdf.set_font("Helvetica", "I", 8.5)
    pdf.cell(63, 5, clean_text("Nom: TGCC"), 0, 0, "C")
    pdf.cell(64, 5, clean_text("Nom: O. IKEN"), 0, 0, "C")
    pdf.cell(63, 5, clean_text("Nom: H. BAALLAL"), 0, 1, "C")

    pdf.cell(63, 4, clean_text("Visa:"), 0, 0, "C")
    pdf.cell(64, 4, clean_text("Visa:"), 0, 0, "C")
    pdf.cell(63, 4, clean_text("Visa:"), 0, 1, "C")

    return bytes(pdf.output())


# ==========================================
# MODULE VUE STREAMLIT : CONTRÔLE DE COMPACITÉ
# ==========================================
def show(supabase_client, can_edit=False, is_admin=False):
    user_role = str(st.session_state.get("role", st.session_state.get("user_role", ""))).upper()
    user_is_admin = is_admin or ("ADMIN" in user_role)
    user_can_edit = can_edit or user_is_admin or ("LABO" in user_role)

    st.title("🧱 Contrôle de Compacité (NF P 94-093 / NF P 94-061-2)")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    is_editing_mode = st.session_state.get("compacite_edit_mode", False)
    if is_editing_mode:
        st.warning(f"✏️ **Mode Modification** activé pour le PV : `{st.session_state.get('compacite_edit_num_rapport')}`")

    tabs = st.tabs(["➕ Saisie & Modification PV", "📋 Historique, Consultation & Administration"])

    # ---------------------------------------------------------
    # TAB 1 : SAISIE & MODIFICATION PV
    # ---------------------------------------------------------
    with tabs[0]:
        if not user_can_edit:
            st.warning("🔒 Mode lecture seule. Vous n'avez pas les droits de modification.")

        st.subheader("1. Informations Générales du PV")
        col_h1, col_h2, col_h3 = st.columns(3)

        default_seq = st.session_state.get("edit_comp_num_seq", 1264)
        default_dossier = st.session_state.get("edit_comp_dossier", "2025-260-05985-2025 0247")
        default_lieu = st.session_state.get("edit_comp_lieu", "OA-SOUS-RN11/12éme couche de remblai contigu du plot 2 gauche (Inferieur 1,50m)")
        default_d_opn = float(st.session_state.get("edit_comp_d_opn", 2.09))
        default_w_opn = float(st.session_state.get("edit_comp_w_opn", 6.3))
        default_mat = st.session_state.get("edit_comp_mat", "GNT / Grave 0/60 - couche de forme LGV")

        with col_h1:
            st.markdown("**N° Rapport d'essai**")
            c_prefix, c_num = st.columns([2.5, 1.5])
            with c_prefix:
                fixed_prefix = st.text_input("Préfixe fixe", value="26/260/LGV/CS/", disabled=True, key="fixed_comp_prefix")
            with c_num:
                num_pv_seq = st.number_input("N° PV", value=default_seq, step=1, key="num_comp_pv_seq", disabled=not user_can_edit or is_editing_mode)

            num_rapport = f"{fixed_prefix}{num_pv_seq}"
            st.info(f"Rapport : **{num_rapport}**")

            client_name = st.text_input("Client", value="TGCC", disabled=not user_can_edit)
            num_dossier = st.text_input("N° Dossier", value=default_dossier, disabled=not user_can_edit)

        with col_h2:
            lieu_prelevement = st.text_area("Lieu / Zone de prélèvement", value=default_lieu, height=90, disabled=not user_can_edit)
            
            # SELECTBOX DYNAMIQUE MATÉRIAUX
            mat_keys = list(REFERENTIEL_MATERIAUX.keys())
            default_mat_idx = mat_keys.index(default_mat) if default_mat in mat_keys else 1

            type_materiau = st.selectbox(
                "Type de matériau / Famille",
                options=mat_keys,
                index=default_mat_idx,
                disabled=not user_can_edit,
                key="select_type_materiau_comp"
            )

        with col_h3:
            date_prelevement = st.date_input("Date du prélèvement", value=datetime.date.today(), disabled=not user_can_edit)
            densite_opn = st.number_input("Densité Proctor OPN (t/m³)", value=default_d_opn, step=0.01, disabled=not user_can_edit)
            w_opn = st.number_input("Teneur en eau opt. OPN (%)", value=default_w_opn, step=0.1, disabled=not user_can_edit)

        # SYNCHRONISATION AUTOMATIQUE DES EXIGENCES D'APRÈS LE TABLEAU
        mat_info = REFERENTIEL_MATERIAUX[type_materiau]

        c_exig1, c_exig2, c_exig3 = st.columns([2, 1, 1])
        with c_exig1:
            exigence_str = st.text_input("Exigence CCTP", value=mat_info['exigence_str'], disabled=not user_can_edit)
        with c_exig2:
            exigence_mc = st.number_input("Exigence pdmc (% OPN)", value=float(mat_info['exigence_mc']), step=0.5, disabled=not user_can_edit)
        with c_exig3:
            exigence_fc = st.number_input("Exigence pdfc (% OPN)", value=float(mat_info['exigence_fc']), step=0.5, disabled=not user_can_edit)

        st.markdown("---")
        st.subheader("2. Points de Mesure de Compacité")

        # Initialisation avec rérérences successives strictes
        if "compacite_samples" not in st.session_state:
            st.session_state["compacite_samples"] = [
                {"ref_num": 1, "designation": lieu_prelevement, "type_mesure": "mc", "densite_seche": 2.162, "densite_ref": 2.217, "w_mesure": 6.2, "refus_20mm": 27.0},
                {"ref_num": 2, "designation": lieu_prelevement, "type_mesure": "mc", "densite_seche": 2.152, "densite_ref": 2.226, "w_mesure": 6.2, "refus_20mm": 29.0},
                {"ref_num": 3, "designation": lieu_prelevement, "type_mesure": "mc", "densite_seche": 2.144, "densite_ref": 2.211, "w_mesure": 6.9, "refus_20mm": 26.0},
            ]

        col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 3])
        with col_b1:
            if st.button("➕ Ajouter un point de mesure", disabled=not user_can_edit):
                next_ref = len(st.session_state["compacite_samples"]) + 1
                st.session_state["compacite_samples"].append({
                    "ref_num": next_ref,
                    "designation": lieu_prelevement,
                    "type_mesure": "mc",
                    "densite_seche": 2.150,
                    "densite_ref": 2.200,
                    "w_mesure": 6.0,
                    "refus_20mm": 25.0
                })
                st.rerun()

        with col_b2:
            if st.button("➖ Supprimer le dernier", disabled=not user_can_edit or len(st.session_state["compacite_samples"]) <= 1):
                st.session_state["compacite_samples"].pop()
                st.rerun()

        samples_calculated = []

        for i, sample in enumerate(st.session_state["compacite_samples"]):
            # Synchronisation stricte : Point N° X = Réf X
            point_num = i + 1

            with st.expander(f"📍 Point N° {point_num} : Réf {point_num} [{sample['type_mesure'].upper()}]", expanded=True):
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2.5, 1.2, 1.5, 1.5, 1.2, 1.2])
                with c1:
                    ref_num = st.number_input("Réf", value=point_num, step=1, key=f"comp_ref_{i}", disabled=True)
                with c2:
                    desig = st.text_input("Désignation / Localisation", value=sample["designation"], key=f"comp_desig_{i}", disabled=not user_can_edit)
                with c3:
                    type_m = st.selectbox("Niveau", ["mc", "fc"], index=0 if sample["type_mesure"] == "mc" else 1, key=f"comp_typ_{i}", disabled=not user_can_edit)
                with c4:
                    d_s = st.number_input("Densité Sèche", value=float(sample["densite_seche"]), step=0.001, format="%.3f", key=f"comp_ds_{i}", disabled=not user_can_edit)
                with c5:
                    d_ref = st.number_input("Densité Réf (Corrigée)", value=float(sample["densite_ref"]), step=0.001, format="%.3f", key=f"comp_dref_{i}", disabled=not user_can_edit)
                with c6:
                    w_m = st.number_input("w (%)", value=float(sample["w_mesure"]), step=0.1, key=f"comp_wm_{i}", disabled=not user_can_edit)
                with c7:
                    ref_20 = st.number_input("% >20mm", value=float(sample["refus_20mm"]), step=0.1, key=f"comp_ref20_{i}", disabled=not user_can_edit)

                ic, obs = evaluer_compacite(d_s, d_ref, type_mesure=type_m, exigence_mc=exigence_mc, exigence_fc=exigence_fc)

                st.caption(f"📊 **Indice de Compacité (IC)** = `{ic:.1f} %` | **Observation** = `{obs}`")

                # Mise à jour synchronisée dans la session
                st.session_state["compacite_samples"][i] = {
                    "ref_num": point_num,
                    "designation": desig,
                    "type_mesure": type_m,
                    "densite_seche": d_s,
                    "densite_ref": d_ref,
                    "w_mesure": w_m,
                    "refus_20mm": ref_20
                }

                samples_calculated.append({
                    "ref_num": point_num,
                    "designation": desig,
                    "type_mesure": type_m,
                    "densite_seche": d_s,
                    "densite_ref": d_ref,
                    "w_mesure": w_m,
                    "refus_20mm": ref_20,
                    "ic": ic,
                    "observation": obs
                })

        st.markdown("---")

        header_data = {
            "num_rapport": num_rapport,
            "num_dossier": num_dossier,
            "client": client_name,
            "lieu_prelevement": lieu_prelevement,
            "date_prelevement": str(date_prelevement),
            "type_materiau": type_materiau,
            "exigence_str": exigence_str,
            "densite_opn": densite_opn,
            "w_opn": w_opn,
            "exigence_mc": exigence_mc,
            "exigence_fc": exigence_fc
        }

        pdf_bytes = generate_pv_compacite_pdf(header_data, samples_calculated)

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            st.download_button(
                label="📄 Télécharger le PV Officiel Compacité (PDF)",
                data=pdf_bytes,
                file_name=f"PV_Compacite_{num_pv_seq}.pdf",
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
                        # VÉRIFICATION ANTI-DOUBLON
                        if not is_editing_mode:
                            check_pv = supabase_client.table("pv_compacite").select("num_rapport").eq("num_rapport", num_rapport).execute()
                            if check_pv.data:
                                st.error(f"⛔ **Enregistrement bloqué** : Le PV n° **{num_rapport}** existe déjà dans la base de données. Choisissez un autre numéro.")
                                st.stop()

                        # ENREGISTREMENT DE L'EN-TÊTE
                        supabase_client.table("pv_compacite").upsert(header_data).execute()

                        # NETTOYAGE ANCIENS POINTS
                        if is_editing_mode:
                            supabase_client.table("essai_compacite").delete().eq("num_rapport", num_rapport).execute()

                        # INSERTION DES POINTS DE MESURE
                        for item in samples_calculated:
                            item_to_insert = item.copy()
                            item_to_insert["num_rapport"] = num_rapport
                            supabase_client.table("essai_compacite").insert(item_to_insert).execute()

                        st.success(f"✅ PV Compacité **{num_rapport}** enregistré avec succès !")

                        if is_editing_mode:
                            st.session_state["compacite_edit_mode"] = False
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'enregistrement : {e}")

    # ---------------------------------------------------------
    # TAB 2 : HISTORIQUE & ADMINISTRATION
    # ---------------------------------------------------------
    with tabs[1]:
        st.subheader("🖨️ Historique et Gestion des PV de Compacité")

        if not supabase_client:
            st.info("💡 Client Supabase non configuré.")
        else:
            try:
                pv_res = supabase_client.table("pv_compacite").select("*").order("created_at", desc=True).execute()

                if pv_res.data:
                    pv_list = pv_res.data
                    pv_options = {pv["num_rapport"]: pv for pv in pv_list}

                    selected_num_rapport = st.selectbox(
                        "🔍 Choisir un N° de Rapport / PV :",
                        options=list(pv_options.keys()),
                        key="select_pv_compacite"
                    )

                    if selected_num_rapport:
                        selected_pv = pv_options[selected_num_rapport]

                        samples_res = supabase_client.table("essai_compacite") \
                            .select("*") \
                            .eq("num_rapport", selected_num_rapport) \
                            .order("id", desc=False) \
                            .execute()

                        samples_data = samples_res.data if samples_res.data else []

                        with st.expander(f"📄 Détails du PV Compacité : {selected_num_rapport}", expanded=True):
                            c_info1, c_info2 = st.columns(2)
                            with c_info1:
                                st.markdown(f"**Client :** {selected_pv.get('client', 'N/A')}")
                                st.markdown(f"**N° Dossier :** {selected_pv.get('num_dossier', 'N/A')}")
                                st.markdown(f"**Lieu :** {selected_pv.get('lieu_prelevement', 'N/A')}")
                            with c_info2:
                                st.markdown(f"**Date Prélèvement :** {selected_pv.get('date_prelevement', 'N/A')}")
                                st.markdown(f"**Matériau :** {selected_pv.get('type_materiau', 'N/A')}")
                                st.markdown(f"**Exigence CCTP :** `{selected_pv.get('exigence_str', 'N/A')}`")

                            st.markdown("#### Points de mesure :")
                            if samples_data:
                                df_samples = pd.DataFrame(samples_data)
                                display_cols = [c for c in ["ref_num", "designation", "type_mesure", "densite_seche", "densite_ref", "w_mesure", "refus_20mm", "ic", "observation"] if c in df_samples.columns]
                                st.dataframe(df_samples[display_cols], use_container_width=True)

                        col_act1, col_act2, col_act3 = st.columns([2, 1.5, 1.5])

                        with col_act1:
                            pdf_reprint = generate_pv_compacite_pdf(selected_pv, samples_data)
                            st.download_button(
                                label="🖨️ Imprimer / PDF",
                                data=pdf_reprint,
                                file_name=f"PV_Compacite_{selected_num_rapport.replace('/', '_')}.pdf",
                                mime="application/pdf",
                                type="primary",
                                use_container_width=True,
                                key="btn_print_comp"
                            )

                        with col_act2:
                            if st.button("✏️ Modifier ce PV", disabled=not user_can_edit, use_container_width=True, key="btn_edit_comp"):
                                try:
                                    seq_val = int(selected_num_rapport.split('/')[-1])
                                except Exception:
                                    seq_val = 1264

                                st.session_state["compacite_edit_mode"] = True
                                st.session_state["compacite_edit_num_rapport"] = selected_num_rapport
                                st.session_state["edit_comp_num_seq"] = seq_val
                                st.session_state["edit_comp_dossier"] = selected_pv.get("num_dossier", "")
                                st.session_state["edit_comp_lieu"] = selected_pv.get("lieu_prelevement", "")
                                st.session_state["edit_comp_mat"] = selected_pv.get("type_materiau", "")
                                st.session_state["edit_comp_d_opn"] = selected_pv.get("densite_opn", 2.09)
                                st.session_state["edit_comp_w_opn"] = selected_pv.get("w_opn", 6.3)

                                if samples_data:
                                    st.session_state["compacite_samples"] = [
                                        {
                                            "ref_num": idx + 1,
                                            "designation": s.get("designation", ""),
                                            "type_mesure": s.get("type_mesure", "mc"),
                                            "densite_seche": s.get("densite_seche", 2.15),
                                            "densite_ref": s.get("densite_ref", 2.20),
                                            "w_mesure": s.get("w_mesure", 6.0),
                                            "refus_20mm": s.get("refus_20mm", 25.0)
                                        } for idx, s in enumerate(samples_data)
                                    ]
                                st.success("PV chargé dans l'onglet 'Saisie & Modification'.")
                                st.rerun()

                        with col_act3:
                            if st.button("🗑️ Supprimer ce PV", disabled=not user_is_admin, use_container_width=True, key="btn_del_comp"):
                                try:
                                    supabase_client.table("essai_compacite").delete().eq("num_rapport", selected_num_rapport).execute()
                                    supabase_client.table("pv_compacite").delete().eq("num_rapport", selected_num_rapport).execute()
                                    st.success(f"✅ PV `{selected_num_rapport}` supprimé avec succès.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Erreur lors de la suppression : {err}")

                else:
                    st.info("Aucun PV de compacité enregistré dans la base de données.")

            except Exception as e:
                st.error(f"❌ Erreur lors de la récupération des données : {e}")

        st.markdown("---")
        st.subheader("📋 Base de données brute des mesures (essai_compacite)")
        if supabase_client:
            try:
                res = supabase_client.table("essai_compacite").select("*").order("created_at", desc=True).execute()
                if res.data:
                    df = pd.DataFrame(res.data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Aucune donnée d'échantillon enregistrée.")
            except Exception as e:
                st.error(f"Erreur de chargement de la table brute : {e}")
