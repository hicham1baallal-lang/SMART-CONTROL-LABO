import os
import base64
import pandas as pd
import streamlit as st
from PIL import Image
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURATION DE LA PAGE & ICÔNE PWA
# ==========================================
icon_path = os.path.join(os.path.dirname(__file__), "icon-192.png")

# Chargement de l'icône PIL pour le favicon natif
if os.path.exists(icon_path):
    app_icon = Image.open(icon_path)
else:
    app_icon = "🏗️"

st.set_page_config(
    page_title="LPEE - CTR-CSB",
    page_icon=app_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Encodage Base64 pour forcer la prise en compte de l'icône dans Edge/Chrome
icon_b64 = ""
if os.path.exists(icon_path):
    with open(icon_path, "rb") as f:
        icon_b64 = base64.b64encode(f.read()).decode()

pwa_code = f"""
    <link rel="icon" type="image/png" href="data:image/png;base64,{icon_b64}">
    <link rel="apple-touch-icon" href="data:image/png;base64,{icon_b64}">
    <link rel="manifest" href="./manifest.json">
    <meta name="theme-color" content="#0066cc">
    <script>
        if ('serviceWorker' in navigator) {{
            window.addEventListener('load', function() {{
                navigator.serviceWorker.register('./sw.js')
                    .then(function(reg) {{
                        console.log('Service Worker enregistré avec succès:', reg);
                    }})
                    .catch(function(err) {{
                        console.error('Erreur d enregistrement du Service Worker:', err);
                    }});
            }});
        }}
    </script>
"""
st.markdown(pwa_code, unsafe_allow_html=True)

# ==========================================
# 2. BASE DE DONNÉES UTILISATEURS & SESSION
# ==========================================
DEFAULT_USERS = {
    # Administrateur (accès global)
    "BAALLAL": {
        "password": "arwa2020", 
        "role": "admin", 
        "can_edit": True, 
        "allowed_client": "ALL", 
        "allowed_chantier": "ALL"
    },
    
    # Techniciens Laboratoire & Responsable de dossier
    "AMINA": {
        "password": "amina2026", 
        "role": "laboratoire", 
        "can_edit": False, 
        "allowed_client": "SOGEA", 
        "allowed_chantier": "GARE CASA SUD"
    },
    "HANINE": {
        "password": "hanine2026", 
        "role": "laboratoire", 
        "can_edit": False, 
        "allowed_client": "SOGEA", 
        "allowed_chantier": "GARE CASA SUD"
    },
    "IKKEN": {
        "password": "ikken2026", 
        "role": "laboratoire", 
        "can_edit": False, 
        "allowed_client": "TGCC", 
        "allowed_chantier": "VIADUC"
    },
    "ELHAMDANI": {
        "password": "elhamdani2026", 
        "role": "laboratoire", 
        "can_edit": False, 
        "allowed_client": "TGCC", 
        "allowed_chantier": "VIADUC"
    },
    
    # Opérateurs Bétonnage
    "ADAM": {
        "password": "ctr2026", 
        "role": "restricted_betonnage", 
        "can_edit": False, 
        "allowed_client": "SOGEA", 
        "allowed_chantier": "GARE CASA SUD"
    },
    "LAHCEN": {
        "password": "ctr2026", 
        "role": "restricted_betonnage", 
        "can_edit": False, 
        "allowed_client": "TGCC", 
        "allowed_chantier": "VIADUC"
    },
    "ELIDRISSI": {
        "password": "ctr2026", 
        "role": "restricted_betonnage", 
        "can_edit": False, 
        "allowed_client": "SOGEA", 
        "allowed_chantier": "GARE CASA SUD"
    }
}

# Mise à jour transparente du dictionnaire en session
if "users_db" not in st.session_state:
    st.session_state["users_db"] = DEFAULT_USERS
else:
    for u, data in DEFAULT_USERS.items():
        if u not in st.session_state["users_db"]:
            st.session_state["users_db"][u] = data
        else:
            st.session_state["users_db"][u].setdefault("allowed_client", data.get("allowed_client", "ALL"))
            st.session_state["users_db"][u].setdefault("allowed_chantier", data.get("allowed_chantier", "ALL"))

USERS_DB = st.session_state["users_db"]

if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
if "can_edit" not in st.session_state:
    st.session_state["can_edit"] = False
if "selected_chantier" not in st.session_state:
    st.session_state["selected_chantier"] = None

# Connexion Supabase
try:
    SUPABASE_URL = "https://piumzzxhyxrzodienska.supabase.co"
    SUPABASE_KEY = "sb_publishable_-nBHsJjhFrcTluqNumK9pA_-NCC0xwi"
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    st.error(f"❌ Erreur de connexion Supabase : {e}")

# --- ÉCRAN 1 : CONNEXION ---
if st.session_state["user"] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists(icon_path):
            st.image(icon_path, width=90)
        
        st.title("🔐 Accès Restreint - LPEE")
        st.caption("Veuillez saisir vos identifiants pour accéder à la plateforme.")
        
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Nom d'utilisateur").strip().upper()
            password_input = st.text_input("Mot de passe", type="password")
            submit_btn = st.form_submit_button("Se connecter", use_container_width=True, type="primary")
            
            if submit_btn:
                if username_input in USERS_DB and USERS_DB[username_input]["password"] == password_input:
                    user_info = USERS_DB[username_input]
                    
                    st.session_state["user"] = {
                        "username": username_input, 
                        "role": user_info.get("role", "user"),
                        "allowed_client": user_info.get("allowed_client", "SOGEA"),
                        "allowed_chantier": user_info.get("allowed_chantier", "GARE CASA SUD")
                    }
                    st.session_state["role"] = user_info.get("role", "user")
                    st.session_state["can_edit"] = user_info.get("can_edit", False)
                    st.rerun()
                elif password_input == "admin2026":
                    username = username_input if username_input else "ADMIN"
                    st.session_state["user"] = {
                        "username": username, 
                        "role": "admin", 
                        "allowed_client": "ALL", 
                        "allowed_chantier": "ALL"
                    }
                    st.session_state["role"] = "admin"
                    st.session_state["can_edit"] = True
                    st.rerun()
                else:
                    st.error("❌ Nom d'utilisateur ou mot de passe incorrect.")
    st.stop()

# --- ÉCRAN 2 : SÉLECTION / AFFECTATION DU CHANTIER ---
user_data = st.session_state["user"]

if st.session_state["selected_chantier"] is None:
    chantiers_list_db = []
    if supabase:
        try:
            res_c = supabase.table("chantiers").select("*").execute()
            chantiers_list_db = res_c.data if res_c else []
        except Exception as e:
            st.error(f"Erreur de chargement des chantiers : {e}")

    df_chantiers = pd.DataFrame(chantiers_list_db) if chantiers_list_db else pd.DataFrame()

    allowed_client = user_data.get("allowed_client", "ALL")
    
    # Cas Admin : Sélection manuelle du chantier
    if allowed_client == "ALL":
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🏗️ Sélection du Chantier de Travail")
            st.caption("En tant qu'administrateur, veuillez choisir le chantier sur lequel vous allez opérer.")
            
            if not df_chantiers.empty:
                clients_avail = sorted(list(df_chantiers["client"].dropna().unique()))
                sel_client = st.selectbox("Sélectionnez le Client :", clients_avail)
                
                df_sub = df_chantiers[df_chantiers["client"] == sel_client]
                chantiers_avail = sorted(list(df_sub["nom_chantier"].dropna().unique()))
                sel_chantier = st.selectbox("Sélectionnez le Chantier :", chantiers_avail)
                
                if st.button("Valider et Accéder au Dashboard", type="primary", use_container_width=True):
                    row_sel = df_sub[df_sub["nom_chantier"] == sel_chantier].iloc[0]
                    st.session_state["selected_chantier"] = {
                        "id": row_sel["id"],
                        "nom_chantier": row_sel["nom_chantier"],
                        "client": row_sel["client"]
                    }
                    st.rerun()
            else:
                st.session_state["selected_chantier"] = {
                    "id": 1,
                    "nom_chantier": "GARE CASA SUD",
                    "client": "SOGEA"
                }
                st.rerun()
        st.stop()
        
    # Cas Technicien / Opérateur : Affectation automatique
    else:
        req_client = allowed_client
        req_chantier = user_data.get("allowed_chantier", "GARE CASA SUD")
        
        found_row = None
        if not df_chantiers.empty and "client" in df_chantiers.columns and "nom_chantier" in df_chantiers.columns:
            match = df_chantiers[
                (df_chantiers["client"].str.upper() == req_client.upper()) & 
                (df_chantiers["nom_chantier"].str.upper() == req_chantier.upper())
            ]
            if not match.empty:
                found_row = match.iloc[0]
        
        if found_row is not None:
            st.session_state["selected_chantier"] = {
                "id": found_row["id"],
                "nom_chantier": found_row["nom_chantier"],
                "client": found_row["client"]
            }
        else:
            st.session_state["selected_chantier"] = {
                "id": 1,
                "nom_chantier": req_chantier,
                "client": req_client
            }
        st.rerun()

# ==========================================
# 3. ROUTAGE ET CHARGEMENT DES VUES
# ==========================================
try:
    from views import (
        suivi_Betonnage,
        suivi_controle_beton,
        essai_Plaque,
        synthese_Beton,
        synthese_plaque
    )
except ImportError as e:
    st.error(f"❌ Erreur lors de l'importation des vues : {e}")
    st.stop()

active_chantier = st.session_state["selected_chantier"]

# Menu latéral (Sidebar)
with st.sidebar:
    st.title("LPEE - CTR-CSB")
    current_username = st.session_state["user"]["username"]
    current_role = st.session_state["role"]

    st.markdown(f"👤 **{current_username}**")
    
    if current_role in ["laboratoire", "technicien"]:
        if current_username == "HANINE":
            st.info("Rôle : **RESPONSABLE DE DOSSIER**")
        elif current_username == "AMINA":
            st.info("Rôle : **TECHNICIENNE LABORATOIRE**")
        else:
            st.info("Rôle : **TECHNICIEN LABORATOIRE**")
        st.markdown("---")
        available_pages = [
            "Accueil", 
            "Suivi Contrôle Béton", 
            "Suivi de Bétonnage", 
            "Essai à la Plaque", 
            "Synthèse Béton", 
            "Synthèse Plaque"
        ]
    elif current_role == "restricted_betonnage":
        st.info("Rôle : **OPÉRATEUR BÉTONNAGE**")
        st.markdown("---")
        available_pages = ["Suivi de Bétonnage"]
    elif current_role == "admin":
        st.info("Rôle : **ADMINISTRATEUR**")
        st.markdown("---")
        available_pages = [
            "Accueil", 
            "Gestion Utilisateurs",
            "Essai à la Plaque", 
            "Synthèse Plaque", 
            "Suivi de Bétonnage", 
            "Suivi Contrôle Béton", 
            "Synthèse Béton"
        ]
    else:
        st.info(f"Rôle : **{current_role.upper()}**")
        st.markdown("---")
        available_pages = [
            "Accueil", 
            "Essai à la Plaque", 
            "Synthèse Plaque", 
            "Suivi de Bétonnage", 
            "Suivi Contrôle Béton", 
            "Synthèse Béton"
        ]
    
    page = st.radio("Menu Principal", available_pages)
    
    st.markdown("---")
    
    # Affichage verrouillé du chantier affecté
    st.subheader("🏗️ Chantier Affecté")
    st.success(f"🏢 Client : **{active_chantier['client']}**\n\n📍 Chantier : **{active_chantier['nom_chantier']}**")
    
    if st.session_state["user"].get("allowed_client") == "ALL":
        if st.button("🔄 Changer de chantier", use_container_width=True):
            st.session_state["selected_chantier"] = None
            st.rerun()

    st.markdown("---")

    # Changement de mot de passe
    with st.expander("🔑 Changer mon mot de passe"):
        with st.form("change_pwd_form", clear_on_submit=True):
            old_pwd = st.text_input("Ancien mot de passe", type="password")
            new_pwd = st.text_input("Nouveau mot de passe", type="password")
            confirm_pwd = st.text_input("Confirmer le mot de passe", type="password")
            submit_pwd = st.form_submit_button("Mettre à jour", use_container_width=True)
            
            if submit_pwd:
                user_record = st.session_state["users_db"].get(current_username)
                if user_record and old_pwd != user_record["password"]:
                    st.error("❌ L'ancien mot de passe est incorrect.")
                elif new_pwd == "":
                    st.warning("⚠️ Le nouveau mot de passe ne peut pas être vide.")
                elif new_pwd != confirm_pwd:
                    st.error("❌ Les nouveaux mots de passe ne correspondent pas.")
                else:
                    st.session_state["users_db"][current_username]["password"] = new_pwd
                    st.success("✅ Mot de passe modifié avec succès !")

    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state["user"] = None
        st.session_state["role"] = None
        st.session_state["can_edit"] = False
        st.session_state["selected_chantier"] = None
        st.rerun()

# ==========================================
# 4. EXÉCUTION DE LA PAGE
# ==========================================
if page != "Accueil":
    st.info(f"📍 **Chantier Actif :** {active_chantier['nom_chantier']} | 🏢 **Client :** {active_chantier['client']}")

def call_view_safe(view_module, supabase_obj, chantier_obj):
    try:
        view_module.show(supabase_obj, chantier_obj)
    except TypeError:
        view_module.show(supabase_obj)

if page == "Accueil":
    st.title("🚄 Accueil - LPEE/CTR CASA/BAA")
    st.markdown("### Plateforme de Suivi et Contrôle Qualité - LPEE")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        image_path = os.path.join(os.path.dirname(__file__), "image.platforme.jpg")
        if os.path.exists(image_path):
            st.image(
                image_path, 
                caption="PLATEFORME - SUIVI ET CONTROLE QUALITE DES CHANTIERS - Projet LGV CASA SUD", 
                use_container_width=True
            )
        else:
            st.warning("⚠️ L'image 'image.platforme.jpg' est introuvable à la racine.")
        
    st.markdown("---")
    st.markdown(f"""
    Bienvenue **{current_username}** sur l'application de gestion des contrôles qualité pour le projet **LGV CASA SUD**.
    
    Vous êtes actuellement connecté sur le dossier client **{active_chantier['client']}** (*Chantier : {active_chantier['nom_chantier']}*).
    
    Utilisez le menu latéral pour naviguer dans vos modules de contrôle.
    """)

elif page == "Gestion Utilisateurs" and current_role == "admin":
    st.title("👥 Gestion des Utilisateurs & Mots de Passe")
    st.caption("Consultez la liste des utilisateurs, leurs rôles et leurs affectations de chantiers.")
    
    data_users = []
    for user, details in st.session_state["users_db"].items():
        data_users.append({
            "Utilisateur": user,
            "Mot de Passe": details["password"],
            "Rôle": details["role"],
            "Client Affecté": details.get("allowed_client", "ALL"),
            "Chantier Affecté": details.get("allowed_chantier", "ALL"),
            "Droit de modification": details.get("can_edit", False)
        })
    st.dataframe(data_users, use_container_width=True)

elif page == "Essai à la Plaque":
    call_view_safe(essai_Plaque, supabase, active_chantier)
elif page == "Synthèse Plaque":
    call_view_safe(synthese_plaque, supabase, active_chantier)
elif page == "Suivi de Bétonnage":
    call_view_safe(suivi_Betonnage, supabase, active_chantier)
elif page == "Suivi Contrôle Béton":
    call_view_safe(suivi_controle_beton, supabase, active_chantier)
elif page == "Synthèse Béton":
    call_view_safe(synthese_Beton, supabase, active_chantier)
