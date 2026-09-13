import datetime
import io
import os
import numpy as np
import pandas as pd
import streamlit as st
from fpdf import FPDF


def classer_gtr(dmax, pass_80um, ip, vbs=0.5):
    """Classification GTR automatique selon l'abaque officiel LPEE/SETRA."""
    if dmax <= 50:
        if pass_80um >= 35.0:
            if ip < 12: return "A1"
            elif ip < 25: return "A2"
            elif ip < 40: return "A3"
            else: return "A4"
        elif pass_80um >= 12.0:
            if vbs < 0.2:
                return "B1" if pass_80um < 20 else "B5"
            elif vbs <= 1.5: return "B2"
            elif vbs <= 6.0: return "B6"
            else: return "B4"
        else:
            if vbs < 0.1: return "D1" if pass_80um < 6 else "D2"
            else: return "B3" if vbs <= 0.2 else "B2"
    else:
        if pass_80um < 12.0 and vbs < 0.1:
            return "D3"
        else:
            return "C1" if pass_80um <= 40 else "C2"


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
    pdf.cell(0, 8, f"PROCES VERBAL - GRANULO & GTR ({type_mat.upper()})", 0, 1, "C")
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
    pdf.cell(190, 8, " II - Synthèse Granulométrique & GTR (NM 00.8.082)", 1, 1, "L", fill=True)
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

    st.title("🔬 Granulométrie NM 00.8.082 & Classification GTR")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    if not user_can_edit:
        st.warning("🔒 Mode lecture seule. Droits de modification restreints.")

    tabs = st.tabs([
        "➕ Saisir un PV & Granulo",
        "📋 PVS / Historique, Consultation & Administration",
        "📊 Synthèse"
    ])

    # ---------------------------------------------------------
    # TAB 0 : ➕ SAISIR UN PV & GRANULOMETRIE TYPE LPEE
    # ---------------------------------------------------------
    with tabs[0]:
        st.subheader("➕ Saisie PV & Feuille d'Essai Granulométrique (NM 00.8.082)")
        c1, c2, c3 = st.columns(3)
        with c1:
            num_rapport = st.text_input("N° Rapport", value="25/260/LGV/CS/IDENT/001", disabled=not user_can_edit)
            lieu = st.text_input("Lieu / Zone", value="Zone T4 / Remblai d'apport", disabled=not user_can_edit)
        with c2:
            pk = st.text_input("PK / Section", value="PK 8+540", disabled=not user_can_edit)
            date_essai = st.date_input("Date Essai", value=datetime.date.today(), disabled=not user_can_edit)
        with c3:
            type_mat = st.selectbox(
                "Type de matériau",
                ["Sol - GNF 1 (Remblai / GNF type 1)", "Sol (Standard)", "Grave"],
                disabled=not user_can_edit
            )

        st.markdown("---")
        is_sol = "Sol" in type_mat
        obs = "Conforme"
        data_dict = {}

        if is_sol:
            st.subheader("🧪 Entête Masses Globales (g)")
            gm1, gm2, gm3, gm4, gre = st.columns(5)
            with gm1:
                m1_val = st.number_input("Masse sèche totale M1", value=13435.4, step=0.1, disabled=not user_can_edit)
            with gm2:
                m2_val = st.number_input("Masse sèche étuve M2", value=12918.7, step=0.1, disabled=not user_can_edit)
            with gm3:
                m3_val = st.number_input("Masse lavage M3", value=10079.7, step=0.1, disabled=not user_can_edit)
            with gm4:
                m4_val = st.number_input("Prise tamisage M4", value=1930.0, step=1.0, disabled=not user_can_edit)
            with gre:
                re_val = st.number_input("Refus Re (10mm)", value=6012.8, step=1.0, disabled=not user_can_edit)

            a_factor = (m3_val - re_val) / m4_val if m4_val > 0 else 0

            st.markdown("### 📊 Tableau des Refus par Tamis (NM 00.8.082)")
            sieves_data = [
                (80, 0.0), (63, 2141.3), (50, 1743.5), (40, 753.3), (31.5, 183.5),
                (25, 250.3), (20, 296.8), (16, 287.1), (12.5, 147.0), (10, 6012.8),
                (8, 72.4), (6.3, 151.0), (5, 197.6), (4, 238.5), (3.15, 278.4),
                (2.5, 321.6), (2, 361.1), (1.6, 401.9), (1.25, 445.4), (1, 483.1),
                (0.8, 524.9), (0.63, 563.3), (0.5, 624.5), (0.4, 683.8), (0.315, 857.0),
                (0.25, 1141.6), (0.2, 1403.9), (0.16, 1642.3), (0.1, 1809.4), (0.08, 1919.2)
            ]
            df_tamis_input = pd.DataFrame(sieves_data, columns=["Ouverture (mm)", "Refus R_i ou r_i (g)"])
            
            edited_df = st.data_editor(
                df_tamis_input,
                disabled=["Ouverture (mm)"] if not user_can_edit else [],
                use_container_width=True,
                height=350
            )

            # Calculs automatiques cumulés & passant
            refus_vals = edited_df["Refus R_i ou r_i (g)"].values
            cum_refus = np.cumsum(refus_vals)
            pct_refus_cum = (cum_refus / m2_val) * 100.0 if m2_val > 0 else np.zeros_like(cum_refus)
            pct_passant = 100.0 - pct_refus_cum

            edited_df["Refus Cumulé (g)"] = np.round(cum_refus, 1)
            edited_df["% Refus Cumulé"] = np.round(pct_refus_cum, 1)
            edited_df["% Passant"] = np.round(pct_passant, 1)

            st.dataframe(edited_df, use_container_width=True)

            # Extraction valeurs clés
            dmax_detected = float(edited_df[edited_df["Refus R_i ou r_i (g)"] > 0]["Ouverture (mm)"].max()) if any(edited_df["Refus R_i ou r_i (g)"] > 0) else 50.0
            row_80um = edited_df[edited_df["Ouverture (mm)"] == 0.08]
            pass_80um_val = float(row_80um["% Passant"].values[0]) if not row_80um.empty else 22.2

            st.markdown("### 🧪 Atterberg & GTR Auto")
            gp1, gp2, gp3 = st.columns(3)
            with gp1:
                w_l = st.number_input("wL (%)", value=35.0, step=0.5, disabled=not user_can_email if 'email' in locals() else not user_can_edit)
            with gp2:
                w_p = st.number_input("wP (%)", value=20.0, step=0.5, disabled=not user_can_edit)
            with gp3:
                ip = w_l - w_p
                st.metric("Indice plasticité IP", f"{ip:.1f} %")

            gv1, gv2, gv3 = st.columns(3)
            with gv1:
                vbs_val = st.number_input("VBS", value=0.5, step=0.1, disabled=not user_can_edit)
            with gv2:
                es_val = st.selectbox("Équivalent de sable (ES)", ["ESV > 60 (Propre)", "40 < ESV <= 60 (Acceptable)", "ESV <= 40 / EST"], disabled=not user_can_edit)
            with gv3:
                classe_gtr_auto = classer_gtr(dmax_detected, pass_80um_val, ip, vbs_val)
                st.metric("Classe GTR (Auto)", classe_gtr_auto)

            m6_sim = a_factor * (cum_refus[-1] if len(cum_refus)>0 else 0) + re_val
            val_ecart = abs(100.0 * (m3_val - m6_sim) / m3_val) if m3_val > 0 else 0.0
            is_gnf1_conf = (pass_80um_val <= 35.0) and (ip < 25)
            obs = f"Conforme GNF 1 (Passant 80µm={pass_80um_val:.1f}%)" if is_gnf1_conf else "Non Conforme GNF 1"

            st.write(f"**Dmax détecté** : `{dmax_detected} mm` | **Passant 80µm** : `{pass_80um_val:.1f}%` | **Écart fermeture** : `{val_ecart:.2f}%`")

            data_dict = {
                "Type Matériau": type_mat,
                "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}", "M3 (g)": f"{m3_val}", "M4 (g)": f"{m4_val}", "Re (g)": f"{re_val}",
                "Facteur a": f"{a_factor:.4f}",
                "Dmax (mm)": f"{dmax_detected}", "Passant 80µm (%)": f"{pass_80um_val:.1f}",
                "wL (%)": f"{w_l}", "wP (%)": f"{w_p}", "IP (%)": f"{ip:.1f}",
                "VBS": f"{vbs_val}", "ES": es_val,
                "Classe GTR (Auto)": classe_gtr_auto,
                "Observation": obs
            }
        else:
            st.subheader("Paramètres d'identification - Grave")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                la = st.number_input("Los Angeles (LA)", value=25.0, step=1.0, disabled=not user_can_edit)
                md = st.number_input("Micro-Deval humide (MDE)", value=18.0, step=1.0, disabled=not user_can_edit)
            with col_g2:
                es_grav = st.selectbox("ES à 10% / Piston (Grave)", ["ES >= 75", "ES < 75"], disabled=not user_can_edit)

            obs = "Conforme" if la <= 30 and md <= 20 else "Non Conforme"
            data_dict = {
                "Type": "Grave",
                "Los Angeles (LA)": f"{la}", "Micro-Deval (MDE)": f"{md}",
                "ES Grave": es_grav, "Observation": obs
            }

        st.info(f"Observation automatique : **{obs}**")
        header_info = {"num_rapport": num_rapport, "lieu": lieu, "pk": pk, "date_essai": str(date_essai)}

        pdf_bytes = generate_pdf(header_info, data_dict, type_mat.split()[0])
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📄 Télécharger PV (PDF)", data=pdf_bytes, file_name=f"PV_Granulo_{num_rapport.replace('/','_')}.pdf", mime="application/pdf", use_container_width=True)
        with col_d2:
            if st.button("💾 Enregistrer dans Supabase", type="primary", use_container_width=True, disabled=not user_can_edit):
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").upsert({
                            "num_rapport": num_rapport,
                            "type_materiau": "SOL" if is_sol else "GRAVE",
                            "lieu": lieu,
                            "pk": pk,
                            "date_essai": str(date_essai),
                            "details": data_dict,
                            "observation": obs
                        }).execute()
                        st.success("✅ PV enregistré avec succès !")
                    except Exception as e:
                        st.error(f"Erreur Supabase : {e}")

    # ---------------------------------------------------------
    # TAB 1 : 📋 PVS / HISTORIQUE, CONSULTATION & ADMINISTRATION
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
    # TAB 2 : 📊 SYNTHÈSE
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
                    m2.metric("Conformes", len(df_s[df_s["observation"].str.contains("Conforme", na=False)]) if "observation" in df_s else 0)
                    
                    sol_count = len(df_s[df_s['type_materiau']=='SOL']) if 'type_materiau' in df_s else 0
                    grav_count = len(df_s[df_s['type_materiau']=='GRAVE']) if 'type_materiau' in df_s else 0
                    m3.metric("Type Sol / Grave", f"{sol_count} / {grav_count}")
                    
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
