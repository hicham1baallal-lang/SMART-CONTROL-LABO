import streamlit as st
import pandas as pd
from datetime import datetime, date

def show(supabase):
    st.title("🏗️ Suivi et Contrôle Qualité Béton")
    
    # ---------------------------------------------------------
    # 1. FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    st.subheader("Saisie d'un contrôle")
    
    # Champ Date de livraison
    date_livraison = st.date_input("Date de livraison", value=date.today())
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        technicien = st.text_input("Nom du Technicien LPEE", value="Agent LPEE")
        bl_num = st.text_input("N° BL", value="BL-2026-001")
        ouvrage = st.text_input("Ouvrage", value="Voile / Semelle")
        quantite_m3 = st.number_input("Quantité (m³)", min_value=0.0, value=8.0, step=0.5)
        
    with col2:
        client = st.text_input("Client", value="TGCC", disabled=True)
        
        # Saisie des heures
        heure_fin = st.time_input("Heure de fin de production", value=datetime.strptime("08:00", "%H:%M").time())
        heure_arrivee = st.time_input("Heure d'arrivée au chantier", value=datetime.strptime("08:35", "%H:%M").time())
        
        # Calcul de la durée en minutes
        dt_fin = datetime.combine(date.today(), heure_fin)
        dt_arr = datetime.combine(date.today(), heure_arrivee)
        duree_minutes = int((dt_arr - dt_fin).total_seconds() / 60)
        
        st.text_input("Durée de transport / attente (min)", value=f"{duree_minutes} min", disabled=True)
        
        classe_beton = st.selectbox(
            "Classe", 
            ["C25/30", "C30/37", "C35/45", "C40/50", "C45/55"]
        )
        
    with col3:
        centrale = st.text_input("Centrale à Béton", value="TG PREFA")
        meteo = st.selectbox("Météo", ["Ensoleillé ☀️", "Nuageux ☁️", "Pluie 🌧️"])
        
        temp_beton = st.number_input("Température du Béton (°C)", value=20.0, step=0.1, format="%.1f")
        temp_ambiante = st.number_input("Température Ambiante (°C)", value=25.0, step=0.1, format="%.1f")
        affaissement = st.number_input("Affaissement (mm)", min_value=0, value=150, step=10)
        
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
            "date_livraison": str(date_livraison),
            "bl_num": bl_num,
            "ouvrage": ouvrage,
            "quantite_m3": quantite_m3,
            "client": client,
            "classe_beton": classe_beton,
            "centrale_beton": centrale,
            "meteo": meteo,
            "heure_fin_coulage": heure_fin.strftime("%H:%M"),
            "heure_arrivee": heure_arrivee.strftime("%H:%M"),
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
            
            # 1. Calcul de la colonne "Durée de transport"
            if "heure_fin_coulage" in df.columns and "heure_arrivee" in df.columns:
                def calculer_duree(row):
                    try:
                        h_fin = datetime.strptime(str(row["heure_fin_coulage"]), "%H:%M")
                        h_arr = datetime.strptime(str(row["heure_arrivee"]), "%H:%M")
                        diff = int((h_arr - h_fin).total_seconds() / 60)
                        return f"{diff} min"
                    except:
                        return "-"
                
                df["Durée de transport"] = df.apply(calculer_duree, axis=1)

            # 2. Masquer les colonnes non désirées (y compris Client et Centrale)
            cols_to_drop = [
                col for col in ["id", "created_at", "created", "heure_fin_coulage", "heure_fin", "client", "centrale_beton"] 
                if col in df.columns
            ]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            # 3. Réorganisation des colonnes
            cols = list(df.columns)
            
            # Placement de 'heure_arrivee' juste après 'date_livraison'
            if "date_livraison" in cols and "heure_arrivee" in cols:
                cols.remove("heure_arrivee")
                pos = cols.index("date_livraison") + 1
                cols.insert(pos, "heure_arrivee")
            
            # 🔹 MODIFICATION : Déplacement de 'meteo' tout à la fin
            if "meteo" in cols:
                cols.remove("meteo")
                cols.append("meteo")

            df = df[cols]

            # 4. Renommage propre des colonnes pour l'affichage
            df = df.rename(columns={
                "date_livraison": "Date Livraison",
                "heure_arrivee": "Heure d'arrivée",
                "bl_num": "N° BL",
                "ouvrage": "Ouvrage",
                "quantite_m3": "Quantité (m³)",
                "classe_beton": "Classe",
                "temperature": "Temp. Béton",
                "temperature_ambiante": "Temp. Ambiante",
                "affaissement": "Affaissement",
                "prelevement": "Prélèvement",
                "nb_eprouvettes": "Nb Éprouvettes",
                "observations": "Observations",
                "technicien": "Technicien",
                "meteo": "Météo"
            })
                
            # Numérotation à partir de 1
            df.index = range(1, len(df) + 1)
                
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Aucune donnée enregistrée pour le moment.")
    except Exception as e:
        st.error(f"Erreur lors de la récupération de l'historique : {e}")
