import streamlit as st
import pandas as pd
from datetime import date

def show(supabase):
    st.title("🧪 Saisie - Essai à la Plaque")

    # ---------------------------------------------------------
    # FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    with st.form("form_essai_plaque"):
        
        # --- 1. CHAMPS DÉSACTIVÉS (CLIENT & PROJET) ---
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.text_input("Client", value="TGCC", disabled=True)
        with col_info2:
            st.text_input("Projet", value="LGV CASA SUD", disabled=True)

        st.markdown("---")

        # --- 2. INFORMATIONS GÉNÉRALES ---
        col1, col2 = st.columns(2)
        with col1:
            date_selected = st.date_input("Date de l'essai", value=date.today())
            norme = st.selectbox(
                "Norme d'essai", 
                ["NF P 94-117-1 (Plaque 600 mm)", "NF P 94-117-2 (Dynaplaque)", "Autre"]
            )
        with col2:
            couche = st.selectbox(
                "Type de couche", 
                ["Remblai", "Assise", "PST", "Couche de forme"]
            )
            emplacement = st.text_input("Emplacement PK / Profil", placeholder="Ex: PK 12+450 / Profil 12")

        st.markdown("### 📊 Données de Chargement (Enfoncements)")
        
        # --- 3. SAISIE Z1 ET Z2 ---
        col_z1, col_z2 = st.columns(2)
        with col_z1:
            z1 = st.number_input("Z1 - 1er chargement (mm)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with col_z2:
            z2 = st.number_input("Z2 - 2ème chargement (mm)", min_value=0.0, value=0.0, step=0.01, format="%.2f")

        # --- 4. CALCULS AUTOMATIQUES ---
        ev1 = round(112.5 / (z1 * 2), 2) if z1 > 0 else 0.0
        ev2 = round(90.0 / (z2 * 2), 2) if z2 > 0 else 0.0
        k_val = round(ev2 / ev1, 2) if ev1 > 0 else 0.0

        st.markdown("### 📈 Résultats Calculés Automatiquement")
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("EV1 (MPa)", f"{ev1:.2f}")
        with col_res2:
            st.metric("EV2 (MPa)", f"{ev2:.2f}")
        with col_res3:
            st.metric("Coefficient K (EV2/EV1)", f"{k_val:.2f}")

        st.markdown("---")
        submitted = st.form_submit_button("💾 Enregistrer l'essai", use_container_width=True)

    # ---------------------------------------------------------
    # ENREGISTREMENT DANS SUPABASE
    # ---------------------------------------------------------
    if submitted:
        if z1 <= 0 or z2 <= 0:
            st.warning("⚠️ Veuillez saisir des valeurs supérieures à 0 pour Z1 et Z2 afin d'effectuer les calculs.")
        else:
            try:
                data_payload = {
                    "date_essai": str(date_selected),
                    "client": "TGCC",
                    "projet": "LGV CASA SUD",
                    "norme": norme,
                    "couche": couche,
                    "emplacement": emplacement,
                    "z1": float(z1),
                    "z2": float(z2),
                    "ev1": float(ev1),
                    "ev2": float(ev2),
                    "k": float(k_val)
                }

                supabase.table("essai_plaque").insert(data_payload).execute()
                st.success("✅ Essai à la plaque enregistré avec succès !")

            except Exception as e:
                st.error(f"Erreur d'enregistrement : {e}")
