import datetime
import io
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.drawing.image import Image as OpenpyxlImage
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
        return "B5" if vbs < 1.5 else "B6"
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
    """Classification GTR officielle avec complément C1/C2 pour dmax > 50 mm."""
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
        if not os.path.exists(logo_path):
            logo_path = "logo.png"
        if os.path.exists(logo_path):
            try:
                self.image(logo_path, 10, 5, 18)
            except Exception:
                pass
        
        self.set_font("Helvetica", "B", 11)
        self.set_xy(10, 5)
        self.cell(190, 4.5, "L.P.E.E - LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES", 0, 1, "C")
        
        self.set_font("Helvetica", "", 8.5)
        self.set_x(10)
        self.cell(190, 4, "Centre Technique Régional CASA-SETTAT-BENI MELLAL", 0, 1, "C")
        
        self.line(10, 18, 200, 18)
        
        self.set_xy(10, 21)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 51, 102)
        self.multi_cell(190, 4.5, "RAPPORT D'ESSAI D'IDENTIFICATION\nDES MATÉRIAUX", 0, "C")
        self.set_text_color(0, 0, 0)
        
        self.line(10, 32, 200, 32)
        self.set_xy(10, 34)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.cell(0, 8, f"CTR-CSB - Projet LGV CASA SUD | Page {self.page_no()}/{{nb}}", 0, 0, "C")


def generate_pdf(header_info, data_dict, type_mat, curve_img_path=None):
    pdf = IdentificationPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    if not data_dict or not isinstance(data_dict, dict):
        data_dict = {
            "Ref Echantillon": "Ech 1",
            "Passant 80um (%)": "22,3",
            "Passant 2mm (%)": "66",
            "Passant 50mm (%)": "100",
            "Dmax (mm)": "50",
            "VBS": "0,42",
            "wL (%)": "14,2",
            "IP (%)": "4,2",
            "Densité OPN": "1,73",
            "Classe GTR (Auto)": "B5",
            "Observation": "Le matériau peut être utilisé pour un remblai."
        }
    
    pdf.set_font("Helvetica", "B", 7)
    pdf.multi_cell(190, 3.5, "TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000 - GARE CASA SUD", 0, "C")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 8)
    pdf.cell(95, 5.5, f" Client : TGCC", 1, 0, "L")
    pdf.cell(95, 5.5, f" Rapport d'Essai N° : {header_info.get('num_rapport') or 'N/A'}", 1, 1, "L")
    pdf.cell(95, 5.5, f" Dossier : 2025-260-05985-2025-0247", 1, 0, "L")
    pdf.cell(95, 5.5, f" Date du prélèvement : {header_info.get('date_essai') or ''}", 1, 1, "L")
    pdf.cell(95, 5.5, f" Lieux de prélèvement : {header_info.get('lieu') or 'Stock sur chantier'}", 1, 0, "L")
    pdf.cell(95, 5.5, f" Provenance d'échantillon : {header_info.get('pk') or ''}", 1, 1, "L")
    pdf.cell(190, 5.5, f" Objet : IDENTIFICATION DU MATÉRIAU ({str(type_mat).upper()})", 1, 1, "L")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(190, 4.5, " Normes : A.G: NM 00.8.082 | IP: NF P94-051 | VBS: NM 13.1.178 | LOS ANGELES: NM EN 1097-2 | MDE: NM EN 1097-1", 1, 1, "L")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(190, 5.5, " Résultats d'essais", 1, 1, "C", fill=True)
    
    ech_label = data_dict.get('Ref Echantillon', 'Ech 1')
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(60, 5.5, "", 1, 0, "C", fill=True)
    pdf.cell(130, 5.5, str(ech_label), 1, 1, "C", fill=True)

    val_80um = str(data_dict.get('Passant 80um (%)', data_dict.get('Passant 80µm (%)', '22,3')))
    val_2mm = str(data_dict.get('Passant 2mm (%)', '66'))
    val_50mm = str(data_dict.get('Passant 50mm (%)', '100'))
    val_dmax = str(data_dict.get('Dmax (mm)', '50'))
    val_vbs = str(data_dict.get('VBS', '0,42'))
    val_wopt = str(data_dict.get('wL (%)', '14,2'))
    val_ip = str(data_dict.get('IP (%)', '4,2'))
    val_dens = str(data_dict.get('Densité OPN', '1,73'))
    val_gtr = str(data_dict.get('Classe GTR (Auto)', 'B5'))

    pdf.set_font("Helvetica", "", 7.5)

    pdf.cell(60, 5, " %< 80 µm", 1, 0, "L")
    pdf.cell(130, 5, val_80um, 1, 1, "C")

    pdf.cell(60, 5, " %< 2 mm", 1, 0, "L")
    pdf.cell(130, 5, val_2mm, 1, 1, "C")

    pdf.cell(60, 5, " %< 50 mm", 1, 0, "L")
    pdf.cell(130, 5, val_50mm, 1, 1, "C")

    pdf.cell(60, 5, " D MAX", 1, 0, "L")
    pdf.cell(130, 5, val_dmax, 1, 1, "C")

    pdf.cell(60, 5, " VBS", 1, 0, "L")
    pdf.cell(130, 5, val_vbs, 1, 1, "C")

    pdf.cell(60, 5, " Indice de Plasticité (IP)", 1, 0, "L")
    pdf.cell(130, 5, val_ip, 1, 1, "C")

    pdf.cell(60, 5, " Proctor", 1, 0, "L")
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(26, 5, " Wopt", 1, 0, "C", fill=True)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(26, 5, val_wopt, 1, 0, "C")
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(34, 5, " Densité OPN", 1, 0, "C", fill=True)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(44, 5, val_dens, 1, 1, "C")

    pdf.cell(60, 5, " GTR", 1, 0, "L")
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(130, 5, val_gtr, 1, 1, "C")

    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(190, 5, " COURBE GRANULOMÉTRIQUE", 1, 1, "L", fill=True)
    if curve_img_path and os.path.exists(curve_img_path):
        try:
            pdf.image(curve_img_path, x=10, y=pdf.get_y() + 1, w=190, h=6.2 * 10)
            pdf.ln(64)
        except Exception:
            pdf.cell(190, 62, "[Erreur d'insertion de la courbe]", 1, 1, "C")
    else:
        pdf.cell(190, 62, "[Courbe non disponible]", 1, 1, "C")
    
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(190, 5, " Commentaires :", 1, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 7.5)
    obs_text = data_dict.get('Observation', 'Le matériau peut être utilisé pour un remblai.')
    pdf.multi_cell(190, 4, f" - Observation : {obs_text}\n - .", 1, "L")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 4.5, "LE REÇU PAR LE CLIENT", 1, 0, "C", fill=True)
    pdf.cell(63, 4.5, "LE COORDINATEUR DES ESSAIS", 1, 0, "C", fill=True)
    pdf.cell(64, 4.5, "LE CHEF DU LABORATOIRE", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(63, 10, "Nom : ", 1, 0, "L")
    pdf.cell(63, 10, "Nom : B. ELAMRI", 1, 0, "L")
    pdf.cell(64, 10, "Nom : H. BAALLAL", 1, 1, "L")

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

    selected_mat_sub = f_st.session_state.get("sub_page_identification", "Remblai ordinaire")

    f_st.title("🔬 Identification & Granulométrie des Matériaux")
    f_st.subheader(f"📌 Sous-catégorie sélectionnée : **{selected_mat_sub}**")
    f_st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD (Modèle LPEE / NM 00.8.082)")

    if not user_can_edit:
        f_st.warning("🔒 Mode lecture seule. Droits de modification restreints.")

    tab_saisir, tab_hist, tab_synth = f_st.tabs([
        f"➕ Saisir Essai ({selected_mat_sub})",
        "📋 PVs / Historique & Administration",
        "📊 Synthèse Globale"
    ])

    # ---------------------------------------------------------
    # TAB 0 : ➕ SAISIE D'UN PV
    # ---------------------------------------------------------
    with tab_saisir:
        f_st.subheader(f"➕ Saisie PV d'identification — {selected_mat_sub}")
        
        c1, c2, c3 = f_st.columns(3)
        with c1:
            num_rapport = f_st.text_input("N° Rapport", value="25/260/LGV/CS/1150", disabled=not user_can_edit)
            lieu = f_st.text_input("Lieu / Zone", value="Stock sur chantier (Zone T4)", disabled=not user_can_edit)
        with c2:
            pk = f_st.text_input("Provenance d'échantillon", value="PK 5+450 à PK 10+000", disabled=not user_can_edit)
            date_essai = f_st.date_input("Date du prélèvement", value=datetime.date.today(), disabled=not user_can_edit)
        with c3:
            ref_ech = f_st.text_input("Référence Échantillon", value="Ech 1", disabled=not user_can_edit)

        f_st.markdown("---")
        
        f_st.markdown("### 📄 Feuille d'Analyse Granulométrique & Propriétés physiques")
        
        col_e1, col_e2, col_e3, col_e4 = f_st.columns(4)
        with col_e1:
            m1_val = f_st.number_input("Masse totale M1 (g)", value=14000.0, step=0.1, disabled=not user_can_edit)
        with col_e2:
            m2_val = f_st.number_input("Masse sèche étuve M2 (g)", value=13500.0, step=0.1, disabled=not user_can_edit)
        with col_e3:
            m3_val = f_st.number_input("Masse après lavage M3 (g)", value=11200.0, step=0.1, disabled=not user_can_edit)
        with col_e4:
            m4_val = f_st.number_input("Prise tamisage M4 (g)", value=2000.0, step=1.0, disabled=not user_can_edit)

        f_st.markdown("#### Tableau de Tamisage & Refus")
        default_sieves_desc = [
            (80, 0.0, 0.0), (63, 0.0, 0.0), (50, 0.0, 0.0), (40, 2500.0, 0.0),
            (31.5, 3800.0, 0.0), (25, 4500.0, 0.0), (20, 5200.0, 0.0), (16, 5800.0, 0.0),
            (12.5, 6200.0, 0.0), (10, 6500.0, 0.0),
            (8, 0.0, 80.0), (6.3, 0.0, 160.0), (5, 0.0, 210.0), (4, 0.0, 260.0),
            (3.15, 0.0, 310.0), (2.5, 0.0, 350.0), (2, 0.0, 400.0), (1.6, 0.0, 450.0),
            (1.25, 0.0, 500.0), (1, 0.0, 550.0), (0.8, 0.0, 600.0), (0.63, 0.0, 650.0),
            (0.5, 0.0, 700.0), (0.4, 0.0, 780.0), (0.315, 0.0, 900.0), (0.25, 0.0, 1100.0),
            (0.2, 0.0, 1300.0), (0.16, 0.0, 1500.0), (0.1, 0.0, 1700.0), (0.08, 0.0, 1850.0)
        ]
        df_template = pd.DataFrame(default_sieves_desc, columns=["Tamis (mm)", "R_i (g) [≥10mm]", "r_i (g) [<10mm]"])
        
        col_main_tbl, col_params_right = f_st.columns([1.3, 0.9])
        
        with col_main_tbl:
            edited_sieve_df = f_st.data_editor(
                df_template,
                disabled=["Tamis (mm)"] if not user_can_edit else [],
                use_container_width=True,
                height=500,
                key=f"sieve_editor_{selected_mat_sub.replace(' ', '_')}"
            )

        try:
            row_10 = edited_sieve_df[np.isclose(edited_sieve_df["Tamis (mm)"].astype(float), 10.0, atol=1e-3)]
            re_val_calc = float(row_10["R_i (g) [≥10mm]"].values[0]) if not row_10.empty else 6500.0
        except Exception:
            re_val_calc = 6500.0
        me_val_calc = m3_val - re_val_calc

        with col_params_right:
            f_st.markdown("##### ⚙️ Caractéristiques, Limites & Paramètres Spécifiques")
            re_val = f_st.number_input("Refus R_e (10mm) (g)", value=re_val_calc, disabled=True, key="re_10mm_mat")
            me_val = f_st.number_input("Prise Me (g) [M3-Re]", value=me_val_calc, disabled=True, key="me_val_mat")
            
            fond_tamis_val = f_st.number_input("Fond de tamis (g)", value=1.4, step=0.1, disabled=not user_can_edit)
            
            # Calcul automatique de M5 (Refus du tamis 0.08 mm + Fond de tamis)
            try:
                row_008 = edited_sieve_df[np.isclose(edited_sieve_df["Tamis (mm)"].astype(float), 0.08, atol=1e-3)]
                r_008_val = float(row_008["r_i (g) [<10mm]"].values[0]) if not row_008.empty else 1850.0
            except Exception:
                r_008_val = 1850.0
            
            m5_calc = r_008_val + fond_tamis_val
            
            m5_val = f_st.number_input("M5 (Total refus et passant sur 80µm)", value=m5_calc, disabled=True, key="m5_auto_val")
            
            w_opt = f_st.number_input("Proctor Wopt (%)", value=13.2, step=0.5, disabled=not user_can_edit)
            ip = f_st.number_input("Indice de Plasticité (IP)", value=12.0, step=0.5, disabled=not user_can_edit)
            vbs_val = f_st.number_input("VBS (Bleu de Manganèse)", value=1.45, step=0.01, format="%.2f", disabled=not user_can_edit)
            dens_val = f_st.number_input("Proctor Densité OPN", value=1.73, step=0.01, disabled=not user_can_edit)

            a_factor = me_val / m4_val if m4_val > 0 else 0
            m6_val = (a_factor * m5_val) + re_val
            validation_m6 = 100.0 * (m3_val - m6_val) / m3_val if m3_val > 0 else 0.0

            f_st.markdown(
                f"""
                <div style="background-color: #f0f2f6; padding: 10px; border-radius: 6px; font-size: 0.85em;">
                    <b>Facteur a (Me/M4)</b> : {a_factor:.4f}<br>
                    <b>M6 (Masse tamisat)</b> : {m6_val:.2f} g<br>
                    <b>Contrôle 100(M3-M6)/M3</b> : {validation_m6:.2f}% (doit être <2%)<br>
                    <b>Proctor Wopt</b> : {w_opt:.1f}%<br>
                    <b>Indice de Plasticité (IP)</b> : {ip:.1f}%<br>
                    <b>VBS</b> : {vbs_val:.2f}
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

        f_st.markdown("#### Courbe Granulométrique & Résultats")
        col_tbl_res, col_plt = f_st.columns([1.1, 0.9])
        with col_tbl_res:
            f_st.dataframe(result_df, use_container_width=True, height=380)
        with col_plt:
            fig, ax = plt.subplots(figsize=(7.0, 6.2))
            plot_curve_df = result_df.sort_values(by="Tamis (mm)", ascending=True).reset_index(drop=True)
            
            x_indices = np.arange(len(plot_curve_df))
            sieve_values = plot_curve_df["Tamis (mm)"].values
            
            ticks_positions = []
            ticks_labels = []
            for idx, (x_pos, t_val) in enumerate(zip(x_indices, sieve_values)):
                if t_val >= 10.0 or idx % 3 == 0:
                    ticks_positions.append(x_pos)
                    ticks_labels.append(f"{t_val}mm")

            ax.plot(
                x_indices, plot_curve_df["% Passant"],
                marker='o', markersize=4, linestyle='-', color='#004080', linewidth=1.8, label=ref_ech
            )
            ax.set_xticks(ticks_positions)
            ax.set_xticklabels(ticks_labels, rotation=70, ha='right', fontsize=7)
            ax.set_xlabel("Ouverture des tamis (mm)")
            ax.set_ylabel("% Passant (%)")
            ax.set_ylim(-2, 105)
            ax.grid(True, which="both", linestyle=":", alpha=0.6)
            ax.legend(loc="lower right")
            fig.tight_layout()
            
            temp_curve_path = "temp_granulometrie.png"
            fig.savefig(temp_curve_path, dpi=200)
            
            f_st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        dmax_detected = float(result_df[(result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)]["Tamis (mm)"].max()) if any((result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)) else 50.0
        row_80um = result_df[result_df["Tamis (mm)"] == 0.08]
        pass_80um_val = float(row_80um["% Passant"].values[0]) if not row_80um.empty else 22.3

        row_2mm = result_df[result_df["Tamis (mm)"] == 2.0]
        pass_2mm_val = float(row_2mm["% Passant"].values[0]) if not row_2mm.empty else 66.0

        row_50mm = result_df[np.isclose(result_df["Tamis (mm)"].astype(float), 50.0, atol=1e-3)]
        pass_50mm_val = float(row_50mm["% Passant"].values[0]) if not row_50mm.empty else 100.0

        classe_gtr_auto = classer_gtr(dmax_detected, pass_80um_val, ip, vbs_val, pass_2mm_val)
        f_st.metric("Classe GTR (Auto)", classe_gtr_auto)

        is_conf = pass_80um_val <= 35.0
        obs = f"Le matériau peut être utilisé pour un remblai. ({selected_mat_sub})" if is_conf else f"Non Conforme / Hors fuseau ({selected_mat_sub})"
        f_st.info(f"Observation automatique : **{obs}** | Dmax: **{dmax_detected} mm** | Passant 50mm: **{pass_50mm_val:.1f}%** | Passant 80um: **{pass_80um_val:.1f}%** | VBS: **{vbs_val:.2f}** | IP: **{ip:.1f}%**")

        data_dict = {
            "Sous-Type Matériau": selected_mat_sub,
            "Ref Echantillon": ref_ech,
            "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}", "M3 (g)": f"{m3_val}", "M4 (g)": f"{m4_val}",
            "M5 (g)": f"{m5_val:.2f}", "Fond de tamis (g)": f"{fond_tamis_val}", "M6 (g)": f"{m6_val:.2f}",
            "Dmax (mm)": f"{int(dmax_detected)}", 
            "Passant 80um (%)": f"{pass_80um_val:.1f}".replace('.', ','), 
            "Passant 2mm (%)": f"{int(pass_2mm_val)}",
            "Passant 50mm (%)": f"{pass_50mm_val:.1f}".replace('.', ','),
            "wL (%)": f"{w_opt:.1f}".replace('.', ','), 
            "IP (%)": f"{ip:.1f}".replace('.', ','),
            "Densité OPN": f"{dens_val:.2f}".replace('.', ','),
            "VBS": f"{vbs_val:.2f}".replace('.', ','),
            "Classe GTR (Auto)": classe_gtr_auto,
            "Observation": obs
        }

        if f_st.button("💾 Enregistrer le PV dans l'Historique", type="primary", use_container_width=True, disabled=not user_can_edit):
            existing_records = _safe_supabase_fetch(supabase_client)
            if not existing_records:
                existing_records = f_st.session_state["pv_ident_local_db"]
            
            is_duplicate = any(str(r.get("num_rapport")).strip().lower() == str(num_rapport).strip().lower() for r in existing_records)
            
            if is_duplicate:
                f_st.error(f"❌ Erreur de blocage : Le numéro de rapport '{num_rapport}' existe déjà dans la base de données. Veuillez modifier le N° de rapport pour éviter les doublons.")
            else:
                payload_record = {
                    "num_rapport": num_rapport,
                    "type_materiau": selected_mat_sub,
                    "lieu": lieu,
                    "pk": pk,
                    "date_essai": str(date_essai),
                    "details": data_dict,
                    "observation": obs
                }
                saved_to_db = False
                if supabase_client:
                    try:
                        res = supabase_client.table("pv_identification_materiaux").insert(payload_record).execute()
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
                    f_st.warning("⚠️ Stocké en session locale.")

    # ---------------------------------------------------------
    # TAB 1 : 📋 PVs / HISTORIQUE & TÉLÉCHARGEMENT PDF
    # ---------------------------------------------------------
    with tab_hist:
        f_st.subheader("📋 PVs / Historique, Consultation & Téléchargement PDF")
        raw_data = _safe_supabase_fetch(supabase_client)
        
        if not raw_data and not f_st.session_state["pv_ident_local_db"]:
            f_st.info("💡 Aucun PV d'identification enregistré.")
        else:
            combined_records = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
            df_hist = pd.DataFrame(combined_records)
            
            search_q = f_st.text_input("Filtrer par N° Rapport, Lieu ou Type :", key="search_hist_input").lower()
            if search_q:
                df_hist = df_hist[df_hist.apply(lambda r: search_q in str(r.values).lower(), axis=1)]
            
            f_st.markdown("#### Liste des PVs enregistrés et Téléchargement")
            
            for idx, row in df_hist.iterrows():
                with f_st.expander(f"📄 N° Rapport : {row.get('num_rapport')} | Type : {row.get('type_materiau')} | Date : {row.get('date_essai')}"):
                    c_info1, c_info2 = f_st.columns(2)
                    with c_info1:
                        f_st.write(f"**Lieu / Zone :** {row.get('lieu')}")
                        f_st.write(f"**Provenance d'échantillon :** {row.get('pk')}")
                    with c_info2:
                        f_st.write(f"**Observation :** {row.get('observation')}")
                        f_st.write(f"**Date d'essai :** {row.get('date_essai')}")
                    
                    header_info = {
                        "num_rapport": row.get("num_rapport"),
                        "lieu": row.get("lieu"),
                        "pk": row.get("pk"),
                        "date_essai": str(row.get("date_essai"))
                    }
                    
                    curve_path_to_use = "temp_granulometrie.png" if os.path.exists("temp_granulometrie.png") else None
                    pdf_bytes = generate_pdf(header_info, row.get("details", {}), str(row.get("type_materiau")), curve_path_to_use)
                    
                    f_st.download_button(
                        label=f"📄 Télécharger PV PDF LPEE (Mis en page optimisée) ({row.get('num_rapport')})",
                        data=pdf_bytes,
                        file_name=f"PV_{str(row.get('num_rapport')).replace('/', '_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_btn_{idx}_{row.get('num_rapport')}",
                        use_container_width=True
                    )

            f_st.markdown("---")
            f_st.dataframe(df_hist, use_container_width=True)

            selected_del = f_st.selectbox("Sélectionner un PV à supprimer (Admin/Labo)", options=[""] + df_hist["num_rapport"].tolist() if "num_rapport" in df_hist else [], key="del_pv_select")
            if selected_del and f_st.button("🗑️ Supprimer ce PV", disabled=not user_can_edit, key="del_pv_btn"):
                if supabase_client:
                    try:
                        supabase_client.table("pv_identification_materiaux").delete().eq("num_rapport", selected_del).execute()
                    except Exception:
                        pass
                f_st.session_state["pv_ident_local_db"] = [
                    r for r in f_st.session_state["pv_ident_local_db"] if r.get("num_rapport") != selected_del
                ]
                f_st.success(f"PV {selected_del} supprimé.")
                f_st.rerun()

    # ---------------------------------------------------------
    # TAB 2 : 📊 SYNTHÈSE GLOBALE
    # ---------------------------------------------------------
    with tab_synth:
        f_st.subheader(f"📊 Synthèse Globale - {selected_mat_sub}")
        raw_data = _safe_supabase_fetch(supabase_client)
        data_to_use = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
        
        if data_to_use:
            df_s = pd.DataFrame(data_to_use)
            
            if "type_materiau" in df_s.columns:
                df_s = df_s[df_s["type_materiau"].str.lower() == selected_mat_sub.lower()]

            if df_s.empty:
                f_st.info(f"Aucune donnée disponible pour le matériau : **{selected_mat_sub}**.")
            else:
                df_s["date_essai_dt"] = pd.to_datetime(df_s["date_essai"], errors="coerce")
                
                mois_fr = {
                    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
                    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
                }
                
                def get_mois_Annee(dt):
                    if pd.isna(dt):
                        return "Inconnu"
                    return f"{mois_fr.get(dt.month, '')} {dt.year}"

                df_s["Mois_Annee"] = df_s["date_essai_dt"].apply(get_mois_Annee)

                f_st.markdown("#### 📅 Filtres de Synthèse")
                mois_disponibles = sorted(df_s["Mois_Annee"].unique().tolist())
                options_filtre = ["Tous les mois"] + [m for m in mois_disponibles if m != "Inconnu"]
                
                col_f1, col_f2 = f_st.columns(2)
                with col_f1:
                    filtre_mois = f_st.selectbox("Filtrer par mois de prélèvement", options=options_filtre, key="select_filtre_mois")

                if filtre_mois != "Tous les mois":
                    df_filtered = df_s[df_s["Mois_Annee"] == filtre_mois]
                else:
                    df_filtered = df_s.copy()

                total_essais_count = len(df_filtered)

                m1, m2, m3 = f_st.columns(3)
                m1.metric(f"Total PVs / Essais ({selected_mat_sub})", total_essais_count)
                m2.metric("Conformes", len(df_filtered[df_filtered["observation"].str.contains("Conforme", na=False)]) if "observation" in df_filtered else 0)
                m3.metric("Mois sélectionné", filtre_mois)
                
                f_st.markdown("---")
                f_st.markdown("#### Aperçu du tableau de synthèse")
                
                export_rows = []
                for _, row in df_filtered.iterrows():
                    details = row.get("details", {})
                    if not isinstance(details, dict):
                        details = {}
                    
                    export_rows.append({
                        "N° Rapport": row.get("num_rapport"),
                        "Date de prélèvement": row.get("date_essai"),
                        "Nombre d'essais": 1,
                        "Lieu / Zone": row.get("lieu"),
                        "Provenance d'échantillon": row.get("pk"),
                        "Classification GTR": details.get("Classe GTR (Auto)", "N/A"),
                        "Observation": row.get("observation")
                    })

                df_display_synth = pd.DataFrame(export_rows)
                f_st.dataframe(df_display_synth, use_container_width=True)

                excel_buf = io.BytesIO()
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Synthèse Identification"

                ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
                ws.page_setup.paperSize = ws.PAPERSIZE_A4
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = 0

                font_main_title = Font(name="Helvetica", size=11, bold=True, color="003366")
                font_sub_title = Font(name="Helvetica", size=9, italic=True, color="333333")
                font_section = Font(name="Helvetica", size=10, bold=True, color="000000")
                font_tbl_header = Font(name="Helvetica", size=10, bold=True, color="FFFFFF")
                font_data = Font(name="Helvetica", size=9, color="000000")

                fill_tbl_header = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
                fill_zebra = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
                fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

                border_thin = Border(
                    left=Side(style='thin', color='CCCCCC'),
                    right=Side(style='thin', color='CCCCCC'),
                    top=Side(style='thin', color='CCCCCC'),
                    bottom=Side(style='thin', color='CCCCCC')
                )

                logo_path_excel = "logo.png.jpg"
                if not os.path.exists(logo_path_excel):
                    logo_path_excel = "logo.png"
                if os.path.exists(logo_path_excel):
                    try:
                        img_ex = OpenpyxlImage(logo_path_excel)
                        img_ex.width = 45
                        img_ex.height = 25
                        ws.add_image(img_ex, 'A1')
                    except Exception:
                        pass

                ws.merge_cells('A1:G1')
                ws['A1'] = "L.P.E.E - LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES"
                ws['A1'].font = font_main_title
                ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[1].height = 20

                ws.merge_cells('A2:G2')
                ws['A2'] = "Centre Technique Régional CASA-SETTAT-BENI MELLAL"
                ws['A2'].font = font_sub_title
                ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[2].height = 16

                ws.merge_cells('A3:G3')
                ws['A3'] = f"SYNTHÈSE DES ESSAIS D'IDENTIFICATION — {selected_mat_sub.upper()} (Période: {filtre_mois})"
                ws['A3'].font = font_section
                ws['A3'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[3].height = 22

                ws.row_dimensions[4].height = 8

                start_row = 5
                headers = [
                    "N° Rapport", 
                    "Date de prélèvement", 
                    "Nombre d'essais",
                    "Lieu / Zone", 
                    "Provenance d'échantillon", 
                    "Classification GTR", 
                    "Observation"
                ]

                for col_num, h_text in enumerate(headers, 1):
                    cell = ws.cell(row=start_row, column=col_num, value=h_text)
                    cell.font = font_tbl_header
                    cell.fill = fill_tbl_header
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    cell.border = border_thin
                ws.row_dimensions[start_row].height = 25

                current_row = start_row + 1
                for r_idx, row_dict in enumerate(export_rows):
                    ws.cell(row=current_row, column=1, value=row_dict.get("N° Rapport")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=2, value=row_dict.get("Date de prélèvement")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=3, value=row_dict.get("Nombre d'essais")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=4, value=row_dict.get("Lieu / Zone")).alignment = Alignment(horizontal='left', vertical='center')
                    ws.cell(row=current_row, column=5, value=row_dict.get("Provenance d'échantillon")).alignment = Alignment(horizontal='left', vertical='center')
                    ws.cell(row=current_row, column=6, value=row_dict.get("Classification GTR")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=7, value=row_dict.get("Observation")).alignment = Alignment(horizontal='left', vertical='center')

                    row_fill = fill_zebra if r_idx % 2 == 1 else fill_white
                    for col_num in range(1, 8):
                        c = ws.cell(row=current_row, column=col_num)
                        c.font = font_data
                        c.fill = row_fill
                        c.border = border_thin
                    
                    ws.row_dimensions[current_row].height = 20
                    current_row += 1

                total_row_idx = current_row
                ws.cell(row=total_row_idx, column=1, value="TOTAL GENERAL").font = Font(name="Helvetica", size=9, bold=True)
                ws.cell(row=total_row_idx, column=1).alignment = Alignment(horizontal='center', vertical='center')
                ws.merge_cells(start_row=total_row_idx, start_column=1, end_row=total_row_idx, end_column=2)
                
                cell_tot_val = ws.cell(row=total_row_idx, column=3, value=f"=SUM(C{start_row+1}:C{total_row_idx-1})")
                cell_tot_val.font = Font(name="Helvetica", size=9, bold=True)
                cell_tot_val.alignment = Alignment(horizontal='center', vertical='center')

                for col_num in range(1, 8):
                    c = ws.cell(row=total_row_idx, column=col_num)
                    c.border = border_thin
                    if col_num > 3:
                        c.value = ""

                ws.row_dimensions[total_row_idx].height = 22

                for col in ws.columns:
                    max_len = 0
                    col_letter = openpyxl.utils.get_column_letter(col[0].column)
                    for cell in col:
                        if cell.row >= start_row and cell.row <= total_row_idx:
                            val_str = str(cell.value or "")
                            if len(val_str) > max_len:
                                max_len = len(val_str)
                    ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

                wb.save(excel_buf)
                excel_buf.seek(0)
                
                f_st.download_button(
                    label=f"📥 Télécharger la synthèse Excel formatée (A4 Portrait) — {selected_mat_sub}",
                    data=excel_buf,
                    file_name=f"Synthese_LPEE_{selected_mat_sub.replace(' ', '_')}_{filtre_mois.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
        else:
            f_st.info("Aucune donnée disponible pour la synthèse.")
