import datetime
import streamlit as st


def convertir_payload_safe(data: dict) -> dict:
    """Nettoie et convertit toutes les valeurs en types natifs Python (float, int, str, bool)

    pour éviter les erreurs de sérialisation JSON et Gateway Timeout (504).
    """
    clean_data = {}
    for key, value in data.items():
        if value is None:
            clean_data[key] = None
        elif isinstance(value, (datetime.date, datetime.datetime)):
            clean_data[key] = value.isoformat()
        elif hasattr(value, "item"):  # Types NumPy (float64, int64)
            clean_data[key] = value.item()
        else:
            clean_data[key] = value
    return clean_data


def enregistrer_essai_plaque(supabase, payload: dict):
    """Gère la sauvegarde vers Supabase avec fallback automatique vers SQLite."""
    clean_payload = convertir_payload_safe(payload)

    with st.spinner("💾 Enregistrement de l'essai à la plaque..."):
        # 1. Tentative d'insertion Supabase
        if supabase is not None:
            try:
                res = (
                    supabase.table("essais_plaque")
                    .insert(clean_payload)
                    .execute()
                )
                if res.data:
                    st.success("✅ Essai enregistré avec succès sur Supabase !")
                    st.rerun()
                    return
            except Exception as e:
                err_msg = str(e)
                if (
                    "504" in err_msg
                    or "Gateway Timeout" in err_msg
                    or "Timeout" in err_msg
                ):
                    st.warning(
                        "⚠️ Connexion lente à Supabase (Timeout 504). Passage en sauvegarde locale."
                    )
                else:
                    st.warning(
                        f"⚠️ Inaccessible directement sur Supabase : {err_msg}"
                    )

        # 2. Sauvegarde de secours en mode Hors-Ligne (SQLite)
        try:
            from offline_manager import insert_safe

            insert_safe("essais_plaque", clean_payload)
            st.info(
                "📦 Essai sauvegardé localement en mode hors-ligne. Il sera synchronisé à la réouverture du réseau."
            )
        except ImportError:
            st.error(
                "❌ Le gestionnaire SQLite (offline_manager.py) n'est pas configuré."
            )
        except Exception as offline_err:
            st.error(
                f"❌ Erreur lors de la sauvegarde en local : {offline_err}"
            )


def show(supabase=None):
    st.title("🚜 Essai de Portance à la Plaque")
    st.caption("Normes NF P 94-117-1 / NF P 94-117-2 — LPEE LGV CASA SUD")
    st.markdown("---")

    # --- FORMULAIRE DE SAISIE ---
    with st.form("form_essai_plaque"):
        st.subheader("📋 Identification & Informations Générales")
        col1, col2, col3 = st.columns(3)

        with col1:
            num_pv = st.text_input("N° du PV / Fiche", value="PV-PLQ-2026-001")
            pk_station = st.text_input("Localisation (PK)", value="PK 1+200")

        with col2:
            couche = st.selectbox(
                "Couche / Structure",
                [
                    "PST",
                    "Couche de Forme (GNT)",
                    "Sous-couche",
                    "Plateforme Ballast",
                ],
            )
            operateur = st.text_input(
                "Opérateur",
                value=st.session_state.get("user", {}).get(
                    "username", "BAALLAL"
                ),
            )

        with col3:
            date_essai = st.date_input(
                "Date de l'essai", value=datetime.date.today()
            )
            diametre_plaque = st.selectbox(
                "Diamètre Plaque (mm)", [600, 300], index=0
            )

        st.markdown("---")
        st.subheader("📊 Saisie des Valeurs d'Essai")

        cp1, cp2 = st.columns(2)

        # Point 1
        with cp1:
            st.markdown("##### 📍 Point N°1")
            ev1_p1 = st.number_input(
                "EV1 (MPa) - Point 1", min_value=0.0, value=106.13, step=0.01
            )
            ev2_p1 = st.number_input(
                "EV2 (MPa) - Point 1", min_value=0.0, value=86.54, step=0.01
            )
            k_p1 = round(ev2_p1 / ev1_p1, 2) if ev1_p1 > 0 else 0.0
            st.metric(label="Coefficient K (EV2/EV1)", value=k_p1)

        # Point 2
        with cp2:
            st.markdown("##### 📍 Point N°2")
            ev1_p2 = st.number_input(
                "EV1 (MPa) - Point 2", min_value=0.0, value=106.13, step=0.01
            )
            ev2_p2 = st.number_input(
                "EV2 (MPa) - Point 2", min_value=0.0, value=86.54, step=0.01
            )
            k_p2 = round(ev2_p2 / ev1_p2, 2) if ev1_p2 > 0 else 0.0
            st.metric(label="Coefficient K (EV2/EV1)", value=k_p2)

        st.markdown("---")
        txt_defaut = f"Point {pk_station} : EV2 = {ev2_p1} MPa, K = {k_p1}.\nPoint {pk_station} : EV2 = {ev2_p2} MPa, K = {k_p2}."
        commentaires = st.text_area(
            "Commentaire / Remarques", value=txt_defaut, height=90
        )

        btn_submit = st.form_submit_button(
            "💾 Enregistrer l'essai", use_container_width=True, type="primary"
        )

    # --- TRAITEMENT DU FORMULAIRE ---
    if btn_submit:
        payload = {
            "num_pv": str(num_pv),
            "pk_station": str(pk_station),
            "couche": str(couche),
            "operateur": str(operateur),
            "date_essai": date_essai,
            "diametre_plaque": int(diametre_plaque),
            "ev1_p1": float(ev1_p1),
            "ev2_p1": float(ev2_p1),
            "k_p1": float(k_p1),
            "ev1_p2": float(ev1_p2),
            "ev2_p2": float(ev2_p2),
            "k_p2": float(k_p2),
            "commentaires": str(commentaires),
            "created_at": datetime.datetime.now(),
        }
        enregistrer_essai_plaque(supabase, payload)

    # --- HISTORIQUE DES ESSAIS ---
    st.markdown("---")
    st.subheader("📋 Derniers Essais Enregistrés")

    if supabase is not None:
        try:
            res = (
                supabase.table("essais_plaque")
                .select("*")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            if res.data:
                st.dataframe(res.data, use_container_width=True)
            else:
                st.info("Aucun essai enregistré sur Supabase pour le moment.")
        except Exception:
            st.info("Consultation de l'historique Supabase indisponible.")
