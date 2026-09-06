# views/pv_granulats.py
import datetime
from fpdf import FPDF
import pandas as pd
import streamlit as st


class PVGranulatsPDF(FPDF):

    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(
            0,
            7,
            "LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES - LPEE",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "B", 10)
        self.cell(
            0,
            6,
            "CENTRE TECHNIQUE RÉGIONAL - LGV CASA SUD (CTR-CSB)",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "I", 9)
        self.cell(
            0,
            5,
            "Procès-Verbal d'Essai sur Granulats pour Béton",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)
        self.line(10, 27, 200, 27)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(
            0, 10, f"Page {self.page_no()}/{{nb}}", align="C", border=False
        )


def generate_pv_granulats_pdf(pv_data):
    pdf = PVGranulatsPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"N° PV : {pv_data.get('num_pv', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Date de prélèvement / Essai : {pv_data.get('date_essai', 'N/A')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Designation Matériau : {pv_data.get('designation', 'N/A')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Provenance / Carrière : {pv_data.get('provenance', 'N/A')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    pdf.set_fill_color(220, 230, 242)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 7, "Résultats des Essais de Caractérisation", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 9)
    results = [
        ("Équivalent de Sable (ES %)", str(pv_data.get("es_valeur", "N/A"))),
        ("Valeur au Bleu de Méthylène (VBS)", str(pv_data.get("vbs_valeur", "N/A"))),
        ("Los Angeles (LA %)", str(pv_data.get("la_valeur", "N/A"))),
        ("Micro-Deval (MDE %)", str(pv_data.get("mde_valeur", "N/A"))),
        ("Aplatissement (FI %)", str(pv_data.get("fi_valeur", "N/A"))),
        ("Conformité globale", str(pv_data.get("conformite", "N/A"))),
    ]

    for param, val in results:
        pdf.cell(110, 6, param, 1, 0, "L")
        pdf.cell(80, 6, val, 1, 1, "C")

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, f"Observations / Remarques : {pv_data.get('remarques', 'Aucune remarque.')}")

    return bytes(pdf.output())


def show(supabase_client, can_edit=False, is_admin=False, **kwargs):
    st.title("🪨 Contrôle & Essais sur Granulats pour Béton")
    st.caption("CTR-CSB - Laboratoire Public d'Essais et d'Études")

    tab1, tab2 = st.tabs(["📝 Saisie & Modification Essai", "📋 Historique & Consultation PVs"])

    with tab1:
        st.subheader("Nouveau Procès-Verbal - Granulats")

        if not can_edit and not is_admin:
            st.info("ℹ️ Mode consultation seule (Droit d'édition non accordé).")

        with st.form("form_pv_granulats", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                num_pv = st.text_input("Numéro de PV *", placeholder="ex: PV-GR-2026-001")
                date_essai = st.date_input("Date de l'essai", value=datetime.date.today())
            with c2:
                designation = st.text_input("Désignation du granulat", placeholder="ex: Sable 0/4, Gravette 8/15")
                provenance = st.text_input("Provenance / Carrière", placeholder="ex: Carrière Casa Sud")
            with c3:
                ouvrage = st.text_input("Ouvrage / Utilisation", placeholder="ex: Béton Piles PRO 0636")
                operateur = st.text_input("Opérateur / Technicien", value=st.session_state.get("user", {}).get("username", ""))

            st.markdown("---")
            st.markdown("##### 🧪 Paramètres Physico-Mécaniques")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                es_valeur = st.number_input("Équivalent de Sable - ES (%)", min_value=0.0, max_value=100.0, value=75.0, step=0.1)
                vbs_valeur = st.number_input("Bleu de Méthylène - VBS (g/kg)", min_value=0.0, max_value=10.0, value=0.8, step=0.01)
            with col_b:
                la_valeur = st.number_input("Los Angeles - LA (%)", min_value=0.0, max_value=100.0, value=22.0, step=0.1)
                mde_valeur = st.number_input("Micro-Deval - MDE (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.1)
            with col_c:
                fi_valeur = st.number_input("Coefficient d'Aplatissement - FI (%)", min_value=0.0, max_value=100.0, value=12.0, step=0.1)
                conformite = st.selectbox("Conformité", ["CONFORME", "NON CONFORME", "A CONFIRMER"])

            remarques = st.text_area("Observations / Remarques", value="", height=80)

            submitted = st.form_submit_button("💾 Enregistrer dans Supabase", type="primary", disabled=not (can_edit or is_admin))

            if submitted:
                if not num_pv:
                    st.error("❌ Le numéro de PV est obligatoire.")
                else:
                    record = {
                        "num_pv": num_pv,
                        "date_essai": str(date_essai),
                        "designation": designation,
                        "provenance": provenance,
                        "ouvrage": ouvrage,
                        "operateur": operateur,
                        "es_valeur": es_valeur,
                        "vbs_valeur": vbs_valeur,
                        "la_valeur": la_valeur,
                        "mde_valeur": mde_valeur,
                        "fi_valeur": fi_valeur,
                        "conformite": conformite,
                        "remarques": remarques,
                        "created_at": datetime.datetime.utcnow().isoformat(),
                    }

                    if supabase_client:
                        try:
                            res = supabase_client.table("pv_granulats").upsert(record).execute()
                            st.success(f"✅ PV `{num_pv}` enregistré avec succès sur Supabase !")
                        except Exception as e:
                            st.error(f"❌ Erreur de sauvegarde Supabase : {e}")
                    else:
                        st.warning("⚠️ Supabase non connecté. Données traitées localement.")

    with tab2:
        st.subheader("📋 Historique des Procès-Verbaux Granulats")

        records = []
        if supabase_client:
            try:
                res = supabase_client.table("pv_granulats").select("*").order("created_at", desc=True).execute()
                records = res.data or []
            except Exception as e:
                st.info(f"Impossible de charger l'historique depuis Supabase ({e}).")

        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)

            selected_pv_num = st.selectbox("Sélectionner un PV pour télécharger le PDF", df["num_pv"].unique())
            pv_selected = df[df["num_pv"] == selected_pv_num].iloc[0].to_dict()

            pdf_bytes = generate_pv_granulats_pdf(pv_selected)
            st.download_button(
                label=f"📄 Télécharger le PDF ({selected_pv_num})",
                data=pdf_bytes,
                file_name=f"PV_Granulats_{selected_pv_num}.pdf",
                mime="application/pdf",
                type="primary",
            )
        else:
            st.info("Aucun enregistrement trouvé dans la base de données.")
