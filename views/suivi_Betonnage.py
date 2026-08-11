import streamlit as st
import pandas as pd

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    # ---------------------------------------------------------
    # 1. FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    st.subheader("Saisie d'un contrôle")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        technicien = st.text_input("Nom du Technicien LPEE", value="Agent LPEE")
        bl_num = st.text_input("N° BL", value="BL-2026-001")
        
        # 🔹 MODIFICATION 1 : Saisie libre pour l'Ouvrage
        ouvrage = st.text_input("Ouvrage", value="Voile / Semelle")
        
        quantite_m3 = st.number_input("Quantité (m³)", min_value=0.0, value=8.0, step=0.5)
        
    with col2:
        # Client désactivé (TGCC par défaut)
        client = st.text_input("Client", value="TGCC", disabled=True)
        
        heure_fin = st.time_input("Heure de fin de production")
        heure_arrivee = st.time_input("Heure d'arrivée au chantier")
        
        # 🔹 MODIFICATION 2 : Classes C40/50 et C45/55 ajoutées
        classe_beton = st.selectbox(
            "Classe", 
            ["C25/30", "C30/37", "C35/45", "C40/50", "C45/55"]
        )
        
    with col3:
        centrale = st.text_input("Centrale à Béton", value="TG PREFA")
        meteo = st.selectbox("Météo", ["Ensoleillé ☀️", "Nuageux ☁️", "Pluie 🌧️"])
        temp_beton = st.number_input("Température du Béton (°C)", value=20.0)
        temp_ambiante = st.number_input("Température Ambiante (°C)", value=25.0)
        affaissement = st.number_input("Affaissement (mm)", value=150.0)
        
        # Prélèvement et gestion dynamique du nombre d'éprouvettes
        prelevement = st.selectbox(
            "Prélèvement", 
            ["OUI - Conforme (NF EN 12350-2)", "NON"]
        )
        
        is_non_prelevement = "NON" in prelevement
        
        nb_eprouvettes = st.number_input(
            "Nb d'éprouvettes", 
            min_value=0, 
            value=0 if is_non_prelevement else 6,
            disabled=is_non_prelevement
        )

    observations = st.text_area("Observations", value="Béton conforme")

    # Bouton Enregistrer
    if st.button("💾 Enregistrer"):
        data = {
            "bl_num": bl_num,
            "ouvrage": ouvrage,
            "quantite_m3": quantite_m3,
            "client": client,
            "classe_beton": classe_beton,
            "centrale_beton": centrale,
            "meteo": meteo,
            "temperature": temp_beton,
            "temperature_ambiante": temp_ambiante,
            "affaissement": affaissement,
            "prelevement": prelevement,
            "nb_eprouvettes": nb_eprouvettes,
            "observations": observations,
            "technicien": technicien
        }
        
        try:
            supabase.table("suivi_betonnage").insert(data).execute()
            st.success("Enregistrement réussi !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur d'enregistrement : {e}")

    # ---------------------------------------------------------
    # 2. AFFICHAGE DE L'HISTORIQUE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 Historique")
    
    try:
        res = supabase.table("suivi_betonnage").select("*").order("id", desc=True).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            
            # Masquer la colonne created_at / created
            cols_to_drop = [col for col in ["created_at", "created"] if col in df.columns]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)
                
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Aucune donnée enregistrée pour le moment.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération de l'historique : {e}")
