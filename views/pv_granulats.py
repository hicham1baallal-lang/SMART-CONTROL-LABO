import datetime
import io
import pandas as pd
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
    
    x_g10 = [40, 28, 20, 10, 5, 0.063]
    y_g10 = [g10_20['2d'], g10_20['1_4d'], g10_20['d'], g10_20['d_min'], g10_20['d_2'], g10_20['f']]
    
    x_g4 = [20, 14, 10, 4, 2, 0.063]
    y_g4 = [g4_10['2d'], g4_10['1_4d'], g4_10['d'], g4_10['d_min'], g4_10['d_2'], g4_10['f']]
    
    x_sf = [1.26, 0.88, 0.63, 0.25, 0.063]
    y_sf = [s_fin['2d'], s_fin['1_4d'], s_fin['d'], s_fin['p_250'], s_fin['f']]
    
    x_sg = [8, 5.6, 4, 1.0, 0.25, 0.063]
    y_sg = [s_gros['2d'], s_gros['1_4d'], s_gros['d'], s_gros['p_1mm'], s_gros['p_250'], s_gros['f']]

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

    # EN-TÊTE
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

    # TABLEAUX
    def draw_table(title, cols, sieves, results, specs):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(40, 5, clean_text(title), 1, 0, "C", fill=True)
        for c in cols: pdf.cell(18, 5, clean_text(c), 1, 0, "C", fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(40, 5, "Tamis (mm)", 1, 0, "C")
        for s in sieves: pdf.cell(18, 5, clean_text(s), 1, 0, "C")
        pdf.ln()
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(40, 5, "Résultats", 1, 0, "C")
        for r in results: pdf.cell(18, 5, clean_text(str(r)), 1, 0, "C")
        pdf.ln()
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(40, 5, "Exigences (Générale)", 1, 0, "C")
        for sp in specs: pdf.cell(18, 5, clean_text(sp), 1, 0, "C")
        pdf.ln(8)

    draw_table("Gravillons GII-10/20", 
               ["2D", "1.4D", "D", "d", "d/2", "f (<63um)", "FI", "LA"],
               ["40", "28", "20", "10", "5", "-", "-", "-"],
               [data_g10['2d'], data_g10['1_4d'], data_g10['d'], data_g10['d_min'], data_g10['d_2'], data_g10['f'], data_g10['fi'], data_g10['la']],
               ["100", "98-100", "80-99", "0-20", "0-5", "<1.5", "<=20", "<=30"])

    draw_table("Gravillons GI-4/10", 
               ["2D", "1.4D", "D", "d", "d/2", "f (<63um)", "FI", "LA"],
               ["20", "14", "10", "4", "2", "-", "-", "-"],
               [data_g4['2d'], data_g4['1_4d'], data_g4['d'], data_g4['d_min'], data_g4['d_2'], data_g4['f'], data_g4['fi'], data_g4['la']],
               ["100", "98-100", "80-99", "0-20", "0-5", "<1.5", "<=20", "<=30"])

    draw_table("Sable fin 0/0.630", 
               ["2D", "1.4D", "D", "%<1mm", "<250um", "%<63um", "MB", ""],
               ["1.26", "0.88", "0.63", "-", "-", "-", "-", "-"],
               [data_sfin['2d'], data_sfin['1_4d'], data_sfin['d'], data_sfin['p_1mm'], data_sfin['p_250'], data_sfin['f'], data_sfin['mb'], ""],
               ["100", "95-100", "85-99", "e40(±20)", "e50(±25)", "Ls=10", "VSS 2", ""])

    draw_table("Sable grossier 0/4", 
               ["2D", "1.4D", "D", "<1mm", "<250um", "<63um", "Mod. CF", "SE(10)"],
               ["8", "5.6", "4", "-", "-", "-", "-", "-"],
               [data_sgros['2d'], data_sgros['1_4d'], data_sgros['d'], data_sgros['p_1mm'], data_sgros['p_250'], data_sgros['f'], data_sgros['mf'], data_sgros['se']],
               ["100", "95-100", "85-99", "e40(±20)", "e50(±20)", "Ls=16", "2.4-4.0", "Vsi 60"])

    # GRAPHIQUE
    chart_buf = generate_granulometry_chart(data_g10, data_g4, data_sfin, data_sgros)
    pdf.image(chart_buf, x=10, y=pdf.get_y(), w=190)
    pdf.set_y(pdf.get_y() + 75)

    # SIGNATURES
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
def show(supabase_client, can_edit=False, is_admin=False):
    st.title("🪨 Identification Granulats pour Béton")
    st.caption("Laboratoire de Contrôle Externe - Projet LGV CASA SUD")

    tabs = st.tabs(["➕ Saisie & Génération", "📋 Consultation & Base de Données"])

    # ----------------------------------------------------
    # ONGLET 1 : SAISIE ET ENREGISTREMENT
    # ----------------------------------------------------
    with tabs[0]:
        st.subheader("1. Informations Générales")
        c1, c2 = st.columns(2)
        with c1:
            num_pv_seq = st.number_input("N° PV", value=1237, step=1)
            num_rapport = f"26/260/LGV/CS/{num_pv_seq}"
            st.info(f"Rapport : **{num_rapport}**")
            client = st.text_input("Client", value="TGCC")
            chantier = st.text_area("Chantier", value="TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000-GARE CASA SUD")
        with c2:
            num_dossier = st.text_input("N° Dossier", value="2025-260-05985-2025 0247")
            date_prelevement = st.date_input("Date du prélèvement")
            lieux = st.text_input("Lieux de prélèvement", value="Stock sur centrale à béton")
            provenance = st.text_input("Provenance échantillon", value="TG PREFA OULAD SALEH")

        st.markdown("---")
        st.subheader("2. Saisie des Essais par Classe Granulaire")
        
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
        
        header_data = {
            "num_pv_seq": num_pv_seq, "num_rapport": num_rapport, "client": client, 
            "chantier": chantier, "num_dossier": num_dossier, 
            "date_prelevement": str(date_prelevement), "lieux": lieux, "provenance": provenance
        }

        payload_db = {
            **header_data,
            "g10_2d": g10_20["2d"], "g10_14d": g10_20["1_4d"], "g10_d": g10_20["d"], "g10_dmin": g10_20["d_min"],
            "g10_d2": g10_20["d_2"], "g10_f": g10_20["f"], "g10_fi": g10_20["fi"], "g10_la": g10_20["la"],
            
            "g4_2d": g4_10["2d"], "g4_14d": g4_10["1_4d"], "g4_d": g4_10["d"], "g4_dmin": g4_10["d_min"],
            "g4_d2": g4_10["d_2"], "g4_f": g4_10["f"], "g4_fi": g4_10["fi"], "g4_la": g4_10["la"],
            
            "sf_2d": s_fin["2d"], "sf_14d": s_fin["1_4d"], "sf_d": s_fin["d"], "sf_p1": s_fin["p_1mm"],
            "sf_p250": s_fin["p_250"], "sf_f": s_fin["f"], "sf_mb": s_fin["mb"],
            
            "sg_2d": s_gros["2d"], "sg_14d": s_gros["1_4d"], "sg_d": s_gros["d"], "sg_p1": s_gros["p_1mm"],
            "sg_p250": s_gros["p_250"], "sg_f": s_gros["f"], "sg_mf": s_gros["mf"], "sg_se": s_gros["se"]
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
            if st.button("💾 Enregistrer dans Supabase", type="primary", use_container_width=True):
                if supabase_client:
                    try:
                        supabase_client.table("pv_granulats").upsert(payload_db, on_conflict="num_rapport").execute()
                        st.success(f"✅ PV Granulats {num_rapport} enregistré avec succès !")
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'enregistrement : {e}")
                else:
                    st.warning("Client Supabase non connecté.")

    # ----------------------------------------------------
    # ONGLET 2 : CONSULTATION, IMPRESSION & GESTION DU PV
    # ----------------------------------------------------
    with tabs[1]:
        if supabase_client:
            try:
                res = supabase_client.table("pv_granulats").select("*").order("created_at", desc=True).execute()
                if res.data:
                    df = pd.DataFrame(res.data)
                    
                    # 1. Menu de sélection du PV (Identique à l'image)
                    rapports_list = df["num_rapport"].tolist()
                    selected_rapport = st.selectbox("🔍 Choisir un N° de Rapport / PV :", options=rapports_list)
                    
                    pv_data = df[df["num_rapport"] == selected_rapport].iloc[0]
                    
                    # 2. Section d'affichage structurée
                    with st.expander(f"📄 Détails du PV Granulats : {pv_data['num_rapport']}", expanded=True):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Client :** {pv_data.get('client', '-')}")
                            st.markdown(f"**N° Dossier :** {pv_data.get('num_dossier', '-')}")
                            st.markdown(f"**Lieu de prélèvement :** {pv_data.get('lieux', '-')}")
                        with c2:
                            st.markdown(f"**Date Prélèvement :** {pv_data.get('date_prelevement', '-')}")
                            st.markdown(f"**Chantier :** {pv_data.get('chantier', '-')}")
                            st.markdown(f"**Provenance :** {pv_data.get('provenance', '-')}")
                        
                        st.markdown("---")
                        st.markdown("**Synthèse des mesures granulométriques :**")
                        
                        # Tableau récapitulatif
                        summary_rows = [
                            {"Classe Granulaire": "Gravillons GII 10/20", "2D": pv_data.get("g10_2d"), "1.4D": pv_data.get("g10_14d"), "D": pv_data.get("g10_d"), "d": pv_data.get("g10_dmin"), "d/2": pv_data.get("g10_d2"), "f (<63µm)": pv_data.get("g10_f"), "FI": pv_data.get("g10_fi"), "LA": pv_data.get("g10_la")},
                            {"Classe Granulaire": "Gravillons GI 4/10", "2D": pv_data.get("g4_2d"), "1.4D": pv_data.get("g4_14d"), "D": pv_data.get("g4_d"), "d": pv_data.get("g4_dmin"), "d/2": pv_data.get("g4_d2"), "f (<63µm)": pv_data.get("g4_f"), "FI": pv_data.get("g4_fi"), "LA": pv_data.get("g4_la")},
                            {"Classe Granulaire": "Sable fin 0/0.630", "2D": pv_data.get("sf_2d"), "1.4D": pv_data.get("sf_14d"), "D": pv_data.get("sf_d"), "d": "-", "d/2": "-", "f (<63µm)": pv_data.get("sf_f"), "MB": pv_data.get("sf_mb"), "LA": "-"},
                            {"Classe Granulaire": "Sable grossier 0/4", "2D": pv_data.get("sg_2d"), "1.4D": pv_data.get("sg_14d"), "D": pv_data.get("sg_d"), "d": "-", "d/2": "-", "f (<63µm)": pv_data.get("sg_f"), "Mod. CF": pv_data.get("sg_mf"), "SE(10)": pv_data.get("sg_se")}
                        ]
                        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # 3. Rangée des 3 boutons d'action (Même disposition que sur l'image)
                        b_col1, b_col2, b_col3 = st.columns(3)
                        
                        with b_col1:
                            # Re-génération du PDF pour téléchargement direct
                            header_pdf = {
                                "num_rapport": pv_data["num_rapport"], "client": pv_data["client"],
                                "chantier": pv_data["chantier"], "num_dossier": pv_data["num_dossier"],
                                "date_prelevement": str(pv_data["date_prelevement"]),
                                "lieux": pv_data["lieux"], "provenance": pv_data["provenance"]
                            }
                            g10 = {"2d": pv_data["g10_2d"], "1_4d": pv_data["g10_14d"], "d": pv_data["g10_d"], "d_min": pv_data["g10_dmin"], "d_2": pv_data["g10_d2"], "f": pv_data["g10_f"], "fi": pv_data["g10_fi"], "la": pv_data["g10_la"]}
                            g4 = {"2d": pv_data["g4_2d"], "1_4d": pv_data["g4_14d"], "d": pv_data["g4_d"], "d_min": pv_data["g4_dmin"], "d_2": pv_data["g4_d2"], "f": pv_data["g4_f"], "fi": pv_data["g4_fi"], "la": pv_data["g4_la"]}
                            sf = {"2d": pv_data["sf_2d"], "1_4d": pv_data["sf_14d"], "d": pv_data["sf_d"], "p_1mm": pv_data["sf_p1"], "p_250": pv_data["sf_p250"], "f": pv_data["sf_f"], "mb": pv_data["sf_mb"]}
                            sg = {"2d": pv_data["sg_2d"], "1_4d": pv_data["sg_14d"], "d": pv_data["sg_d"], "p_1mm": pv_data["sg_p1"], "p_250": pv_data["sg_p250"], "f": pv_data["sg_f"], "mf": pv_data["sg_mf"], "se": pv_data["sg_se"]}
                            
                            pdf_export = generate_pv_granulats_pdf(header_pdf, g10, g4, sf, sg)
                            st.download_button(
                                label="🖨️ Imprimer / PDF",
                                data=pdf_export,
                                file_name=f"PV_Granulats_{pv_data.get('num_pv_seq', 'export')}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary"
                            )
                        
                        with b_col2:
                            if st.button("✏️ Modifier ce PV", use_container_width=True):
                                st.info("Pensez à charger ce PV dans le premier onglet pour le modifier.")
                        
                        with b_col3:
                            if st.button("🗑️ Supprimer ce PV", use_container_width=True):
                                supabase_client.table("pv_granulats").delete().eq("num_rapport", pv_data["num_rapport"]).execute()
                                st.success(f"PV {pv_data['num_rapport']} supprimé avec succès !")
                                st.rerun()

                else:
                    st.info("Aucun PV enregistré dans la base de données.")
            except Exception as e:
                st.error(f"Erreur lors du chargement des PVs : {e}")
