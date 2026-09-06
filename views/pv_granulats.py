import io
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# ==========================================
# 1. TAMIS ET FRACTIONS STANDARDS (NM / EN)
# ==========================================
TAMIS_STANDARD = [
    100.0, 80.0, 63.0, 50.0, 40.0, 31.5, 25.0, 20.0, 16.0, 14.0, 12.5,
    10.0, 8.0, 6.3, 5.0, 4.0, 3.15, 2.5, 2.0, 1.6, 1.25, 1.0, 0.8,
    0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063,
]

TAMIS_MF = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125]

FRACTIONS_CONFIG = {
    "GII": {"nom": "Gravette II (10/20)", "tamis_defaut": TAMIS_STANDARD},
    "GI": {"nom": "Gravette I (4/10)", "tamis_defaut": [t for t in TAMIS_STANDARD if t <= 31.5]},
    "SC": {"nom": "Sable Concassé (0/4)", "tamis_defaut": [t for t in TAMIS_STANDARD if t <= 10.0]},
    "SD": {"nom": "Sable Doux / Dune (0/2)", "tamis_defaut": [t for t in TAMIS_STANDARD if t <= 5.0]},
}

# ==========================================
# 2. LOGIQUE DE CALCUL CONFORME
# ==========================================
def calculer_feuille_essai(m1, m2, fond_p, dict_refus, tamis_list, proced_lavage=True):
    if not proced_lavage:
        m2 = m1

    fines_lavage = max(0.0, m1 - m2)

    df = pd.DataFrame({"Tamis (mm)": tamis_list})
    df["Refus Partiel Ri (g)"] = df["Tamis (mm)"].map(lambda t: float(dict_refus.get(t, 0.0)))

    if m1 > 0:
        df["% Refus Partiel"] = (df["Refus Partiel Ri (g)"] / m1) * 100.0
        df["% Refus Cumulé"] = df["% Refus Partiel"].cumsum()
        df["% Passant Cumulé"] = 100.0 - df["% Refus Cumulé"]
    else:
        df["% Refus Partiel"] = 0.0
        df["% Refus Cumulé"] = 0.0
        df["% Passant Cumulé"] = 100.0

    df["% Passant Cumulé"] = df["% Passant Cumulé"].clip(lower=0.0, upper=100.0)
    df["% Refus Cumulé"] = df["% Refus Cumulé"].clip(lower=0.0, upper=100.0)

    # Règle d'arrondi (*) : Entier le plus proche, sauf 0,063 mm (1 décimale)
    def formater_tamisat(row):
        t = row["Tamis (mm)"]
        val = row["% Passant Cumulé"]
        if abs(t - 0.063) < 1e-4:
            return f"{val:.1f}".replace(".", ",")
        return f"{int(round(val))}"

    df["Tamisats (*) 100-∑((Ri/M1)x100)"] = df.apply(formater_tamisat, axis=1)

    sum_ri = df["Refus Partiel Ri (g)"].sum()
    sum_ri_p = sum_ri + fond_p

    pct_fines = (((fines_lavage + fond_p) / m1) * 100.0) if m1 > 0 else 0.0
    ecart_masse = (((m2 - sum_ri_p) / m2) * 100.0) if m2 > 0 else 0.0

    return {
        "df": df,
        "m1": m1,
        "m2": m2,
        "fines_lavage": fines_lavage,
        "fond_p": fond_p,
        "sum_ri": sum_ri,
        "sum_ri_p": sum_ri_p,
        "pct_fines": pct_fines,
        "ecart_masse": ecart_masse,
        "procede": "Lavage et tamisage" if proced_lavage else "Tamisage par voie sèche",
    }

# ==========================================
# 3. GÉNÉRATEUR D'EXCEL AVEC MISE EN PAGE EXACTE
# ==========================================
def ajouter_feuille_essai_excel(wb, title, key, infos_pv, data_frac):
    ws = wb.create_sheet(title=f"Feuille {key}")

    # Remplissage Jaune exact pour les champs de saisie du labo
    fill_yellow = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    fill_header = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    font_bold = Font(name="Arial", size=9, bold=True)
    font_regular = Font(name="Arial", size=9)
    font_italic = Font(name="Arial", size=8, italic=True)

    # Entête supérieure
    ws["A1"] = "Référence échantillon :"
    ws["A1"].font = font_bold
    ws["B1"] = data_frac.get("nom", key)
    ws["B1"].fill = fill_yellow
    ws["B1"].alignment = Alignment(horizontal="center")
    ws["B1"].font = font_bold

    ws["D1"] = "Date de l'essai :"
    ws["D1"].font = font_bold
    ws["E1"] = str(infos_pv.get("date_essai", ""))
    ws["E1"].fill = fill_yellow
    ws["E1"].alignment = Alignment(horizontal="center")
    ws["E1"].font = font_bold

    ws["A2"] = "Procédé utilisé"
    ws["A2"].font = font_bold
    ws["B2"] = "(rayer la mention inutile)"
    ws["B2"].font = font_italic
    
    proc_str = "⦿ Lavage et tamisage   ◯ Tamisage par voie sèche" if "Lavage" in data_frac["procede"] else "◯ Lavage et tamisage   ⦿ Tamisage par voie sèche"
    ws["C2"] = proc_str
    ws["C2"].font = font_regular

    ws["D2"] = "Masse sèche totale en g  M₁ ="
    ws["D2"].font = font_regular
    ws["E2"] = data_frac["m1"]
    ws["E2"].fill = fill_yellow
    ws["E2"].font = font_bold
    ws["E2"].alignment = Alignment(horizontal="right")

    ws["F2"] = "ou (granulats impropres) M'₁ ="
    ws["F2"].font = font_regular

    ws["A3"] = "Masse sèche après lavage en g M₂ ="
    ws["A3"].font = font_regular
    ws["B3"] = data_frac["m2"]
    ws["B3"].fill = fill_yellow
    ws["B3"].font = font_bold
    ws["B3"].alignment = Alignment(horizontal="right")

    ws["C3"] = "Masse sèche des fines retirées par lavage M₁ - M₂ ="
    ws["C3"].font = font_regular
    ws["D3"] = data_frac["fines_lavage"]
    ws["D3"].font = font_bold

    # En-têtes des colonnes du tableau
    headers = [
        "Ouverture\ndes tamis\n(mm)",
        "Masse\nde refus\nRi  (g)",
        "Pourcentage\nde refus\n(Ri / M₁) x 100",
        "Pourcentage\nde refus\ncumulés",
        "Pourcentage\ncumulé de\ntamisats (*)\n100-∑((Ri/M₁) x 100)",
    ]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font = font_bold
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws.row_dimensions[4].height = 45

    df_data = data_frac["df"]
    start_row = 5

    for idx, r in df_data.iterrows():
        r_idx = start_row + idx
        t_val = r["Tamis (mm)"]

        # Ouverture tamis (mm)
        c1 = ws.cell(row=r_idx, column=1, value=t_val if t_val != int(t_val) else int(t_val))
        c1.alignment = Alignment(horizontal="center")
        c1.font = font_bold

        # Masse de refus Ri (g) -> Jaune
        c2 = ws.cell(row=r_idx, column=2, value=round(r["Refus Partiel Ri (g)"], 1))
        c2.fill = fill_yellow
        c2.alignment = Alignment(horizontal="right")

        # Pourcentage de refus
        c3 = ws.cell(row=r_idx, column=3, value=round(r["% Refus Partiel"], 1))
        c3.alignment = Alignment(horizontal="right")

        # Pourcentage de refus cumulés
        c4 = ws.cell(row=r_idx, column=4, value=round(r["% Refus Cumulé"], 1))
        c4.alignment = Alignment(horizontal="right")

        # Tamisats (*) - Règle d'arrondi
        passant_val = r["% Passant Cumulé"]
        if abs(t_val - 0.063) < 1e-4:
            c5 = ws.cell(row=r_idx, column=5, value=round(passant_val, 1))
        else:
            c5 = ws.cell(row=r_idx, column=5, value=int(round(passant_val)))
        c5.alignment = Alignment(horizontal="right")

        for cell in [c1, c2, c3, c4, c5]:
            cell.border = thin_border

    # Bloc latéral droit (Nota, Formules et Écarts)
    ws["F4"] = "Nota :"
    ws["F4"].font = font_bold

    ws["F5"] = "La masse sèche de la prise d'essai devrait être portée en M1, lorsqu'elle est déterminée directement, ou en M1', lorsqu'elle est calculée à partir d'une prise d'essai en double."
    ws["F5"].font = font_regular

    ws["F11"] = "Matériau resté au fond (en g)  P ="
    ws["F11"].font = font_regular
    ws["G11"] = data_frac["fond_p"]
    ws["G11"].fill = fill_yellow
    ws["G11"].font = font_bold
    ws["G11"].alignment = Alignment(horizontal="right")

    ws["F14"] = "Pourcentage de tamisat de fines (f) sur le tamis de 63 µm est :"
    ws["F14"].font = font_regular
    ws["F15"] = "100 x ((M1 - M2) + P) / M1"
    ws["F15"].font = font_regular
    ws["F16"] = "(à la première décimale la plus proche)"
    ws["F16"].font = font_italic

    ws["F17"] = "égale à :"
    ws["F17"].font = font_regular
    ws["G17"] = round(data_frac["pct_fines"], 1)
    ws["G17"].font = font_bold
    ws["G17"].alignment = Alignment(horizontal="right")
    ws["H17"] = "%"
    ws["H17"].font = font_regular

    ws["F19"] = "ΣRi + P ="
    ws["F19"].font = font_regular
    ws["G19"] = round(data_frac["sum_ri_p"], 1)
    ws["G19"].font = font_bold
    ws["G19"].alignment = Alignment(horizontal="right")
    ws["H19"] = "g"
    ws["H19"].font = font_regular

    ws["F21"] = "100 x (M2 - (ΣRi + P)) / M2"
    ws["F21"].font = font_regular

    ws["F23"] = "soit :"
    ws["F23"].font = font_regular
    ws["G23"] = round(data_frac["ecart_masse"], 2)
    ws["G23"].font = font_bold
    ws["G23"].alignment = Alignment(horizontal="right")
    ws["H23"] = "%"
    ws["H23"].font = font_regular

    ws["F25"] = "(doit être < 1 %)"
    ws["F25"].font = font_italic

    last_table_row = start_row + len(df_data) + 1
    ws.cell(row=last_table_row, column=1, value="(*) au nombre entier le plus proche sauf pour le tamis 0,063 mm un chiffre après la virgule").font = font_italic

    # Ajustement des largeurs de colonnes
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 22
    ws.column_dimensions["F"].width = 48

def generer_pv_excel_complet(infos_pv, resultats_fractions):
    wb = openpyxl.Workbook()

    # Feuille 1 : PV Synthèse
    ws_pv = wb.active
    ws_pv.title = "PV Synthèse"

    ws_pv.merge_cells("A1:G1")
    ws_pv["A1"] = "PROCES-VERBAL D'ESSAI : ANALYSE GRANULOMETRIQUE"
    ws_pv["A1"].font = Font(size=14, bold=True, color="1F497D")
    ws_pv["A1"].alignment = Alignment(horizontal="center", vertical="center")

    infos = [
        ("N° PV :", infos_pv.get("num_pv", "")),
        ("Date d'essai :", str(infos_pv.get("date_essai", ""))),
        ("Chantier / Projet :", infos_pv.get("chantier", "")),
        ("Client :", infos_pv.get("client", "")),
        ("Norme de référence :", infos_pv.get("norme", "NM 10.1.271 / EN 933-1")),
        ("Opérateur :", infos_pv.get("operateur", "")),
    ]

    row_idx = 3
    for label, val in infos:
        ws_pv.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
        ws_pv.cell(row=row_idx, column=2, value=val)
        row_idx += 1

    row_idx += 1
    ws_pv.cell(row=row_idx, column=1, value="Synthèse des Passants Cumulés (%)").font = Font(bold=True, size=11)
    row_idx += 1

    headers = ["Tamis (mm)"] + list(resultats_fractions.keys())
    for col_idx, h in enumerate(headers, 1):
        cell = ws_pv.cell(row=row_idx, column=col_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    row_idx += 1
    for t in TAMIS_STANDARD:
        ws_pv.cell(row=row_idx, column=1, value=t).alignment = Alignment(horizontal="center")
        for col_idx, key in enumerate(resultats_fractions.keys(), 2):
            df_frac = resultats_fractions[key]["df"]
            val_row = df_frac[df_frac["Tamis (mm)"] == t]
            if not val_row.empty:
                p_val = round(val_row["% Passant Cumulé"].values[0], 1)
                ws_pv.cell(row=row_idx, column=col_idx, value=p_val).alignment = Alignment(horizontal="center")
            else:
                ws_pv.cell(row=row_idx, column=col_idx, value="-").alignment = Alignment(horizontal="center")
        row_idx += 1

    for key, data in resultats_fractions.items():
        ajouter_feuille_essai_excel(wb, data["nom"], key, infos_pv, data)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

# ==========================================
# 4. INTERFACE UTILISATEUR STREAMLIT
# ==========================================
def show(supabase=None, supabase_client=None, *args, **kwargs):
    st.title("🧪 Feuille d'Essai d'Analyse Granulométrique")
    st.caption("Conforme à la norme NM 10.1.271 / NF EN 933-1")

    with st.expander("📌 Informations du Procès-Verbal (PV)", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            num_pv = st.text_input("N° PV", value="PV-2026-1237")
            client = st.text_input("Client", value="LPEE - Laboratoire BTP")
        with col_b:
            chantier = st.text_input("Chantier / Ouvrage", value="LGV CASA SUD / Ouvrage PRO 0636")
            date_essai = st.date_input("Date de l'essai")
        with col_c:
            norme = st.text_input("Norme d'essai", value="NM 10.1.271 / NF EN 933-1")
            operateur = st.text_input("Opérateur", value="Technicien LPEE")

    infos_pv = {
        "num_pv": num_pv,
        "client": client,
        "chantier": chantier,
        "date_essai": date_essai,
        "norme": norme,
        "operateur": operateur,
    }

    st.divider()

    tabs = st.tabs([
        "GII - Gravette II (10/20)",
        "GI - Gravette I (4/10)",
        "SC - Sable Concassé (0/4)",
        "SD - Sable Doux (0/2)",
    ])

    dict_fractions_data = {}
    keys_fractions = ["GII", "GI", "SC", "SD"]

    for i, tab in enumerate(tabs):
        key = keys_fractions[i]
        config = FRACTIONS_CONFIG[key]

        with tab:
            st.markdown(f"### **Feuille d'Essai : {config['nom']}**")

            c_h1, c_h2 = st.columns(2)
            with c_h1:
                st.markdown(f"**Référence échantillon :** `{config['nom']}`")
            with c_h2:
                st.markdown(f"**Date de l'essai :** `{date_essai}`")

            st.markdown("---")

            c_p1, c_p2, c_p3 = st.columns([2, 2, 2])
            with c_p1:
                procede_lavage = (
                    st.radio(
                        "Procédé utilisé",
                        ["Lavage et tamisage", "Tamisage par voie sèche"],
                        key=f"proc_{key}",
                    )
                    == "Lavage et tamisage"
                )
            with c_p2:
                m1 = st.number_input(
                    "Masse sèche totale en g (M₁)",
                    min_value=100.0,
                    max_value=20000.0,
                    value=4110.5 if key == "GII" else 1000.0,
                    step=0.1,
                    key=f"m1_{key}",
                )
            with c_p3:
                m2 = st.number_input(
                    "Masse sèche après lavage en g (M₂)",
                    min_value=0.0,
                    max_value=m1,
                    value=4095.2 if key == "GII" else m1,
                    step=0.1,
                    disabled=not procede_lavage,
                    key=f"m2_{key}",
                )

            fines_lavage_calc = max(0.0, m1 - m2) if procede_lavage else 0.0
            st.info(f"**Masse sèche des fines retirées par lavage (M₁ - M₂) :** `{fines_lavage_calc:.1f} g`")

            st.markdown("---")

            col_left, col_right = st.columns([3, 2])

            with col_left:
                st.markdown("#### **Saisie des Refus Partiels Ri (g)**")

                tamis_choisis = st.multiselect(
                    f"Série de tamis pour {key} (mm)",
                    options=TAMIS_STANDARD,
                    default=config["tamis_defaut"],
                    key=f"tamis_select_{key}",
                )
                tamis_choisis = sorted(tamis_choisis, reverse=True)

                refus_dict = {}
                cols_per_row = 4
                cols = st.columns(cols_per_row)

                for idx, t in enumerate(tamis_choisis):
                    col_curr = cols[idx % cols_per_row]

                    val_defaut = 0.0
                    if key == "GII":
                        ex_vals = {
                            20.0: 199.7, 16.0: 2200.3, 14.0: 732.7, 12.5: 308.7,
                            10.0: 424.0, 8.0: 163.2, 6.3: 45.0, 5.0: 6.9,
                            4.0: 2.1, 3.15: 0.2, 2.5: 0.1, 2.0: 0.2, 1.6: 0.2,
                            1.25: 0.1, 1.0: 0.1, 0.8: 0.1, 0.63: 0.2, 0.5: 0.1,
                            0.4: 0.1, 0.315: 0.1, 0.25: 0.1, 0.2: 0.1, 0.16: 0.2,
                            0.125: 0.1, 0.1: 0.1, 0.08: 0.1, 0.063: 0.1,
                        }
                        val_defaut = ex_vals.get(t, 0.0)

                    val_refus = col_curr.number_input(
                        f"Tamis {t} mm",
                        min_value=0.0,
                        max_value=m1,
                        value=val_defaut,
                        step=0.1,
                        key=f"refus_{key}_{t}",
                    )
                    refus_dict[t] = val_refus

            with col_right:
                st.markdown("#### **Calculs & Contrôles**")

                fond_p = st.number_input(
                    "Matériau resté au fond P (g)",
                    min_value=0.0,
                    max_value=500.0,
                    value=1.3 if key == "GII" else 0.5,
                    step=0.1,
                    key=f"p_{key}",
                )

                res = calculer_feuille_essai(
                    m1, m2, fond_p, refus_dict, tamis_choisis, procede_lavage
                )
                res["nom"] = config["nom"]
                dict_fractions_data[key] = res

                st.warning(
                    "**Nota :** La masse sèche de la prise d'essai devrait être portée en M1, "
                    "lorsqu'elle est déterminée directement, ou en M1', lorsqu'elle est calculée à partir d'une prise d'essai en double."
                )

                st.markdown("**Pourcentage de tamisats de fines (f) sur 63 µm :**")
                st.markdown(r"$$\frac{100 \times ((M_1 - M_2) + P)}{M_1} = " + f"{res['pct_fines']:.1f}\\%$$")

                st.markdown(f"**Somme des refus + Fond :** $\\Sigma R_i + P = {res['sum_ri_p']:.1f}\\text{{ g}}$")

                st.markdown("**Écart de masse :**")
                st.markdown(r"$$\frac{100 \times (M_2 - (\Sigma R_i + P))}{M_2} = " + f"{res['ecart_masse']:.2f}\\%$$")

                if abs(res["ecart_masse"]) < 1.0:
                    st.success("✅ Conforme (Écart < 1 %)")
                else:
                    st.error("❌ Non Conforme (Écart ≥ 1 %)")

            st.markdown("---")
            st.dataframe(
                res["df"],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("(*) au nombre entier le plus proche sauf pour le tamis 0,063 mm un chiffre après la virgule")

    st.divider()

    st.subheader("📈 Courbe Granulométrique Globale")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = {"GII": "#1f77b4", "GI": "#ff7f0e", "SC": "#2ca02c", "SD": "#d62728"}

    for key in keys_fractions:
        df_f = dict_fractions_data[key]["df"]
        if not df_f.empty:
            ax.plot(
                df_f["Tamis (mm)"],
                df_f["% Passant Cumulé"],
                marker="o",
                linewidth=2,
                label=f"{key} - {FRACTIONS_CONFIG[key]['nom']}",
                color=colors[key],
            )

    ax.set_xscale("log")
    ax.set_xticks([0.063, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 31.5, 63.0])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

    ax.set_xlim(0.063, 100)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Ouverture des tamis (mm) - Échelle Logarithmique", fontsize=10, fontweight="bold")
    ax.set_ylabel("% Passants Cumulés", fontsize=10, fontweight="bold")
    ax.set_title("Courbes Granulométriques des Granulats", fontsize=12, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper left")

    st.pyplot(fig)

    st.subheader("📄 Exportation Excel (Génération de la Feuille Exacte)")
    pv_excel_bytes = generer_pv_excel_complet(infos_pv, dict_fractions_data)

    st.download_button(
        label="📥 Télécharger la Feuille d'Essai Conforme (Excel)",
        data=pv_excel_bytes,
        file_name=f"Feuille_Essai_Granulats_{num_pv}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
