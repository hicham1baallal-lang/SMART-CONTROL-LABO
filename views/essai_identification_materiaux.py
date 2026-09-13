import datetime
import io
import os
import pandas as pd
import streamlit as st
from fpdf import FPDF


class IdentificationPDF(FPDF):
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


def generate_pdf(header_info, data_dict, type_mat):
    pdf = IdentificationPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"PROCES VERBAL - IDENTIFICATION {type_mat.upper()}", 0, 1, "C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"Rapport d'Essai n° : {header_info.get('num_rapport') or 'N/A'}", 0, 1, "R")
    pdf.ln(4)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 8, " I - Informations générales", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 7, f"   Lieu : {header_info.get('lieu') or ''}", 1, 0, "L")
    pdf.cell(95, 7, f"   Date : {header_info.get('date_essai') or ''}", 1, 1, "L")
    pdf.cell(190, 7, f"   Origine / PK : {header_info.get('pk') or ''}", 1, 1, "L")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 8, f" II - Résultats d'identification ({type_mat})", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 9)
    for k, v in data_dict.items():
        pdf.cell(95, 7, f"   {k}", 1, 0, "L")
        pdf.cell(95, 7, f"   {v}", 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 6, "Le Technicien", 0, 0, "C")
    pdf.cell(95, 6, "Le Chef de Laboratoire", 0, 1, "C")
    return bytes(pdf.output())


def show(supabase_client):
    user_name = str(st.session_state.get("user_name", st.session_state.get("user", {}).get("username", ""))).upper()
    user_role = str(st.session_state.get("role", "")).upper()
    is_admin = ("ADMIN" in user_role) or ("BAALLAL" in user_name)
    user_can_edit = is_admin or ("LABO" in user_role)

    st.title("🔬 Identification des Matériaux")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    if not user_can_edit:
        st.warning("🔒 Mode lecture seule. Droits de modification restreints.")

    tabs = st.tabs([
        "➕ Saisir un sol",
        "➕ Saisir un grave",
        "📋 PVS / Historique, Consultation & Administration",
        "📊 Synthèse"
    ])

    # ---------------------------------------------------------
    # TAB 0 : ➕ SAISIR UN SOL
    # ---------------------------------------------------------
    with tabs[0]:
        st.subheader("➕ Saisie Identification Sol (Atterberg, ES, GTR)")
        c1, c2, c3 = st.columns(3)
        with c1:
            num_rapp_sol = st.text_input("N° Rapport Sol", value="25/260/LGV/CS/SOL/001", disabled=not user_can_edit)
            lieu_sol = st.text_input("Lieu / Zone Sol", value="Zone T4", disabled=not user_can_edit)
        with c2:
            pk_sol = st.text_input("PK / Section Sol", value="PK 8+540", disabled=not user_can_edit)
            date_sol = st.date_input("Date Essai Sol", value=datetime.date.today(), disabled=not user_can_edit)
        with c3:
            w_l = st.number_input("Limite de liquidité wL (%)", value=35.0, step=0.5, disabled=not user_can_edit)
            w_p = st.number_input("Limite de plasticité wP (%)", value=20.0, step=0.5, disabled=not user_can_edit)

        ip = w_l - w_p
        c4, c5, c6 = st.columns(3)
        with c4:
            st.metric("Indice de plasticité IP", f"{ip:.1f} %")
        with c5:
            es_visuel = st.selectbox("Équivalent de sable (ES)", ["ESV > 60 (Propre)", "40 < ESV <= 60 (Acceptable)", "ESV <= 40 / EST"], disabled=not user_can_edit)
        with c6:
            gtr_sol = st.selectbox("Classe GTR Sol", ["A1", "A2", "A3", "A4", "B1", "B2", "C1", "D1"], disabled=not user_can_edit)

        obs_sol = "Conforme" if ip < 25 else "Non Conforme / Argileux"
        st.info(f"Observation automatique : **{obs_sol}**")

        data_sol_dict = {
            "wL (%)": f"{w_l}", "wP (%)": f"{w_p}", "IP (%)": f"{ip:.1f}",
            "ES": es_visuel, "Classe GTR": gtr_sol, "Observation": obs_sol
        }
        header_sol = {"num_rapport": num_rapp_sol, "lieu": lieu_sol, "pk": pk_sol, "date_essai": str(date_sol), "type": "SOL"}

        pdf_sol = generate_pdf(header_sol, data_sol_dict, "Sol")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📄 Télécharger PV Sol (PDF)", data=pdf_sol, file_name=f"PV_Sol_{num_rapp_sol.replace('/','_')}.pdf", mime="application/pdf", use_container_width=True)
        with col_d2:
            if st.button("💾 Enregistrer Sol (Supabase)", type="primary", use_container_width=True, disabled=not user_can_edit):
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").upsert({
                            "num_rapport": num_rapp_sol,
                            "type_materiau": "SOL",
                            "lieu": lieu_sol,
                            "pk": pk_sol,
                            "date_essai": str(date_sol),
                            "details": data_sol_dict,
                            "observation": obs_sol
                        }).execute()
                        st.success("✅ Sol enregistré avec succès !")
                    except Exception as e:
                        st.error(f"Erreur Supabase : {e}")

    # ---------------------------------------------------------
    # TAB 1 : ➕ SAISIR UN GRAVE
    # ---------------------------------------------------------
    with tabs:
        st.subheader("➕ Saisie Identification Grave (Los Angeles, Micro-Deval, ES)")
        c1, c2, c3 = st.columns(3)
        with c1:
            num_rapp_grav = st.text_input("N° Rapport Grave", value="25/260/LGV/CS/GRV/001", disabled=not user_can_edit)
            lieu_grav = st.text_input("Lieu / Zone Grave", value="Centrale / Carrière", disabled=not user_can_edit)
        with c2:
            pk_grav = st.text_input("PK / Section Grave", value="Section 2", disabled=not user_can_edit)
            date_grav = st.date_input("Date Essai Grave", value=datetime.date.today(), disabled=not user_can_edit)
        with c3:
            la = st.number_input("Los Angeles (LA)", value=25.0, step=1.0, disabled=not user_can_edit)
            md = st.number_input("Micro-Deval humide (MDE)", value=18.0, step=1.0, disabled=not user_can_edit)

        es_grav = st.selectbox("ES à 10% / Piston (Grave)", ["ES >= 75", "ES < 75"], disabled=not user_can_edit)
        obs_grav = "Conforme" if la <= 30 and md <= 20 else "Non Conforme"
        st.info(f"Observation automatique : **{obs_grav}**")

        data_grav_dict = {
            "Los Angeles (LA)": f"{la}", "Micro-Deval (MDE)": f"{md}",
            "ES Grave": es_grav, "Observation": obs_grav
        }
        header_grav = {"num_rapport": num_rapp_grav, "lieu": lieu_grav, "pk": pk_grav, "date_essai": str(date_grav), "type": "GRAVE"}

        pdf_grav = generate_pdf(header_grav, data_grav_dict, "Grave")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.download_button("📄 Télécharger PV Grave (PDF)", data=pdf_grav, file_name=f"PV_Grave_{num_rapp_grav.replace('/','_')}.pdf", mime="application/pdf", use_container_width=True)
        with col_g2:
            if st.button("💾 Enregistrer Grave (Supabase)", type="primary", use_container_width=True, disabled=not user_can_edit):
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").upsert({
                            "num_rapport": num_rapp_grav,
                            "type_materiau": "GRAVE",
                            "lieu": lieu_grav,
                            "pk": pk_grav,
                            "date_essai": str(date_grav),
                            "details": data_grav_dict,
                            "observation": obs_grav
                        }).execute()
                        st.success("✅ Grave enregistré avec succès !")
                    except Exception as e:
                        st.error(f"Erreur Supabase : {e}")

    # ---------------------------------------------------------
    # TAB 2 : 📋 PVS / HISTORIQUE, CONSULTATION & ADMINISTRATION
    # ---------------------------------------------------------
    with tabs:
        st.subheader("📋 PVS / Historique, Consultation & Administration")
        if not supabase_client:
            st.info("💡 Client Supabase non configuré.")
        else:
            try:
                res = supabase_client.table("pv_identification_materiaux").select("*").order("date_essai", desc=True).execute()
                if res.data:
                    df_hist = pd.DataFrame(res.data)
                    search_q = st.text_input("Filtrer par N° Rapport ou Lieu :").lower()
                    if search_q:
                        df_hist = df_hist[df_hist.apply(lambda r: search_q in str(r.values).lower(), axis=1)]
                    st.dataframe(df_hist, use_container_width=True)

                    selected_del = st.selectbox("Sélectionner un PV à supprimer (Admin/Labo)", options=[""] + df_hist["num_rapport"].tolist())
                    if selected_del and st.button("🗑️ Supprimer ce PV", disabled=not user_can_edit):
                        supabase_client.table("pv_identification_materiaux").delete().eq("num_rapport", selected_del).execute()
                        st.success(f"PV {selected_del} supprimé.")
                        st.rerun()
                else:
                    st.info("Aucun PV d'identification enregistré.")
            except Exception as e:
                st.warning(f"Table non initialisée ou erreur de lecture : {e}")

    # ---------------------------------------------------------
    # TAB 3 : 📊 SYNTHÈSE
    # ---------------------------------------------------------
    with tabs:
        st.subheader("📊 Synthèse Identification Matériaux")
        if not supabase_client:
            st.info("💡 Client Supabase non configuré.")
        else:
            try:
                res = supabase_client.table("pv_identification_materiaux").select("*").execute()
                if res.data:
                    df_s = pd.DataFrame(res.data)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total PVs Ident.", len(df_s))
                    m2.metric("Conformes", len(df_s[df_s["observation"]=="Conforme"]) if "observation" in df_s else 0)
                    m3.metric("Type Sol / Grave", f"{len(df_s[df_s['type_materiau']=='SOL'])} / {len(df_s[df_s['type_materiau']=='GRAVE'])}")
                    
                    st.dataframe(df_s, use_container_width=True)
                    
                    excel_buf = io.BytesIO()
                    with pd.ExcelWriter(excel_buf, engine='openpyxl') as w:
                        df_s.to_excel(w, index=False, sheet_name='Synthese_Identification')
                    excel_buf.seek(0)
                    st.download_button(
                        "📥 Télécharger la synthèse en Excel (.xlsx)",
                        data=excel_buf,
                        file_name=f"synthese_identification_{datetime.date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.info("Aucune donnée disponible pour la synthèse.")
            except Exception as e:
                st.info(f"Synthèse indisponible : {e}")
