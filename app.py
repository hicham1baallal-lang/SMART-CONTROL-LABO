import streamlit as st
from supabase import create_client

# 🔹 Importation des vues (Vérifiez bien la casse exacte de vos fichiers dans views/)
from views import suivi_Betonnage, essai_Plaque, synthese_Beton, synthese_plaque

# Configuration de la page
st.set_page_config(
    page_title="LPEE - CTR-CSB",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS personnalisé
st.markdown("""
    <style>
    .main { padding: 1rem 2rem; }
    .stButton>button { background-color: #e63946; color: white; border-radius: 5px; border: none; }
    .stButton>button:hover { background-color: #d62828; color: white; }
    </style>
""", unsafe_allow_html=True)

# Connexion Supabase
SUPABASE_URL = "https://pfyfmfujccibiwfiwknu.supabase.co"
SUPABASE_KEY = "sb_publishable_6h8ZUeV8ii5TjKUV9B1Ewg_eDawQRkW"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    supabase = None
    st.error(f"Erreur de connexion Supabase : {e}")

# Barre latérale (Sidebar)
with st.sidebar:
    st.title("LPEE - CTR-CSB")
    st.caption("Projet : LGV CASA SETTAT | Client : TGCC")
    st.markdown("---")
    st.subheader("Menu Principal")
    
    page = st.radio(
        "",
        ["Accueil", "Essai à la Plaque", "Synthèse Plaque", "Suivi de Bétonnage", "Synthèse Béton"],
        index=0
    )
    
    st.markdown("---")
    if st.button("🚪 Déconnexion"):
        st.info("Déconnecté")

# Routage des vues
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur la plateforme de suivi de chantier LPEE.")

elif page == "Essai à la Plaque":
    essai_Plaque.show(supabase)

elif page == "Synthèse Plaque":
    synthese_Plaque.show(supabase)

elif page == "Suivi de Bétonnage":
    suivi_Betonnage.show(supabase)

elif page == "Synthèse Béton":
    synthese_Beton.show(supabase)
