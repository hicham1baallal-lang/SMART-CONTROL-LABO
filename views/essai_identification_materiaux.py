import datetime
import io
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as f_st
from fpdf import FPDF


def _get_subclass_1st_table(pass_80um, ip, vbs, pass_2mm):
    """Sous-classification fine issue du diagramme dmax <= 50 mm."""
    if pass_80um >= 35.0:
        if ip < 12: return "A1"
        elif ip < 25: return "A2"
        elif ip < 40: return "A3"
        else: return "A4"
    elif pass_80um >= 12.0:
        return "B5" if vbs < 0.2 else "B6"
    else:
        if vbs < 0.1:
            return "D1" if pass_2mm >= 70.0 else "D2"
        elif vbs <= 0.2:
            return "B1"
        elif vbs <= 6.0:
            return "B2"
        else:
            return "B4"


def classer_gtr(dmax, pass_80um, ip, vbs=0.5, pass_2mm=70.0, is_roche=False, roche_type=None, is_organique=False):
    """Classification GTR fidèle au tableau synoptique officiel (tableau IV) avec complément C1/C2 pour dmax > 50."""
    if is_organique:
        return "F"
    
    if is_roche and roche_type:
        rt = roche_type.upper()
        if "CRAIE" in rt: return "R1"
        elif "CALCAIRE" in rt: return "R2"
        elif any(k in rt for k in ["MARNE", "ARGILITE", "PELITE"]): return "R3"
        elif any(k in rt for k in ["GRES", "POUDINGUE", "BRECHE"]): return "R4"
        elif any(k in rt for k in ["SEL", "GEMME", "GYPSE"]): return "R5"
        else: return "R6"

    if dmax <= 50:
        return _get_subclass_1st_table(pass_80um, ip, vbs, pass_2mm)
    else:
        if pass_80um < 12.0 and vbs < 0.1:
            return "D3"
        c_base = "C1" if pass_2mm <= 80.0 else "C2"
        sub_comp = _get_subclass_1st_table(pass_80um, ip, vbs, pass_2mm)
        return f"{c_base}{sub_comp}"


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


def _safe_supabase_fetch(supabase_client):
    if "pv_ident_local_db" not in f_st.session_state:
        f_st.session_state["pv_ident_local_db"] = []
    if not supabase_client:
        return f_st.session_state["pv_ident_local_db"]
    try:
        res = supabase_client.table("pv_identification_materiaux").select("*").order("date_essai", desc=True).execute()
        return res.data if res.data is not None else []
    except Exception:
        return f_st.session_state["pv_ident_local_db"]


def show(supabase_client):
    user_name = str(f_st.session_state.get("user_name", f_st.session_state.get("user", {}).get("username", ""))).upper()
    user_role = str(f_st.session_state.get("role", "")).upper()
    is_admin = ("ADMIN" in user_role) or ("BAALLAL" in user_name)
    user_can_edit = is_admin or ("LABO" in user_role)

    if "pv_ident_local_db" not in f_st.session_state:
        f_st.session_state["pv_ident_local_db"] = []

    f_st.title("🔬 Identification & Granulométrie Sol / GTR")
    f_st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD (Modèle LPEE / NM 00.8.082)")

    if not user_can_edit:
        f_st.warning("🔒 Mode lecture seule. Droits de modification restreints.")

    tabs = f_st.tabs([
        "➕ Saisir un PV & Granulo (Sol)",
        "📋 PVS / Historique, Consultation & Administration",
        "📊 Synthèse"
    ])

    # ---------------------------------------------------------
    # TAB 0 : ➕ SAISIR UN PV & GRANULOMETRIE TYPE LPEE (SOL)
    # ---------------------------------------------------------
    with tabs[0]:
        f_st.subheader("➕ Saisie PV & Feuille d'Essai Granulométrique (Norme LPEE)")
        c1, c2, c3 = f_st.columns(3)
        with c1:
            num_rapport = f_st.text_input("N° Rapport", value="25/260/LGV/CS/IDENT/001", disabled=not user_can_edit)
            lieu = f_st.text_input("Lieu / Zone", value="Stock / Remblai d'apport", disabled=not user_can_edit)
        with c2:
            pk = f_st.text_input("PK / Section", value="PK 8+540", disabled=not user_can_edit)
            date_essai = f_st.date_input("Date Essai", value=datetime.date.today(), disabled=not user_can_edit)
        with c3:
            type_mat = f_st.selectbox(
                "Type de matériau",
                ["Sol - GNF 1 (Remblai / GNF type 1)", "Sol (Standard)", "Grave / Rocheux / Particulier"],
                disabled=not user_can_edit
            )

        f_st.markdown("---")
        is_sol = "Sol" in type_mat
        obs = "Conforme"
        data_dict = {}

        if is_sol:
            f_st.markdown("### 📄 Feuille d'Essai type LPEE — Analyse Granulométrique (Sol)")
            
            col_e1, col_e2, col_e3, col_e4 = f_st.columns(4)
            with col_e1:
                ref_ech = f_st.text_input("Référence Échantillon", value="ECH-SOL-0247", disabled=not user_can_edit)
            with col_e2:
                m1_val = f_st.number_input("Masse totale M1 (g)", value=13435.4, step=0.1, disabled=not user_can_edit)
            with col_e3:
                m2_val = f_st.number_input("Masse sèche étuve M2 (g)", value=12918.7, step=0.1, disabled=not user_can_edit)
            with col_e4:
                m3_val = f_st.number_input("Masse après lavage M3 (g)", value=10079.7, step=0.1, disabled=not user_can_edit)

            f_st.markdown("#### Tableau de Granulométrie & Paramètres associés")
            default_sieves_desc = [
                (80, 0.0, 0.0), (63, 2141.3, 0.0), (50, 3884.8, 0.0), (40, 4638.1, 0.0),
                (31.5, 4821.6, 0.0), (25, 5032.0, 0.0), (20, 5282.0, 0.0), (16, 5579.0, 0.0),
                (12.5, 5866.0, 0.0), (10, 6012.8, 0.0),
                (8, 0.0, 72.4), (6.3, 0.0, 151.0), (5, 0.0, 197.6), (4, 0.0, 238.5),
                (3.15, 0.0, 278.4), (2.5, 0.0, 321.6), (2, 0.0, 361.1), (1.6, 0.0, 401.9),
                (1.25, 0.0, 445.4), (1, 0.0, 483.1), (0.8, 0.0, 524.9), (0.63, 0.0, 563.3),
                (0.5, 0.0, 624.5), (0.4, 0.0, 683.8), (0.315, 0.0, 857.0), (0.25, 0.0, 1141.6),
                (0.2, 0.0, 1403.9), (0.16, 0.0, 1642.3), (0.1, 0.0, 1809.4), (0.08, 0.0, 1919.2)
            ]
            df_template = pd.DataFrame(default_sieves_desc, columns=["Tamis (mm)", "R_i (g) [≥10mm]", "r_i (g) [<10mm]"])
            
            col_main_tbl, col_params_right = f_st.columns([1.3, 0.9])
            
            with col_main_tbl:
                edited_sieve_df = f_st.data_editor(
                    df_template,
                    disabled=["Tamis (mm)"] if not user_can_edit else [],
                    use_container_width=True,
                    height=520,
                    key="sieve_editor_sol_desc"
                )

            try:
                row_10 = edited_sieve_df[np.isclose(edited_sieve_df["Tamis (mm)"].astype(float), 10.0, atol=1e-3)]
                re_val_calc = float(row_10["R_i (g) [≥10mm]"].values[0]) if not row_10.empty else 6012.8
            except Exception:
                re_val_calc = 6012.8
            me_val_calc = m3_val - re_val_calc

            with col_params_right:
                f_st.markdown("##### ⚙️ Paramètres d'analyse")
                m4_val = f_st.number_input("Prise tamisage M4 (g)", value=1930.0, step=1.0, disabled=not user_can_edit)
                re_val = f_st.number_input("Refus R_e (10mm) (g)", value=re_val_calc, disabled=True, key="re_10mm_mod")
                me_val = f_st.number_input("Prise Me (g) [M3-Re]", value=me_val_calc, disabled=True, key="me_val_mod")
                w_l = f_st.number_input("wL (%)", value=35.0, step=0.5, disabled=not user_can_edit)
                w_p = f_st.number_input("wP (%)", value=20.0, step=0.5, disabled=not user_can_edit)

                a_factor = me_val / m4_val if m4_val > 0 else 0
                ip = w_l - w_p
                f_st.markdown(
                    f"""
                    <div style="background-color: #f0f2f6; padding: 10px; border-radius: 6px; font-size: 0.85em;">
                        <b>Coeff. a = Me/M4</b> : {a_factor:.4f}<br>
                        <b>IP</b> : {ip:.1f}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            work_df = edited_sieve_df.sort_values(by="Tamis (mm)", ascending=False).reset_index(drop=True)
            cum_refus_list = []
            
            for idx, row in work_df.iterrows():
                sz = row["Tamis (mm)"]
                r_i_val = row["R_i (g) [≥10mm]"]
                r_fine_val = row["r_i (g) [<10mm]"]
                if sz >= 10:
                    cum_val = r_i_val
                else:
                    cum_val = (r_fine_val * a_factor) + re_val
                cum_refus_list.append(cum_val)
            
            work_df["Refus Cumulé R (g)"] = np.round(cum_refus_list, 1)
            work_df["% Refus Cumulé"] = np.round((work_df["Refus Cumulé R (g)"] / m2_val) * 100.0, 1) if m2_val > 0 else 0.0
            work_df["% Passant"] = np.round(100.0 - work_df["% Refus Cumulé"], 1)

            result_df = work_df.copy()

            f_st.markdown("#### Résultats & Courbe Granulométrique")
            col_tbl_res, col_plt = f_st.columns([1.1, 0.9])
            with col_tbl_res:
                f_st.dataframe(result_df, use_container_width=True, height=420)
            with col_plt:
                fig, ax = plt.subplots(figsize=(5.2, 4.3))
                plot_curve_df = result_df.sort_values(by="Tamis (mm)", ascending=True).reset_index(drop=True)
                
                x_indices = np.arange(len(plot_curve_df))
                sieve_values = plot_curve_df["Tamis (mm)"].values
                
                ticks_positions = []
                ticks_labels = []
                for idx, (x_pos, t_val) in enumerate(zip(x_indices, sieve_values)):
                    if t_val >= 10.0:
                        ticks_positions.append(x_pos)
                        ticks_labels.append(f"{t_val}mm")
                    else:
                        if idx % 3 != 0:
                            ticks_positions.append(x_pos)
                            ticks_labels.append(f"{t_val}mm")

                ax.plot(
                    x_indices, plot_curve_df["% Passant"],
                    marker='o', markersize=4, linestyle='-', color='#1f77b4', linewidth=1.5
                )
                ax.set_xticks(ticks_positions)
                ax.set_xticklabels(ticks_labels, rotation=70, ha='right', fontsize=7)
                ax.set_xlabel("Ouverture des tamis (mm)")
                ax.set_ylabel("% Passant (%)")
                ax.set_ylim(-2, 105)
                ax.grid(True, which="both", linestyle=":", alpha=0.6)
                fig.tight_layout()
                f_st.pyplot(fig, use_container_width=True)
                plt.close(fig)

            dmax_detected = float(result_df[(result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)]["Tamis (mm)"].max()) if any((result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)) else 50.0
            row_80um = result_df[result_df["Tamis (mm)"] == 0.08]
            pass_80um_val = float(row_80um["% Passant"].values[0]) if not row_80um.empty else 22.2

            row_2mm = result_df[result_df["Tamis (mm)"] == 2.0]
            pass_2mm_val = float(row_2mm["% Passant"].values[0]) if not row_2mm.empty else 70.0

            col_v1, col_v2, col_v3 = f_st.columns(3)
            with col_v1:
                vbs_val = f_st.number_input("VBS", value=0.5, step=0.1, disabled=not user_can_edit)
            with col_v2:
                es_val = f_st.selectbox("Équivalent de sable (ES)", ["ESV > 60 (Propre)", "40 < ESV <= 60 (Acceptable)", "ESV <= 40 / EST"], disabled=not user_can_edit)
            with col_v3:
                classe_gtr_auto = classer_gtr(dmax_detected, pass_80um_val, ip, vbs_val, pass_2mm_val)
                f_st.metric("Classe GTR (Auto - Tableau IV)", classe_gtr_auto)

            row_10_check = result_df[result_df["Tamis (mm)"] == 10]
            m6_sim = float(row_10_check["Refus Cumulé R (g)"].values[0]) if not row_10_check.empty else 0.0
            val_ecart = abs(100.0 * (m3_val - m6_sim) / m3_val) if m3_val > 0 else 0.0
            is_gnf1_conf = (pass_80um_val <= 35.0) and (ip < 25)
            obs = f"Conforme GNF 1 (Passant 80µm={pass_80um_val:.1f}%)" if is_gnf1_conf else "Non Conforme / Hors fuseau"

            f_st.info(f"Observation automatique : **{obs}** | Dmax: **{dmax_detected} mm** | Passant 2mm: **{pass_2mm_val:.1f}%** | Écart de référence 10mm/M3: **{val_ecart:.2f}%**")

            data_dict = {
                "Type Matériau": type_mat,
                "Ref Echantillon": ref_ech,
                "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}", "M3 (g)": f"{m3_val}", "M4 (g)": f"{m4_val}",
                "Re (10mm) (g)": f"{re_val:.1f}", "Me (g)": f"{me_val:.1f}", "Facteur a": f"{a_factor:.4f}",
                "Dmax (mm)": f"{dmax_detected}", "Passant 80µm (%)": f"{pass_80um_val:.1f}", "Passant 2mm (%)": f"{pass_2mm_val:.1f}",
                "wL (%)": f"{w_l}", "wP (%)": f"{w_p}", "IP (%)": f"{ip:.1f}",
                "VBS": f"{vbs_val}", "ES": es_val,
                "Classe GTR (Auto)": classe_gtr_auto,
                "Observation": obs
            }
        else:
            f_st.subheader("Paramètres d'identification - Rocheux / Grave / Particulier")
            sub_mat_type = f_st.radio("Nature spécifique", ["Rocheux (R1-R6)", "Matériaux particuliers (Organiques / F)", "Grave standard"], horizontal=True, disabled=not user_can_edit)
            
            is_roche = False
            roche_type = None
            is_organique = False
            
            col_g1, col_g2 = f_st.columns(2)
            if "Rocheux" in sub_mat_type:
                is_roche = True
                roche_type = f_st.selectbox("Type de roche (Tableau GTR)", ["Craies", "Calcaires", "Roches argileuses (Marnes, argilites, pélites...) ", "Roches siliceuses (Grès, poudingues, brèches...) ", "Roches salines (Sel gemme, gypse) ", "Roches magmatiques et métamorphiques (Granites, basaltes, gneiss...)"], disabled=not user_can_edit)
                with col_g1:
                    la = f_st.number_input("Los Angeles (LA)", value=25.0, step=1.0, disabled=not user_can_edit)
                    md = f_st.number_input("Micro-Deval humide (MDE)", value=18.0, step=1.0, disabled=not user_can_edit)
                with col_g2:
                    es_grav = f_st.selectbox("ES / Piston", ["Conforme", "Non Conforme"], disabled=not user_can_edit)
                obs = "Conforme"
            elif "particuliers" in sub_mat_type:
                is_organique = True
                la, md, es_grav = 0, 0, "N/A"
                obs = "Matériau organique / Particulier"
            else:
                with col_g1:
                    la = f_st.number_input("Los Angeles (LA)", value=25.0, step=1.0, disabled=not user_can_edit)
                    md = f_st.number_input("Micro-Deval humide (MDE)", value=18.0, step=1.0, disabled=not user_can_edit)
                with col_g2:
                    es_grav = f_st.selectbox("ES à 10% / Piston (Grave)", ["ES >= 75", "ES < 75"], disabled=not user_can_edit)
                obs = "Conforme" if la <= 30 and md <= 20 else "Non Conforme"

            classe_gtr_auto = classer_gtr(dmax=0, pass_80um=0, ip=0, is_roche=is_roche, roche_type=roche_type, is_organique=is_organique)
            f_st.metric("Classe GTR (Auto - Tableau IV)", classe_gtr_auto)

            data_dict = {
                "Type": sub_mat_type,
                "Sous-type Roche / Particulier": roche_type if is_roche else ("Organique/F" if is_organique else "Grave"),
                "Los Angeles (LA)": f"{la}", "Micro-Deval (MDE)": f"{md}",
                "ES Grave": es_grav, "Classe GTR (Auto)": classe_gtr_auto, "Observation": obs
            }

        header_info = {"num_rapport": num_rapport, "lieu": lieu, "pk": pk, "date_essai": str(date_essai)}
        pdf_bytes = generate_pdf(header_info, data_dict, type_mat.split()[0])
        
        col_d1, col_d2 = f_st.columns(2)
        with col_d1:
            f_st.download_button("📄 Télécharger PV (PDF)", data=pdf_bytes, file_name=f"PV_Granulo_Sol_{num_rapport.replace('/','_')}.pdf", mime="application/pdf", use_container_width=True)
        with col_d2:
            if f_st.button("💾 Enregistrer dans Supabase", type="primary", use_container_width=True, disabled=not user_can_edit):
                payload_record = {
                    "num_rapport": num_rapport,
                    "type_materiau": "SOL" if is_sol else "GRAVE_ROCHE",
                    "lieu": lieu,
                    "pk": pk,
                    "date_essai": str(date_essai),
                    "details": data_dict,
                    "observation": obs
                }
                saved_to_db = False
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").upsert(payload_record).execute()
                        saved_to_db = True
                    except Exception:
                        saved_to_db = False
                
                f_st.session_state["pv_ident_local_db"] = [
                    r for r in f_st.session_state["pv_ident_local_db"] if r.get("num_rapport") != num_rapport
                ]
                f_st.session_state["pv_ident_local_db"].insert(0, payload_record)
                
                if saved_to_db:
                    f_st.success("✅ PV enregistré avec succès dans Supabase !")
                else:
                    f_st.warning("⚠️ Table Supabase non trouvée/inaccessible (PGRST205) -> Enregistré en mémoire locale session.")

    # ---------------------------------------------------------
    # TAB 1 : 📋 PVS / HISTORIQUE, CONSULTATION & ADMINISTRATION
    # ---------------------------------------------------------
    with tabs:
        f_st.subheader("📋 PVS / Historique, Consultation & Administration")
        raw_data = _safe_supabase_fetch(supabase_client)
        if not raw_data and not f_st.session_state["pv_ident_local_db"]:
            f_st.info("💡 Aucun PV d'identification enregistré.")
        else:
            combined_records = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
            df_hist = pd.DataFrame(combined_records)
            search_q = f_st.text_input("Filtrer par N° Rapport ou Lieu :").lower()
            if search_q:
                df_hist = df_hist[df_hist.apply(lambda r: search_q in str(r.values).lower(), axis=1)]
            f_st.dataframe(df_hist, use_container_width=True)

            selected_del = f_st.selectbox("Sélectionner un PV à supprimer (Admin/Labo)", options=[""] + df_hist["num_rapport"].tolist() if "num_rapport" in df_hist else [])
            if selected_del and f_st.button("🗑️ Supprimer ce PV", disabled=not user_can_edit):
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").delete().eq("num_rapport", selected_del).execute()
                    except Exception:
                        pass
                f_st.session_state["pv_ident_local_db"] = [
                    r for r in f_st.session_state["pv_ident_local_db"] if r.get("num_rapport"] != selected_del
                ]
                f_st.success(f"PV {selected_del} supprimé.")
                f_st.rerun()

    # ---------------------------------------------------------
    # TAB 2 : 📊 SYNTHÈSE
    # ---------------------------------------------------------
    with tabs[2]:
        f_st.subheader("📊 Synthèse Identification Matériaux")
        raw_data = _safe_supabase_fetch(supabase_client)
        data_to_use = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
        if data_to_use:
            df_s = pd.DataFrame(data_to_use)
            m1, m2, m3 = f_st.columns(3)
            m1.metric("Total PVs Ident.", len(df_s))
            m2.metric("Conformes", len(df_s[df_s["observation"].str.contains("Conforme", na=False)]) if "observation" in df_s else 0)
            
            sol_count = len(df_s[df_s['type_materiau']=='SOL']) if 'type_materiau' in df_s else 0
            grav_count = len(df_s[df_s['type_materiau']=='GRAVE_ROCHE']) if 'type_materiau' in df_s else 0
            m3.metric("Type Sol / Grave-Roche", f"{sol_count} / {grav_count}")
            
            f_st.dataframe(df_s, use_container_width=True)
            
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as w:
                df_s.to_excel(w, index=False, sheet_name='Synthese_Identification')
            excel_buf.seek(0)
            f_st.download_button(
                "📥 Télécharger la synthèse en Excel (.xlsx)",
                data=excel_buf,
                file_name=f"synthese_identification_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        else:
            f_st.info("Aucune donnée disponible pour la synthèse.")
