import streamlit as st
import pandas as pd
from datetime import datetime

def show(supabase, active_chantier=None):
    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")
    
    # 1. Récupération et vérification du chantier actif
    if active_chantier is None:
        active_chantier = st.session_state.get("selected_chantier")
        
    if not active_chantier or "id" not in active_chantier:
        st.error("⚠️ Aucun chantier sélectionné ou affecté. Veuillez vous reconnecter.")
        st.stop()
        
    chantier_id = active_chantier["id"]
    nom_chantier = active_chantier.get("nom_chantier", "N/A")
    client_name = active_chantier.get("client", "N/A")
    
    st.caption(f"🔒 **Chantier Actif :** {nom_chantier} | **Client :** {client_name}")
    st.markdown("---")

    # ==========================================
    # 2. SAISIE D'UN NOUVEL ESSAI À LA PLAQUE
    # ==========================================
    st.subheader("➕ Saisie d'un Essai à la Plaque")
    
    can_edit = st.session_state.get("can_edit", True) or st.session_state.get("role") in ["admin", "laboratoire", "technicien"]

    with st.form("form_essai_plaque", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_essai = st.date_input("Date de l'essai", value=datetime.today())
            repere_point = st.text_input("Repère / Point d'essai (ex: P1, PK 12+500)")
            couche = st.selectbox("Couche / Support", ["PST", "Forme", "Fondation", "Base", "Remblai"])

        with col2:
            ev1 = st.number_input("EV1 (MPa)", min_value=0.0, max_value=300.0, step=0.1, format="%.1f")
            ev2 = st.number_input("EV2 (MPa)", min_value=0.0, max_value=300.0, step=0.1, format="%.1f")
            k_exige = st.number_input("EV2 Exigé / Objectif (MPa)", min_value=0.0, max_value=300.0, step=5.0, value=50.0)

        with col3:
            remarques = st.text_area("Remarques / Localisation précise", height=100)

        # Calcul automatique du rapport K = EV2 / EV1
        k_ratio = round(ev2 / ev1, 2) if ev1 > 0 else 0.0
        st.info(f"📊 **Rapport K (EV2/EV1) :** {k_ratio}")

        submit_btn = st.form_submit_button("💾 Enregistrer l'essai", type="primary", disabled=not can_edit)

        if submit_btn:
            if not repere_point:
                st.warning("⚠️ Veuillez renseigner le repère ou le point d'essai.")
            elif ev1 <= 0 or ev2 <= 0:
                st.warning("⚠️ EV1 et EV2 doivent être supérieurs à 0.")
            else:
                conforme = (ev2 >= k_exige) and (k_ratio <= 2.0 if ev1 > 0 else True)
                
                # Attachement obligatoire du chantier_id
                new_record = {
                    "chantier_id": chantier_id,
                    "date_essai": str(date_essai),
                    "repere_point": repere_point,
                    "couche": couche,
                    "ev1": ev1,
                    "ev2": ev2,
                    "k_ratio": k_ratio,
                    "ev2_exige": k_exige,
                    "conforme": conforme,
                    "remarques": remarques,
                    "saisi_par": st.session_state.get("user", {}).get("username", "Inconnu")
                }
                
                try:
                    if supabase:
                        supabase.table("essais_plaque").insert(new_record).execute()
                        st.success("✅ Essai à la plaque enregistré avec succès !")
                        st.rerun()
                    else:
                        st.error("❌ Connexion Supabase indisponible.")
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement dans Supabase : {e}")

    st.markdown("---")

    # ==========================================
    # 3. LECTURE : DONNÉES FILTRÉES PAR CHANTIER
    # ==========================================
    st.subheader("📋 Historique des Essais à la Plaque du Chantier")

    records = []
    if supabase:
        try:
            # Requete strictement filtrée sur le chantier_id actif
            res = supabase.table("essais_plaque") \
                .select("*") \
                .eq("chantier_id", chantier_id) \
                .order("date_essai", descending=True) \
                .execute()
            records = res.data if res and res.data else []
        except Exception as e:
            st.error(f"❌ Erreur de chargement des données : {e}")

    if records:
        df = pd.DataFrame(records)
        
        # Mise en forme des colonnes pour l'affichage
        cols_display = {
            "date_essai": "Date",
            "repere_point": "Point/Repère",
            "couche": "Couche",
            "ev1": "EV1 (MPa)",
            "ev2": "EV2 (MPa)",
            "k_ratio": "K (EV2/EV1)",
            "ev2_exige": "EV2 Exigé",
            "conforme": "Conformité",
            "saisi_par": "Opérateur",
            "remarques": "Remarques"
        }
        
        present_cols = [c for c in cols_display.keys() if c in df.columns]
        df_show = df[present_cols].rename(columns=cols_display)
        
        if "Conformité" in df_show.columns:
            df_show["Conformité"] = df_show["Conformité"].apply(lambda x: "✅ Conforme" if x else "❌ Non Conforme")

        st.dataframe(df_show, use_container_width=True)
    else:
        st.info("ℹ️ Aucun essai à la plaque enregistré pour ce chantier.")

if __name__ == "__main__":
    st.error("Ce fichier doit être appelé depuis app.py.")
