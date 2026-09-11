import os
import streamlit as st
from supabase import create_client, Client

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Smart Control Béton — LPEE",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# 1. INITIALISATION DE LA CONNEXION SUPABASE (Cached)
# -------------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    """Initialise le client Supabase avec mise en cache pour éviter la surcharge de connexions."""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Erreur de connexion à Supabase : {e}")
        st.stop()

supabase = init_supabase()

# -------------------------------------------------------------
# 2. GESTION DU PROFIL UTILISATEUR & SESSION
# -------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = {"email": "h.baallal@lpee.ma", "role": "Chef de Laboratoire"}

user = st.session_state["user"]

# -------------------------------------------------------------
# 3. BARRE LATÉRALE & NAVIGATION
# -------------------------------------------------------------
with st.sidebar:
    if os.path.exists("logo.png.jpg"):
        st.image("logo.png.jpg", use_container_width=True)
    elif os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)

    st.title("Smart Control Béton")
    st.caption(f"👤 Connecté : **{user.get('email', 'Utilisateur')}**")
    st.markdown("---")

    menu_option = st.radio(
        "📍 Navigation",
        [
            "🚜 Essai à la Plaque",
            "📊 Suivi Bétonnage",
            "🧪 Contrôle Béton",
            "💧 Teneur en Eau",
            "🏗️ Compacité",
            "📈 Synthèse Plaque",
            "📜 Historique & Audit"
        ],
        index=0
    )

    st.markdown("---")
    st.caption("LPEE - CTR Casablanca | LGV CASA SUD")

# -------------------------------------------------------------
# 4. ROUTAGE ET CHARGEMENT DES MODULES (VIEWS)
# -------------------------------------------------------------
try:
    if menu_option == "🚜 Essai à la Plaque":
        from views import essai_Plaque
        essai_Plaque.show(supabase)

    elif menu_option == "📊 Suivi Bétonnage":
        from views import suivi_Betonnage
        suivi_Betonnage.show(supabase)

    elif menu_option == "🧪 Contrôle Béton":
        from views import suivi_controle_beton
        suivi_controle_beton.show(supabase)

    elif menu_option == "💧 Teneur en Eau":
        from views import essai_teneur_eau
        essai_teneur_eau.show(supabase)

    elif menu_option == "🏗️ Compacité":
        from views import essai_compacite
        essai_compacite.show(supabase)

    elif menu_option == "📈 Synthèse Plaque":
        from views import synthese_plaque
        synthese_plaque.show(supabase)

    elif menu_option == "📜 Historique & Audit":
        from views import historique_pvs
        historique_pvs.show(supabase)

except Exception as e:
    st.error(f"⚠️ Une erreur s'est produite lors du chargement du module **{menu_option}** : {e}")
