"""
Gestion des Utilisateurs & Mots de Passe — module d'administration.

Permet de consulter, ajouter, modifier et supprimer des utilisateurs de la
plateforme, avec sauvegarde permanente sur la table Supabase `users`
(username, password, role, can_edit, projets_autorises).

Réservé aux administrateurs (role == "admin").
"""

import streamlit as st
import pandas as pd
import re
import projets_config

TABLE_USERS = "users"

ROLES_CONNUS = ["admin", "laboratoire", "restricted_betonnage"]


def _colonne_manquante_depuis_erreur(erreur):
    """Extrait le nom de colonne d'un message d'erreur PostgREST du type
    "Could not find the 'xxx' column of 'users' in the schema cache"."""
    m = re.search(r"Could not find the '([^']+)' column", str(erreur))
    return m.group(1) if m else None


def _ecrire_utilisateur_adaptatif(operation_fn, payload):
    """Exécute une opération d'écriture (insert/update) sur `payload`, en
    s'adaptant automatiquement si certaines colonnes n'existent pas dans la
    table `users` réelle (schéma inconnu/partiel) : renomme "password" en
    "password_hash" si besoin, ou retire silencieusement les colonnes
    optionnelles absentes (can_edit, projets_autorises...), et réessaie.
    Lève l'erreur si elle n'est pas liée à une colonne manquante, ou si le
    payload devient vide après retraits."""
    payload = dict(payload)
    for _ in range(8):
        try:
            operation_fn(payload)
            return payload
        except Exception as e:
            col = _colonne_manquante_depuis_erreur(e)
            if col is None:
                raise
            if col == "password" and "password" in payload and "password_hash" not in payload:
                payload["password_hash"] = payload.pop("password")
            elif col in payload:
                del payload[col]
            else:
                raise
            if not payload:
                raise Exception("Aucune colonne compatible trouvée dans la table 'users'.")
    raise Exception("Impossible d'adapter automatiquement les colonnes après plusieurs tentatives.")


def _normaliser_projets(valeur):
    """Uniformise le champ projets_autorises (peut arriver en liste, en
    texte séparé par des virgules, ou vide) en liste Python de chaînes."""
    if not valeur:
        return []
    if isinstance(valeur, list):
        return [str(p).strip() for p in valeur if str(p).strip()]
    if isinstance(valeur, str):
        return [p.strip() for p in valeur.split(",") if p.strip()]
    return []


@st.cache_data(ttl=60)
def _charger_utilisateurs(_supabase_client):
    """Charge tous les utilisateurs depuis Supabase. Retourne une liste de
    dicts (username, password, role, can_edit, projets_autorises)."""
    if _supabase_client is None:
        return []
    try:
        res = _supabase_client.table(TABLE_USERS).select("*").order("username").execute()
        lignes = res.data or []
        for l in lignes:
            l["projets_autorises"] = _normaliser_projets(l.get("projets_autorises"))
            # Le mot de passe peut être stocké sous "password" ou
            # "password_hash" selon le schéma réel de la table.
            if "password" not in l and "password_hash" in l:
                l["password"] = l["password_hash"]
        return lignes
    except Exception as e:
        st.error(f"❌ Impossible de charger les utilisateurs : {e}")
        return []


def _libelle_projets_autorises(user_row):
    if str(user_row.get("role", "")).lower() == "admin":
        return "Tous (admin)"
    projets = user_row.get("projets_autorises") or []
    if not projets:
        return "-"
    return ", ".join(projets_config.nom_projet(p) for p in projets)


def show(supabase_client, can_edit=True, **kwargs):
    st.title("👥 Gestion des Utilisateurs & Mots de Passe")
    st.caption("Consultez, ajoutez, modifiez et supprimez des utilisateurs de la plateforme (sauvegarde permanente Supabase).")

    # --------------------------------------------------------------------
    # Contrôle d'accès : réservé aux administrateurs
    # --------------------------------------------------------------------
    user_raw = st.session_state.get("user") or {}
    current_username = str(user_raw.get("username", "")).strip().upper()
    user_role = str(st.session_state.get("role", "")).upper()
    is_admin = st.session_state.get("is_admin", False) or user_role == "ADMIN"

    if not is_admin:
        st.error("⛔ Cette page est réservée aux administrateurs.")
        return

    if supabase_client is None:
        st.error("❌ Aucun client Supabase disponible : la gestion des utilisateurs nécessite une connexion à la base de données.")
        return

    utilisateurs = _charger_utilisateurs(supabase_client)
    projets_options = list(projets_config.PROJETS.keys())

    # --------------------------------------------------------------------
    # ➕ AJOUTER UN UTILISATEUR
    # --------------------------------------------------------------------
    with st.expander("➕ Ajouter un utilisateur"):
        with st.form("form_ajouter_utilisateur", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nouv_username = st.text_input("Nom d'utilisateur").strip().upper()
                nouv_password = st.text_input("Mot de passe")
            with col2:
                nouv_role = st.selectbox("Rôle", ROLES_CONNUS)
                nouv_can_edit = st.checkbox("Droit de modification (can_edit)", value=False)

            nouv_projets = []
            if nouv_role != "admin":
                nouv_projets = st.multiselect(
                    "Projets autorisés",
                    options=projets_options,
                    format_func=projets_config.nom_projet,
                    default=[projets_config.PROJET_PAR_DEFAUT] if projets_config.PROJET_PAR_DEFAUT in projets_options else []
                )

            submit_ajout = st.form_submit_button("➕ Ajouter", type="primary", use_container_width=True)

            if submit_ajout:
                if not nouv_username or not nouv_password:
                    st.error("Le nom d'utilisateur et le mot de passe sont obligatoires.")
                elif any(u.get("username", "").upper() == nouv_username for u in utilisateurs):
                    st.error(f"⛔ L'utilisateur '{nouv_username}' existe déjà. Utilisez plutôt 'Modifier un utilisateur'.")
                else:
                    try:
                        payload_ajout = {
                            "username": nouv_username,
                            "password": nouv_password,
                            "role": nouv_role,
                            "can_edit": nouv_can_edit,
                            "projets_autorises": nouv_projets,
                        }
                        _ecrire_utilisateur_adaptatif(
                            lambda p: supabase_client.table(TABLE_USERS).insert(p).execute(),
                            payload_ajout
                        )
                        st.success(f"✅ Utilisateur '{nouv_username}' ajouté avec succès.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Échec de l'ajout : {e}")

    # --------------------------------------------------------------------
    # ✏️ MODIFIER UN UTILISATEUR
    # --------------------------------------------------------------------
    with st.expander("✏️ Modifier un utilisateur"):
        if not utilisateurs:
            st.caption("Aucun utilisateur à modifier.")
        else:
            noms = [u["username"] for u in utilisateurs]
            choix_mod = st.selectbox("Utilisateur à modifier", noms, key="select_user_modifier")
            user_mod = next(u for u in utilisateurs if u["username"] == choix_mod)

            with st.form("form_modifier_utilisateur"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Nom d'utilisateur", value=user_mod["username"], disabled=True)
                    mod_password = st.text_input("Mot de passe", value=user_mod.get("password", ""))
                with col2:
                    role_idx = ROLES_CONNUS.index(user_mod.get("role")) if user_mod.get("role") in ROLES_CONNUS else 0
                    mod_role = st.selectbox("Rôle", ROLES_CONNUS, index=role_idx)
                    mod_can_edit = st.checkbox("Droit de modification (can_edit)", value=bool(user_mod.get("can_edit", False)))

                mod_projets = []
                if mod_role != "admin":
                    mod_projets = st.multiselect(
                        "Projets autorisés",
                        options=projets_options,
                        format_func=projets_config.nom_projet,
                        default=[p for p in user_mod.get("projets_autorises", []) if p in projets_options]
                    )

                submit_mod = st.form_submit_button("💾 Enregistrer les modifications", type="primary", use_container_width=True)

                if submit_mod:
                    try:
                        payload_mod = {
                            "password": mod_password,
                            "role": mod_role,
                            "can_edit": mod_can_edit,
                            "projets_autorises": mod_projets,
                        }
                        _ecrire_utilisateur_adaptatif(
                            lambda p: supabase_client.table(TABLE_USERS).update(p).eq("username", user_mod["username"]).execute(),
                            payload_mod
                        )
                        st.success(f"✅ Utilisateur '{user_mod['username']}' mis à jour avec succès.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Échec de la mise à jour : {e}")

    # --------------------------------------------------------------------
    # 🗑️ SUPPRIMER UN UTILISATEUR
    # --------------------------------------------------------------------
    with st.expander("🗑️ Supprimer un utilisateur"):
        if not utilisateurs:
            st.caption("Aucun utilisateur à supprimer.")
        else:
            noms_sup = [u["username"] for u in utilisateurs]
            choix_sup = st.selectbox("Utilisateur à supprimer", noms_sup, key="select_user_supprimer")

            nb_admins = sum(1 for u in utilisateurs if str(u.get("role", "")).lower() == "admin")
            user_est_admin = next((u for u in utilisateurs if u["username"] == choix_sup), {}).get("role") == "admin"

            if choix_sup == current_username:
                st.warning("⚠️ Vous ne pouvez pas supprimer votre propre compte pendant que vous êtes connecté avec.")
            elif user_est_admin and nb_admins <= 1:
                st.warning("⚠️ Impossible de supprimer le dernier compte administrateur restant.")
            else:
                st.warning(f"⚠️ Suppression définitive de l'utilisateur **{choix_sup}**. Cette action est irréversible.")
                confirm_sup = st.checkbox(f"Je confirme vouloir supprimer '{choix_sup}'", key="confirm_del_user")
                if st.button("🗑️ Supprimer définitivement", type="primary", disabled=not confirm_sup, use_container_width=True):
                    try:
                        supabase_client.table(TABLE_USERS).delete().eq("username", choix_sup).execute()
                        st.success(f"✅ Utilisateur '{choix_sup}' supprimé avec succès.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Échec de la suppression : {e}")

    st.markdown("---")

    # --------------------------------------------------------------------
    # Tableau récapitulatif (identique à la maquette)
    # --------------------------------------------------------------------
    if utilisateurs:
        lignes_affichage = []
        for u in utilisateurs:
            lignes_affichage.append({
                "Utilisateur": u.get("username", "-"),
                "Mot de Passe": u.get("password", "-"),
                "Rôle": u.get("role", "-"),
                "Droit de modification (can_edit)": bool(u.get("can_edit", False)),
                "Projets autorisés": _libelle_projets_autorises(u),
            })
        df_users = pd.DataFrame(lignes_affichage)
        st.dataframe(
            df_users,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Droit de modification (can_edit)": st.column_config.CheckboxColumn(
                    "Droit de modification (can_edit)", disabled=True
                )
            }
        )
    else:
        st.info("Aucun utilisateur enregistré.")
