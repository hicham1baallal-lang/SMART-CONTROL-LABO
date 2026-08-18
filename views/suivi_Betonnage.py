import streamlit as st
import pandas as pd
from datetime import date

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    # 1. DIAGNOSTIC : Récupération automatique de la structure
    try:
        # On essaie de lire une seule ligne pour voir les noms des colonnes
        test_res = supabase.table("suivi_betonnage").select("*").limit(1).execute()
        if test_res.data:
            colonnes_reelles = list(test_res.data[0].keys())
            st.success(f"✅ Colonnes trouvées dans la base : {colonnes_reelles}")
        else:
            st.warning("⚠️ Table vide : impossible de détecter les colonnes automatiquement.")
            colonnes_reelles = []
    except Exception as e:
        st.error(f"❌ Erreur lors du diagnostic : {e}")
        colonnes_reelles = []

    st.markdown("---")
    
    # 2. FORMULAIRE SIMPLE POUR TESTER L'ENREGISTREMENT
    st.subheader("Test d'enregistrement")
    ouvrage = st.text_input("Nom de l'ouvrage (pour test)")
    
    if st.button("Envoyer test"):
        # On envoie uniquement ce qui correspond aux noms que tu verras en vert plus haut
        # Si 'ouvrage' n'est pas dans la liste verte, change le nom ici !
        data = {"ouvrage": ouvrage} 
        
        try:
            supabase.table("suivi_betonnage").insert(data).execute()
            st.success("Enregistrement réussi !")
        except Exception as e:
            st.error(f"Erreur d'enregistrement : {e}")

    # 3. HISTORIQUE
    st.markdown("---")
    try:
        res = supabase.table("suivi_betonnage").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data))
    except Exception as e:
        st.error(f"Erreur historique : {e}")
