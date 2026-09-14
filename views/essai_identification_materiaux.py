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
        # En-tête utilisant uniquement le logo LPEE à droite (sans texte arabe)
        logo_path = "logo.png.jpg"
        if not os.path.exists(logo_path):
            logo_path = "logo.png"
        
        # Positionnement du logo sur le côté droit
        if os.path.exists(logo_path):
            try:
                self.image(logo_path, 160, 6, 30)
            except Exception:
                pass

        self.set_font("Helvetica", "B", 10)
        self.cell(100, 5, "L.P.E.E", 0, 1, "L")
        
        self.set_font("Helvetica", "B", 8)
        self.cell(100, 4, "LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES", 0, 1, "L")
        
        self.set_font("Helvetica", "I", 8)
        self.cell(100, 4, "Laboratoire du controle externe", 0, 1, "L")
        
        self.set_font("Helvetica", "", 8)
        self.cell(100, 4, "Centre Technique Regional CASA-SETTAT-BENI MELLAL", 0, 1, "L")
        self.ln(2)
        self.line(10, 24, 200, 24)
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, "C")


def generate_pdf(header_info, data_dict, type_mat, graph_img_bytes=None):
    pdf = IdentificationPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Numéro de rapport encadré
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 6, "", 0, 0)
    pdf.cell(70, 6, f"RAPPORT D'ESSAI N°: {header_info.get('num_rapport', '')}", 1, 1, "C")
    pdf.ln(3)

    # Intitulé du Projet
    pdf.set_font("Helvetica", "B", 8)
    projet_text = header_info.get("projet", "TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000 - GARE CASA SUD")
    pdf.multi_cell(190, 4, projet_text, border=1, align="C")
    pdf.ln(3)

    # Tableau Informations Client / Prélèvement
    pdf.set_font("Helvetica", "", 8)
    client_val = header_info.get("client", "TGCC")
    dossier_val = header_info.get("dossier", "2025-260-05985-2025-0247")
    date_prelev = header_info.get("date_prelevement", "07/05/2026")
    lieu_val = header_info.get("lieu", "Stock sur chantier (Zone T4)")
    num_prelev = header_info.get("num_prelevement", "Ech N°1")

    pdf.cell(40, 5, "Client", 1, 0, "L")
    pdf.cell(150, 5, f": {client_val}", 1, 1, "L")
    pdf.cell(40, 5, "Dossier", 1, 0, "L")
    pdf.cell(150, 5, f": {dossier_val}", 1, 1, "L")
    pdf.cell(40, 5, "Date du prelevement", 1, 0, "L")
    pdf.cell(150, 5, f": {date_prelev}", 1, 1, "L")
    pdf.cell(40, 5, "Lieux de prelevement", 1, 0, "L")
    pdf.cell(150, 5, f": {lieu_val}", 1, 1, "L")
    pdf.cell(40, 5, "Numero de prelevement", 1, 0, "L")
    pdf.cell(150, 5, f": {num_prelev}", 1, 1, "L")
    pdf.cell(40, 5, "Materiau", 1, 0, "L")
    pdf.cell(150, 5, f": {type_mat}", 1, 1, "L")
    pdf.ln(3)

    # Objet & Référence de normes
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(190, 5, f"OBJET : IDENTIFICATION DU MATERIAU DE {str(type_mat).upper()}", 1, 1, "L")
    
    pdf.set_font("Helvetica", "", 7)
    normes_text = "[X] A.G: NM 00.8.082  |  [ ] IP: NF P94-051  |  [X] LOS ANGELES: NM EN 1097-2  |  [X] MDE: NM EN 1097-1  |  [X] PROCTOR: NM 13.1.023  |  [X] VBS: NM 13.1.178"
    pdf.cell(190, 5, normes_text, 1, 1, "C")
    pdf.ln(3)

    # Table Résultats d'essais
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(190, 5, "Resultats d'essais", 1, 1, "C", fill=False)
    
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(30, 5, "% < 80 µm", 1, 0, "C")
    pdf.cell(30, 5, "% < 2 mm", 1, 0, "C")
    pdf.cell(30, 5, "D MAX (mm)", 1, 0, "C")
    pdf.cell(25, 5, "VBS", 1, 0, "C")
    pdf.cell(25, 5, "Wopt (%)", 1, 0, "C")
    pdf.cell(25, 5, "Densite OPN", 1, 0, "C")
    pdf.cell(25, 5, "GTR", 1, 1, "C")

    pdf.set_font("Helvetica", "", 8)
    pdf.cell(30, 5, str(data_dict.get("Passant 80µm (%)", "22.3")), 1, 0, "C")
    pdf.cell(30, 5, str(data_dict.get("Passant 2mm (%)", "66")), 1, 0, "C")
    pdf.cell(30, 5, str(data_dict.get("Dmax (mm)", "50")), 1, 0, "C")
    pdf.cell(25, 5, str(data_dict.get("VBS", "0.42")), 1, 0, "C")
    pdf.cell(25, 5, str(data_dict.get("Wopt (%)", "14.2")), 1, 0, "C")
    pdf.cell(25, 5, str(data_dict.get("Densité OPN", "1.73")), 1, 0, "C")
    pdf.cell(25, 5, str(data_dict.get("Classe GTR (Auto)", "B5")), 1, 1, "C")
    pdf.ln(3)

    # Commentaires & Conditions d'utilisation
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(190, 5, "Commentaires & Conditions d'utilisation :", 1, 1, "L")
    pdf.set_font("Helvetica", "", 8)
    obs_txt = data_dict.get("Observation", "Le materiau peut etre utilise pour un remblai.")
    cond_txt = f"• Conditions d'utilisation : {data_dict.get('Classe GTR (Auto)', 'B5')} m = ni pluie, ni evaporation importante | C: compactage moyen"
    pdf.multi_cell(190, 4, f"{obs_txt}\n{cond_txt}", border=1)
    pdf.ln(3)

    # Graphique Courbe Granulométrique
    if graph_img_bytes:
        try:
            img_stream = io.BytesIO(graph_img_bytes)
            pdf.image(img_stream, x=15, w=180, h=65)
            pdf.ln(2)
        except Exception:
            pass

    # Bloc Signatures (3 Signatures)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(63, 5, "RECU PAR LE CLIENT", 1, 0, "C")
    pdf.cell(63, 5, "LE COORDINATEUR DES ESSAIS", 1, 0, "C")
    pdf.cell(64, 5, "LE CHEF DU LABORATOIRE", 1, 1, "C")

    pdf.set_font("Helvetica", "", 8)
    pdf.cell(63, 5, "Nom :", "LR", 0, "L")
    pdf.cell(63, 5, "Nom : B.ELAMRI", "LR", 0, "L")
    pdf.cell(64, 5, "Nom : H.BAALLAL", "LR", 1, "L")

    pdf.cell(63, 12, "Visa :", "LRB", 0, "L")
    pdf.cell(63, 12, "Visa :", "LRB", 0, "L")
    pdf.cell(64, 12, "Visa :", "LRB", 1, "L")

    return bytes(pdf.output())


def generate_granulo_curve_image(result_df):
    """Génère l'image de la courbe granulométrique au format binaire pour le PDF."""
    fig, ax = plt.subplots(figsize=(8, 3.2))
    plot_curve_df = result_df.sort_values(by="Tamis (mm)", ascending=True).reset_index(drop=True)
    
    x_indices = np.arange(len(plot_curve_df))
    sieve_values = plot_curve_df["Tamis (mm)"].values
    
    ticks_positions = []
    ticks_labels = []
    for idx, (x_pos, t_val) in enumerate(zip(x_indices, sieve_values)):
        if t_val in [0.08, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 50.0, 80.0, 100.0] or idx % 3 == 0:
            ticks_positions.append(x_pos)
            ticks_labels.append(f"{t_val}")

    ax.plot(
        x_indices, plot_curve_df["% Passant"],
        marker='o', markersize=3, linestyle='-', color='#000000', linewidth=1.5, label="Ech N°1"
    )
    ax.set_xticks(ticks_positions)
    ax.set_xticklabels(ticks_labels, rotation=90, fontsize=6)
    ax.set_xlabel("Tamis (mm)", fontsize=7)
    ax.set_ylabel("% des tamisats", fontsize=7)
    ax.set_ylim(-5, 105)
    ax.grid(True, which="both", linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", fontsize=7)
    ax.set_title("COURBE GRANULOMETRIQUE", fontsize=8, fontweight="bold")
    fig.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=200)
    plt.close(fig)
    img_buf.seek(0)
    return img_buf.getvalue()


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
            client_input = f_st.text_input("Client", value="TGCC", disabled=not user_can_edit)
            dossier_input = f_st.text_input("Dossier N°", value="2025-260-05985-2025-0247", disabled=not user_can_edit)
        with c2:
            lieu = f_st.text_input("Lieu / Zone", value="Stock sur chantier (Zone T4)", disabled=not user_can_edit)
            pk = f_st.text_input("PK / Section", value="PK 5+450 à PK 10+000 - GARE CASA SUD", disabled=not user_can_edit)
            date_prelev = f_st.date_input("Date du prélèvement", value=datetime.date(2026, 5, 7), disabled=not user_can_edit)
        with c3:
            num_prelev = f_st.text_input("Numéro de prélèvement", value="Ech N°1", disabled=not user_can_edit)
            date_essai = f_st.date_input("Date Essai", value=datetime.date.today(), disabled=not user_can_edit)

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
            (80, 0.0, 0.0), (63, 0.0, 0.0), (50, 1200.0, 0.0), (40, 2500.0, 0.0),
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
            f_st.markdown("##### ⚙️ Caractéristiques & Limites")
            w_l = f_st.number_input("Lim. Liquidité wL (%)", value=30.0, step=0.5, disabled=not user_can_edit)
            w_p = f_st.number_input("Lim. Plasticité wP (%)", value=18.0, step=0.5, disabled=not user_can_edit)
            vbs_val = f_st.number_input("VBS (Bleu de Manganèse)", value=0.42, step=0.01, disabled=not user_can_edit)
            wopt_val = f_st.number_input("Proctor Wopt (%)", value=14.2, step=0.1, disabled=not user_can_edit)
            opn_val = f_st.number_input("Densité OPN (t/m³)", value=1.73, step=0.01, disabled=not user_can_edit)
            la_val = f_st.number_input("Los Angeles (LA)", value=24.0, step=1.0, disabled=not user_can_edit)
            mde_val = f_st.number_input("Micro-Deval (MDE)", value=18.0, step=1.0, disabled=not user_can_edit)

            a_factor = me_val_calc / m4_val if m4_val > 0 else 0
            ip = max(0.0, w_l - w_p)

        work_df = edited_sieve_df.sort_values(by="Tamis (mm)", ascending=False).reset_index(drop=True)
        cum_refus_list = []
        
        for idx, row in work_df.iterrows():
            sz = row["Tamis (mm)"]
            r_i_val = row["R_i (g) [≥10mm]"]
            r_fine_val = row["r_i (g) [<10mm]"]
            if sz >= 10:
                cum_val = r_i_val
            else:
                cum_val = (r_fine_val * a_factor) + re_val_calc
            cum_refus_list.append(cum_val)
        
        work_df["Refus Cumulé R (g)"] = np.round(cum_refus_list, 1)
        work_df["% Refus Cumulé"] = np.round((work_df["Refus Cumulé R (g)"] / m2_val) * 100.0, 1) if m2_val > 0 else 0.0
        work_df["% Passant"] = np.round(100.0 - work_df["% Refus Cumulé"], 1)

        result_df = work_df.copy()

        dmax_detected = float(result_df[(result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)]["Tamis (mm)"].max()) if any((result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)) else 50.0
        row_80um = result_df[result_df["Tamis (mm)"] == 0.08]
        pass_80um_val = float(row_80um["% Passant"].values[0]) if not row_80um.empty else 22.3

        row_2mm = result_df[result_df["Tamis (mm)"] == 2.0]
        pass_2mm_val = float(row_2mm["% Passant"].values[0]) if not row_2mm.empty else 66.0

        classe_gtr_auto = classer_gtr(dmax_detected, pass_80um_val, ip, vbs_val, pass_2mm_val)
        f_st.metric("Classe GTR (Auto - Tableau IV)", classe_gtr_auto)

        obs = "Le matériau peut être utilisé pour un remblai."
        f_st.info(f"Observation automatique : **{obs}** | Classe: **{classe_gtr_auto}** | Dmax: **{dmax_detected} mm** | Passant 80µm: **{pass_80um_val:.1f}%** | VBS: **{vbs_val}**")

        data_dict = {
            "Sous-Type Matériau": selected_mat_sub,
            "Ref Echantillon": num_prelev,
            "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}", "M3 (g)": f"{m3_val}", "M4 (g)": f"{m4_val}",
            "Dmax (mm)": f"{dmax_detected}", "Passant 80µm (%)": f"{pass_80um_val:.1f}", "Passant 2mm (%)": f"{pass_2mm_val:.1f}",
            "wL (%)": f"{w_l}", "wP (%)": f"{w_p}", "IP (%)": f"{ip:.1f}", "VBS": f"{vbs_val}",
            "Wopt (%)": f"{wopt_val}", "Densité OPN": f"{opn_val}",
            "Los Angeles (LA)": f"{la_val}", "Micro-Deval (MDE)": f"{mde_val}",
            "Classe GTR (Auto)": classe_gtr_auto,
            "Observation": obs
        }

        # Génération du graphique pour stockage
        graph_bytes = generate_granulo_curve_image(result_df)

        if f_st.button("💾 Enregistrer le PV dans l'Historique", type="primary", use_container_width=True, disabled=not user_can_edit):
            payload_record = {
                "num_rapport": num_rapport,
                "client": client_input,
                "dossier": dossier_input,
                "type_materiau": selected_mat_sub,
                "lieu": lieu,
                "pk": pk,
                "date_prelevement": str(date_prelev),
                "num_prelevement": num_prelev,
                "date_essai": str(date_essai),
                "details": data_dict,
                "observation": obs,
                "sieve_data": result_df.to_dict(orient="records")
            }
            saved_to_db = False
            db_error_msg = ""
            if supabase_client:
                try:
                    res = supabase_client.table("pv_identification_materiaux").upsert(payload_record, on_conflict="num_rapport").execute()
                    saved_to_db = True
                except Exception as e:
                    saved_to_db = False
                    db_error_msg = str(e)
            
            f_st.session_state["pv_ident_local_db"] = [
                r for r in f_st.session_state["pv_ident_local_db"] if r.get("num_rapport") != num_rapport
            ]
            f_st.session_state["pv_ident_local_db"].insert(0, payload_record)
            
            if saved_to_db:
                f_st.success("✅ PV enregistré avec succès ! Retrouvez-le et téléchargez-le dans l'onglet '📋 PVs / Historique & Administration'.")
            else:
                f_st.warning(f"⚠️ Stocké en session locale. Rendez-vous à la fenêtre 2 pour télécharger le PV PDF.")

    # ---------------------------------------------------------
    # TAB 1 : 📋 PVs / HISTORIQUE & ADMINISTRATION
    # ---------------------------------------------------------
    with tab_hist:
        f_st.subheader("📋 PVs / Historique, Consultation & Téléchargement PDF")
        raw_data = _safe_supabase_fetch(supabase_client)
        
        if not raw_data and not f_st.session_state["pv_ident_local_db"]:
            f_st.info("💡 Aucun PV d'identification enregistré.")
        else:
            combined_records = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
            df_hist = pd.DataFrame(combined_records)
            
            search_q = f_st.text_input("Filtrer par N° Rapport, Client, Lieu ou Type :", key="search_hist_input").lower()
            if search_q:
                df_hist = df_hist[df_hist.apply(lambda r: search_q in str(r.values).lower(), axis=1)]
            
            f_st.markdown("#### Liste des PVs enregistrés")
            
            for idx, row in df_hist.iterrows():
                with f_st.expander(f"📄 N° Rapport : {row.get('num_rapport')} | Client : {row.get('client', 'TGCC')} | Date : {row.get('date_essai')}"):
                    c_info1, c_info2 = f_st.columns(2)
                    with c_info1:
                        f_st.write(f"**Client :** {row.get('client', 'TGCC')}")
                        f_st.write(f"**Dossier N° :** {row.get('dossier', '2025-260-05985-2025-0247')}")
                        f_st.write(f"**Lieu :** {row.get('lieu')}")
                        f_st.write(f"**PK / Section :** {row.get('pk')}")
                    with c_info2:
                        f_st.write(f"**Prélèvement N° :** {row.get('num_prelevement', 'Ech N°1')}")
                        f_st.write(f"**Date prélèvement :** {row.get('date_prelevement')}")
                        f_st.write(f"**Observation :** {row.get('observation')}")
                        f_st.write(f"**Date essai :** {row.get('date_essai')}")
                    
                    sieve_rec = row.get("sieve_data")
                    graph_bytes_row = None
                    if sieve_rec and isinstance(sieve_rec, list):
                        try:
                            df_sieve_rec = pd.DataFrame(sieve_rec)
                            graph_bytes_row = generate_granulo_curve_image(df_sieve_rec)
                        except Exception:
                            graph_bytes_row = None

                    header_info = {
                        "num_rapport": row.get("num_rapport"),
                        "client": row.get("client", "TGCC"),
                        "dossier": row.get("dossier", "2025-260-05985-2025-0247"),
                        "lieu": row.get("lieu"),
                        "pk": row.get("pk"),
                        "date_prelevement": str(row.get("date_prelevement", "07/05/2026")),
                        "num_prelevement": str(row.get("num_prelevement", "Ech N°1")),
                        "date_essai": str(row.get("date_essai"))
                    }
                    
                    pdf_bytes = generate_pdf(
                        header_info,
                        row.get("details", {}),
                        str(row.get("type_materiau", "Remblai d'apport")),
                        graph_img_bytes=graph_bytes_row
                    )
                    
                    f_st.download_button(
                        label=f"📄 Télécharger PV PDF Conforme ({row.get('num_rapport')})",
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
        f_st.subheader("📊 Synthèse Globale - Identification Matériaux")
        raw_data = _safe_supabase_fetch(supabase_client)
        data_to_use = raw_data if raw_data else f_st.session_state["pv_ident_local_db"]
        if data_to_use:
            df_s = pd.DataFrame(data_to_use)
            m1, m2, m3 = f_st.columns(3)
            m1.metric("Total PVs Ident.", len(df_s))
            m2.metric("Conformes", len(df_s[df_s["observation"].str.contains("Conforme|peut être utilisé", na=False)]) if "observation" in df_s else 0)
            m3.metric("Type en cours", selected_mat_sub)
            
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
