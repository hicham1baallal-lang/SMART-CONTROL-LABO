import streamlit as st
import datetime

def show(supabase):
    st.title("🧪 Essai à la Plaque (Portance des Sols)")
    
    date_essai = st.date_input("Date de l'essai :", datetime.date.today())
    
    st.subheader(f"📝 Saisie d'un essai à la plaque ({date_essai.strftime('%d/%m/%Y')})")
    
    with st.form("form_plaque", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tech = st.text_input("Technicien", value="Agent LPEE")
            emplacement = st.text_input("Emplacement / PK", value="PK 12+500")
            diametre = st.selectbox("Diamètre de la plaque (mm)", [300, 600, 750], index=0)
            pression = st.number_input("Pression appliquée (MPa)", value=0.25, step=0.01)

        with col2:
            ev1 = st.number_input("Module EV1 (MPa)", value=45.0, step=1.0)
            ev2 = st.number_input("Module EV2 (MPa)", value=90.0, step=1.0)
            
            # Calcul automatique du rapport K = EV2 / EV1
            k_ratio = round(ev2 / ev1, 2) if ev1 > 0 else 0.0
            st.metric("Rapport k (EV2 / EV1)", value=k_ratio)

        obs = st.text_area("Observations", value="Compactage conforme aux exigences.")
        
        btn_submit = st.form_submit_button("💾 Enregistrer l'essai")
        
        if btn_submit:
            data = {
                "date_essai": str(date_essai),
                "technicien": tech,
                "emplacement": emplacement,
                "diametre_plaque": diametre,
                "pression_mpa": pression,
                "ev1": ev1,
                "ev2": ev2,
                "k_ratio": k_ratio,
                "observations": obs
            }
            if supabase:
                try:
                    supabase.table("essai_plaque").insert(data).execute()
                    st.success("Essai à la plaque enregistré avec succès !")
                except Exception as e:
                    st.error(f"Erreur d'enregistrement : {e}")
            else:
                st.warning("Mode hors-ligne : Données non envoyées à Supabase.")

    # Section Historique Plaque
    st.markdown("---")
    st.subheader("📋 Historique des essais à la plaque")
    if supabase:
        try:
            res = supabase.table("essai_plaque").select("*").order("id", desc=True).execute()
            if res.data:
                st.dataframe(res.data, use_container_width=True)
            else:
                st.info("Aucun enregistrement trouvé dans la table essai_plaque.")
        except Exception as e:
            st.error(f"Impossible de charger l'historique : {e}")
