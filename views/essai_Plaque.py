import streamlit as st
from datetime import datetime

def show(supabase):
    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")
    st.markdown("---")

    col_inputs, col_chart = st.columns([1, 1])

    with col_inputs:
        st.subheader("Saisie des mesures")
        date_e = st.date_input("Date essai", datetime.now())
        pk = st.text_input("Emplacement (PK)", "PK 14+250 - Voie 1")
        couche = st.selectbox("Couche / Élément", ["PFT3 (Couche de Forme)", "PST (Arase)", "Sous-couche"])
        
        z1 = st.number_input("Enfoncement z1 (mm)", value=1.20, step=0.01)
        z2 = st.number_input("Enfoncement z2 (mm)", value=2.10, step=0.01)

        ev1 = round(22.5 / z1, 2) if z1 > 0 else 0.0
        ev2 = round(45.0 / z2, 2) if z2 > 0 else 0.0
        k_ratio = round(ev2 / ev1, 2) if ev1 > 0 else 0.0

        st.markdown("---")
        st.metric("Module EV1", f"{ev1} MPa")
        st.metric("Module EV2", f"{ev2} MPa")
        st.metric("Rapport k (EV2 / EV1)", f"{k_ratio}")

        if st.button("💾 Enregistrer dans Supabase", type="primary"):
            data = {
                "date_essai": str(date_e),
                "pk_emplacement": pk,
                "couche_element": couche,
                "z1": z1,
                "z2": z2,
                "ev1": ev1,
                "ev2": ev2,
                "rapport_ev2_ev1": k_ratio
            }
            try:
                supabase.table("essais_plaque").insert(data).execute()
                st.success("✅ Essai enregistré avec succès !")
            except Exception as e:
                st.error(f"Erreur d'enregistrement : {e}")
