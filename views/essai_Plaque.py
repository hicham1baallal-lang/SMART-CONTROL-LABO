import streamlit as st
import pandas as pd
from datetime import datetime, date

def show(supabase, active_chantier=None):
    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")
    
    # ---------------------------------------------------------
    # 1. RÉCUPÉRATION ET VÉRIFICATION DU CHANTIER ACTIF
    # ---------------------------------------------------------
    if active_chantier is None:
        active_chantier = st.session_state.get("selected_chantier")
        
    if not active_chantier or "id" not in active_chantier:
        st.error("⚠️ Aucun chantier sélectionné ou affecté. Veuillez vous reconnecter.")
        st.stop()
        
    chantier_id = active_chantier["id"]
    nom_chantier = active_chantier.get("nom_chantier", active_chantier.get("projet", "N/A"))
    client_name = active_chantier.get("client", "N/A")
    
    st.caption(f"🔒 **Chantier Actif :** {nom_chantier} | **Client :** {client_name}")
    st.markdown("---")

    can_edit = st.session_state.get("can_edit", True) or st.session_state.get("role") in ["admin", "laboratoire", "technicien"]
    is_admin = st.session_state.get("is_admin", False) or st.session_state.get("role") == "admin"

    # Vérification si un enregistrement est en cours de modification
    editing_item = st.session_state.get("edit_plaque_item", None)

    # ---------------------------------------------------------
    # 2. SAISIE / MODIFICATION D'UN ESSAI À LA PLAQUE
    # ---------------------------------------------------------
    if editing_item:
        st.subheader(f"✏️ Modification de l'Essai #{editing_item['id']}")
    else:
        st.subheader("➕ Saisie d'un Essai à la Plaque")

    # Valeurs par défaut selon le mode (Création vs Édition)
    if editing_item:
        def_date = datetime.strptime(editing_item["date_essai"], "%Y-%m-%d").date() if isinstance(editing_item.get("date_essai"), str) else date.today()
        def_repere = editing_item.get("repere_point", editing_item.get("emplacement", ""))
        def_couche = editing_item.get("couche", "Forme")
        def_ev1 = float(editing_item.get("ev1", 0.0))
        def_ev2 = float(editing_item.get("ev2", 0.0))
        def_exige = float(editing_item.get("ev2_exige", 50.0))
        def_remarques = editing_item.get("remarques", editing_item.get("observations", ""))
    else:
        def_date = date.today()
        def_repere = ""
        def_couche = "Forme"
        def_ev1 = 0.0
        def_ev2 = 0.0
        def_exige = 50.0
        def_remarques = ""

    couche_options = ["PST", "Forme", "Fondation", "Base", "Remblai", "Autre"]
    couche_index = couche_options.index(def_couche) if def_couche in couche_options else 0

    with st.form("form_essai_plaque", clear_on_submit=not editing_item):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_essai = st.date_input("Date de l'essai", value=def_date)
            repere_point = st.text_input("Repère / Point d'essai (ex: P1, PK 12+500)", value=def_repere)
            couche = st.selectbox("Couche / Support", couche_options, index=couche_index)

        with col2:
            ev1 = st.number_input("EV1 (MPa)", min_value=0.0, max_value=300.0, value=def_ev1, step=0.1, format="%.1f")
            ev2 = st.number_input("EV2 (MPa)", min_value=0.0, max_value=300.0, value=def_ev2, step=0.1, format="%.1f")
            k_exige = st.number_input("EV2 Exigé / Objectif (MPa)", min_value=0.0, max_value=300.0, value=def_exige, step=5.0)

        with col3:
            remarques = st.text_area("Remarques / Localisation précise", value=def_remarques, height=100)

        # Calcul automatique du rapport K = EV2 / EV1
        k_ratio = round(ev2 / ev1, 2) if ev1 > 0 else 0.0
        st.info(f"📊 **Rapport K (EV2/EV1) :** {k_ratio:.2f}")

        btn_label = "🔄 Mettre à jour l'essai" if editing_item else "💾 Enregistrer l'essai"
        submit_btn = st.form_submit_button(btn_label, type="primary", disabled=not can_edit)

        if submit_btn:
            if not repere_point:
                st.warning("⚠️ Veuillez renseigner le repère ou le point d'essai.")
            elif ev1 <= 0 or ev2 <= 0:
                st.warning("⚠️ EV1 et EV2 doivent être supérieurs à 0.")
            else:
                conforme = (ev2 >= k_exige) and (k_ratio <= 2.0 if ev1 > 0 else True)
                
                record_payload = {
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
                        if editing_item:
                            supabase.table("essais_plaque").update(record_payload).eq("id", editing_item["id"]).execute()
                            st.success(f"✅ Essai #{editing_item['id']} mis à jour avec succès !")
                            st.session_state["edit_plaque_item"] = None
                        else:
                            supabase.table("essais_plaque").insert(record_payload).execute()
                            st.success("✅ Essai à la plaque enregistré avec succès !")
                        st.rerun()
                    else:
                        st.error("❌ Connexion Supabase indisponible.")
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement dans Supabase : {e}")

    if editing_item:
        if st.button("❌ Annuler la modification"):
            st.session_state["edit_plaque_item"] = None
            st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # 3. LECTURE ET HISTORIQUE FILTRÉ PAR CHANTIER
    # ---------------------------------------------------------
    st.subheader(f"📋 Historique des Essais ({nom_chantier})")

    records = []
    if supabase:
        try:
            # Requête strictement filtrée sur le chantier_id actif
            res = supabase.table("essais_plaque") \
                .select("*") \
                .eq("chantier_id", chantier_id) \
                .order("date_essai", desc=True) \
                .execute()
            records = res.data if res and res.data else []
        except Exception as e:
            st.error(f"❌ Erreur de chargement des données : {e}")

    if records:
        df = pd.DataFrame(records)
        
        cols_display = {
            "id": "ID",
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

        st.dataframe(df_show, use_container_width=True, hide_index=True)

        # --- ACTIONS ADMINISTRATEUR (MODIFICATION & SUPPRESSION) ---
        if is_admin:
            st.markdown("### ⚙️ Actions Administrateur")
            
            selected_id = st.selectbox(
                "Sélectionner un essai à modifier ou supprimer :",
                options=[r["id"] for r in records],
                key="select_plaque_admin"
            )
            
            col_act1, col_act2 = st.columns(2)
            
            with col_act1:
                if st.button("✏️ Modifier cet essai", use_container_width=True):
                    item = next((r for r in records if r["id"] == selected_id), None)
                    if item:
                        st.session_state["edit_plaque_item"] = item
                        st.rerun()

            with col_act2:
                if st.button("🗑️ Supprimer cet essai", type="primary", use_container_width=True):
                    try:
                        supabase.table("essais_plaque").delete().eq("id", selected_id).execute()
                        st.success(f"🗑️ Essai #{selected_id} supprimé avec succès.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la suppression : {e}")
    else:
        st.info("ℹ️ Aucun essai à la plaque enregistré pour ce chantier.")

if __name__ == "__main__":
    st.error("Ce fichier doit être appelé depuis app.py.")
