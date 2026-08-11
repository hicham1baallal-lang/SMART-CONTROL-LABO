import streamlit as st
import datetime

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    date_livraison = st.date_input("Date de livraison :", datetime.date.today())
    
    # Section Saisie du contrôle
    st.subheader(f"📝 Saisie d'un contrôle ({date_livraison.strftime('%d/%m/%Y')})")
    
    with st.form("form_betonnage", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tech = st.text_input("Nom du Technicien LPEE", value="Agent LPEE")
            num_bl = st.text_input("N° B.L.", value="BL-2026-001")
            ouvrage = st.text_input("Ouvrage", value="Voile / Semelle")
            quantite = st.number_input("Quantité (m³)", min_value=0.0, value=8.0, step=0.5)
        
        with col2:
            client = st.text_input("Client", value="TGCC")
            h_fin_prod = st.time_input("Heure de fin de production", datetime.time(8, 30))
            h_arrivee = st.time_input("Heure d'arrivée au chantier", datetime.time(8, 15))
            classe = st.selectbox("Classe", ["C25/30", "C30/37", "C35/45", "C40/50"])
            
        with col3:
            centrale = st.text_input("Centrale à Béton", value="TG PREFA")
            meteo = st.selectbox("Météo", ["Ensoleillé ☀️", "Nuageux ☁️", "Pluie 🌧️"])
            temp_beton = st.number_input("Température du Béton (°C)", value=20.0, step=0.5)
            temp_amb = st.number_input("Température Ambiante (°C)", value=25.0, step=0.5)
            affaissement = st.number_input("Affaissement (mm)", value=150.0, step=5.0)
            prelevement = st.selectbox("Prélèvement", ["OUI - Conforme (NF EN 12350-2)", "NON"])
            nb_eprouvettes = st.number_input("Nb d'éprouvettes", min_value=0, value=6)

        obs = st.text_area("Observations", value="Béton conforme")
        
        btn_submit = st.form_submit_button("💾 Enregistrer")
        
        if btn_submit:
            data = {
                "date_livraison": str(date_livraison),
                "technicien": tech,
                "client": client,
                "centrale_beton": centrale,
                "bl_num": num_bl,
                "heure_fin_coulage": str(h_fin_prod),
                "heure_arrivee": str(h_arrivee),
                "meteo": meteo,
                "ouvrage": ouvrage,
                "quantite_m3": quantite,
                "classe_beton": classe,
                "temperature": temp_beton,
                "temperature_ambiante": temp_amb,
                "affaissement": affaissement,
                "prelevement": prelevement,
                "nb_eprouvettes": nb_eprouvettes,
                "observations": obs
            }
            if supabase:
                try:
                    supabase.table("suivi_betonnage").insert(data).execute()
                    st.success("Données de bétonnage enregistrées avec succès !")
                except Exception as e:
                    st.error(f"Erreur d'enregistrement : {e}")
            else:
                st.warning("Mode hors-ligne : Données non envoyées à Supabase.")

    # Section Historique
    st.markdown("---")
    st.subheader("📋 Historique des contrôles béton")
    if supabase:
        try:
            res = supabase.table("suivi_betonnage").select("*").order("id", desc=True).execute()
            if res.data:
                st.dataframe(res.data, use_container_width=True)
            else:
                st.info("Aucun enregistrement trouvé dans la table suivi_betonnage.")
        except Exception as e:
            st.error(f"Impossible de charger l'historique : {e}")
