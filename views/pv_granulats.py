import datetime
import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from fpdf import FPDF

# ==========================================
# UTILITAIRE NETTOYAGE TEXTE UTF-8 POUR FPDF
# ==========================================
def clean_text(text):
    if text is None:
        return ""
    text_str = str(text)
    text_str = text_str.replace("–", "-").replace("—", "-").replace("’", "'").replace("µ", "u")
    return text_str.encode("latin-1", "replace").decode("latin-1")

# ==========================================
# GÉNÉRATION DE LA COURBE GRANULOMÉTRIQUE
# ==========================================
def generate_granulometry_chart(g10_20, g4_10, s_fin, s_gros):
    plt.figure(figsize=(10, 4))
    
    # Définition des tamis (x) et passants (y) pour chaque matériau
    # Gravillon 10/20 : 40, 28, 20, 10, 5, 0.063
    x_g10 = [40, 28, 20, 10, 5, 0.063]
    y_g10 = [g10_20['2d'], g10_20['1_4d'], g10_20['d'], g10_20['d_min'], g10_20['d_2'], g10_20['f']]
    
    # Gravillon 4/10 : 20, 14, 10, 4, 2, 0.063
    x_g4 = [20, 14, 10, 4, 2, 0.063]
    y_g4 = [g4_10['2d'], g4_10['1_4d'], g4_10['d'], g4_10['d_min'], g4_10['d_2'], g4_10['f']]
    
    # Sable fin 0/0.63 : 1.26, 0.88, 0.63, 0.25, 0.063 (On interpole approximativement pour 1mm si besoin)
    x_sf = [1.26, 0.88, 0.63, 0.25, 0.063]
    y_sf = [s_fin['2d'], s_fin['1_4d'], s_fin['d'], s_fin['p_250'], s_fin['f']]
    
    # Sable grossier 0/4 : 8, 5.6, 4, 1.0, 0.25, 0.063
    x_sg = [8, 5.6, 4, 1.0, 0.25, 0.063]
    y_sg = [s_gros['2d'], s_gros['1_4d'], s_gros['d'], s_gros['p_1mm'], s_gros['p_250'], s_gros['f']]

    # Tracé
    plt.plot(x_g10, y_g10, marker='o', linestyle='-', color='black', label='Gravillon 10/20')
    plt.plot(x_g4, y_g4, marker='o', linestyle='-', color='blue', label='Gravillon 4/10')
    plt.plot(x_sf, y_sf, marker='o', linestyle='-', color='orange', label='Sable fin 0/0.63')
    plt.plot(x_sg, y_sg, marker='o', linestyle='-', color='green', label='Sable grossier 0/4')

    plt.xscale('log')
    plt.xlim(0.05, 50)
    plt.ylim(0, 105)
    plt.grid(True, which="both", ls="--", linewidth=0.5)
    plt.title("COURBE GRANULOMETRIQUE", fontsize=10, fontweight='bold')
    plt.xlabel("Tamis (mm)", fontsize=8)
    plt.ylabel("% Passant", fontsize=8)
    plt.legend(loc="lower right", fontsize=8)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    return buf

# ==========================================
# CLASSE DE GÉNÉRATION DU PV EN PDF
# ==========================================
class LPEEGranulatsPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 5, clean_text("LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES"), 0, 1, "C")
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 4, clean_text("Centre Technique Régional CASA-SETTAT"), 0, 1, "C")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 4, clean_text("Laboratoire du contrôle externe"), 0, 1, "C")
        self.ln(2)
        self.line(10, 24, 200, 24)
        self.ln(3)

def generate_pv_granulats_pdf(header_info, data_g10, data_g4, data_sfin, data_sgros):
    pdf = LPEEGranulatsPDF()
    pdf.add_page()

    # --- EN-TÊTE DU PV ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(100, 5, clean_text(f"Client : {header_info['client']}"), 0, 0, "L")
    pdf.cell(90, 5, clean_text(f"RAPPORT D'ESSAI N° : {header_info['num_rapport']}"), 0, 1, "R")
    
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4, clean_text(f"Chantier : {header_info['chantier']}"))
    pdf.cell(100, 4, clean_text(f"N° dossier : {header_info['num_dossier']}"), 0, 0, "L")
    pdf.cell(90, 4, clean_text(f"Date du prélèvement : {header_info['date_prelevement']}"), 0, 1, "L")
    pdf.cell(100, 4, clean_text(f"Lieux de prélèvement : {header_info['lieux']}"), 0, 0, "L")
    pdf.cell(90, 4, clean_text(f"Provenance échantillon : {header_info['provenance']}"), 0, 1, "L")
    
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, clean_text("OBJET : IDENTIFICATION DES GRANULATS POUR BETON"), 1, 1, "C", fill=False)
    pdf.ln(2)

    # --- TABLEAUX DES RÉSULTATS ---
    def draw_table(title, cols, sieves, results, specs):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 240)
        # Titre
        pdf.cell(40, 5, clean_text(title), 1, 0, "C", fill=True)
        for c in cols: pdf.cell(18, 5, clean_text(c), 1, 0, "C", fill=True)
        pdf.ln()
        # Tamis
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(40, 5, "Tamis (mm)", 1, 0, "C")
        for s in sieves: pdf.cell(18, 5, clean_text(s), 1, 0, "C")
        pdf.ln()
        # Résultats
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(40, 5, "Résultats", 1, 0, "C")
        for r in results: pdf.cell(18, 5, clean_text(str(r)), 1, 0, "C")
        pdf.ln()
        # Spécifications
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(40, 5, "Exigences (Générale)", 1, 0, "C")
        for sp in specs: pdf.cell(18, 5, clean_text(sp), 1, 0, "C")
        pdf.ln(8)

    # Gravillon 10/20
    draw_table("Gravillons GII-10/20", 
               ["2D", "1.4D", "D", "d", "d/2", "f (<63um)", "FI", "LA"],
               ["40", "28", "20", "10", "5", "-", "-", "-"],
               [data_g10['2d'], data_g10['1_4d'], data_g10['d'], data_g10['d_min'], data_g10['d_2'], data_g10['f'], data_g10['fi'], data_g10['la']],
               ["100", "98-100", "80-99", "0-20", "0-5", "<1.5", "<=20", "<=30"])

    # Gravillon 4/10
    draw_table("Gravillons GI-4/10", 
               ["2D", "1.4D", "D", "d", "d/2", "f (<63um)", "FI", "LA"],
               ["20", "14", "10", "4", "2", "-", "-", "-"],
               [data_g4['2d'], data_g4['1_4d'], data_g4['d'], data_g4['d_min'], data_g4['d_2'], data_g4['f'], data_g4['fi'], data_g4['la']],
               ["100", "98-100", "80-99", "0-20", "0-5", "<1.5", "<=20", "<=30"])

    # Sable fin
    draw_table("Sable fin 0/0.630", 
               ["2D", "1.4D", "D", "%<1mm", "<250um", "%<63um", "MB", ""],
               ["1.26", "0.88", "0.63", "-", "-", "-", "-", "-"],
               [data_sfin['2d'], data_sfin['1_4d'], data_sfin['d'], data_sfin['p_1mm'], data_sfin['p_250'], data_sfin['f'], data_sfin['mb'], ""],
               ["100", "95-100", "85-99", "e40(±20)", "e50(±25)", "Ls=10", "VSS 2", ""])

    # Sable grossier
    draw_table("Sable grossier 0/4", 
               ["2D", "1.4D", "D", "<1mm", "<250um", "<63um", "Mod. CF", "SE(10)"],
               ["8", "5.6", "4", "-", "-", "-", "-", "-"],
               [data_sgros['2d'], data_sgros['1_4d'], data_sgros['d'], data_sgros['p_1mm'], data_sgros['p_250'], data_sgros['f'], data_sgros['mf'], data_sgros['se']],
               ["100", "95-100", "85-99", "e40(±20)", "e50(±20)", "Ls=16", "2.4-4.0", "Vsi 60"])

    # --- COURBE GRANULOMÉTRIQUE ---
    chart_buf = generate_granulometry_chart(data_g10, data_g4, data_sfin, data_sgros)
    pdf.image(chart_buf, x=10, y=pdf.get_y(), w=190)
    pdf.set_y(pdf.get_y() + 75) # Espace pour l'image

    # --- PIED DE PAGE & SIGNATURES ---
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4, clean_text("COMMENTAIRES : Les essais des identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545"))
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(63, 5, clean_text("REÇU PAR LE CLIENT"), 0, 0, "C")
    pdf.cell(64, 5, clean_text("LE COORDINATEUR DES ESSAIS"), 0, 0, "C")
    pdf.cell(63, 5, clean_text("LE CHEF DU LABORATOIRE"), 0, 1, "C")

    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(63, 5, clean_text("Nom: TGCC"), 0, 0, "C")
    pdf.cell(64, 5, clean_text("Nom: O. IKEN"), 0, 0, "C")
    pdf.cell(63, 5, clean_text("Nom: H. BAALLAL"), 0, 1, "C")

    return bytes(pdf.output())

# ==========================================
# VUE STREAMLIT
# ==========================================
def show(supabase_client=None):
    st.title("🪨 Identification Granulats pour Béton")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    # 1. En-tête
    st.subheader("1. Informations Générales")
    c1, c2 = st.columns(2)
    with c1:
        num_pv_seq = st.number_input("N° PV", value=1237, step=1)
        num_rapport = f"26/260/LGV/CS/{num_pv_seq}"
        st.info(f"Rapport : **{num_rapport}**")
        client = st.text_input("Client", value="TGCC")
        chantier = st.text_area("Chantier", value="TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART... GARE CASA SUD")
    with c2:
        num_dossier = st.text_input("N° Dossier", value="2025-260-05985-2025 0247")
        date_prelevement = st.date_input("Date du prélèvement")
        lieux = st.text_input("Lieux de prélèvement", value="Stock sur centrale à béton")
        provenance = st.text_input("Provenance échantillon", value="TG PREFA OULAD SALEH")

    st.markdown("---")
    st.subheader("2. Saisie des Essais par Classe Granulaire")
    
    # 2. Saisie des données dans des Expanders
    with st.expander("🔵 Gravillons GII-10/20", expanded=True):
        col = st.columns(8)
        g10_20 = {
            "2d": col[0].number_input("2D (40)", value=100.0, key="g10_2d"),
            "1_4d": col[1].number_input("1.4D (28)", value=100.0, key="g10_14d"),
            "d": col[2].number_input("D (20)", value=95.0, key="g10_D"),
            "d_min": col[3].number_input("d (10)", value=6.0, key="g10_dmin"),
            "d_2": col[4].number_input("d/2 (5)", value=1.0, key="g10_d2"),
            "f": col[5].number_input("f (<63µm)", value=0.6, key="g10_f"),
            "fi": col[6].number_input("FI", value=16.0, key="g10_fi"),
            "la": col[7].number_input("LA", value=26.0, key="g10_la")
        }

    with st.expander("🔵 Gravillons GI-4/10", expanded=True):
        col = st.columns(8)
        g4_10 = {
            "2d": col[0].number_input("2D (20)", value=100.0, key="g4_2d"),
            "1_4d": col[1].number_input("1.4D (14)", value=100.0, key="g4_14d"),
            "d": col[2].number_input("D (10)", value=84.0, key="g4_D"),
            "d_min": col[3].number_input("d (4)", value=2.0, key="g4_dmin"),
            "d_2": col[4].number_input("d/2 (2)", value=1.0, key="g4_d2"),
            "f": col[5].number_input("f (<63µm)", value=1.1, key="g4_f"),
            "fi": col[6].number_input("FI", value=14.0, key="g4_fi"),
            "la": col[7].number_input("LA", value=26.0, key="g4_la")
        }

    with st.expander("🟡 Sable fin 0/0.630", expanded=True):
        col = st.columns(7)
        s_fin = {
            "2d": col[0].number_input("2D (1.26)", value=99.0, key="sf_2d"),
            "1_4d": col[1].number_input("1.4D (0.88)", value=98.0, key="sf_14d"),
            "d": col[2].number_input("D (0.63)", value=98.0, key="sf_D"),
            "p_1mm": col[3].number_input("%<1mm", value=98.0, key="sf_p1"),
            "p_250": col[4].number_input("<250µm", value=82.0, key="sf_p250"),
            "f": col[5].number_input("f (<63µm)", value=10.2, key="sf_f"),
            "mb": col[6].number_input("MB", value=0.7, key="sf_mb")
        }

    with st.expander("🟡 Sable grossier 0/4", expanded=True):
        col = st.columns(8)
        s_gros = {
            "2d": col[0].number_input("2D (8)", value=96.0, key="sg_2d"),
            "1_4d": col[1].number_input("1.4D (5.6)", value=100.0, key="sg_14d"),
            "d": col[2].number_input("D (4)", value=92.0, key="sg_D"),
            "p_1mm": col[3].number_input("<1mm", value=41.0, key="sg_p1"),
            "p_250": col[4].number_input("<250µm", value=16.0, key="sg_p250"),
            "f": col[5].number_input("f (<63µm)", value=9.3, key="sg_f"),
            "mf": col[6].number_input("Mod. CF", value=3.50, key="sg_mf"),
            "se": col[7].number_input("SE(10)", value=65.0, key="sg_se")
        }

    st.markdown("---")
    
    # 3. Actions
    header_data = {
        "num_rapport": num_rapport, "client": client, "chantier": chantier,
        "num_dossier": num_dossier, "date_prelevement": str(date_prelevement),
        "lieux": lieux, "provenance": provenance
    }

    pdf_bytes = generate_pv_granulats_pdf(header_data, g10_20, g4_10, s_fin, s_gros)

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        st.download_button(
            label="📄 Télécharger le PV Granulats (PDF)",
            data=pdf_bytes,
            file_name=f"PV_Granulats_{num_pv_seq}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with c_btn2:
        st.button("💾 Enregistrer dans Supabase", type="primary", use_container_width=True)

if __name__ == "__main__":
    show()
