import streamlit as st
from supabase import create_client, Client

# 1. Configuration globale de la page Streamlit
st.set_page_config(
    page_title="LPEE - Essais à la Plaque",
    page_icon="🧪",
    layout="wide"
)

# 2. Importation des vues (Assurez-vous que les fichiers se nomment essai_plaque.py et synthese_plaque.py dans le dossier views/)
try:
    from views import essai_plaque, synthese_plaque
except ImportError as e:
    st.error(f"❌ Erreur d'importation des vues : {e}")
    st.info("Vérifiez le nom des fichiers dans le dossier 'views/' et les imports internes de ces fichiers.")
    st.stop()

# 3. Initialisation Supabase sécurisée
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except KeyError as e:
    st.error(f"❌ Clé manquante dans Streamlit Secrets : {e}")
    st.info("Ajoutez SUPABASE_URL et SUPABASE_KEY dans le menu 'Manage app' > 'Settings' > 'Secrets' de Streamlit Cloud.")
    supabase = None
except Exception as e:
    st.error(f"❌ Erreur de connexion Supabase : {e}")
    supabase = None

# 4. MENU LATÉRAL (SIDEBAR)
st.sidebar.image("https://via.placeholder.com/200x60?text=LPEE+CTR-CSB", use_container_width=True) # Remplace use_column_width
st.sidebar.title("📌 Menu Principal")

# Choix de la fenêtre
menu_selection = st.sidebar.radio(
    "Navigation :",
    ["🧪 Saisie - Essai Plaque", "📊 Synthèse - Essai Plaque"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.info("Projet : **LGV CASA SUD**\nClient : **TGCC**\nNorme : **NF P 94-117-1**")

# 5. ROUTAGE DES PAGES
if menu_selection == "🧪 Saisie - Essai Plaque":
    essai_plaque.show(supabase)

elif menu_selection == "📊 Synthèse - Essai Plaque":
    synthese_plaque.show(supabase)
