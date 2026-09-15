import streamlit as st
import pandas as pd
from datetime import datetime

def show(page=None):
    """Affiche l'interface de gestion et d'historique des Procès-Verbaux (PVs)."""
    st.title("📂 Historique & Audit des Procès-Verbaux")
    st.markdown("Consultez, suivez et téléchargez les rapports d'essai et PVs enregistrés.")

    # Synchronisation des clés de session possibles pour l'historique
    if "historique_pvs" not in st.session_state:
        if "historique_pv" in st.session_state:
            st.session_state["historique_pvs"] = st.session_state["historique_pv"]
        else:
            st.session_state["historique_pvs"] = []

    pvs = st.session_state["historique_pvs"]

    if not pvs:
        st.info("Aucun procès-verbal n'a été enregistré pour le moment dans cette session.")
        st.markdown(
            """
            *Astuce : Rendez-vous dans le module de génération des PVs (ex: Granulats pour Béton) 
            et cliquez sur **Enregistrer dans l'historique** pour alimenter cette liste.*
            """
        )
        return

    # Barre de recherche ou filtres rapides
    search_query = st.text_input("🔍 Rechercher par N° de PV ou nom de projet :", "").lower()

    filtered_pvs = [
        pv for pv in pvs 
        if search_query in str(pv.get('ref_pv', '')).lower() or search_query in str(pv.get('projet', '')).lower()
    ]

    st.write(f"**Nombre de rapports trouvés :** {len(filtered_pvs)}")
    st.markdown("---")

    # Affichage de chaque PV sous forme de carte interactive / expander
    for idx, pv in enumerate(filtered_pvs):
        ref_pv = pv.get('ref_pv', 'Réf Inconnue')
        projet = pv.get('projet', 'Projet non spécifié')
        date_pv = pv.get('date', 'Date non spécifiée')
        client = pv.get('client', 'Client non spécifié')

        with st.expander(f"📄 PV N° : {ref_pv} | Chantier : {projet} ({date_pv})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Client :** {client}")
                st.markdown(f"**Coordinateur des essais :** {pv.get('coord_essais', '-')}")
                st.markdown(f"**Chef de laboratoire :** {pv.get('chef_labo', '-')}")
            
            with col2:
                st.markdown(f"**Date de prélèvement :** {date_pv}")
                st.markdown(f"**Commentaires :** {pv.get('commentaires', 'Aucun commentaire')}")

            st.markdown("---")
            
            # Actions de téléchargement et suppression individuelle
            col_dl1, col_dl2, col_del, col_spacer = st.columns([1.5, 1.5, 1.5, 2])
            
            with col_dl1:
                if "pdf_bytes" in pv and pv["pdf_bytes"]:
                    st.download_button(
                        label="📥 Télécharger PDF",
                        data=pv["pdf_bytes"],
                        file_name=f"PV_{str(ref_pv).replace('/', '_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{idx}"
                    )
                else:
                    st.warning("PDF non disponible")

            with col_dl2:
                if "html_content" in pv and pv["html_content"]:
                    st.download_button(
                        label="🌐 Télécharger HTML",
                        data=pv["html_content"],
                        file_name=f"PV_{str(ref_pv).replace('/', '_')}.html",
                        mime="text/html",
                        key=f"dl_html_{idx}"
                    )
                else:
                    st.info("HTML non disponible")

            with col_del:
                if st.button("🗑️ Supprimer", key=f"del_pv_{idx}", type="secondary"):
                    st.session_state["historique_pvs"].remove(pv)
                    if "historique_pv" in st.session_state and pv in st.session_state["historique_pv"]:
                        st.session_state["historique_pv"].remove(pv)
                    st.rerun()

    # Option de nettoyage global de l'historique
    st.markdown("---")
    if st.button("🗑️ Vider tout l'historique", type="primary"):
        st.session_state["historique_pvs"] = []
        if "historique_pv" in st.session_state:
            st.session_state["historique_pv"] = []
        st.success("L'historique a été réinitialisé.")
        st.rerun()
