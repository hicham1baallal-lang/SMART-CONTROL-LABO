import streamlit as st
from supabase import create_client, Client

# Configuration globale de la page Streamlit
st.set_page_config(
    page_title="LPEE - Essais à la Plaque",
    page_icon="🧪",
    layout="wide"
)

# Initialisation Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import des vues
# --- MENU LATÉRAL (SIDEBAR) ---
st.sidebar.image("https://via.placeholder.com/200x60?text=LPEE+CTR-CSB", use_column_width=True) # Remplacer par votre logo LPEE
st.sidebar.title("📌 Menu Principal")

# Choix de la fenêtre
menu_selection = st.sidebar.radio(
    "Navigation :",
    ["🧪 Saisie - Essai Plaque", "📊 Synthèse - Essai Plaque"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.info("Projet : **LGV CASA SUD**\nClient : **TGCC**\nNorme : **NF P 94-117-1**")

# --- ROUTAGE DES PAGES ---
if menu_selection == "🧪 Saisie - Essai Plaque":
    essai_plaque.show(supabase)

elif menu_selection == "📊 Synthèse - Essai Plaque":
    synthese_plaque.show(supabase)
