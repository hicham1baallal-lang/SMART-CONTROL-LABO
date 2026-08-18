import streamlit as st
import pandas as pd
from datetime import datetime, date

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    # ---------------------------------------------------------
    # 1. FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    st.subheader("Saisie d'un contrôle")
    
    date_livraison = st.date_input("Date de livraison", value=date.today(), key="saisie_date")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        technicien = st.text_input("Nom du Technicien LPEE", value="Agent LPEE", key="saisie_tech")
        bl = st.text_input("N° BL", value="BL-2026-001", key="saisie_bl")
        ouvrage = st.text_input("Ouvrage", value="Voile / Semelle", key="saisie_ouvrage")
        quantite_m3 = st.number_input("Quantité (m³)", min_value=0.0, value=8.0, step=0.5, key="saisie_qte")
        
    with col2:
        client = st.text_input("Client", value="TGCC", disabled=True, key="saisie_client")
        
        heure_fin = st.time_input("Heure de fin de production", value=datetime.strptime("08:00", "%H:%M").time(), key="saisie_h_fin")
        heure_arrivee = st.time_input("Heure d'arrivée au chantier", value=datetime.strptime("08:35", "%H:%M").time(), key="saisie_h_arr")
        
        dt_fin = datetime.combine(date.today(), heure_fin)
        dt_arr = datetime.combine(date.today(), heure_arrivee)
        duree_minutes = int((dt_arr - dt_fin).total_seconds() / 60)
        if duree_minutes < 0:
            duree_minutes += 1440
        
        st.text_input("Durée de transport / attente (min)", value=f"{duree_minutes} min", disabled=True, key="saisie_duree")
        
        classe_beton = st.selectbox(
            "Classe", 
            ["C25/30", "C30/37", "C35/45", "C40/50", "C45/55"],
            key="saisie_classe"
        )
        
    with col3:
        centrale = st.text_input("Centrale à Béton", value="TG PREFA", key="saisie_centrale")
        meteo = st.selectbox("Météo", ["Ensoleillé ☀️", "Nuageux ☁️", "Pluie 🌧️"], key="saisie_meteo")
        
        temp_beton = st.number_input("Température du Béton (°C)", value=20.0, step=0.1, format="%.1f", key="saisie_t_beton")
        temp_ambiante = st.number_input("Température Ambiante (°C)", value=25.0, step=0.1, format="%.1f", key="saisie_t_amb")
        affaissement = st.number_input("Affaissement (mm)", min_value=0, value=150, step=10, key="saisie_aff")
        
        prelevement = st.selectbox(
            "Prélèvement", 
            ["OUI - Conforme (NF EN 12350-2)", "NON"],
            key="saisie_prel"
        )
        
        is_non_prelevement = "NON" in prelevement
        nb_eprouvettes = st.number_input(
            "Nb d'éprouvettes", 
            min_value=0, 
            value=0 if is_non_prelevement else 6,
            disabled=is_non_prelevement,
            key="saisie_eprov"
        )

    observations = st.text_area("Observations", value="Béton conforme", key="saisie_obs")

    # Bouton Enregistrer avec uniquement les champs de base validés
    if st.button("💾 Enregistrer", key="btn_enregistrer"):
        data = {
            "date_livraison": str(date_livraison),
            "bl": bl,
            "ouvrage": ouvrage,
            "quantite_m3": float(quantite_m3),
            "client": client,
            "classe_beton": classe_beton,
            "centrale_beton": centrale,
            "meteo": meteo,
            "temperature": float(temp_beton),
            "temperature_ambiante": float(temp_ambiante),
            "affaissement": int(affaissement),
            "prelevement": prelevement,
            "nb_eprouvettes": int(nb_eprouvettes),
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
    # 2. AFFICHAGE DE L'HISTORIQUE ET ESPACE ADMIN
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 Historique")
    
    try:
        res = supabase.table("suivi_betonnage").select("*").order("id", desc=True).execute()
        if res.data:
            df = pd.DataFrame(res.data)

            cols_to_drop = [col for col in ["id", "created_at", "created"] if col in df.columns]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            df.index = range(1, len(df) + 1)
            st.dataframe(df, use_container_width=True)

            # --- BLOC D'ADMINISTRATION ---
            if st.session_state.get("role") == "admin":
                st.markdown("---")
                st.subheader("🛠️ Espace Administration - Suivi Béton")
                
                record_options = {f"ID {r['id']} - BL: {r.get('bl', 'N/A')} - Ouvrage: {r.get('ouvrage', '')}": r for r in res.data}
                selected_key = st.selectbox("Sélectionner l'enregistrement à gérer", list(record_options.keys()), key="admin_select_record")
                selected_item = record_options[selected_key]
                
                if st.button("🗑️ Supprimer définitivement ce contrôle", type="primary", key="btn_supprimer_admin"):
                    try:
                        supabase.table("suivi_betonnage").delete().eq("id", selected_item["id"]).execute()
                        st.success("Enregistrement supprimé avec succès.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur de suppression : {e}")

        else:
            st.info("Aucune donnée enregistrée pour le moment.")
            
    except Exception as e:
        st.error(f"Erreur lors de la récupération de l'historique : {e}")
