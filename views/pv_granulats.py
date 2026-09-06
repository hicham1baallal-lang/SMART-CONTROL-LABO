import io
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Analyse Granulométrique - Granulats Béton", layout="wide"
)

# ------------------------------------------------------------------------------
# CONSTANTES & SÉRIES DE TAMIS REGLEMENTAIRES (NF EN 933-1 / NM 10.1.271)
# ------------------------------------------------------------------------------
TAMIS_STANDARD = [
    31.5,
    25.0,
    20.0,
    16.0,
    12.5,
    10.0,
    8.0,
    6.3,
    5.0,
    4.0,
    2.0,
    1.0,
    0.5,
    0.25,
    0.125,
    0.063,
]
TAMIS_MF = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125]  # Tamis pour module de finesse

FRACTIONS_CONFIG = {
    "GII": {"nom": "Gravette II (10/20)", "tamis_defaut": TAMIS_STANDARD[:10]},
    "GI": {"nom": "Gravette I (4/10)", "tamis_defaut": TAMIS_STANDARD[5:13]},
    "SC": {"nom": "Sable Concassé (0/4)", "tamis_defaut": TAMIS_STANDARD[9:]},
    "SD": {"nom": "Sable Doux / Dune (0/2)", "tamis_defaut": TAMIS_STANDARD[10:]},
}


# ------------------------------------------------------------------------------
# FONCTIONS COMPLEMENTAIRES DE CALCUL ET EXPORT
# ------------------------------------------------------------------------------
def calculer_granulo(m_masser_sec, dict_refus_partiels, tamis_list):
    """
    Calcule les refus cumulés (g), % refus cumulés et % passants cumulés.
    """
    df = pd.DataFrame({"Tamis (mm)": tamis_list})
    df["Refus Partiel (g)"] = df["Tamis (mm)"].map(
        lambda t: dict_refus_partiels.get(t, 0.0)
    )

    df["Refus Cumulé (g)"] = df["Refus Partiel (g)"].cumsum()

    if m_masser_sec > 0:
        df["% Refus Cumulé"] = (df["Refus Cumulé (g)"] / m_masser_sec) * 100
        df["% Passant Cumulé"] = 100.0 - df["% Refus Cumulé"]
    else:
        df["% Refus Cumulé"] = 0.0
        df["% Passant Cumulé"] = 100.0

    # Bornage entre 0 et 100%
    df["% Passant Cumulé"] = df["% Passant Cumulé"].clip(lower=0.0, upper=100.0)
    df["% Refus Cumulé"] = df["% Refus Cumulé"].clip(lower=0.0, upper=100.0)

    return df


def calculer_module_finesse(df_resultats):
    """
    Module de finesse (MF) = somme des % refus cumulés sur la série spécifiée / 100.
    """
    sum_refus = 0.0
    for t in TAMIS_MF:
        row = df_resultats[df_resultats["Tamis (mm)"] == t]
        if not row.empty:
            sum_refus += row["% Refus Cumulé"].values[0]
    return round(sum_refus / 100.0, 2)


def generer_pv_excel(infos_pv, resultats_fractions):
    """
    Génère le fichier Excel du Procès-Verbal (PV) mis en forme.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PV Analyse Granulométrique"

    # En-tête du PV
    ws.merge_cells("A1:G1")
    ws["A1"] = "PROCES-VERBAL D'ESSAI : ANALYSE GRANULOMETRIQUE"
    ws["A1"].font = Font(size=14, bold=True, color="1F497D")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    infos = [
        ("N° PV :", infos_pv.get("num_pv", "")),
        ("Date d'essai :", str(infos_pv.get("date_essai", ""))),
        ("Chantier / Projet :", infos_pv.get("chantier", "")),
        ("Client :", infos_pv.get("client", "")),
        ("Norme de référence :", infos_pv.get("norme", "NM 10.1.271 / EN 933-1")),
    ]

    row_idx = 3
    for label, val in infos:
        ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row_idx, column=2, value=val)
        row_idx += 1

    row_idx += 1

    # Tableau récapitulatif des Passants
    ws.cell(
        row=row_idx, column=1, value="Synthèse des Passants Cumulés (%)"
    ).font = Font(bold=True, size=11)
    row_idx += 1

    headers = ["Tamis (mm)"] + list(resultats_fractions.keys())
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(
            start_color="1F497D", end_color="1F497D", fill_type="solid"
        )
        cell.alignment = Alignment(horizontal="center")

    # Consolidation de la liste complète des tamis
    all_tamis = sorted(list(set(TAMIS_STANDARD)), reverse=True)

    row_idx += 1
    for t in all_tamis:
        ws.cell(row=row_idx, column=1, value=t).alignment = Alignment(
            horizontal="center"
        )
        for col_idx, key in enumerate(resultats_fractions.keys(), 2):
            df_frac = resultats_fractions[key]["data"]
            val_row = df_frac[df_frac["Tamis (mm)"] == t]
            if not val_row.empty:
                p_val = round(val_row["% Passant Cumulé"].values[0], 1)
                ws.cell(row=row_idx, column=col_idx, value=p_val).alignment = (
                    Alignment(horizontal="center")
                )
            else:
                ws.cell(row=row_idx, column=col_idx, value="-").alignment = (
                    Alignment(horizontal="center")
                )
        row_idx += 1

    # Modules de finesse pour SC et SD
    row_idx += 1
    ws.cell(row=row_idx, column=1, value="Module de Finesse (MF)").font = Font(
        bold=True
    )
    for col_idx, key in enumerate(resultats_fractions.keys(), 2):
        mf = resultats_fractions[key].get("mf", "-")
        ws.cell(row=row_idx, column=col_idx, value=mf if mf else "-").font = (
            Font(bold=True)
        )
        ws.cell(row=row_idx, column=col_idx).alignment = Alignment(
            horizontal="center"
        )

    # Export buffer
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ------------------------------------------------------------------------------
# INTERFACE STREAMLIT
# ------------------------------------------------------------------------------
st.title("🧪 Module Granulats : Analyse Granulométrique")
st.markdown(
    "Saisie des feuilles d'essais pour **GII, GI, SC, SD**, génération de la courbe granulométrique et du PV d'essai."
)

# Section 1: Informations Générales du PV
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

# Section 2: Saisie des feuilles d'essais par fraction
st.subheader("📝 Saisie des Feuilles d'Essais")

tabs = st.tabs(
    [
        "GII - Gravette II",
        "GI - Gravette I",
        "SC - Sable Concassé",
        "SD - Sable Doux",
    ]
)

dict_fractions_data = {}
keys_fractions = ["GII", "GI", "SC", "SD"]

for i, tab in enumerate(tabs):
    key = keys_fractions[i]
    config = FRACTIONS_CONFIG[key]

    with tab:
        st.markdown(f"#### Fraction : **{config['nom']}**")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            m_sec = st.number_input(
                f"Masse Sèche Initiale M0 (g) - [{key}]",
                min_value=100.0,
                max_value=20000.0,
                value=5000.0 if "G" in key else 1000.0,
                step=50.0,
                key=f"msec_{key}",
            )

        # Choix de la série de tamis
        tamis_choisis = st.multiselect(
            f"Série de tamis pour {key} (mm)",
            options=TAMIS_STANDARD,
            default=config["tamis_defaut"],
            key=f"tamis_select_{key}",
        )
        tamis_choisis = sorted(tamis_choisis, reverse=True)

        st.caption(
            "Entrez la masse du refus partiel pour chaque tamis (en grammes) :"
        )

        # Grille d'entrée dynamique pour les refus partiels
        refus_dict = {}
        cols_per_row = 4
        cols = st.columns(cols_per_row)

        for idx, t in enumerate(tamis_choisis):
            col_curr = cols[idx % cols_per_row]
            val_refus = col_curr.number_input(
                f"Tamis {t} mm",
                min_value=0.0,
                max_value=m_sec,
                value=0.0,
                step=5.0,
                key=f"refus_{key}_{t}",
            )
            refus_dict[t] = val_refus

        # Calculs granulométriques
        df_res = calculer_granulo(m_sec, refus_dict, tamis_choisis)

        mf_val = None
        if key in ["SC", "SD"]:
            mf_val = calculer_module_finesse(df_res)
            st.info(f"**Module de Finesse (MF) : {mf_val}**")

        dict_fractions_data[key] = {
            "m_sec": m_sec,
            "data": df_res,
            "mf": mf_val,
        }

        # Visualisation locale de la feuille calculée
        with st.expander(f"📊 Table de calcul détaillée - {key}"):
            st.dataframe(
                df_res.style.format(
                    {
                        "Refus Partiel (g)": "{:.1f}",
                        "Refus Cumulé (g)": "{:.1f}",
                        "% Refus Cumulé": "{:.2f} %",
                        "% Passant Cumulé": "{:.2f} %",
                    }
                ),
                use_container_width=True,
            )

st.divider()

# Section 3: Courbe Granulométrique Systématique
st.subheader("📈 Courbe Granulométrique")

fig, ax = plt.subplots(figsize=(10, 5))

colors = {"GII": "#1f77b4", "GI": "#ff7f0e", "SC": "#2ca02c", "SD": "#d62728"}

for key in keys_fractions:
    df_f = dict_fractions_data[key]["data"]
    if not df_f.empty:
        ax.plot(
            df_f["Tamis (mm)"],
            df_f["% Passant Cumulé"],
            marker="o",
            linewidth=2,
            label=f"{key} - {FRACTIONS_CONFIG[key]['nom']}",
            color=colors[key],
        )

# Échelle logarithmique sur l'axe des tamis
ax.set_xscale("log")
ax.set_xticks(TAMIS_STANDARD)
ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

# Limites & Quadrillage
ax.set_xlim(0.063, 40)
ax.set_ylim(0, 105)
ax.set_xlabel("Ouverture des tamis (mm) - Échelle Log", fontsize=10, fontweight="bold")
ax.set_ylabel("% Passants Cumulés", fontsize=10, fontweight="bold")
ax.set_title("Courbe Granulométrique des Granulats", fontsize=12, fontweight="bold")
ax.grid(True, which="both", linestyle="--", linewidth=0.5)
ax.legend(loc="upper left")

st.pyplot(fig)

# Section 4: Procès-Verbal & Export
st.subheader("📄 Exportation du Procès-Verbal (PV)")

pv_excel_bytes = generer_pv_excel(infos_pv, dict_fractions_data)

st.download_button(
    label="📥 Télécharger le PV d'Essai (Excel)",
    data=pv_excel_bytes,
    file_name=f"PV_Granulats_{num_pv}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
