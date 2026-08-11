import streamlit as st
import pandas as pd
from datetime import date

def show(supabase):
    # --- EN-TÊTE : TITRE ET NORME CÔTE À CÔTE ---
    col_header1, col_header2 = st.columns([2, 1])
    with col_header1:
        st.title("🧪 Saisie - Essai à la Plaque")
    with col_header2:
        st.markdown(
            "<div style='text-align: right; padding-top: 15px; font-weight: bold; color: #1F4E79; font-size: 1.1em;'>"
            "📋 Norme : NF P 94-117-1"
            "</div>", 
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ---------------------------------------------------------
    # GESTION DES VALEURS EN MÉMOIRE (SESSION STATE)
    # ---------------------------------------------------------
    if 'ep_date' not in st.session_state:
        st.session_state['ep_date'] = date.today()
    if 'ep_technicien' not in st.session_state:
        st.session_state['ep_technicien'] = ""
    if 'ep_couche' not in st.session_state:
        st.session_state['ep_couche'] = "Remblai"
    if 'ep_emplacement' not in st.session_state:
        st.session_state['ep_emplacement'] = ""
    if 'ep_pk_profil' not in st.session_state:
        st.session_state['ep_pk_profil'] = ""
    if 'ep_z1' not in st.session_state:
        st.session_state['ep_z1'] = 0.0
    if 'ep_z2' not in st.session_state:
        st.session_state['ep_z2'] = 0.0

    couche_options = ["Remblai", "Assise", "PST", "Couche de forme"]
    couche_idx = couche_options.index(st.session_state['ep_couche']) if st.session_state['ep_couche'] in couche_options else 0

    # ---------------------------------------------------------
    # 1. FORMULAIRE DE SAISIE
    # ---------------------------------------------------------
    with st.form("form_essai_plaque", clear_on_submit=False):
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.text_input("Client", value="TGCC", disabled=True)
        with col_info2:
            st.text_input("Projet", value="LGV CASA SUD", disabled=True)

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            date_selected = st.date_input("Date de l'essai", value=st.session_state['ep_date'])
            technicien = st.text_input("Technicien :", value=st.session_state['ep_technicien'], placeholder="Nom du technicien")
            
        with col2:
            couche = st.selectbox(
                "Type de couche", 
                couche_options,
                index=couche_idx
            )

        col_loc1, col_loc2 = st.columns(2)
        with col_loc1:
            emplacement = st.text_input("Emplacement", value=st.session_state['ep_emplacement'], placeholder="Ex: Zone Nord / Voie 1")
        with col_loc2:
            pk_profil = st.text_input("PK / Profil", value=st.session_state['ep_pk_profil'], placeholder="Ex: PK 12+450 / Profil 12")

        st.markdown("### 📊 Données de Chargement (Enfoncements)")
        
        col_z1, col_z2 = st.columns(2)
        with col_z1:
            z1 = st.number_input("Z1 - 1er chargement (mm)", min_value=0.0, value=st.session_state['ep_z1'], step=0.01, format="%.2f")
        with col_z2:
            z2 = st.number_input("Z2 - 2ème chargement (mm)", min_value=0.0, value=st.session_state['ep_z2'], step=0.01, format="%.2f")

        ev1 = round(112.5 / (z1 * 2), 2) if z1 > 0 else 0.0
        ev2 = round(90.0 / (z2 * 2), 2) if z2 > 0 else 0.0
        k_val = round(ev2 / ev1, 2) if ev1 > 0 else 0.0

        st.markdown("### 📈 Résultats Calculés Automatiquement")
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("EV1 (MPa)", f"{ev1:.2f}")
        with col_res2:
            st.metric("EV2 (MPa)", f"{ev2:.2f}")
        with col_res3:
            st.metric("Coefficient K (EV2/EV1)", f"{k_val:.2f}")

        st.markdown("---")
        submitted = st.form_submit_button("💾 Enregistrer l'essai", use_container_width=True)

    # ---------------------------------------------------------
    # 2. ENREGISTREMENT DANS SUPABASE
    # ---------------------------------------------------------
    if submitted:
        if z1 <= 0 or z2 <= 0:
            st.warning("⚠️ Veuillez saisir des valeurs supérieures à 0 pour Z1 et Z2 afin d'effectuer les calculs.")
        else:
            try:
                st.session_state['ep_date'] = date_selected
                st.session_state['ep_technicien'] = technicien
                st.session_state['ep_couche'] = couche
                st.session_state['ep_emplacement'] = emplacement
                st.session_state['ep_pk_profil'] = pk_profil
                st.session_state['ep_z1'] = z1
                st.session_state['ep_z2'] = z2

                data_payload = {
                    "date_essai": str(date_selected),
                    "client": "TGCC",
                    "projet": "LGV CASA SUD",
                    "norme": "NF P 94-117-1",
                    "technicien": technicien,
                    "couche": couche,
                    "emplacement": emplacement,
                    "pk_profil": pk_profil,
                    "z1": float(z1),
                    "z2": float(z2),
                    "ev1": float(ev1),
                    "ev2": float(ev2),
                    "k": float(k_val)
                }

                supabase.table("essai_plaque").insert(data_payload).execute()
                st.success("✅ Essai à la plaque enregistré avec succès !")
                st.rerun()

            except Exception as e:
                st.error(f"Erreur d'enregistrement : {e}")

    # ---------------------------------------------------------
    # 3. AFFICHAGE DES ESSAIS ENREGISTRÉS & BLOC ADMIN
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📋 Historique des Essais à la Plaque Enregistrés")

    try:
        res = supabase.table("essai_plaque").select("*").order("date_essai", desc=True).execute()
        data = res.data if res else []

        if data:
            df = pd.DataFrame(data)

            cols_order = [
                "date_essai", "couche", "emplacement", "pk_profil", 
                "z1", "z2", "ev1", "ev2", "k", "technicien"
            ]

            cols_present = [c for c in cols_order if c in df.columns]
            df_display = df[cols_present]

            renames = {
                "date_essai": "Date d'essai",
                "couche": "Couche",
                "emplacement": "Emplacement",
                "pk_profil": "PK / Profil",
                "z1": "Z1 (mm)",
                "z2": "Z2 (mm)",
                "ev1": "EV1 (MPa)",
                "ev2": "EV2 (MPa)",
                "k": "Coefficient K",
                "technicien": "Technicien"
            }
            df_display = df_display.rename(columns=renames)

            st.dataframe(
                df_display, 
                use_container_width=True,
                hide_index=True
            )
            st.caption(f"Total des essais enregistrés : {len(df_display)}")

            # --- BLOC D'ADMINISTRATION (MODIFIER / SUPPRIMER) ---
            if st.session_state.get("role") == "admin":
                st.markdown("---")
                st.subheader("🛠️ Espace Administration")
                
                record_options = {f"ID {r['id']} - {r.get('date_essai', 'N/A')} - {r.get('pk_profil', '')}": r for r in data}
                selected_key = st.selectbox("Sélectionner l'essai à gérer", list(record_options.keys()))
                selected_item = record_options[selected_key]
                
                col_ed, col_del = st.columns(2)
                
                with col_ed:
                    with st.expander("📝 Modifier cet essai"):
                        with st.form("edit_form_saisie"):
                            new_pk = st.text_input("PK / Profil", value=selected_item.get("pk_profil", ""))
                            new_ev1 = st.number_input("EV1 (MPa)", value=float(selected_item.get("ev1", 0)))
                            new_ev2 = st.number_input("EV2 (MPa)", value=float(selected_item.get("ev2", 0)))
                            
                            if st.form_submit_button("Enregistrer les modifications"):
                                try:
                                    new_k = new_ev2 / new_ev1 if new_ev1 > 0 else 0
                                    supabase.table("essai_plaque").update({
                                        "pk_profil": new_pk,
                                        "ev1": new_ev1,
                                        "ev2": new_ev2,
                                        "k": new_k
                                    }).eq("id", selected_item["id"]).execute()
                                    st.success("Données mises à jour !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur : {e}")
                                    
                with col_del:
                    st.markdown("##### ⚠️ Suppression")
                    if st.button("🗑️ Supprimer définitivement", type="primary"):
                        try:
                            supabase.table("essai_plaque").delete().eq("id", selected_item["id"]).execute()
                            st.success("Supprimé avec succès.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        else:
            st.info("Aucun essai à la plaque n'a encore été enregistré.")

    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
