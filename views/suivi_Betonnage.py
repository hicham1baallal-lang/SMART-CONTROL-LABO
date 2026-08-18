import streamlit as st
import pandas as pd
from datetime import datetime, date

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    # ---------------------------------------------------------
    # 1. FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    st.subheader("Saisie d'un contrôle")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        technicien = st.text_input("Nom du Technicien LPEE", value="Agent LPEE", key="saisie_tech")
        ouvrage = st.text_input("Ouvrage", value="Voile / Semelle", key="saisie_ouvrage")
        quantite_m3 = st.number_input("Quantité (m³)", min_value=0.0, value=8.0, step=0.5, key="saisie_qte")
        
    with col2:
        classe_beton = st.selectbox(
            "Classe", 
            ["C25/30", "C30/37", "C35/45", "C40/50", "C45/55"],
            key="saisie_classe"
        )
        affaissement = st.number_input("Affaissement (mm)", min_value=0, value=150, step=10, key="saisie_aff")
        
    with col3:
        temp_beton = st.number_input("Température du Béton (°C)", value=20.0, step=0.1, format="%.1f", key="saisie_t_beton")
        nb_eprouvettes = st.number_input("Nb d'éprouvettes", min_value=0, value=6, key="saisie_eprov")

    observations = st.text_area("Observations", value="Béton conforme", key="saisie_obs")

    # Bouton Enregistrer (uniquement avec les champs de base pour éviter tout blocage de schéma)
    if st.button("💾 Enregistrer", key="btn_enregistrer"):
        data = {
            "ouvrage": ouvrage,
            "quantite_m3": float(quantite_m3),
            "classe_beton": classe_beton,
            "affaissement": int(affaissement),
            "temperature": float(temp_beton),
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

            # Masquer les colonnes système superflues si présentes
            cols_to_drop = [col for col in ["id", "created_at", "created"] if col in df.columns]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            # Numérotation à partir de 1
            df.index = range(1, len(df) + 1)
                
            st.dataframe(df, use_container_width=True)

            # --- BLOC D'ADMINISTRATION (SUPPRIMER) ---
            if st.session_state.get("role") == "admin":
                st.markdown("---")
                st.subheader("🛠️ Espace Administration - Suivi Béton")
                
                record_options = {f"ID {r['id']} - Ouvrage: {r.get('ouvrage', '')}": r for r in res.data}
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
