import streamlit as st

st.set_page_config(page_title="SMART CONTROL LABO", page_icon="🛠️", layout="wide")

st.sidebar.title("🛠️ SMART CONTROL LABO")
page = st.sidebar.radio("Navigation", ["Suivi Bétonnage", "Essai à la Plaque"])

SUPABASE_URL = "https://pfyfmfujccibiwfiwknu.supabase.co"
SUPABASE_KEY = "sb_publishable_6h8ZUeV8ii5TjKUV9B1Ewg_"

@st.cache_resource
def init_supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.sidebar.error(f"Erreur Supabase: {e}")
    supabase = None

from views import suivi_Betonnage, essai_Plaque

if page == "Suivi Bétonnage":
    suivi_Betonnage.show(supabase)
elif page == "Essai à la Plaque":
    essai_Plaque.show(supabase)
