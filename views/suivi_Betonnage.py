import streamlit as st
from datetime import datetime

def show(supabase):
    st.title("🏗️ Suivi du Bétonnage")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("1. Identification")
        no_b = st.text_input("N° Bétonnage", "BET-2026-001")
        projet = st.text_input("Projet", "Ouvrage d'Art - OA1")
        ouvrage = st.text_input("Ouvrage / Élément", "Culée C1")
        element = st.selectbox("Type d'élément", ["Semelle", "Voile", "Tablier", "Pieu"])
        entreprise = st.text_input("Entreprise", "STAM")

    with col2:
        st.subheader("2. Livraison")
        volume = st.number_input("Volume (m³)", value=8.0, step=0.5)
        centrale = st.text_input("Centrale à béton", "LPEE Béton")
        bl = st.text_input("N° Bon de Livraison", "BL-8842")
        toupie = st.text_input("Camion toupie", "T12")
        classe = st.selectbox("Classe béton", ["C25/30", "C30/37", "C35/45"], index=1)
        date_b = st.date_input("Date bétonnage", datetime.now())

    with col3:
        st.subheader("3. Conditions")
        meteo = st.selectbox("Météo", ["Soleil", "Nuageux", "Pluie", "Vent fort"])
        obs = st.text_area("Observations", "RAS")

    if st.button("💾 Enregistrer dans Supabase", type="primary"):
        data = {
            "no_betonnage": no_b,
            "projet": projet,
            "ouvrage": ouvrage,
            "element_betonne": element,
            "entreprise": entreprise,
            "volume_beton": volume,
            "centrale_beton": centrale,
            "bon_livraison": bl,
            "toupie": toupie,
            "classe_beton": classe,
            "date_betonnage": str(date_b),
            "meteo": meteo,
            "observations": obs
        }
        try:
            supabase.table("suivi_beton").insert(data).execute()
            st.success("✅ Fiche enregistrée avec succès !")
        except Exception as e:
            st.error(f"Erreur d'enregistrement : {e}")
