import streamlit as st
import pandas as pd
from datetime import date

def show(supabase):
    st.title("🧪 Saisie - Essai à la Plaque")

    # 1. FORMULAIRE DE SAISIE
    with st.form("form_essai_plaque"):
        date_selected = st.date_input("Date de l'essai", value=date.today())
        ev1 = st.number_input("EV1 (MPa)", min_value=0.0, value=0.0)
        ev2 = st.number_input("EV2 (MPa)", min_value=0.0, value=0.0)
        k_value = st.number_input("Coefficient K", min_value=0.0, value=0.0)
        
        # Bouton de soumission
        submitted = st.form_submit_button("💾 Enregistrer l'essai")

    # 2. TRAITEMENT LORS DU CLIC (C'EST ICI QU'ON PLACE LE CODE)
    if submitted:
        try:
            # Dictionnaire préparé pour Supabase
            data_payload = {
                "date_essai": str(date_selected),  # Doit correspondre à la colonne Supabase
                "ev1": float(ev1),
                "ev2": float(ev2),
                "k": float(k_value)
            }

            # Envoi vers Supabase
            supabase.table("essai_plaque").insert(data_payload).execute()
            
            st.success("✅ Essai enregistré avec succès !")
            
        except Exception as e:
            st.error(f"Erreur d'enregistrement : {e}")
