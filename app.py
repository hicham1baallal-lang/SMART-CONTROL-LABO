import streamlit as st
from supabase import create_client, Client

# 1. Configuration de la page Streamlit
st.set_page_config(
    page_title="LPEE - CTR-CSB",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Importation des 4 vues avec la CASSE EXACTE de votre GitHub
try:
    from views import suivi_Betonnage, essai_Plaque, synthese_Beton, synthese_plaque
except ImportError as e:
    st.error(f"❌ Erreur lors de l'importation des vues : {e}")
    st.stop()

# 3. Connexion Supabase
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    st.error(f"❌ Erreur de connexion Supabase : {e}")

# Style CSS
st.markdown("""
    <style>
    .main { padding: 1rem 2rem; }
    .stButton>button { background-color: #e63946; color: white; border-radius: 5px; border: none; }
    .stButton>button:hover { background-color: #d62828; color: white; }
    </style>
""", unsafe_allow_html=True)

# 4. Barre latérale (Sidebar)
with st.sidebar:
    st.title("LPEE - CTR-CSB")
    st.caption("Projet : LGV CASA SETTAT | Client : TGCC")
    st.markdown("---")
    st.subheader("Menu Principal")
    
    page = st.radio(
        "",
        ["Accueil", "Essai à la Plaque", "Synthèse Plaque", "Suivi de Bétonnage", "Synthèse Béton"],
        index=2
    )
    
    st.markdown("---")
    if st.button("🚪 Déconnexion"):
        st.info("Déconnecté")

# 5. Routage des vues
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur la plateforme de suivi de chantier LPEE.")

elif page == "Essai à la Plaque":
    essai_Plaque.show(supabase)

elif page == "Synthèse Plaque":
    synthese_plaque.show(supabase)

elif page == "Suivi de Bétonnage":
    suivi_Betonnage.show(supabase)

elif page == "Synthèse Béton":
    synthese_Beton.show(supabase)
