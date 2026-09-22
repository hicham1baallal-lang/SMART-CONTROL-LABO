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
