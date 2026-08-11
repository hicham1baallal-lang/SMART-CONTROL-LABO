import streamlit as st
from supabase import create_client, Client

# 1. Configuration de la page Streamlit
st.set_page_config(
    page_title="LPEE - CTR-CSB",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Gestion de l'état d'authentification et des Rôles
if "role" not in st.session_state:
    st.session_state.role = None  # Peut être None, "user", ou "admin"

# --- ÉCRAN DE CONNEXION ---
if st.session_state.role is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Connexion LPEE")
        
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter"):
            if password == "ctr2026": # Mot de passe Utilisateur
                st.session_state.role = "user"
                st.rerun()
            elif password == "admin2026": # <-- CHANGEZ CE MOT DE PASSE ADMIN
                st.session_state.role = "admin"
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect.")
    st.stop()

# --- DÉCONNEXION (dans la sidebar) ---
with st.sidebar:
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.role = None
        st.rerun()

# ==========================================
# 3. CODE PRINCIPAL (Affiché uniquement si connecté)
# ==========================================

# Importation des 4 vues
try:
    from views import suivi_Betonnage, essai_Plaque, synthese_Beton, synthese_plaque
except ImportError as e:
    st.error(f"❌ Erreur lors de l'importation des vues : {e}")
    st.stop()

# Connexion Supabase
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
        index=0
    )
    
    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

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
