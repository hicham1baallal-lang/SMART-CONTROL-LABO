import streamlit as st
import pandas as pd


def charger_essais(supabase, table, type_essai):
    """Charge une table Supabase et la convertit au format commun."""
    try:
        response = supabase.table(table).select("*").execute()
        df = pd.DataFrame(response.data or [])

        if df.empty:
            return pd.DataFrame()

        # La colonne date peut avoir un nom différent selon le module.
        if "date_essai" in df.columns:
            df["Date"] = pd.to_datetime(df["date_essai"], errors="coerce")
        elif "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"], errors="coerce")
        else:
            df["Date"] = pd.NaT

        df["Type d'essai"] = type_essai
        df["Référence"] = df.get("reference", df.get("ref_essai", "—"))
        df["Résultat"] = df.get(
            "conformite",
            df.get("resultat", df.get("conclusion", "Non renseigné"))
        )

        return df[["Date", "Type d'essai", "Référence", "Résultat"]]

    except Exception as e:
        st.warning(f"Impossible de charger {type_essai} : {e}")
        return pd.DataFrame()
def show(supabase):
    st.title("📊 Synthèse globale mensuelle")
    st.caption("Récapitulatif de tous les essais pour le mois sélectionné.")

    tableaux = [
        charger_essais(supabase, "essai_plaque", "Essai à la plaque"),
        charger_essais(supabase, "essai_compacite", "Essai de compacité"),
        charger_essais(supabase, "essai_teneur_eau", "Essai teneur en eau"),
        charger_essais(supabase, "pv_granulats", "Granulats pour béton"),
        charger_essais(
            supabase,
            "essai_identification_materiaux",
            "Identification matériaux"
        ),
    ]

    tableaux_valides = [df for df in tableaux if not df.empty]

    if not tableaux_valides:
        st.info("Aucun essai enregistré.")
        return

    synthese = pd.concat(tableaux_valides, ignore_index=True)
    synthese["Mois"] = synthese["Date"].dt.strftime("%Y-%m")

    mois_disponibles = sorted(
        synthese["Mois"].dropna().unique(),
        reverse=True
    )

    mois_choisi = st.selectbox(
        "📅 Choisir le mois",
        mois_disponibles
    )

    synthese_mois = synthese[synthese["Mois"] == mois_choisi].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("Nombre total d'essais", len(synthese_mois))

    nb_conformes = synthese_mois[
        synthese_mois["Résultat"]
        .astype(str)
        .str.contains("conforme", case=False, na=False)
    ].shape[0]

    col2.metric("Essais conformes", nb_conformes)
    col3.metric("Autres résultats", len(synthese_mois) - nb_conformes)

    st.subheader("Détail des essais du mois")
    st.dataframe(
        synthese_mois.sort_values("Date", ascending=False),
        use_container_width=True,
        hide_index=True
    )
