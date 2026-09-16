import datetime
import io
import os
import unicodedata
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


# =====================================================================
# REGISTRE DES TYPES DE MATÉRIAUX — chaque type a son propre code
# et appartient à une famille de feuille d'essai :
#   - "REMBLAI" : feuille classique GTR (VBS + IP)
#   - "GRAVE"   : feuille graves non traitées (LA / MDE / Coeff. Aplat. / ES)
#                 avec VBS en plus uniquement pour GNF et GNA
# =====================================================================
MATERIAL_TYPES = {
    "REM-ORD": {"label": "Remblai ordinaire", "family": "REMBLAI", "has_vbs": True},
    "REM-CTG2": {"label": "Remblai contigu type 2", "family": "REMBLAI", "has_vbs": True},
    "CDF": {"label": "Couche de forme", "family": "GRAVE", "has_vbs": False},
    "SC-031": {"label": "Sous couche 0/31.5", "family": "GRAVE", "has_vbs": False},
    "GNF-040": {"label": "GNF 0/40", "family": "GRAVE", "has_vbs": True},
    "GNA-031": {"label": "GNA 0/31.5", "family": "GRAVE", "has_vbs": True},
    "GNT-060": {"label": "GNT 0/60", "family": "GRAVE", "has_vbs": False},
    "GNT-PRA": {"label": "GNT Bloc technique PRA", "family": "GRAVE", "has_vbs": False},
}


def _normalize_label(txt):
    """Normalise un libellé (accents/casse/espaces) pour un matching robuste."""
    txt = str(txt or "").strip().upper()
    txt = "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")
    return " ".join(txt.split())


_LABEL_TO_CODE = {_normalize_label(v["label"]): k for k, v in MATERIAL_TYPES.items()}


def get_material_code(selected_label):
    """Retrouve le code matériau (ex: GNF-040) à partir du libellé affiché."""
    key = _normalize_label(selected_label)
    if key in _LABEL_TO_CODE:
        return _LABEL_TO_CODE[key]
    for norm_label, code in _LABEL_TO_CODE.items():
        if norm_label in key or key in norm_label:
            return code
    return "REM-ORD"


def get_material_config(selected_label):
    """Retourne (code, config) pour le libellé de matériau sélectionné."""
    code = get_material_code(selected_label)
    return code, MATERIAL_TYPES[code]


def _zero_to_star(value):
    """Remplace une valeur d'essai égale à 0 (numérique, '0', '0,0'...) par '*'."""
    if value is None:
        return value
    txt = str(value).strip()
    if txt in ("", "-", "N/A"):
        return value
    try:
        num = float(txt.replace(',', '.'))
        if num == 0:
            return "*"
    except (ValueError, TypeError):
        pass
    return value


def build_flat_hist_df(combined_records):
    """Construit un tableau lisible (une ligne par PV) à partir des enregistrements
    historiques, en aplatissant le dict 'details' et en remplaçant les valeurs
    d'essai égales à 0 par '*'."""
    rows = []
    for r in combined_records:
        details = r.get("details", {}) or {}
        code = r.get("code_materiau") or get_material_code(r.get("type_materiau"))
        flat = {
            "N° Rapport": r.get("num_rapport"),
            "Code": code,
            "Type": r.get("type_materiau"),
            "Date": r.get("date_essai"),
            "Lieu": r.get("lieu"),
            "Ref Ech.": details.get("Ref Echantillon", "-"),
            "Dmax (mm)": details.get("Dmax (mm)", "-"),
            "Passant Fines (%)": details.get("Passant Fines (%)", details.get("Passant 80um (%)", "-")),
            "Passant 2mm (%)": details.get("Passant 2mm (%)", "-"),
            "Passant 50mm (%)": details.get("Passant 50mm (%)", "-"),
            "LA (%)": details.get("LA (%)", "-"),
            "MDE (%)": details.get("MDE (%)", "-"),
            "Coef. Aplat. (%)": details.get("Coefficient Aplatissement (%)", "-"),
            "ES (%)": details.get("ES (%)", "-"),
            "VB / VBS": details.get("VB", details.get("VBS", "-")),
            "IP (%)": details.get("IP (%)", "-"),
            "Wopt (%)": details.get("wL (%)", "-"),
            "Densité OPN": details.get("Densité OPN", "-"),
            "Classification": details.get("Classification (Auto)", details.get("Classe GTR (Auto)", "-")),
            "CPC": details.get("Conforme CPC", "-"),
            "Observation": r.get("observation", "-"),
        }
        rows.append(flat)

    df = pd.DataFrame(rows)
    skip_cols = {"N° Rapport", "Code", "Type", "Date", "Lieu", "Ref Ech.", "Classification", "CPC", "Observation"}
    for col in df.columns:
        if col not in skip_cols:
            df[col] = df[col].apply(_zero_to_star)
    return df


# =====================================================================
# FUSEAUX GRANULOMÉTRIQUES DE SPÉCIFICATION (par code matériau)
# Chaque entrée : (Tamis mm, VSI = Valeur Seuil Inférieure %, VSS = Valeur Seuil Supérieure %)
# Ajouter une entrée par code pour afficher son fuseau sur la courbe.
# =====================================================================
FUSEAUX_GRANULO = {
    "GNF-040": [
        (0.08, 2, 14),
        (2, 20, 48),
        (6.3, 33, 64),
        (10, 40, 70),
        (20, 60, 90),
        (31.5, 80, 100),
        (40, 85, 100),
    ],
}


def verifier_cpc_grave(la, mde, es, ip, vb, has_vb):
    """
    Vérifie l'exigence CPC pour les graves non traitées :
    LA < 30, MDE < 25, ES > 45, et IP < 12 — sauf pour les matériaux qui utilisent
    le VB (Valeur au Bleu) au lieu de l'IP (ex: GNF, GNA), auquel cas VB < 1,2.
    """
    ok_la = la < 30
    ok_mde = mde < 25
    ok_es = es > 45
    if has_vb:
        ok_fines = vb < 1.2
        fines_txt = f"VB {'<' if ok_fines else '>='} 1,2 ({vb:.2f})"
    else:
        ok_fines = ip < 12
        fines_txt = f"IP {'<' if ok_fines else '>='} 12 ({ip:.1f}%)"

    conforme = ok_la and ok_mde and ok_es and ok_fines
    detail = (
        f"LA {'<' if ok_la else '>='} 30 ({la:.1f}%) | "
        f"MDE {'<' if ok_mde else '>='} 25 ({mde:.1f}%) | "
        f"ES {'>' if ok_es else '<='} 45 ({es:.1f}%) | "
        f"{fines_txt}"
    )
    return conforme, detail


def classer_grave(la, mde, coeff_apl, es, pass_80um):
    """
    Classification indicative des graves non traitées (GNF/GNA/GNT/Couche de forme)
    à partir de Los Angeles (LA), Micro-Deval (MDE), coefficient d'aplatissement et
    équivalent de sable (ES). Seuils usuels indicatifs — à ajuster selon le CCTP du projet.
    """
    if la <= 25 and mde <= 15 and coeff_apl <= 20 and es >= 40:
        classe = "GNT1"
    elif la <= 30 and mde <= 20 and coeff_apl <= 30 and es >= 30:
        classe = "GNT2"
    elif la <= 35 and mde <= 25 and coeff_apl <= 35 and es >= 25:
        classe = "GNT3"
    else:
        classe = "Hors classe"

    if pass_80um > 12.0:
        classe += " (fines > 12% : à vérifier)"
    return classe


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
            "Code Materiau": "REM-ORD",
            "Ref Echantillon": "Ech 1",
            "Passant 80um (%)": "22,3",
            "Passant 2mm (%)": "66",
            "Passant 50mm (%)": "100",
            "Dmax (mm)": "50",
            "VBS": "0,42",
            "wL (%)": "14,2",
            "IP (%)": "4,2",
            "Densité OPN": "1,73",
            "Classification (Auto)": "B5",
            "Observation": "Le matériau peut être utilisé pour un remblai."
        }

    mat_code = data_dict.get("Code Materiau") or get_material_code(type_mat)
    mat_config = MATERIAL_TYPES.get(mat_code, MATERIAL_TYPES["REM-ORD"])
    family = mat_config["family"]
    mat_label = mat_config["label"]

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
    pdf.cell(190, 5.5, f" Objet : IDENTIFICATION DU MATÉRIAU - {mat_code} ({mat_label.upper()})", 1, 1, "L")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 7)
    if family == "REMBLAI":
        normes_txt = " Normes : A.G: NM 00.8.082 | IP: NF P94-051 | VBS: NM 13.1.178"
    else:
        normes_txt = " Normes : A.G: NM 00.8.082 | LA: NM EN 1097-2 | MDE: NM EN 1097-1 | Coef. Aplatissement: NM EN 933-3 | ES: NM EN 933-8"
        if mat_config["has_vbs"]:
            normes_txt += " | VB: NM 13.1.178"
    pdf.cell(190, 4.5, normes_txt, 1, 1, "L")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(190, 5.5, " Résultats d'essais", 1, 1, "C", fill=True)
    
    ech_label = data_dict.get('Ref Echantillon', 'Ech 1')
    val_wopt = str(data_dict.get('wL (%)', '14,2'))
    val_dens = str(data_dict.get('Densité OPN', '1,73'))
    val_class = str(data_dict.get('Classification (Auto)', data_dict.get('Classe GTR (Auto)', 'B5')))

    if family == "REMBLAI":
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(60, 5.5, "", 1, 0, "C", fill=True)
        pdf.cell(130, 5.5, str(ech_label), 1, 1, "C", fill=True)

        def _row(label, value):
            pdf.set_font("Helvetica", "", 7.5)
            pdf.cell(60, 5, f" {label}", 1, 0, "L")
            pdf.cell(130, 5, str(value), 1, 1, "C")

        _row("%< 80 µm", data_dict.get('Passant Fines (%)', data_dict.get('Passant 80um (%)', data_dict.get('Passant 80µm (%)', '22,3'))))
        _row("%< 2 mm", data_dict.get('Passant 2mm (%)', '66'))
        _row("%< 50 mm", data_dict.get('Passant 50mm (%)', '100'))
        _row("D MAX", data_dict.get('Dmax (mm)', '50'))
        _row("VBS", data_dict.get('VBS', '0,42'))
        _row("Indice de Plasticité (IP)", data_dict.get('IP (%)', '4,2'))

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
        pdf.cell(130, 5, val_class, 1, 1, "C")

    else:
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(60, 5.5, "", 1, 0, "C", fill=True)
        pdf.cell(65, 5.5, str(ech_label), 1, 0, "C", fill=True)
        pdf.cell(65, 5.5, "Exigence marché et CPC", 1, 1, "C", fill=True)

        def _row3(label, value, exigence="-"):
            pdf.set_font("Helvetica", "", 7.5)
            pdf.cell(60, 5, f" {label}", 1, 0, "L")
            pdf.cell(65, 5, str(value), 1, 0, "C")
            pdf.cell(65, 5, str(exigence), 1, 1, "C")

        _row3("%< 0,063 mm", data_dict.get('Passant Fines (%)', data_dict.get('Passant 80um (%)', '22,3')))
        _row3("%< 2 mm", data_dict.get('Passant 2mm (%)', '66'))
        _row3("%< 50 mm", data_dict.get('Passant 50mm (%)', '100'))
        _row3("D MAX", data_dict.get('Dmax (mm)', '50'))
        _row3("Los Angeles LA (%)", data_dict.get('LA (%)', '-'), "< 30")
        _row3("Micro-Deval MDE (%)", data_dict.get('MDE (%)', '-'), "< 25")
        _row3("Coefficient d'aplatissement (%)", data_dict.get('Coefficient Aplatissement (%)', '-'))
        _row3("Équivalent de Sable ES (%)", data_dict.get('ES (%)', '-'), "> 45")
        if mat_config["has_vbs"]:
            _row3("VB", data_dict.get('VB', data_dict.get('VBS', '-')), "< 1,2")
        else:
            _row3("Indice de Plasticité (IP)", data_dict.get('IP (%)', '-'), "< 12")

        pdf.cell(60, 5, " Proctor", 1, 0, "L")
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(26, 5, " Wopt", 1, 0, "C", fill=True)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(26, 5, val_wopt, 1, 0, "C")
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(34, 5, " Densité OPN", 1, 0, "C", fill=True)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(44, 5, val_dens, 1, 1, "C")

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
    pdf.multi_cell(190, 4, f" - Observation : {obs_text}\n ", 1, "L")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(63, 4.5, "LE REÇU PAR LE CLIENT", 1, 0, "C", fill=True)
    pdf.cell(63, 4.5, "LE COORDINATEUR DES ESSAIS", 1, 0, "C", fill=True)
    pdf.cell(64, 4.5, "LE CHEF DU LABORATOIRE", 1, 1, "C", fill=True)

    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(63, 10, "Nom : ", 1, 0, "L")
    pdf.cell(63, 10, "Nom :                 O. IKKEN", 1, 0, "L")
    pdf.cell(64, 10, "Nom :                 H. BAALLAL", 1, 1, "L")

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
    mat_code, mat_config = get_material_config(selected_mat_sub)

    f_st.title("🔬 Identification & Granulométrie des Matériaux")
    f_st.subheader(f"📌 Sous-catégorie sélectionnée : **{mat_code} — {selected_mat_sub}**")
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

        ecart_tamisage_txt = ""

        if mat_config["family"] == "REMBLAI":
            # =====================================================================
            # MOTEUR 1 : NM 00.8.082 (sols) — tamisage/sédimentation avec prise
            # réduite Me pour la fraction fine, contrôle de bilan massique M6.
            # =====================================================================
            f_st.caption("Méthode NM 00.8.082 (sols) — tamisage + sédimentation, prise réduite Me pour la fraction fine")

            col_e1, col_e2, col_e3, col_e4 = f_st.columns(4)
            with col_e1:
                m1_val = f_st.number_input("Masse totale M1 (g)", value=14000.0, step=0.1, disabled=not user_can_edit, key=f"m1_{mat_code}")
            with col_e2:
                m2_val = f_st.number_input("Masse sèche étuve M2 (g)", value=13500.0, step=0.1, disabled=not user_can_edit, key=f"m2_{mat_code}")
            with col_e3:
                m3_val = f_st.number_input("Masse après lavage M3 (g)", value=11200.0, step=0.1, disabled=not user_can_edit, key=f"m3_{mat_code}")
            with col_e4:
                m4_val = f_st.number_input("Prise tamisage M4 (g)", value=2000.0, step=1.0, disabled=not user_can_edit, key=f"m4_{mat_code}")

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
                    key=f"sieve_editor_{mat_code}"
                )

            try:
                row_10 = edited_sieve_df[np.isclose(edited_sieve_df["Tamis (mm)"].astype(float), 10.0, atol=1e-3)]
                re_val_calc = float(row_10["R_i (g) [≥10mm]"].values[0]) if not row_10.empty else 6500.0
            except Exception:
                re_val_calc = 6500.0
            me_val_calc = m3_val - re_val_calc

            with col_params_right:
                f_st.markdown("##### ⚙️ Caractéristiques, Limites & Paramètres Spécifiques")
                re_val = f_st.number_input("Refus R_e (10mm) (g)", value=re_val_calc, disabled=True, key=f"re_10mm_mat_{mat_code}")
                me_val = f_st.number_input("Prise Me (g) [M3-Re]", value=me_val_calc, disabled=True, key=f"me_val_mat_{mat_code}")

                fond_tamis_val = f_st.number_input("Fond de tamis (g)", value=1.4, step=0.1, disabled=not user_can_edit, key=f"fond_tamis_{mat_code}")

                try:
                    row_008 = edited_sieve_df[np.isclose(edited_sieve_df["Tamis (mm)"].astype(float), 0.08, atol=1e-3)]
                    r_008_val = float(row_008["r_i (g) [<10mm]"].values[0]) if not row_008.empty else 1850.0
                except Exception:
                    r_008_val = 1850.0

                m5_calc = r_008_val + fond_tamis_val
                m5_val = f_st.number_input("M5 (Total refus et passant sur 80µm)", value=m5_calc, disabled=True, key=f"m5_auto_val_{mat_code}")

                w_opt = f_st.number_input("Proctor Wopt (%)", value=13.2, step=0.5, disabled=not user_can_edit, key=f"wopt_{mat_code}")
                dens_val = f_st.number_input("Proctor Densité OPN", value=1.73, step=0.01, disabled=not user_can_edit, key=f"dens_{mat_code}")

                ip = f_st.number_input("Indice de Plasticité (IP)", value=12.0, step=0.5, disabled=not user_can_edit, key=f"ip_{mat_code}")
                vbs_val = f_st.number_input("VBS (Bleu de Méthylène)", value=1.45, step=0.01, format="%.2f", disabled=not user_can_edit, key=f"vbs_{mat_code}")
                la_val = mde_val = coeff_apl_val = es_val = 0.0

                a_factor = me_val / m4_val if m4_val > 0 else 0
                m6_val = (a_factor * m5_val) + re_val
                validation_m6 = 100.0 * (m3_val - m6_val) / m3_val if m3_val > 0 else 0.0

                f_st.markdown(
                    f"""
                    <div style="background-color: #f0f2f6; padding: 10px; border-radius: 6px; font-size: 0.85em;">
                        <b>Facteur a (Me/M4)</b> : {a_factor:.4f}<br>
                        <b>M6 (Masse tamisat)</b> : {m6_val:.2f} g<br>
                        <b>Contrôle 100(M3-M6)/M3</b> : {validation_m6:.2f}% (doit être &lt;2%)<br>
                        <b>Proctor Wopt</b> : {w_opt:.1f}%<br>
                        <b>Indice de Plasticité (IP)</b> : {ip:.1f}%<br>
                        <b>VBS</b> : {vbs_val:.2f}<br>
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

            fine_sieve_ref = 0.08
            fine_sieve_label = "80 µm"

        else:
            # =====================================================================
            # MOTEUR 2 : NM EN 933-1 (granulats) — tamisage à sec après un seul
            # lavage sur le tamis 0,063 mm, sans prise réduite ni sédimentation.
            # =====================================================================
            f_st.caption("Méthode NM EN 933-1 (granulats) — tamisage à sec après lavage sur le tamis 0,063 mm")

            col_e1, col_e2 = f_st.columns(2)
            with col_e1:
                m1_val = f_st.number_input("Masse sèche avant lavage M1 (g)", value=5000.0, step=0.1, disabled=not user_can_edit, key=f"m1g_{mat_code}")
            with col_e2:
                m2_val = f_st.number_input("Masse sèche après lavage 0,063mm M2 (g)", value=4850.0, step=0.1, disabled=not user_can_edit, key=f"m2g_{mat_code}")

            f_st.markdown("#### Tableau de Tamisage à sec — Refus partiels")
            TAMIS_GRAVE_MM = [
                80, 63, 50, 40, 31.5, 25, 20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15,
                2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16,
                0.125, 0.1, 0.08, 0.063
            ]
            df_template_grave = pd.DataFrame({
                "Tamis (mm)": TAMIS_GRAVE_MM,
                "Refus partiel Ri (g)": [0.0] * len(TAMIS_GRAVE_MM)
            })

            col_main_tbl, col_params_right = f_st.columns([1.3, 0.9])
            with col_main_tbl:
                edited_sieve_df = f_st.data_editor(
                    df_template_grave,
                    disabled=["Tamis (mm)"] if not user_can_edit else [],
                    use_container_width=True,
                    height=500,
                    key=f"sieve_editor_{mat_code}"
                )

            with col_params_right:
                f_st.markdown("##### ⚙️ Caractéristiques, Limites & Paramètres Spécifiques")
                fines_lavage_g = m1_val - m2_val
                pct_fines_lavage = 100.0 * fines_lavage_g / m1_val if m1_val > 0 else 0.0
                f_st.metric("Fines < 0,063mm (par lavage)", f"{pct_fines_lavage:.1f} %")

                fond_tamis_val = f_st.number_input("Fond de tamis (g)", value=0.0, step=0.1, disabled=not user_can_edit, key=f"fond_tamis_g_{mat_code}")

                w_opt = f_st.number_input("Proctor Wopt (%)", value=6.0, step=0.5, disabled=not user_can_edit, key=f"wopt_{mat_code}")
                dens_val = f_st.number_input("Proctor Densité OPN", value=2.10, step=0.01, disabled=not user_can_edit, key=f"dens_{mat_code}")

                f_st.markdown(f"###### Essais spécifiques — {mat_code} (Grave non traitée)")
                la_val = f_st.number_input("Los Angeles LA (%)", value=22.0, step=0.5, disabled=not user_can_edit, key=f"la_{mat_code}")
                mde_val = f_st.number_input("Micro-Deval MDE (%)", value=15.0, step=0.5, disabled=not user_can_edit, key=f"mde_{mat_code}")
                coeff_apl_val = f_st.number_input("Coefficient d'aplatissement (%)", value=18.0, step=0.5, disabled=not user_can_edit, key=f"apl_{mat_code}")
                es_val = f_st.number_input("Équivalent de Sable ES (%)", value=45.0, step=0.5, disabled=not user_can_edit, key=f"es_{mat_code}")
                ip = f_st.number_input("Indice de Plasticité (IP)", value=0.0, step=0.5, disabled=not user_can_edit, key=f"ip_{mat_code}")
                vbs_val = 0.0
                if mat_config["has_vbs"]:
                    vbs_val = f_st.number_input("VB (Valeur au Bleu)", value=0.5, step=0.01, format="%.2f", disabled=not user_can_edit, key=f"vbs_{mat_code}")

            work_df = edited_sieve_df.sort_values(by="Tamis (mm)", ascending=False).reset_index(drop=True)
            work_df["Refus Cumulé R (g)"] = np.round(work_df["Refus partiel Ri (g)"].cumsum(), 1)
            work_df["% Refus Cumulé"] = np.round((work_df["Refus Cumulé R (g)"] / m1_val) * 100.0, 1) if m1_val > 0 else 0.0
            work_df["% Passant"] = np.round(100.0 - work_df["% Refus Cumulé"], 1)
            result_df = work_df.copy()

            somme_ri = float(edited_sieve_df["Refus partiel Ri (g)"].sum())
            somme_ri_avec_fond = somme_ri + fond_tamis_val
            ecart_tamisage = 100.0 * abs(m2_val - somme_ri_avec_fond) / m2_val if m2_val > 0 else 0.0
            ecart_ok = "OK (<1%)" if ecart_tamisage <= 1.0 else "Hors tolérance (>1%)"
            ecart_tamisage_txt = f" | Écart tamisage (ΣRi+Fond vs M2) : **{ecart_tamisage:.2f}%** {ecart_ok}"

            fines_label_grave = "VB" if mat_config["has_vbs"] else "IP"
            fines_display_grave = f"{vbs_val:.2f}" if mat_config["has_vbs"] else f"{ip:.1f}%"

            f_st.markdown(
                f"""
                <div style="background-color: #f0f2f6; padding: 10px; border-radius: 6px; font-size: 0.85em;">
                    <b>Fines &lt; 0,063mm (lavage)</b> : {pct_fines_lavage:.1f}%<br>
                    <b>Σ Refus partiels (tamisage à sec)</b> : {somme_ri:.1f} g + Fond de tamis {fond_tamis_val:.1f} g = {somme_ri_avec_fond:.1f} g (à comparer à M2 = {m2_val:.1f} g)<br>
                    <b>Écart de tamisage</b> : {ecart_tamisage:.2f}% (doit être &lt;1%)<br>
                    <b>Proctor Wopt</b> : {w_opt:.1f}%<br>
                    <b>LA</b> : {la_val:.1f}% &nbsp; | &nbsp; <b>MDE</b> : {mde_val:.1f}%<br>
                    <b>Coef. Aplatissement</b> : {coeff_apl_val:.1f}% &nbsp; | &nbsp; <b>ES</b> : {es_val:.1f}%<br>
                    <b>{fines_label_grave}</b> : {fines_display_grave}
                </div>
                """,
                unsafe_allow_html=True
            )

            m3_val = m4_val = m5_val = m6_val = 0.0
            fine_sieve_ref = 0.063
            fine_sieve_label = "0,063 mm"

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

            # --- Fuseau de spécification (si défini pour ce code matériau) ---
            fuseau_def = FUSEAUX_GRANULO.get(mat_code)
            if fuseau_def:
                fuseau_x, fuseau_vsi, fuseau_vss = [], [], []
                for tamis_f, vsi_f, vss_f in fuseau_def:
                    row_f = plot_curve_df[np.isclose(plot_curve_df["Tamis (mm)"].astype(float), tamis_f, atol=1e-3)]
                    if not row_f.empty:
                        fuseau_x.append(int(row_f.index[0]))
                        fuseau_vsi.append(vsi_f)
                        fuseau_vss.append(vss_f)
                if len(fuseau_x) >= 2:
                    ax.plot(fuseau_x, fuseau_vss, linestyle='--', color='#b30000', linewidth=1.3, label='Fuseau VSS (sup.)')
                    ax.plot(fuseau_x, fuseau_vsi, linestyle='--', color='#1a7a1a', linewidth=1.3, label='Fuseau VSI (inf.)')
                    ax.fill_between(fuseau_x, fuseau_vsi, fuseau_vss, color='#ffcc00', alpha=0.15)

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

        if mat_config["family"] == "REMBLAI":
            dmax_detected = float(result_df[(result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)]["Tamis (mm)"].max()) if any((result_df["R_i (g) [≥10mm]"] > 0) | (result_df["r_i (g) [<10mm]"] > 0)) else 50.0
        else:
            dmax_detected = float(result_df[result_df["Refus partiel Ri (g)"] > 0]["Tamis (mm)"].max()) if any(result_df["Refus partiel Ri (g)"] > 0) else 40.0

        row_fine = result_df[np.isclose(result_df["Tamis (mm)"].astype(float), fine_sieve_ref, atol=1e-3)]
        pass_fines_val = float(row_fine["% Passant"].values[0]) if not row_fine.empty else 22.3

        row_2mm = result_df[np.isclose(result_df["Tamis (mm)"].astype(float), 2.0, atol=1e-3)]
        pass_2mm_val = float(row_2mm["% Passant"].values[0]) if not row_2mm.empty else 66.0

        row_50mm = result_df[np.isclose(result_df["Tamis (mm)"].astype(float), 50.0, atol=1e-3)]
        pass_50mm_val = float(row_50mm["% Passant"].values[0]) if not row_50mm.empty else 100.0

        if mat_config["family"] == "REMBLAI":
            classe_auto = classer_gtr(dmax_detected, pass_fines_val, ip, vbs_val, pass_2mm_val)
            f_st.metric(f"Classe GTR (Auto) — {mat_code}", classe_auto)
            is_conf = pass_fines_val <= 35.0
            cpc_conforme, cpc_detail = None, None
            obs = f"Le matériau peut être utilisé. ({mat_code} - {selected_mat_sub})" if is_conf else f"Non Conforme / Hors fuseau ({mat_code} - {selected_mat_sub})"
        else:
            classe_auto = classer_grave(la_val, mde_val, coeff_apl_val, es_val, pass_fines_val)

            cpc_conforme, cpc_detail = verifier_cpc_grave(la_val, mde_val, es_val, ip, vbs_val, mat_config["has_vbs"])
            cpc_badge = "✅ Conforme CPC" if cpc_conforme else "❌ Non Conforme CPC"
            f_st.metric(f"Exigence marché et CPC — {mat_code}", cpc_badge)
            f_st.caption(f"Détail : {cpc_detail}")

            is_conf = cpc_conforme
            if is_conf:
                obs = f"Les résultats d'identification de la {selected_mat_sub} sont conformes aux spécifications du marché."
            else:
                obs = f"Les résultats d'identification de la {selected_mat_sub} ne sont pas conformes aux spécifications du marché."

        f_st.info(f"Observation automatique : **{obs}** | Dmax: **{dmax_detected} mm** | Passant 50mm: **{pass_50mm_val:.1f}%** | Passant {fine_sieve_label}: **{pass_fines_val:.1f}%**{ecart_tamisage_txt}")


        data_dict = {
            "Code Materiau": mat_code,
            "Sous-Type Matériau": selected_mat_sub,
            "Ref Echantillon": ref_ech,
            "M1 (g)": f"{m1_val}", "M2 (g)": f"{m2_val}",
            "Dmax (mm)": f"{int(dmax_detected)}", 
            "Passant Fines (%)": f"{pass_fines_val:.1f}".replace('.', ','), 
            "Passant 2mm (%)": f"{int(pass_2mm_val)}",
            "Passant 50mm (%)": f"{pass_50mm_val:.1f}".replace('.', ','),
            "wL (%)": f"{w_opt:.1f}".replace('.', ','), 
            "Densité OPN": f"{dens_val:.2f}".replace('.', ','),
            "Classification (Auto)": classe_auto,
            "Observation": obs
        }

        if mat_config["family"] == "REMBLAI":
            data_dict["M3 (g)"] = f"{m3_val}"
            data_dict["M4 (g)"] = f"{m4_val}"
            data_dict["M5 (g)"] = f"{m5_val:.2f}"
            data_dict["Fond de tamis (g)"] = f"{fond_tamis_val}"
            data_dict["M6 (g)"] = f"{m6_val:.2f}"
            data_dict["IP (%)"] = f"{ip:.1f}".replace('.', ',')
            data_dict["VBS"] = f"{vbs_val:.2f}".replace('.', ',')
        else:
            data_dict["Fond de tamis (g)"] = f"{fond_tamis_val}"
            data_dict["Ecart Tamisage (%)"] = f"{ecart_tamisage:.2f}".replace('.', ',')
            data_dict["LA (%)"] = f"{la_val:.1f}".replace('.', ',')
            data_dict["MDE (%)"] = f"{mde_val:.1f}".replace('.', ',')
            data_dict["Coefficient Aplatissement (%)"] = f"{coeff_apl_val:.1f}".replace('.', ',')
            data_dict["ES (%)"] = f"{es_val:.1f}".replace('.', ',')
            data_dict["IP (%)"] = f"{ip:.1f}".replace('.', ',')
            if mat_config["has_vbs"]:
                data_dict["VB"] = f"{vbs_val:.2f}".replace('.', ',')
            data_dict["Conforme CPC"] = "OUI" if cpc_conforme else "NON"
            data_dict["Detail CPC"] = cpc_detail

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
                    "code_materiau": mat_code,
                    "famille_materiau": mat_config["family"],
                    "lieu": lieu,
                    "pk": pk,
                    "date_essai": str(date_essai),
                    "details": data_dict,
                    "observation": obs
                }
                saved_to_db = False
                save_error = None
                if supabase_client:
                    try:
                        res = supabase_client.table("pv_identification_materiaux").insert(payload_record).execute()
                        saved_to_db = True
                    except Exception as e:
                        save_error = str(e)
                        # Repli : la table Supabase n'a peut-être pas encore les colonnes
                        # code_materiau / famille_materiau (schéma pas encore migré).
                        # On retire ces colonnes en trop et on retente l'insertion, pour ne
                        # jamais bloquer l'enregistrement d'un PV à cause de ça.
                        if "schema cache" in save_error or "PGRST204" in save_error or "code_materiau" in save_error or "famille_materiau" in save_error:
                            try:
                                fallback_payload = {
                                    k: v for k, v in payload_record.items()
                                    if k not in ("code_materiau", "famille_materiau")
                                }
                                supabase_client.table("pv_identification_materiaux").insert(fallback_payload).execute()
                                saved_to_db = True
                                save_error = None
                            except Exception as e2:
                                save_error = str(e2)
                
                f_st.session_state["pv_ident_local_db"] = [
                    r for r in f_st.session_state["pv_ident_local_db"] if r.get("num_rapport") != num_rapport
                ]
                f_st.session_state["pv_ident_local_db"].insert(0, payload_record)
                
                if saved_to_db:
                    f_st.success("✅ PV enregistré avec succès dans Supabase !")
                elif supabase_client is None:
                    f_st.warning("⚠️ Stocké en session locale (aucune connexion Supabase fournie à cette page).")
                else:
                    f_st.warning(f"⚠️ Stocké en session locale. Échec de l'enregistrement Supabase : {save_error}")

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
                with f_st.expander(f"📄 N° Rapport : {row.get('num_rapport')} | Code : {row.get('code_materiau', get_material_code(row.get('type_materiau')))} | Type : {row.get('type_materiau')} | Date : {row.get('date_essai')}"):
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
            f_st.markdown("#### 📊 Tableau des résultats d'essai (valeurs à 0 affichées comme « * »)")
            df_flat_hist = build_flat_hist_df(df_hist.to_dict("records"))
            f_st.dataframe(df_flat_hist, use_container_width=True)

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
                        "Code Matériau": details.get("Code Materiau", row.get("code_materiau", get_material_code(row.get("type_materiau")))),
                        "Date de prélèvement": row.get("date_essai"),
                        "Nombre d'essais": 1,
                        "Lieu / Zone": row.get("lieu"),
                        "Provenance d'échantillon": row.get("pk"),
                        "Classification": details.get("Classification (Auto)", details.get("Classe GTR (Auto)", "N/A")),
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

                ws.merge_cells('A1:H1')
                ws['A1'] = "L.P.E.E - LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES"
                ws['A1'].font = font_main_title
                ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[1].height = 20

                ws.merge_cells('A2:H2')
                ws['A2'] = "Centre Technique Régional CASA-SETTAT-BENI MELLAL"
                ws['A2'].font = font_sub_title
                ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[2].height = 16

                ws.merge_cells('A3:H3')
                ws['A3'] = f"SYNTHÈSE DES ESSAIS D'IDENTIFICATION — {selected_mat_sub.upper()} (Période: {filtre_mois})"
                ws['A3'].font = font_section
                ws['A3'].alignment = Alignment(horizontal='center', vertical='center')
                ws.row_dimensions[3].height = 22

                ws.row_dimensions[4].height = 8

                start_row = 5
                headers = [
                    "N° Rapport",
                    "Code Matériau",
                    "Date de prélèvement", 
                    "Nombre d'essais",
                    "Lieu / Zone", 
                    "Provenance d'échantillon", 
                    "Classification", 
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
                    ws.cell(row=current_row, column=2, value=row_dict.get("Code Matériau")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=3, value=row_dict.get("Date de prélèvement")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=4, value=row_dict.get("Nombre d'essais")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=5, value=row_dict.get("Lieu / Zone")).alignment = Alignment(horizontal='left', vertical='center')
                    ws.cell(row=current_row, column=6, value=row_dict.get("Provenance d'échantillon")).alignment = Alignment(horizontal='left', vertical='center')
                    ws.cell(row=current_row, column=7, value=row_dict.get("Classification")).alignment = Alignment(horizontal='center', vertical='center')
                    ws.cell(row=current_row, column=8, value=row_dict.get("Observation")).alignment = Alignment(horizontal='left', vertical='center')

                    row_fill = fill_zebra if r_idx % 2 == 1 else fill_white
                    for col_num in range(1, 9):
                        c = ws.cell(row=current_row, column=col_num)
                        c.font = font_data
                        c.fill = row_fill
                        c.border = border_thin
                    
                    ws.row_dimensions[current_row].height = 20
                    current_row += 1

                total_row_idx = current_row
                ws.cell(row=total_row_idx, column=1, value="TOTAL GENERAL").font = Font(name="Helvetica", size=9, bold=True)
                ws.cell(row=total_row_idx, column=1).alignment = Alignment(horizontal='center', vertical='center')
                ws.merge_cells(start_row=total_row_idx, start_column=1, end_row=total_row_idx, end_column=3)
                
                cell_tot_val = ws.cell(row=total_row_idx, column=4, value=f"=SUM(D{start_row+1}:D{total_row_idx-1})")
                cell_tot_val.font = Font(name="Helvetica", size=9, bold=True)
                cell_tot_val.alignment = Alignment(horizontal='center', vertical='center')

                for col_num in range(1, 9):
                    c = ws.cell(row=total_row_idx, column=col_num)
                    c.border = border_thin
                    if col_num > 4:
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
