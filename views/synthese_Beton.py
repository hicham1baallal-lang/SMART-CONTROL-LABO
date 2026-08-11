import streamlit as st
import pandas as pd
from datetime import datetime, date

def show(supabase):
    # Titre principal
    st.title("📊 Récapitulatif et Synthèse du Bétonnage")
    
    # Onglets : Bilan Journalier / Bilan Mensuel
    tab_journalier, tab_mensuel = st.tabs(["📅 Bilan Journalier", "📅 Bilan Mensuel"])
    
    # =========================================================
    # 1. BILAN JOURNALIER
    # =========================================================
    with tab_journalier:
        st.markdown("### Filtrage par jour et par classe de béton")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_date = st.date_input("Sélectionnez une date :", value=date.today())
            
        with col2:
            selected_class = st.selectbox(
                "Filtrer par classe de béton :", 
                ["Toutes", "C25/30", "C30/37", "C35/45", "C40/50", "C45/55"]
            )
            
        # Requête vers Supabase
        try:
            res = supabase.table("suivi_betonnage").select("*").eq("date_livraison", str(selected_date)).execute()
            data = res.data if res else []
            
            if data:
                df = pd.DataFrame(data)
                
                # Filtrer par classe si un choix spécifique est fait
                if selected_class != "Toutes":
                    df = df[df["classe_beton"] == selected_class]
                
                if df.empty:
                    st.info("Aucun coulage enregistré pour les critères sélectionnés.")
                else:
                    # Cartes d'indicateurs (KPIs) du jour
                    st.markdown("---")
                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("Volume Total", f"{df['quantite_m3'].sum():.1f} m³")
                    kpi2.metric("Nombre de Coulages", len(df))
                    kpi3.metric("Affaissement Moyen", f"{df['affaissement'].mean():.0f} mm")
                    kpi4.metric("Éprouvettes Prélevées", int(df['nb_eprouvettes'].sum()))
                    
                    st.markdown("---")
                    st.subheader("Détail des opérations du jour")
                    
                    # Nettoyage du tableau pour l'affichage
                    cols_to_drop = [c for c in ["id", "created_at", "created", "heure_fin_coulage", "client", "centrale_beton"] if c in df.columns]
                    df_display = df.drop(columns=cols_to_drop)
                    df_display.index = range(1, len(df_display) + 1)
                    
                    st.dataframe(df_display, use_container_width=True)
            else:
                # Message si aucune donnée trouvée (bannière bleue identique à votre image)
                st.info("Aucun coulage enregistré pour les critères sélectionnés.")
                
        except Exception as e:
            st.error(f"Erreur de chargement des données : {e}")

    # =========================================================
    # 2. BILAN MENSUEL
    # =========================================================
    with tab_mensuel:
        st.markdown("### Bilan mensuel global")
        
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            annee = date.today().year
            mois_liste = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
            mois_selected = st.selectbox("Sélectionnez le mois :", mois_liste, index=date.today().month - 1)
            mois_num = mois_liste.index(mois_selected) + 1
            
        with col_m2:
            selected_class_m = st.selectbox(
                "Filtrer par classe de béton (Mensuel) :", 
                ["Toutes", "C25/30", "C30/37", "C35/45", "C40/50", "C45/55"],
                key="class_mensuel"
            )
            
        try:
            # Calcul des dates de début et de fin du mois sélectionné
            date_debut = f"{annee}-{mois_num:02d}-01"
            dernier_jour = 31 if mois_num in [1,3,5,7,8,10,12] else (30 if mois_num in [4,6,9,11] else 28)
            date_fin = f"{annee}-{mois_num:02d}-{dernier_jour}"
            
            res_m = supabase.table("suivi_betonnage").select("*").gte("date_livraison", date_debut).lte("date_livraison", date_fin).execute()
            data_m = res_m.data if res_m else []
            
            if data_m:
                df_m = pd.DataFrame(data_m)
                if selected_class_m != "Toutes":
                    df_m = df_m[df_m["classe_beton"] == selected_class_m]
                    
                if df_m.empty:
                    st.info("Aucun coulage enregistré pour ce mois.")
                else:
                    st.markdown("---")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Volume Cumulé du Mois", f"{df_m['quantite_m3'].sum():.1f} m³")
                    m2.metric("Nombre Total de BL", len(df_m))
                    m3.metric("Total Éprouvettes", int(df_m['nb_eprouvettes'].sum()))
                    
                    st.markdown("---")
                    st.subheader("Répartition par classe de béton (m³)")
                    st.bar_chart(df_m.groupby("classe_beton")["quantite_m3"].sum())
                    
                    st.subheader("Historique du mois")
                    cols_to_drop = [c for c in ["id", "created_at", "created", "heure_fin_coulage", "client", "centrale_beton"] if c in df_m.columns]
                    df_m_display = df_m.drop(columns=cols_to_drop)
                    df_m_display.index = range(1, len(df_m_display) + 1)
                    
                    st.dataframe(df_m_display, use_container_width=True)
            else:
                st.info("Aucun coulage enregistré pour ce mois.")
                
        except Exception as e:
            st.error(f"Erreur de chargement du bilan mensuel : {e}")
