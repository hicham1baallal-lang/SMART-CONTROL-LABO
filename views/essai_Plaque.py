import streamlit as st
import pandas as pd
from datetime import date, datetime
from audit_log import enregistrer_modification, afficher_historique_modifications
import projets_config

def show(supabase):
    st.title("🚜 Essai à la Plaque (NF P 94-117-1)")

    # ---------------------------------------------------------
    # RÉCUPÉRATION DYNAMIQUE DU TECHNICIEN CONNECTÉ
    # ---------------------------------------------------------
    user_raw = (
        st.session_state.get("username") or 
        st.session_state.get("user") or 
        st.session_state.get("user_name") or 
        "Agent LPEE"
    )

    if isinstance(user_raw, dict):
        user_raw = user_raw.get("email") or user_raw.get("name") or "Agent LPEE"

    current_user = str(user_raw).upper()

    # Détection administrateur pour la suppression
    user_role = str(st.session_state.get("role", "")).upper()
    is_admin = st.session_state.get("is_admin", False) or user_role == "ADMIN"
    is_baallal_admin = current_user.strip() == "BAALLAL" and is_admin

    # Projet actif
    user_info_projet = st.session_state.get("user") or {}
    projet_id_actif = projets_config.projet_actif(user_info_projet)
    if not projet_id_actif:
        st.error("⚠️ Aucun projet ne vous est autorisé. Contactez un administrateur.")
        return
    st.caption(f"📁 Projet actif : **{projets_config.nom_projet(projet_id_actif)}**")

    # ---------------------------------------------------------
    # 1. GESTION DU MOTEUR D'ÉDITION / MODIFICATION
    # ---------------------------------------------------------
    editing_item = st.session_state.get("edit_plaque_item", None)

    if editing_item:
        st.info(f"✏️ **Mode Modification** - Essai ID #{editing_item['id']}")
        
        default_ref = editing_item.get("reference") or editing_item.get("ref_essai") or "260/26/PLQ/01"
        default_date = datetime.strptime(editing_item["date_essai"], "%Y-%m-%d").date() if isinstance(editing_item.get("date_essai"), str) else date.today()
        default_client = editing_item.get("client", "TGCC")
        default_projet = editing_item.get("projet", "LGV CASA SUD")
        default_empl = editing_item.get("emplacement", "")
        default_pk = editing_item.get("pk_profil", editing_item.get("pkl", ""))
        default_couche = editing_item.get("couche", "Sous-couche et Couche de forme ferroviaire (LGV)")
        default_mat = editing_item.get("nature_materiau", "")
        default_tech = editing_item.get("technicien", current_user)
        default_obs = editing_item.get("observations", "")
        
        saved_points = editing_item.get("points_mesure")
        if not saved_points or not isinstance(saved_points, list):
            default_points = [{"z1": float(editing_item.get("z1", 0.53)), "z2": float(editing_item.get("z2", 0.52)), "pk_point": default_pk}]
        else:
            default_points = saved_points
    else:
        default_ref = "260/26/PLQ/01"
        default_date = date.today()
        default_client = "TGCC"
        default_projet = "LGV CASA SUD"
        default_empl = "Voie B"
        default_pk = "PK 1+200"
        default_couche = "Sous-couche et Couche de forme ferroviaire (LGV)"
        default_mat = "GNT 0/31.5 Classée B2"
        default_tech = current_user
        default_obs = ""
        default_points = [{"z1": 0.53, "z2": 0.52, "pk_point": "PK 1+200"}]

    # ---------------------------------------------------------
    # 2. FORMULAIRE DE SAISIE / ÉDITION
    # ---------------------------------------------------------
    st.subheader("📝 " + ("Modifier l'essai" if editing_item else "Saisie d'un nouvel essai"))

    # --- SECTION 1 : INFORMATIONS GÉNÉRALES ---
    st.markdown("### 1. Informations Générales d'essai")
    col0, col1, col2 = st.columns(3)

    with col0:
        reference = st.text_input("Référence de l'essai", value=default_ref, key="plaque_reference")
    with col1:
        date_essai = st.date_input("Date de l'essai", value=default_date, key="plaque_date")
        client = st.text_input("Client / Organisme", value=default_client, key="plaque_client")
        projet = st.text_input("Chantier / Projet", value=default_projet, key="plaque_projet")
    with col2:
        couche_options = [
            "Sous-couche et Couche de forme ferroviaire (LGV)",
            "Remblais contigus aux Ouvrages d'Art (PRO)",
            "Arase des terrassements / PST",
            "Corps de remblai courant (avant PST)",
            "Remblais de fouilles d'ouvrages d'art",
            "Couche de forme des rétablissements / accès",
            "Plateforme support d'étaiements / cintres",
            "Autre"
        ]
        couche_idx = couche_options.index(default_couche) if default_couche in couche_options else 0
        couche = st.selectbox("Couche / Ouvrage testé", couche_options, index=couche_idx, key="plaque_couche")
        emplacement = st.text_input("Emplacement / Zone", value=default_empl, key="plaque_empl")
        pk_profil = st.text_input("PK / Profil Global", value=default_pk, key="plaque_pk")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        nature_materiau = st.text_input("Nature du matériau", value=default_mat, key="plaque_mat")
    with col_m2:
        technicien = st.text_input("Technicien LPEE", value=default_tech, key="plaque_tech")

    st.markdown("---")

    # --- SECTION 2 : POINTS DE MESURE D'ESSAI À LA PLAQUE ---
    st.markdown("### 2. Points de Mesure d'essai à la plaque")
    st.caption("Vous pouvez ajouter un ou plusieurs points de mesure pour cet essai, avec un Num/PK/Profil spécifique pour chaque point.")

    if "plaque_points_count" not in st.session_state or editing_item:
        st.session_state["plaque_points_count"] = len(default_points)

    col_add, col_rem, _ = st.columns([1, 1, 3])
    with col_add:
        if st.button("➕ Ajouter un point"):
            st.session_state["plaque_points_count"] += 1
    with col_rem:
        if st.session_state["plaque_points_count"] > 1:
            if st.button("➖ Supprimer un point"):
                st.session_state["plaque_points_count"] -= 1

    points_data = []
    for i in range(st.session_state["plaque_points_count"]):
        st.markdown(f"**Point de mesure N° {i+1}**")
        p_col0, p_col1, p_col2 = st.columns([1, 1, 1])
        
        default_pk_point = default_points[i].get("pk_point", default_pk) if i < len(default_points) else default_pk
        default_z1_val = default_points[i]["z1"] if i < len(default_points) else 0.53
        default_z2_val = default_points[i]["z2"] if i < len(default_points) else 0.52

        with p_col0:
            pk_point = st.text_input(f"Num/PK/Profil [Point {i+1}]", value=str(default_pk_point), key=f"plaque_pk_point_{i}")
        with p_col1:
            z1 = st.number_input(f"Z1 - 1er chrg (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z1_val), step=0.01, format="%.2f", key=f"plaque_z1_{i}")
        with p_col2:
            z2 = st.number_input(f"Z2 - 2ème chrg (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z2_val), step=0.01, format="%.2f", key=f"plaque_z2_{i}")
        
        points_data.append({"z1": z1, "z2": z2, "pk_point": pk_point})

    # Calculs automatiques pour tous les points (NF P 94-117-1)
    st.markdown("---")
    st.subheader("📈 Résultats Calculés Automatiquement pour tous les points")

    points_results = []
    commentaires_points = []
    
    for i, p in enumerate(points_data):
        z1_val = p["z1"]
        z2_val = p["z2"]
        ev1_i = round(112.5 / (z1_val * 2), 2) if z1_val > 0 else 0.0
        ev2_i = round(90.0 / (z2_val * 2), 2) if z2_val > 0 else 0.0
        k_ratio_i = round(ev2_i / ev1_i, 2) if ev1_i > 0 else 0.0

        # --- ÉVALUATION SYSTÉMATIQUE SELON LES EXIGENCES DU MARCHÉ ---
        conforme = True
        motif = []

        if couche == "Sous-couche et Couche de forme ferroviaire (LGV)":
            if ev2_i < 80.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa < 80 MPa requis")
        elif couche == "Remblais contigus aux Ouvrages d'Art (PRO)":
            if ev2_i < 80.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa < 80 MPa requis (plateforme)")
        elif couche == "Arase des terrassements / PST":
            if ev2_i < 50.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa < 50 MPa absolu requis (100%)")
            elif ev2_i < 60.0:
                motif.append(f"EV2 = {ev2_i} MPa entre 50 et 60 MPa")
        elif couche == "Corps de remblai courant (avant PST)":
            if ev2_i < 30.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa < 30 MPa requis")
        elif couche == "Remblais de fouilles d'ouvrages d'art":
            if ev2_i < 80.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa < 80 MPa (800 bars) requis")
        elif couche == "Couche de forme des rétablissements / accès":
            if ev2_i <= 50.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa non supérieur à 50 MPa requis (PF2)")
        elif couche == "Plateforme support d'étaiements / cintres":
            if ev2_i <= 80.0:
                conforme = False
                motif.append(f"EV2 = {ev2_i} MPa non supérieur à 80 MPa requis")

        if k_ratio_i > 2.0:
            motif.append(f"K = {k_ratio_i} > 2.0 (Attention tassement)")

        if conforme and not motif:
            comm_pt = f"Point {p['pk_point']} : Portance conforme aux exigences du marché (EV2 = {ev2_i} MPa, K = {k_ratio_i})."
        elif conforme and motif:
            comm_pt = f"Point {p['pk_point']} : Portance conforme avec remarques ({', '.join(motif)})."
        else:
            comm_pt = f"Point {p['pk_point']} : Non conforme aux exigences du marché ({', '.join(motif)})."

        commentaires_points.append(comm_pt)

        points_results.append({
            "ev1": ev1_i,
            "ev2": ev2_i,
            "k_ratio": k_ratio_i,
            "commentaire": comm_pt
        })

        st.markdown(f"**Point de mesure N° {i+1} ({p['pk_point']})**")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric(f"EV1 (MPa) [Point {i+1}]", f"{ev1_i:.2f}")
        res_col2.metric(f"EV2 (MPa) [Point {i+1}]", f"{ev2_i:.2f}")
        
        k_delta = "Conforme (K ≤ 2.0)" if k_ratio_i <= 2.0 else "Attention (K > 2.0)"
        res_col3.metric(f"Coefficient K [Point {i+1}]", f"{k_ratio_i:.2f}", delta=k_delta, delta_color="normal" if k_ratio_i <= 2.0 else "inverse")
        st.caption(f"💬 **Avis automatique :** {comm_pt}")

    # Valeurs de référence principales (premier point ou moyennes)
    active_z1 = points_data[0]["z1"]
    active_z2 = points_data[0]["z2"]
    ev1 = points_results[0]["ev1"]
    ev2 = points_results[0]["ev2"]
    k_ratio = points_results[0]["k_ratio"]

    # Commentaire global établi systématiquement
    default_obs_systematique = "\n".join(commentaires_points)
    if not default_obs and not editing_item:
        default_obs = default_obs_systematique
    elif editing_item and not default_obs:
        default_obs = default_obs_systematique

    observations = st.text_area("Commentaire / Remarques (établi systématiquement)", value=default_obs, key="plaque_obs")

    # ---------------------------------------------------------
    # 3. ENREGISTREMENT OU MISE À JOUR SÉCURISÉE
    # ---------------------------------------------------------
    btn_col1, btn_col2 = st.columns([3, 1])

    with btn_col1:
        button_label = "🔄 Mettre à jour l'essai" if editing_item else "💾 Enregistrer l'essai"
        if st.button(button_label, key="btn_enregistrer_plaque", type="primary", use_container_width=True):
            
            # --- VÉRIFICATION DU DOUBLON DE RÉFÉRENCE ---
            try:
                ref_query = supabase.table("essai_plaque").select("id").eq("projet_id", projet_id_actif).eq("reference", reference)
                if editing_item:
                    ref_query = ref_query.neq("id", editing_item["id"])
                ref_res = ref_query.execute()
                
                if ref_res.data and len(ref_res.data) > 0:
                    st.error(f"⚠️ Erreur : La référence d'essai '{reference}' existe déjà dans ce projet. Double bloqué.")
                    st.stop()
            except Exception as ref_err:
                pass

            payload = {
                "reference": reference,
                "date_essai": str(date_essai),
                "client": client,
                "projet": projet,
                "emplacement": emplacement,
                "pk_profil": pk_profil,
                "couche": couche,
                "nature_materiau": nature_materiau,
                "z1": float(active_z1),
                "z2": float(active_z2),
                "points_mesure": points_data,
                "ev1": float(ev1),
                "ev2": float(ev2),
                "k_ratio": float(k_ratio),
                "technicien": technicien,
                "observations": observations
            }

            try:
                sample_query = supabase.table("essai_plaque").select("*").limit(1).execute()
                if sample_query.data and len(sample_query.data) > 0:
                    valid_columns = set(sample_query.data[0].keys())
                    safe_payload = {k: v for k, v in payload.items() if k in valid_columns}
                else:
                    safe_payload = payload

                safe_payload["projet_id"] = projet_id_actif

                if editing_item:
                    anciennes_valeurs_plaque = {k: editing_item.get(k) for k in safe_payload}
                    supabase.table("essai_plaque").update(safe_payload).eq("id", editing_item["id"]).eq("projet_id", projet_id_actif).execute()
                    enregistrer_modification(
                        supabase,
                        table_concernee="essai_plaque",
                        enregistrement_id=editing_item["id"],
                        action="MODIFICATION",
                        anciennes_valeurs=anciennes_valeurs_plaque,
                        nouvelles_valeurs=safe_payload,
                    )
                    st.success(f"✅ Essai #{editing_item['id']} mis à jour avec succès !")
                    st.session_state["edit_plaque_item"] = None
                else:
                    res_ins_plaque = supabase.table("essai_plaque").insert(safe_payload).execute()
                    if res_ins_plaque.data:
                        nouvel_id_plaque = res_ins_plaque.data[0].get("id")
                        enregistrer_modification(
                            supabase,
                            table_concernee="essai_plaque",
                            enregistrement_id=nouvel_id_plaque,
                            action="CREATION",
                            nouvelles_valeurs=safe_payload,
                        )
                    st.success("✅ Essai enregistré avec succès !")

                st.rerun()

            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement : {e}")

    with btn_col2:
        if editing_item:
            if st.button("❌ Annuler l'édition", use_container_width=True):
                st.session_state["edit_plaque_item"] = None
                st.rerun()

    # ---------------------------------------------------------
    # 4. HISTORIQUE DES ESSAIS ET ACTIONS DE MODIFICATION
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📋 Historique des Essais Enregistrés")

    try:
        res = supabase.table("essai_plaque").select("*").eq("projet_id", projet_id_actif).order("id", desc=True).execute()
        if res.data and len(res.data) > 0:
            
            clean_rows = []
            for row in res.data:
                # Récupération robuste de la référence (gestion des différentes variations de noms de colonnes en base)
                ref_val = row.get("reference") or row.get("ref_essai") or row.get("ref") or "-"
                if not ref_val or str(ref_val).strip() == "":
                    ref_val = "-"

                pk_val = row.get("pk_profil") if row.get("pk_profil") is not None else row.get("pkl")
                points = row.get("points_mesure")
                if not isinstance(points, list) or len(points) == 0:
                    z1_fallback = float(row.get("z1", 0.53))
                    z2_fallback = float(row.get("z2", 0.52))
                    points = [{"z1": z1_fallback, "z2": z2_fallback, "pk_point": pk_val}]

                ev1_list = []
                ev2_list = []
                k_list = []
                for idx, pt in enumerate(points):
                    z1_val = float(pt.get("z1", 0.53))
                    z2_val = float(pt.get("z2", 0.52))
                    pt_pk = pt.get("pk_point", f"P{idx+1}")
                    ev1_pt = round(112.5 / (z1_val * 2), 2) if z1_val > 0 else 0.0
                    ev2_pt = round(90.0 / (z2_val * 2), 2) if z2_val > 0 else 0.0
                    k_pt = round(ev2_pt / ev1_pt, 2) if ev1_pt > 0 else 0.0
                    
                    ev1_list.append(f"{pt_pk}: {ev1_pt:.2f}")
                    ev2_list.append(f"{pt_pk}: {ev2_pt:.2f}")
                    k_list.append(f"{pt_pk}: {k_pt:.2f}")

                clean_rows.append({
                    "ID": row.get("id"),
                    "Référence": ref_val,
                    "Date d'essai": row.get("date_essai"),
                    "Client": row.get("client"),
                    "Projet": row.get("projet"),
                    "Emplacement": row.get("emplacement"),
                    "PK/profil": pk_val,
                    "Couche": row.get("couche"),
                    "Nature de matériaux": row.get("nature_materiau"),
                    "Nb Points": len(points),
                    "EV1 (MPa)": " | ".join(ev1_list),
                    "EV2 (MPa)": " | ".join(ev2_list),
                    "K (EV2/EV1)": " | ".join(k_list),
                    "Remarques": row.get("observations"),
                    "Technicien": row.get("technicien")
                })

            df_display = pd.DataFrame(clean_rows)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # --- ACTIONS DE SÉLECTION ET EDITION ---
            st.markdown("### ⚙️ Actions de Modification / Gestion")
            
            selected_id = st.selectbox(
                "Sélectionnez un essai par son ID :", 
                options=[item["id"] for item in res.data],
                key="admin_select_plaque_id"
            )

            if is_baallal_admin:
                afficher_historique_modifications(supabase, "essai_plaque", selected_id)

            if is_admin:
                act_col1, act_col2 = st.columns(2)
                with act_col1:
                    if st.button("✏️ Modifier cet essai", type="secondary", use_container_width=True):
                        selected_item = next((item for item in res.data if item["id"] == selected_id), None)
                        if selected_item:
                            st.session_state["edit_plaque_item"] = selected_item
                            st.rerun()

                with act_col2:
                    if st.button("🗑️ Supprimer cet essai", type="primary", use_container_width=True):
                        try:
                            item_a_supprimer = next((item for item in res.data if item["id"] == selected_id), None)
                            enregistrer_modification(
                                supabase,
                                table_concernee="essai_plaque",
                                enregistrement_id=selected_id,
                                action="SUPPRESSION",
                                anciennes_valeurs={k: v for k, v in (item_a_supprimer or {}).items() if k != "id"},
                                commentaire="Suppression définitive de l'essai",
                            )
                            supabase.table("essai_plaque").delete().eq("id", selected_id).eq("projet_id", projet_id_actif).execute()
                            st.success(f"🗑️ Essai #{selected_id} supprimé avec succès.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la suppression : {e}")
            else:
                if st.button("✏️ Modifier cet essai", type="secondary", use_container_width=True):
                    selected_item = next((item for item in res.data if item["id"] == selected_id), None)
                    if selected_item:
                        st.session_state["edit_plquare_item"] = selected_item
                        st.rerun()

        else:
            st.info("Aucun essai à la plaque n'a encore été enregistré.")
    except Exception as e:
        st.warning(f"Impossible de charger l'historique : {e}")
