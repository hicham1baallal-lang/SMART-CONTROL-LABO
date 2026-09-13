import datetime
import io
import os
import matplotlib.pyplot as plt
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
    pdf.cell(190, 8, " II - Synthèse Granulométrique & GTR (NM 00.8.082 / LPEE)", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 9)
    for k, v in data_dict.items():
        pdf.cell(95, 7, f"   {str(k)[:40]}", 1, 0, "L")
        pdf.cell(95, 7, f"   {str(v)[:40]}", 1, 1, "L")
    
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

    st.title("🔬 Identification & Granulométrie Sol / GTR")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD (Modèle LPEE / NM 00.8.082)")

    if not user_can_edit:
        st.warning("🔒 Mode lecture seule. Droits de modification restreints.")

    tabs = st.tabs([
        "➕ Saisir un PV & Granulo (Sol)",
        "📋 PVS / Historique, Consultation & Administration",
        "📊 Synthèse"
    ])

    # ---------------------------------------------------------
    # TAB 0 : ➕ SAISIR UN PV & GRANULOMETRIE TYPE LPEE (SOL)
    # ---------------------------------------------------------
    with tabs[0]:
        st.subheader("➕ Saisie PV & Feuille d'Essai Granulométrique (Norme LPEE)")
        c1, c2, c3 = st.columns(3)
        with c1:
            num_rapport = st.text_input("N° Rapport", value="25/260/LGV/CS/IDENT/001", disabled=not user_can_edit)
            lieu = st.text_input("Lieu / Zone", value="Stock / Remblai d'apport", disabled=not user_can_edit)
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
            st.markdown("### 📄 Feuille d'Essai type LPEE — Analyse Granulométrique (Sol)")
            
            col_e1, col_e2, col_e3, col_e4 = st.columns(4)
            with col_e1:
                ref_ech = st.text_input("Référence Échantillon", value="ECH-SOL-0247", disabled=not user_can_edit)
            with col_e2:
                m1_val = st.number_input("Masse totale M1 (g)", value=13435.4, step=0.1, disabled=not user_can_edit)
            with col_e3:
                m2_val = st.number_input("Masse sèche étuve M2 (g)", value=12918.7, step=0.1, disabled=not user_can_edit)
            with col_e4:
                m3_val = st.number_input("Masse après lavage M3 (g)", value=10079.7, step=0.1, disabled=not user_can_edit)

            st.markdown("#### Tableau de Granulométrie (R_i pour ≥10 mm, r_i pour <10 mm)")
            default_sieves = [
                (80, 0.0, 0.0), (63, 2141.3, 0.0), (50, 1743.5, 0.0), (40, 753.3, 0.0),
                (31.5, 183.5, 0.0), (25, 250.3, 0.0), (20, 296.8, 0.0), (16, 287.1, 0.0),
                (12.5, 147.0, 0.0), (10, 6012.8, 0.0),
                (8, 0.0, 72.4), (6.3, 0.0, 151.0), (5, 0.0, 197.6), (4, 0.0, 238.5),
                (3.15, 0.0, 278.4), (2.5, 0.0, 321.6), (2, 0.0, 361.1), (1.6, 0.0, 401.9),
                (1.25, 0.0, 445.4), (1, 0.0, 483.1), (0.8, 0.0, 524.9), (0.63, 0.0, 563.3),
                (0.5, 0.0, 624.5), (0.4, 0.0, 683.8), (0.315, 0.0, 857.0), (0.25, 0.0, 1141.6),
                (0.2, 0.0, 1403.9), (0.16, 0.0, 1642.3), (0.1, 0.0, 1809.4), (0.08, 0.0, 1919.2)
            ]
            df_template = pd.DataFrame(default_sieves, columns=["Tamis (mm)", "R_i (g) [≥10mm]", "r_i (g) [<10mm]"])
            
            edited_sieve_df = st.data_editor(
                df_template,
                disabled=["Tamis (mm)"] if not user_can_edit else [],
                use_container_width=True,
                height=380,
                key="sieve_editor_sol"
            )

            row_10mm = edited_sieve_df[edited_sieve_df["Tamis (mm)"] == 10]
            re_val = float(row_10mm["R_i (g) [≥10mm]"].values[0]) if not row_10mm.empty else 0.0
            me_val = m3_val - re_val

            col_e5, col_e6, col_e6b, col_e7, col_e8 = st.columns(5)
            with col_e5:
                m4_val = st.number_input("Prise tamisage M4 (g)", value=1930.0, step=1.0, disabled=not user_can_edit)
            with col_e6:
                st.number_input("Refus R_e (10mm) (g)", value=re_val, disabled=True, key="re_10mm_non_mod")
            with col_e6b:
                st.number_input("Prise Me (g) [M3-Re]", value=me_val, disabled=True, key="me_val_non_mod")
            with col_e7:
                w_l = st.number_input("wL (%)", value=35.0, step=0.5, disabled=not user_can_edit)
            with col_e8:
                w_p = st.number_input("wP (%)", value=20.0, step=0.5, disabled=not user_can_edit)

            a_factor = me_val / m4_val if m4_val > 0 else 0
            ip = w_l - w_p

            st.markdown(f"**Refus R_e (10mm) calculé** : `{re_val:.1f} g` | **Prise Me (M3-Re)** : `{me_val:.1f} g` | **Coefficient a = Me/M4** : `{a_factor:.4f}` | **IP** : `{ip:.1f}%`")

            R_vals = edited_sieve_df["R_i (g) [≥10mm]"].values
            r_vals = edited_sieve_df["r_i (g) [<10mm]"].values
            sieve_sz = edited_sieve_df["Tamis (mm)"].values

            effective_refus = np.where(sieve_sz >= 10, R_vals, r_vals * a_factor)
            cum_refus = np.cumsum(effective_refus)
            pct_refus_cum = (cum_refus / m2_val) * 100.0 if m2_val > 0 else np.zeros_like(cum_refus)
            pct_passant = 100.0 - pct_refus_cum

            result_df = edited_sieve_df.copy()
            result_df["Refus Cumulé R (g)"] = np.round(cum_refus, 1)
            result_df["% Refus Cumulé"] = np.round(pct_refus_cum, 1)
            result_df["% Passant"] = np.round(pct_passant, 1)

            # Tri par ordre croissant de taille de tamis (0.08mm à gauche -> 80mm à droite)
            plot_df = result_df.sort_values(by="Tamis (mm)", ascending=True).reset_index(drop=True)

            # Disposition côte à côte : Tableau / Courbe
            col_tbl, col_plt = st.columns([1.1, 0.9])
            with col_tbl:
                st.dataframe(result_df, use_container_width=True, height=420)
            with col_plt:
                st.markdown("#### Courbe Granulométrique (0.08mm → 80mm)")
                fig, ax = plt.subplots(figsize=(5.2, 4.3))
                sieve_labels = [f"{t}mm" for t in plot_df["Tamis (mm)"]]
                x_indices = np.arange(len(plot_df))
                ax.plot(
                    x_indices, plot_df["% Passant"],
                    marker='o', markersize=4, linestyle='-', color='#1f77b4', linewidth=1.5
                )
                ax.set_xticks(x_indices)
                ax.set_xticklabels(sieve_labels, rotation=75, ha='right', fontsize=7)
                ax.set_xlabel("Ouverture des tamis (mm)")
                ax.set_ylabel("% Passant (%)")
                ax.set_ylim(-2, 105)
                ax.grid(True, which="both", linestyle=":", alpha=0.6)
                fig.tight_layout()
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)

            dmax_detected = float(result_df[(result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)]["Tamis (mm)"].max()) if any((result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)) else 50.0
            row_80um = result_df[result_df["Tamis (mm)"] == 0.08]
            pass_80um_val = float(row_80um["% Passant"].values[0]) if not row_80um.empty else 22.2

            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                vbs_val = st.number_input("VBS", value=0.5, step=0.1, disabled=not user_can_edit)
            with col_v2:
                es_val = st.selectbox("Équivalent de sable (ES)", ["ESV > 60 (Propre)", "40 < ESV <= 60 (Acceptable)", "ESV <= 40 / EST"], disabled=not user_can_edit)
            with col_v3:
                classe_gtr_auto = classer_gtr(dmax_detected, pass_80um_val, ip, vbs_val)
                st.metric("Classe GTR (Auto)", classe_gtr_auto)

            m6_sim = cum_refus[-1] if len(cum_refus) > 0 else 0
            val_ecart = abs(100.0 * (m3_val - m6_sim) / m3_val) if m3_val > 0 else 0.0
            is_gnf1_conf = (pass_80um_val <= 35.0) and (ip < 25)
            obs = f"Conforme GNF 1 (Passant 80µm={pass_80um_val:.1f}%)" if is_gnf1_conf else "Non Conforme / Hors fuseau"

            st.info(f"Observation automatique : **{obs}** | Dmax: **{dmax_detected} mm** | Écart de fermeture: **{val_ecart:.2f}%**")

            data_dict = {
                "Type Matériau": type_mat,
                "Ref Echantillon": ref_ech,
                "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}", "M3 (g)": f"{m3_val}", "M4 (g)": f"{m4_val}",
                "Re (10mm) (g)": f"{re_val:.1f}", "Me (g)": f"{me_val:.1f}", "Facteur a": f"{a_factor:.4f}",
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

        header_info = {"num_rapport": num_rapport, "lieu": lieu, "pk": pk, "date_essai": str(date_essai)}
        pdf_bytes = generate_pdf(header_info, data_dict, type_mat.split()[0])
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📄 Télécharger PV (PDF)", data=pdf_bytes, file_name=f"PV_Granulo_Sol_{num_rapport.replace('/','_')}.pdf", mime="application/pdf", use_container_width=True)
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
