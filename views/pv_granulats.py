import io
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import pandas as pd
import streamlit as st

# ==========================================
# CONSTANTES ET CONFIGURATION DES TAMIS
# ==========================================
TAMIS_STANDARD = [
    100.0, 80.0, 63.0, 50.0, 40.0, 31.5, 25.0, 20.0, 16.0, 14.0, 12.5,
    10.0, 8.0, 6.3, 5.0, 4.0, 3.15, 2.5, 2.0, 1.6, 1.25, 1.0, 0.8,
    0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063,
]

TAMIS_MF = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125]

FRACTIONS_CONFIG = {
    "GII": {
        "nom": "Gravette II (10/20)",
        "tamis_defaut": [
            100.0, 80.0, 63.0, 50.0, 40.0, 31.5, 25.0, 20.0, 16.0, 14.0,
            12.5, 10.0, 8.0, 6.3, 5.0, 4.0, 3.15, 2.5, 2.0, 1.6, 1.25,
            1.0, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125,
            0.1, 0.08, 0.063,
        ],
    },
    "GI": {
        "nom": "Gravette I (4/10)",
        "tamis_defaut": [
            31.5, 25.0, 20.0, 16.0, 14.0, 12.5, 10.0, 8.0, 6.3, 5.0,
            4.0, 3.15, 2.5, 2.0, 1.6, 1.25, 1.0, 0.8, 0.63, 0.5, 0.4,
            0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063,
        ],
    },
    "SC": {
        "nom": "Sable Concassé (0/4)",
        "tamis_defaut": [
            10.0, 8.0, 6.3, 5.0, 4.0, 3.15, 2.5, 2.0, 1.6, 1.25, 1.0,
            0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1,
            0.08, 0.063,
        ],
    },
    "SD": {
        "nom": "Sable Doux / Dune (0/2)",
        "tamis_defaut": [
            5.0, 4.0, 3.15, 2.5, 2.0, 1.6, 1.25, 1.0, 0.8, 0.63, 0.5,
            0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063,
        ],
    },
}

# ==========================================
# FONCTIONS DE CALCUL TECHNIQUE
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
        "procede": "Lavage et tamisage" if proced_lavage else "Tamisage à sec",
    }

def calculer_module_finesse(df_resultats):
    sum_refus = 0.0
    for t in TAMIS_MF:
        row = df_resultats[df_resultats["Tamis (mm)"] == t]
        if not row.empty:
            sum_refus += row["% Refus Cumulé"].values[0]
    return round(sum_refus / 100.0, 2)

# ==========================================
# GENERATION DU FICHIER EXCEL MULTI-ONGLETS
# ==========================================
def ajouter_feuille_essai_excel(wb, title, key, infos_pv, data_frac):
    ws = wb.create_sheet(title=f"Feuille {key}")

    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    gray_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    ws["A1"] = f"Référence échantillon : {data_frac['nom']}"
    ws["A1"].font = Font(bold=True)
    ws["F1"] = f"Date de l'essai : {infos_pv.get('date_essai', '')}"
    ws["F1"].font = Font(bold=True)

    ws["A2"] = f"Procédé utilisé : {data_frac['procede']}"
    ws["F2"] = f"Masse sèche totale M1 = {data_frac['m1']:.1f} g"
    ws["F2"].fill = yellow_fill

    ws["A3"] = f"Masse sèche après lavage M2 = {data_frac['m2']:.1f} g"
    ws["A3"].fill = yellow_fill
    ws["F3"] = f"Masse des fines retirées (M1 - M2) = {data_frac['fines_lavage']:.1f} g"

    headers = [
        "Ouverture des tamis (mm)",
        "Masse de refus Ri (g)",
        "Pourcentage de refus (Ri / M1) x 100",
        "Pourcentage de refus cumulés",
        "Pourcentage cumulé de tamisats (100 - %Refus)",
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_idx, value=h)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        cell.fill = gray_fill

    df_data = data_frac["df"]
    start_row = 6

    for idx, r in df_data.iterrows():
        r_idx = start_row + idx
        c1 = ws.cell(row=r_idx, column=1, value=r["Tamis (mm)"])
        c1.alignment = Alignment(horizontal="center")
        c1.font = Font(bold=True)

        c2 = ws.cell(row=r_idx, column=2, value=round(r["Refus Partiel Ri (g)"], 1))
        c2.fill = yellow_fill
        c2.alignment = Alignment(horizontal="right")

        c3 = ws.cell(row=r_idx, column=3, value=round(r["% Refus Partiel"], 1))
        c3.alignment = Alignment(horizontal="right")

        c4 = ws.cell(row=r_idx, column=4, value=round(r["% Refus Cumulé"], 1))
        c4.alignment = Alignment(horizontal="right")

        c5 = ws.cell(row=r_idx, column=5, value=round(r["% Passant Cumulé"], 1))
        c5.alignment = Alignment(horizontal="right")

        for cell in [c1, c2, c3, c4, c5]:
            cell.border = thin_border

    ws["F5"] = "Nota :"
    ws["F5"].font = Font(bold=True)
    ws["F6"] = "La masse sèche de la prise d'essai devrait être portée en M1, lorsqu'elle est déterminée directement."

    ws["F9"] = f"Matériau resté au fond (en g) P = {data_frac['fond_p']:.1f}"
    ws["F9"].fill = yellow_fill
    ws["F9"].font = Font(bold=True)

    ws["F12"] = "Pourcentage de tamisat de fines (f) sur le tamis de 63 µm :"
    ws["F13"] = "100 x ((M1 - M2) + P) / M1"
    ws["F14"] = f"égale à : {data_frac['pct_fines']:.1f} %"
    ws["F14"].font = Font(bold=True)

    ws["F17"] = f"Σ Ri + P = {data_frac['sum_ri_p']:.1f} g"
    ws["F17"].font = Font(bold=True)

    ws["F19"] = "100 x (M2 - (Σ Ri + P)) / M2"
    ws["F20"] = f"soit : {data_frac['ecart_masse']:.2f} %"
    ws["F20"].font = Font(bold=True)
    ws["F21"] = "(doit être < 1 %)"
    ws["F21"].font = Font(italic=True)

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 25
    ws.column_dimensions["F"].width = 45

def generer_pv_excel_complet(infos_pv, resultats_fractions):
    wb = openpyxl.Workbook()

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

    row_idx += 1
    ws_pv.cell(row=row_idx, column=1, value="Module de Finesse (MF)").font = Font(bold=True)
    for col_idx, key in enumerate(resultats_fractions.keys(), 2):
        mf = resultats_fractions[key].get("mf", "-")
        ws_pv.cell(row=row_idx, column=col_idx, value=mf if mf is not None else "-").font = Font(bold=True)
        ws_pv.cell(row=row_idx, column=col_idx).alignment = Alignment(horizontal="center")

    for key, data in resultats_fractions.items():
        ajouter_feuille_essai_excel(wb, data["nom"], key, infos_pv, data)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

# ==========================================
# FONCTION PRINCIPALE EXECUTEE PAR LE ROUTEUR
# ==========================================
def show(supabase=None, supabase_client=None, *args, **kwargs):
    st.title("🧪 Module Granulats : Analyse Granulométrique & Feuilles d'Essais")
    st.markdown("Saisie complète des feuilles d'essais pour **GII, GI, SC, SD** selon NF EN 933-1 / NM 10.1.271.")

    with st.expander("📌 Informations du Procès-Verbal (PV)", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            num_pv = st.text_input("N° PV", value="PV-2026-1237")
            client = st.text_input("Client", value="LPEE - Projet BTP")
        with col_b:
            chantier = st.text_input("Chantier / Ouvrage", value="LGV / Ouvrage d'art")
            date_essai = st.date_input("Date de l'essai")
        with col_c:
            norme = st.text_input("Norme d'essai", value="NM 10.1.271 / NF EN 933-1")
            operateur = st.text_input("Technicien / Opérateur", value="Laboratoire LPEE")

    infos_pv = {
        "num_pv": num_pv,
        "client": client,
        "chantier": chantier,
        "date_essai": date_essai,
        "norme": norme,
        "operateur": operateur,
    }

    st.divider()
    st.subheader("📝 Saisie des Feuilles d'Essais")

    tabs = st.tabs([
        "GII - Gravette II",
        "GI - Gravette I",
        "SC - Sable Concassé",
        "SD - Sable Doux",
    ])

    dict_fractions_data = {}
    keys_fractions = ["GII", "GI", "SC", "SD"]

    for i, tab in enumerate(tabs):
        key = keys_fractions[i]
        config = FRACTIONS_CONFIG[key]

        with tab:
            st.markdown(f"### **Feuille d'Essai : {config['nom']}**")

            c_p1, c_p2, c_p3, c_p4 = st.columns(4)
            with c_p1:
                procede_lavage = (
                    st.radio(
                        f"Procédé utilisé [{key}]",
                        ["Lavage et tamisage", "Tamisage à sec"],
                        key=f"proc_{key}",
                    )
                    == "Lavage et tamisage"
                )
            with c_p2:
                m1 = st.number_input(
                    f"Masse sèche totale M1 (g) [{key}]",
                    min_value=100.0,
                    max_value=20000.0,
                    value=4110.5 if key == "GII" else (5000.0 if "G" in key else 1000.0),
                    step=10.0,
                    key=f"m1_{key}",
                )
            with c_p3:
                m2 = st.number_input(
                    f"Masse sèche après lavage M2 (g) [{key}]",
                    min_value=0.0,
                    max_value=m1,
                    value=4095.2 if key == "GII" else m1,
                    step=10.0,
                    disabled=not procede_lavage,
                    key=f"m2_{key}",
                )
            with c_p4:
                fond_p = st.number_input(
                    f"Matériau resté au fond P (g) [{key}]",
                    min_value=0.0,
                    max_value=500.0,
                    value=1.3 if key == "GII" else 0.5,
                    step=0.1,
                    key=f"p_{key}",
                )

            tamis_choisis = st.multiselect(
                f"Série de tamis pour {key} (mm)",
                options=TAMIS_STANDARD,
                default=config["tamis_defaut"],
                key=f"tamis_select_{key}",
            )
            tamis_choisis = sorted(tamis_choisis, reverse=True)

            st.caption("Saisie des masses de refus partiels Ri (g) :")

            refus_dict = {}
            cols_per_row = 6
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
                    f"{t} mm",
                    min_value=0.0,
                    max_value=m1,
                    value=val_defaut,
                    step=1.0,
                    key=f"refus_{key}_{t}",
                )
                refus_dict[t] = val_refus

            res = calculer_feuille_essai(
                m1, m2, fond_p, refus_dict, tamis_choisis, procede_lavage
            )

            mf_val = None
            if key in ["SC", "SD"]:
                mf_val = calculer_module_finesse(res["df"])
                res["mf"] = mf_val

            res["nom"] = config["nom"]
            dict_fractions_data[key] = res

            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("Fines lavées (M1 - M2)", f"{res['fines_lavage']:.1f} g")
            col_res2.metric("Passants fines (< 63 µm)", f"{res['pct_fines']:.2f} %")
            col_res3.metric(
                "Écart de masse",
                f"{res['ecart_masse']:.2f} %",
                delta="Conforme (<1%)" if abs(res["ecart_masse"]) < 1.0 else "Non conforme",
            )

            st.dataframe(
                res["df"].style.format(
                    {
                        "Refus Partiel Ri (g)": "{:.1f}",
                        "% Refus Partiel": "{:.1f} %",
                        "% Refus Cumulé": "{:.1f} %",
                        "% Passant Cumulé": "{:.1f} %",
                    }
                ),
                use_container_width=True,
            )

    st.divider()

    st.subheader("📈 Courbe Granulométrique Globale")

    fig, ax = plt.subplots(figsize=(10, 5))
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
    ax.set_xlabel("Ouverture des tamis (mm) - Échelle Log", fontsize=10, fontweight="bold")
    ax.set_ylabel("% Passants Cumulés", fontsize=10, fontweight="bold")
    ax.set_title("Courbes Granulométriques des Granulats", fontsize=12, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper left")

    st.pyplot(fig)

    st.subheader("📄 Exportation Excel (PV + Feuille d'Essai par Classe)")

    pv_excel_bytes = generer_pv_excel_complet(infos_pv, dict_fractions_data)

    st.download_button(
        label="📥 Télécharger le PV et les 4 Feuilles d'Essais (Excel multi-onglets)",
        data=pv_excel_bytes,
        file_name=f"Analyse_Granulometrique_Complete_{num_pv}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
