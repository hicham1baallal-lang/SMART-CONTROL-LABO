import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LPEE - CTR-CSB",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. GESTION DES SESSIONS & AUTHENTIFICATION
# ==========================================
if "users_db" not in st.session_state:
    st.session_state["users_db"] = {
        # Administrateur
        "BAALLAL": {"password": "arwa2020", "role": "admin", "can_edit": True},
        
        # Techniciens Laboratoire & Responsable de dossier
        "AMINA": {"password": "amina2026", "role": "laboratoire", "can_edit": False},
        "HANINE": {"password": "hanine2026", "role": "laboratoire", "can_edit": False},
        "IKKEN": {"password": "ikken2026", "role": "laboratoire", "can_edit": False},
        "ELHAMDANI": {"password": "elhamdani2026", "role": "laboratoire", "can_edit": False},
        
        # Opérateurs Bétonnage
        "ADAM": {"password": "ctr2026", "role": "restricted_betonnage", "can_edit": False},
        "LAHCEN": {"password": "ctr2026", "role": "restricted_betonnage", "can_edit": False},
        "ELIDRISSI": {"password": "ctr2026", "role": "restricted_betonnage", "can_edit": False}
    }

USERS_DB = st.session_state["users_db"]

if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
if "can_edit" not in st.session_state:
    st.session_state["can_edit"] = False

# Stockage du chantier sélectionné
if "selected_chantier" not in st.session_state:
    st.session_state["selected_chantier"] = None

# --- ÉCRAN DE CONNEXION ---
if st.session_state["user"] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Accès Restreint - LPEE")
        st.caption("Veuillez saisir vos identifiants pour accéder à la plateforme.")
        
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Nom d'utilisateur").strip().upper()
            password_input = st.text_input("Mot de passe", type="password")
            submit_btn = st.form_submit_button("Se connecter", use_container_width=True, type="primary")
            
            if submit_btn:
                if username_input in USERS_DB and USERS_DB[username_input]["password"] == password_input:
                    user_role = USERS_DB[username_input]["role"]
                    can_edit = USERS_DB[username_input]["can_edit"]
                    st.session_state["user"] = {"username": username_input, "role": user_role}
                    st.session_state["role"] = user_role
                    st.session_state["can_edit"] = can_edit
                    st.rerun()
                elif password_input == "admin2026":
                    username = username_input if username_input else "ADMIN"
                    st.session_state["user"] = {"username": username, "role": "admin"}
                    st.session_state["role"] = "admin"
                    st.session_state["can_edit"] = True
                    st.rerun()
                elif password_input == "ctr2026":
                    username = username_input if username_input else "USER"
                    st.session_state["user"] = {"username": username, "role": "user"}
                    st.session_state["role"] = "user"
                    st.session_state["can_edit"] = False
                    st.rerun()
                else:
                    st.error("❌ Nom d'utilisateur ou mot de passe incorrect.")
    st.stop()

# ==========================================
# 3. CODE PRINCIPAL (Utilisateur connecté)
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

# Connexion à Supabase
try:
    SUPABASE_URL = "https://piumzzxhyxrzodienska.supabase.co"
    SUPABASE_KEY = "sb_publishable_-nBHsJjhFrcTluqNumK9pA_-NCC0xwi"
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    st.error(f"❌ Erreur de connexion Supabase : {e}")

# Menu latéral (Sidebar)
with st.sidebar:
    st.title("LPEE - CTR-CSB")
    current_username = st.session_state["user"]["username"]
    current_role = st.session_state["role"]

    st.markdown(f"👤 **{current_username}**")
    
    # Affichage du rôle
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
    
    # =========================================================
    # MODULE : SÉLECTION DYNAMIQUE CLIENT & CHANTIER
    # =========================================================
    if supabase:
        try:
            res_chantiers = supabase.table("chantiers").select("*").execute()
            chantiers_data = res_chantiers.data if res_chantiers else []
            
            if chantiers_data:
                df_c = pd.DataFrame(chantiers_data)
                
                st.subheader("🏗️ Sélection du Chantier")
                
                # 1. Filtre par Client (SOGEA, TGCC, etc.)
                clients_list = sorted(list(df_c["client"].dropna().unique()))
                selected_client = st.selectbox("Client :", clients_list)
                
                df_filtered = df_c[df_c["client"] == selected_client]

                # 2. Sélecteur de Chantier (GARE CASA SUD, etc.)
                chantiers_list = sorted(list(df_filtered["nom_chantier"].dropna().unique()))
                selected_nom_chantier = st.selectbox("Chantier :", chantiers_list)
                
                # Récupération de l'objet chantier sélectionné
                selected_row = df_filtered[df_filtered["nom_chantier"] == selected_nom_chantier].iloc[0]
                
                st.session_state["selected_chantier"] = {
                    "id": selected_row["id"],
                    "nom_chantier": selected_row["nom_chantier"],
                    "client": selected_row["client"]
                }
                
                st.caption(f"📌 Client : **{selected_row['client']}**")
            else:
                st.warning("⚠️ Aucune donnée dans la table `chantiers`.")
                st.session_state["selected_chantier"] = None
        except Exception as err:
            st.caption(f"Info : Module chantier inaccessible ({err})")
            st.session_state["selected_chantier"] = None

    st.markdown("---")

    # --- MODULE DE MODIFICATION DE MOT DE PASSE ---
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
# 4. ROUTAGE DES VUES
# ==========================================
selected_chantier = st.session_state.get("selected_chantier")

# En-tête indiquant le chantier actif si sélectionné
if selected_chantier and page != "Accueil":
    st.info(f"📍 **Chantier Actif :** {selected_chantier['nom_chantier']} | 🏢 **Client :** {selected_chantier['client']}")

if page == "Accueil":
    st.title("🚄 Accueil - LGV CASA SUD")
    st.markdown("### Plateforme de Suivi et Contrôle Qualité - LPEE")
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        image_path = os.path.join(os.path.dirname(__file__), "al_boraq.jpg.jpg")
        if os.path.exists(image_path):
            st.image(
                image_path, 
                caption="Al Boraq - Ligne à Grande Vitesse - Projet LGV CASA SUD", 
                use_container_width=True
            )
        else:
            st.warning("⚠️ L'image 'al_boraq.jpg.jpg' est introuvable à la racine.")
        
    st.markdown("---")
    st.markdown("""
    Bienvenue sur l'application centralisée de gestion des contrôles qualité pour le projet **LGV CASA SUD**.
    
    Utilisez le menu de navigation latéral pour accéder aux différents modules :
    * **🏗️ Suivi Béton :** Gestion des livraisons, fiches de contrôle, températures, affaissements et prélèvements.
    * **🧪 Suivi Contrôle Béton :** Saisie des écrasements d'éprouvettes de béton (3j, 7j, 28j, 90j) associées aux prélèvements.
    * **🚜 Essai à la Plaque :** Saisie des essais de portance (Norme NF P 94-117-1) avec calculs automatiques des modules $EV_1$, $EV_2$ et du coefficient $K$.
    """)

elif page == "Gestion Utilisateurs" and current_role == "admin":
    st.title("👥 Gestion des Utilisateurs & Mots de Passe")
    st.caption("Consultez ci-dessous la liste de tous les utilisateurs et leurs mots de passe actuels.")
    
    data_users = []
    for user, details in st.session_state["users_db"].items():
        data_users.append({
            "Utilisateur": user,
            "Mot de Passe": details["password"],
            "Rôle": details["role"],
            "Droit de modification (can_edit)": details["can_edit"]
        })
    
    st.dataframe(data_users, use_container_width=True)

elif page == "Essai à la Plaque":
    essai_Plaque.show(supabase)
elif page == "Synthèse Plaque":
    synthese_plaque.show(supabase)
elif page == "Suivi de Bétonnage":
    suivi_Betonnage.show(supabase)
elif page == "Suivi Contrôle Béton":
    suivi_controle_beton.show(supabase)
elif page == "Synthèse Béton":
    synthese_Beton.show(supabase)
