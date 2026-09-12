import datetime
import pandas as pd
import streamlit as st


def convertir_payload_safe(data: dict) -> dict:
    """Nettoie et convertit les types non sérialisables en types natifs Python.

    Évite les erreurs Gateway Timeout 504 et de sérialisation JSON.
    """
    clean_data = {}
    for key, value in data.items():
        if value is None:
            clean_data[key] = None
        elif isinstance(value, (datetime.date, datetime.datetime)):
            clean_data[key] = value.isoformat()
        elif hasattr(value, "item"):  # Conversion des scalaires NumPy
            clean_data[key] = value.item()
        else:
            clean_data[key] = value
    return clean_data


def enregistrer_essai_plaque(supabase, payload: dict):
    """Enregistre les données uniquement et directement sur Supabase."""
    if supabase is None:
        st.error(
            "❌ Connexion Supabase indisponible. Impossible d'enregistrer l'essai."
        )
        return

    clean_payload = convertir_payload_safe(payload)

    with st.spinner("💾 Enregistrement direct sur Supabase..."):
        try:
            res = (
                supabase.table("essais_plaque").insert(clean_payload).execute()
            )
            if res.data:
                st.success(
                    "✅ Essai à la plaque enregistré avec succès sur Supabase !"
                )
                st.rerun()
            else:
                st.error(
                    "❌ L'enregistrement a échoué : aucune donnée retournée par Supabase."
                )
        except Exception as e:
            err_msg = str(e)
            if (
                "504" in err_msg
                or "Gateway Timeout" in err_msg
                or "Timeout" in err_msg
            ):
                st.error(
                    "❌ Erreur 504 (Gateway Timeout) : Le serveur Supabase a mis trop de temps à répondre. Vérifiez votre connexion internet ou la configuration de la table Supabase."
                )
            else:
                st.error(f"❌ Erreur d'enregistrement Supabase : {err_msg}")


def charger_donnees_plaque(supabase):
    """Récupère tous les essais directement depuis la table Supabase essais_plaque."""
    if supabase is not None:
        try:
            res = (
                supabase.table("essais_plaque")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            if res.data:
                return pd.DataFrame(res.data)
        except Exception as e:
            st.warning(
                f"⚠️ Impossible de charger les données depuis Supabase : {e}"
            )
    return pd.DataFrame()


def show(supabase=None):
    st.title("🚜 Essai de Portance à la Plaque (NF P 94-117-1 / 2)")
    st.caption("Laboratoire LPEE — CTR Casablanca | LGV CASA SUD")
    st.markdown("---")

    # -------------------------------------------------------------
    # ORGANISATION EN 3 FENÊTRES / ONGLETS
    # -------------------------------------------------------------
    tab_saisie, tab_pv, tab_synthese = st.tabs(
        ["📝 1. Saisir le PV", "📄 2. Procès-Verbal (PV)", "📊 3. Synthèse"]
    )

    # =============================================================
    # FENÊTRE 1 : SAISIR LE PV
    # =============================================================
    with tab_saisie:
        with st.form("form_saisie_plaque"):
            st.subheader("📋 Identification & Localisation")
            col1, col2, col3 = st.columns(3)

            with col1:
                num_pv = st.text_input(
                    "N° du PV / Fiche", value="PV-PLQ-2026-001"
                )
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
            st.subheader("📊 Mesures de Deformabilité")

            cp1, cp2 = st.columns(2)

            with cp1:
                st.markdown("##### 📍 Point N°1")
                ev1_p1 = st.number_input(
                    "EV1 (MPa) - Point 1",
                    min_value=0.0,
                    value=106.13,
                    step=0.01,
                )
                ev2_p1 = st.number_input(
                    "EV2 (MPa) - Point 1", min_value=0.0, value=86.54, step=0.01
                )
                k_p1 = round(ev2_p1 / ev1_p1, 2) if ev1_p1 > 0 else 0.0
                st.metric(label="Coefficient K1 (EV2/EV1)", value=k_p1)

            with cp2:
                st.markdown("##### 📍 Point N°2")
                ev1_p2 = st.number_input(
                    "EV1 (MPa) - Point 2",
                    min_value=0.0,
                    value=106.13,
                    step=0.01,
                )
                ev2_p2 = st.number_input(
                    "EV2 (MPa) - Point 2", min_value=0.0, value=86.54, step=0.01
                )
                k_p2 = round(ev2_p2 / ev1_p2, 2) if ev1_p2 > 0 else 0.0
                st.metric(label="Coefficient K2 (EV2/EV1)", value=k_p2)

            st.markdown("---")
            txt_defaut = f"Point {pk_station} : EV2 = {ev2_p1} MPa, K = {k_p1}.\nPoint {pk_station} : EV2 = {ev2_p2} MPa, K = {k_p2}."
            commentaires = st.text_area(
                "Commentaire / Remarques", value=txt_defaut, height=90
            )

            btn_submit = st.form_submit_button(
                "💾 Enregistrer l'essai sur Supabase",
                use_container_width=True,
                type="primary",
            )

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

    # =============================================================
    # FENÊTRE 2 : PROCES-VERBAL (PV)
    # =============================================================
    with tab_pv:
        st.subheader("📄 Consultation du Procès-Verbal")
        df_essais = charger_donnees_plaque(supabase)

        if not df_essais.empty and "num_pv" in df_essais.columns:
            list_pvs = df_essais["num_pv"].unique().tolist()
            pv_selectionne = st.selectbox("Sélectionner un PV :", list_pvs)

            pv_data = df_essais[df_essais["num_pv"] == pv_selectionne].iloc[0]

            st.markdown("---")
            st.markdown(f"### 🧪 PV N° : **{pv_data.get('num_pv', '-')}**")

            col_a, col_b = st.columns(2)
            with col_a:
                st.write(
                    f"**Date de l'essai :** {pv_data.get('date_essai', '-')}"
                )
                st.write(
                    f"**Localisation (PK) :** {pv_data.get('pk_station', '-')}"
                )
                st.write(
                    f"**Couche / Matériau :** {pv_data.get('couche', '-')}"
                )
            with col_b:
                st.write(
                    f"**Opérateur :** {pv_data.get('operateur', '-')}"
                )
                st.write(
                    f"**Diamètre de Plaque :** {pv_data.get('diametre_plaque', '-')} mm"
                )

            st.markdown("---")
            st.markdown("#### 📊 Résultats des Mesures")

            c_res1, c_res2 = st.columns(2)
            with c_res1:
                st.info(
                    f"**Point 1 :**\n* EV1 = **{pv_data.get('ev1_p1', 0)} MPa**\n* EV2 = **{pv_data.get('ev2_p1', 0)} MPa**\n* K1 = **{pv_data.get('k_p1', 0)}**"
                )
            with c_res2:
                st.info(
                    f"**Point 2 :**\n* EV1 = **{pv_data.get('ev1_p2', 0)} MPa**\n* EV2 = **{pv_data.get('ev2_p2', 0)} MPa**\n* K2 = **{pv_data.get('k_p2', 0)}**"
                )

            st.markdown("**Observations / Commentaires :**")
            st.text_area(
                "",
                value=str(pv_data.get("commentaires", "")),
                disabled=True,
                height=80,
            )

        else:
            st.info(
                "Aucun enregistrement disponible sur Supabase pour générer un Procès-Verbal."
            )

    # =============================================================
    # FENÊTRE 3 : SYNTHÈSE
    # =============================================================
    with tab_synthese:
        st.subheader("📈 Synthèse globale des essais à la plaque")
        df_synthese = charger_donnees_plaque(supabase)

        if not df_synthese.empty:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Essais", len(df_synthese))
            if "ev1_p1" in df_synthese.columns:
                m2.metric(
                    "Moyenne EV1 (MPa)",
                    round(pd.to_numeric(df_synthese["ev1_p1"]).mean(), 2),
                )
            if "ev2_p1" in df_synthese.columns:
                m3.metric(
                    "Moyenne EV2 (MPa)",
                    round(pd.to_numeric(df_synthese["ev2_p1"]).mean(), 2),
                )
            if "k_p1" in df_synthese.columns:
                m4.metric(
                    "Moyenne Ratio K",
                    round(pd.to_numeric(df_synthese["k_p1"]).mean(), 2),
                )

            st.markdown("---")
            st.markdown("#### 📋 Tableau des Essais Enregistrés")
            st.dataframe(df_synthese, use_container_width=True)

            st.markdown("#### 📊 Évolution des valeurs EV2")
            if (
                "ev2_p1" in df_synthese.columns
                and "ev2_p2" in df_synthese.columns
            ):
                st.line_chart(df_synthese[["ev2_p1", "ev2_p2"]])
        else:
            st.info(
                "Aucune donnée disponible sur Supabase pour afficher la synthèse."
            )
