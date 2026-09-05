import datetime
import pandas as pd
import streamlit as st
from fpdf import FPDF

# ==========================================
# CLASSE DE GÉNÉRATION DU PV EN PDF (FORMAT LPEE)
# ==========================================
class LPEETeneurEauPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 5, "LABORATOIRE PUBLIC D'ESSAIS ET D'ETUDES - LPEE", 0, 1, "C")
        self.set_font("Helvetica", "B", 8)
        self.cell(0, 4, "CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT-BENI MELLAL (CTR-CSB)", 0, 1, "C")
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 4, "Laboratoire de Contrôle Externe - LGV CASA SUD", 0, 1, "C")
        self.ln(2)
        self.line(10, 22, 200, 22)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"CTR-CSB - Page {self.page_no()}/{{nb}}", 0, 0, "C")


def generate_pv_teneur_eau_pdf(header_info, points_data):
    pdf = LPEETeneurEauPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Titre du PV
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "PROCES VERBAL", 0, 1, "C")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "Détermination de la teneur en eau pondérale des matériaux par étuvage (NM EN 1097-5)", 0, 1, "C")
    pdf.ln(3)

    # N° de Rapport
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"Rapport d'Essai n° : {header_info.get('num_rapport', 'N/A')}", 0, 1, "R")
    pdf.ln(2)

    # I - Identification du matériau testé
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 6, " I - Identification du matériau testé", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 8)
    
    type_p = header_info.get('type_proctor', 'OPN')
    pdf.cell(95, 5, f"  Nature du matériau : {header_info.get('nature_materiau', '')}", 1, 0, "L")
    pdf.cell(95, 5, f"  Type de Proctor : {type_p}", 1, 1, "L")
    
    pdf.cell(95, 5, f"  Lieu de prélèvement : {header_info.get('lieu_prelevement', '')}", 1, 0, "L")
    pdf.cell(95, 5, f"  Teneur en eau {type_p} (%) : {header_info.get('w_opn', '')} %", 1, 1, "L")

    pdf.cell(95, 5, f"  Prélèvement effectué le : {header_info.get('date_prelevement', '')}", 1, 0, "L")
    pdf.cell(95, 5, f"  PK : {header_info.get('pk_zone', '')}", 1, 1, "L")
    pdf.ln(4)

    # II - Résultats des Essais
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 6, " II - Résultats des essais", 1, 1, "L", fill=True)
    
    # En-têtes du tableau
    headers = ["Référence", "Date Prél.", "PK / Localisation", "Couche", "w (%)", f"w {type_p} (%)", "État Hydrique", "Observation"]
    widths = [22, 22, 42, 16, 18, 22, 24, 24]
    
    pdf.set_font("Helvetica", "B", 7.5)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 6, h, 1, 0, "C")
    pdf.ln()

    # Lignes du tableau
    pdf.set_font("Helvetica", "", 7.5)
    for p in points_data:
        pdf.cell(widths[0], 6, str(p.get("ref_ech", "")), 1, 0, "C")
        pdf.cell(widths[1], 6, str(p.get("date_prel", "")), 1, 0, "C")
        pdf.cell(widths[2], 6, str(p.get("pk", "")), 1, 0, "C")
        pdf.cell(widths[3], 6, str(p.get("couche", "1")), 1, 0, "C")
        pdf.cell(widths[4], 6, f"{p.get('w_mesure', 0.0):.1f}", 1, 0, "C")
        pdf.cell(widths[5], 6, f"{p.get('w_opn', 0.0):.1f}", 1, 0, "C")
        pdf.cell(widths[6], 6, str(p.get("etat_hydrique", "")), 1, 0, "C")
        pdf.cell(widths[7], 6, str(p.get("observation", "Conforme")), 1, 1, "C")

    pdf.ln(8)

    # Signatures
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(63, 5, "Réception du client", 0, 0, "C")
    pdf.cell(64, 5, "Le Coordinateur des Essais", 0, 0, "C")
    pdf.cell(63, 5, "Le Chef de Laboratoire Externe", 0, 1, "C")
    
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(63, 4, "(Nom, Visa, Date)", 0, 0, "C")
    pdf.cell(64, 4, "B. ELAMRI", 0, 0, "C")
    pdf.cell(63, 4, "H. BAALLAL", 0, 1, "C")

    return bytes(pdf.output())


# ==========================================
# MODULE VUE STREAMLIT : TENEUR EN EAU
# ==========================================
def show(supabase_client, can_edit=False):
    st.title("💧 Essai de Teneur en Eau (NM EN 1097-5)")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    tabs = st.tabs(["➕ Saisie & Création PV", "📋 Historique & Consultation"])

    # ---------------------------------------------------------
    # TAB 1 : SAISIE & CREATION PV
    # ---------------------------------------------------------
    with tabs[0]:
        if not can_edit:
            st.warning("🔒 Mode lecture seule. Vous n'avez pas les droits de modification.")
        
        st.subheader("1. Informations Générales du PV")
        col_h1, col_h2, col_h3 = st.columns(3)
        
        with col_h1:
            st.markdown("**N° Rapport d'essai**")
            c_prefix, c_num = st.columns([2.5, 1.5])
            with c_prefix:
                fixed_prefix = st.text_input("Préfixe fixe", value="25/260/LGV/CS/", disabled=True, key="fixed_prefix")
            with c_num:
                num_pv_seq = st.number_input("N° PV", value=371, step=1, key="num_pv_seq", disabled=not can_edit)
            
            num_rapport = f"{fixed_prefix}{num_pv_seq}"
            st.info(f"Rapport : **{num_rapport}**")

            nature_mat = st.text_input("Nature du matériau", value="Sol - C1 B5", disabled=not can_edit)

        with col_h2:
            lieu_prelevement = st.text_input("Lieu de prélèvement / Zone", value="Zone T4 Axe V3G et V6G", disabled=not can_edit)
            pk_zone = st.text_input("PK / Section", value="pk 8+540 à pk 8+600", disabled=not can_edit)

        with col_h3:
            date_prelevement = st.date_input("Date de prélèvement", value=datetime.date.today(), disabled=not can_edit)
            type_proctor = st.selectbox("Type de Proctor", ["OPN", "OPM"], disabled=not can_edit)
            w_opn = st.number_input(f"Teneur en eau {type_proctor} (%)", value=12.0, step=0.1, disabled=not can_edit)

        st.markdown("---")
        st.subheader("2. Mesures & Prélèvements")

        # Initialisation par défaut de la liste
        if "teneur_eau_samples" not in st.session_state:
            st.session_state["teneur_eau_samples"] = [
                {"pk": pk_zone, "couche": 1, "m_humide": 240.5, "m_seche": 218.2, "m_tare": 39.8},
                {"pk": pk_zone, "couche": 1, "m_humide": 238.1, "m_seche": 217.0, "m_tare": 38.0},
            ]

        # Boutons d'ajout et de suppression d'échantillon
        col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 3])
        with col_b1:
            if st.button("➕ Ajouter un échantillon", disabled=not can_edit):
                st.session_state["teneur_eau_samples"].append({
                    "pk": pk_zone, "couche": 1, "m_humide": 200.0, "m_seche": 180.0, "m_tare": 30.0
                })
                st.rerun()

        with col_b2:
            if st.button("➖ Supprimer le dernier", disabled=not can_edit or len(st.session_state["teneur_eau_samples"]) <= 1):
                st.session_state["teneur_eau_samples"].pop()
                st.rerun()

        samples_calculated = []
        to_delete_idx = None

        for i, sample in enumerate(st.session_state["teneur_eau_samples"]):
            computed_ref = f"{num_pv_seq}/{i+1}"
            
            with st.expander(f"📍 Échantillon N° {i+1} : {computed_ref}", expanded=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1.5, 2, 2, 2, 2, 1])
                with c1:
                    ref = st.text_input("Référence", value=computed_ref, key=f"ref_{i}", disabled=True)
                with c2:
                    pk_item = st.text_input("PK / Localisation", value=sample["pk"], key=f"pk_{i}", disabled=not can_edit)
                with c3:
                    m_h = st.number_input("Masse Humide + Tare (g)", value=float(sample["m_humide"]), step=0.1, key=f"mh_{i}", disabled=not can_edit)
                with c4:
                    m_s = st.number_input("Masse Sèche + Tare (g)", value=float(sample["m_seche"]), step=0.1, key=f"ms_{i}", disabled=not can_edit)
                with c5:
                    m_t = st.number_input("Masse Tare (g)", value=float(sample["m_tare"]), step=0.1, key=f"mt_{i}", disabled=not can_edit)
                with c6:
                    st.markdown("&nbsp;")
                    if st.button("🗑️", key=f"del_{i}", help="Supprimer cet échantillon", disabled=not can_edit or len(st.session_state["teneur_eau_samples"]) <= 1):
                        to_delete_idx = i

                m_eau = m_h - m_s
                m_seche_nette = m_s - m_t
                w_mesure = (m_eau / m_seche_nette * 100) if m_seche_nette > 0 else 0.0

                delta_w = w_mesure - w_opn
                if abs(delta_w) <= 1.5:
                    etat_hydrique = "Moyen"
                    conforme = True
                elif delta_w > 1.5:
                    etat_hydrique = "Humide"
                    conforme = True if delta_w <= 3.0 else False
                else:
                    etat_hydrique = "Sec"
                    conforme = False if delta_w < -2.0 else True

                obs = "Conforme" if conforme else "Non Conforme"

                st.caption(f"📊 **w mesurée** = `{w_mesure:.1f} %` | **État Hydrique** = `{etat_hydrique}` | **Observation** = `{obs}`")

                samples_calculated.append({
                    "ref_ech": computed_ref,
                    "date_prel": str(date_prelevement),
                    "pk": pk_item,
                    "couche": sample["couche"],
                    "m_humide": m_h,
                    "m_seche": m_s,
                    "m_tare": m_t,
                    "w_mesure": round(w_mesure, 1),
                    "w_opn": w_opn,
                    "etat_hydrique": etat_hydrique,
                    "observation": obs
                })

        # Suppression spécifique de l'échantillon sélectionné via le bouton corbeille
        if to_delete_idx is not None:
            st.session_state["teneur_eau_samples"].pop(to_delete_idx)
            st.rerun()

        st.markdown("---")
        
        # Actions : Téléchargement PDF / Enregistrement
        col_act1, col_act2 = st.columns(2)
        
        header_data = {
            "num_rapport": num_rapport,
            "nature_materiau": nature_mat,
            "lieu_prelevement": lieu_prelevement,
            "pk_zone": pk_zone,
            "date_prelevement": str(date_prelevement),
            "type_proctor": type_proctor,
            "w_opn": w_opn
        }

        # Génération du PDF
        pdf_bytes = generate_pv_teneur_eau_pdf(header_data, samples_calculated)

        with col_act1:
            st.download_button(
                label="📄 Télécharger le PV Officiel (PDF)",
                data=pdf_bytes,
                file_name=f"PV_Teneur_en_eau_{num_pv_seq}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col_act2:
            if st.button("💾 Enregistrer dans Supabase", type="primary", use_container_width=True, disabled=not can_edit):
                if not supabase_client:
                    st.error("❌ Connexion Supabase non disponible.")
                else:
                    try:
                        # 1. Vérification si la référence existe déjà
                        refs_to_check = [s["ref_ech"] for s in samples_calculated]
                        check_samples = supabase_client.table("essai_teneur_eau").select("ref_ech").in_("ref_ech", refs_to_check).execute()

                        if check_samples.data:
                            existing_refs = [item["ref_ech"] for item in check_samples.data]
                            st.error(f"⛔ **Saisie bloquée** : Les références suivantes existent déjà dans Supabase : **{', '.join(existing_refs)}**. Veuillez incrémenter le N° PV.")
                        else:
                            # 2. Enregistrement de l'en-tête
                            supabase_client.table("pv_teneur_eau").upsert(header_data).execute()
                            
                            # 3. Enregistrement uniquement des échantillons restants
                            for item in samples_calculated:
                                item["num_rapport"] = num_rapport
                                supabase_client.table("essai_teneur_eau").insert(item).execute()

                            st.success(f"✅ Procès-Verbal **{num_rapport}** ({len(samples_calculated)} échantillons) enregistré avec succès !")
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'enregistrement : {e}")

    # ---------------------------------------------------------
    # TAB 2 : HISTORIQUE ET CONSULTATION
    # ---------------------------------------------------------
    with tabs[1]:
        st.subheader("📋 Historique des mesures de teneur en eau")
        if supabase_client:
            try:
                res = supabase_client.table("essai_teneur_eau").select("*").order("created_at", desc=True).execute()
                if res.data:
                    df = pd.DataFrame(res.data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Aucune donnée enregistrée dans Supabase pour le moment.")
            except Exception as e:
                st.error(f"Erreur de chargement des données : {e}")
        else:
            st.info("💡 Client Supabase non configuré.")
