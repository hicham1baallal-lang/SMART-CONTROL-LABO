import datetime
import json
import os
import time
from fpdf import FPDF
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx
from supabase import Client, create_client

# Importation sécurisée du gestionnaire Hors-Ligne SQLite
try:
    from offline_manager import (
        get_pending_count,
        init_offline_db,
        insert_safe,
        sync_data_to_supabase,
    )
    init_offline_db()
    OFFLINE_SUPPORT = True
except ImportError:
    OFFLINE_SUPPORT = False

# ==========================================
# 1. CONFIGURATION DE LA PAGE & INJECTION PWA
# ==========================================
st.set_page_config(
    page_title="Smart Control Béton — LPEE",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# 1bis. CAPTURE DES PARAMÈTRES QR CODE
# ==========================================
_query_params = st.query_params
_qr_rec = _query_params.get("rec") or _query_params.get("num_reception")
_qr_bid = _query_params.get("beton_id") or _query_params.get("id")
_qr_ep = _query_params.get("ep")

if _qr_rec or _qr_bid:
    if _qr_rec:
        st.session_state["pending_qr_rec"] = str(_qr_rec).strip()
    if _qr_bid:
        st.session_state["pending_qr_bid"] = str(_qr_bid).strip()
    if _qr_ep:
        st.session_state["pending_qr_ep"] = str(_qr_ep).strip()

    st.session_state["qr_page_applied"] = False
    st.query_params.clear()

REMEMBER_SECRET_KEY = os.environ.get("REMEMBER_SECRET_KEY", "lpee_ctr_csb_remember_me_2026_a_changer")
REMEMBER_SESSION_DUREE = datetime.timedelta(hours=4)
REMEMBER_COOKIE_NAME = "remember_data"

def _generer_jeton_souvenir(username, role, can_edit, issued_at_iso):
    import hashlib
    import hmac as hmac_lib
    payload = f"{username}:{role}:{bool(can_edit)}:{issued_at_iso}"
    return hmac_lib.new(REMEMBER_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()

cookie_manager = stx.CookieManager(key="lpee_ctr_csb_cookie_manager")

if "_cookies_bootstrap_ok" not in st.session_state:
    st.session_state["_cookies_bootstrap_ok"] = True
    st.rerun()

pwa_code = """
<script>
const parentDoc = window.parent.document;
if (!parentDoc.querySelector('link[rel="manifest"]')) {
    const manifestLink = parentDoc.createElement('link');
    manifestLink.rel = 'manifest';
    manifestLink.href = '/manifest.json';
    parentDoc.head.appendChild(manifestLink);
}
if (!parentDoc.querySelector('meta[name="theme-color"]')) {
    const metaTheme = parentDoc.createElement('meta');
    metaTheme.name = 'theme-color';
    metaTheme.content = '#0066cc';
    parentDoc.head.appendChild(metaTheme);
}
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
        .then((reg) => console.log('Service Worker PWA enregistré !', reg))
        .catch((err) => console.error('Erreur Service Worker PWA :', err));
}
</script>
"""
components.html(pwa_code, height=0, width=0)

# ==========================================
# 2. CONNEXION SUPABASE & UTILISATEURS
# ==========================================
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://pfyfmfujccibiwfiwknu.supabase.co")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_6h8ZUeV8ii5TjKUV9B1Ewg_eDawQRkW")
    CODE_ACCES_TERRAIN = st.secrets.get("CODE_ACCES_TERRAIN", "lpee2026")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        supabase.postgrest.session.headers.update({"x-code-acces-terrain": CODE_ACCES_TERRAIN})
    except Exception:
        pass
except Exception:
    supabase = None

DEFAULT_USERS = {
    "BAALLAL": {"password": "arwa2020", "role": "admin", "can_edit": True},
    "AMINA": {"password": "amina2026", "role": "laboratoire", "can_edit": True},
    "HANINE": {"password": "hanine2026", "role": "laboratoire", "can_edit": False},
    "IKKEN": {"password": "ikken2026", "role": "laboratoire", "can_edit": False},
    "HAMDANI": {"password": "hamdani2026", "role": "laboratoire", "can_edit": False},
}

def load_users():
    users = DEFAULT_USERS.copy()
    if supabase:
        try:
            res = supabase.table("app_users").select("*").execute()
            if res.data:
                for row in res.data:
                    users[row["username"]] = {
                        "password": row["password"],
                        "role": row["role"],
                        "can_edit": row.get("can_edit", False),
                    }
        except Exception:
            pass
    return users

st.session_state.setdefault("users_db", {})
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
if "can_edit" not in st.session_state:
    st.session_state["can_edit"] = False

# Auto-connexion via Cookie
if st.session_state["user"] is None:
    _cookie_brut = cookie_manager.get(REMEMBER_COOKIE_NAME)
    if _cookie_brut:
        try:
            payload = json.loads(_cookie_brut)
            remembered_user = payload.get("u")
            remembered_role = payload.get("r")
            remembered_can_edit = bool(payload.get("e"))
            remembered_issued_at = payload.get("t")
            remembered_token = payload.get("k")

            jeton_valide = bool(remembered_token) and _generer_jeton_souvenir(
                remembered_user, remembered_role, remembered_can_edit, remembered_issued_at
            ) == remembered_token
            
            if jeton_valide:
                st.session_state["user"] = {
                    "username": remembered_user,
                    "role": remembered_role,
                    "can_edit": remembered_can_edit,
                }
                st.session_state["role"] = remembered_role
                st.session_state["can_edit"] = remembered_can_edit
                st.session_state["users_db"] = load_users()
        except Exception:
            pass

# Formulaire de Connexion
if st.session_state["user"] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Accès Restreint - LPEE")
        with st.form("login_form"):
            username_input = st.text_input("Nom d'utilisateur").strip().upper()
            password_input = st.text_input("Mot de passe", type="password")
            submit_btn = st.form_submit_button("Se connecter", use_container_width=True, type="primary")

            if submit_btn:
                fresh_users = load_users()
                st.session_state["users_db"] = fresh_users
                if username_input in fresh_users and fresh_users[username_input]["password"] == password_input:
                    st.session_state["user"] = {
                        "username": username_input,
                        "role": fresh_users[username_input]["role"],
                        "can_edit": fresh_users[username_input]["can_edit"]
                    }
                    st.session_state["role"] = fresh_users[username_input]["role"]
                    st.session_state["can_edit"] = fresh_users[username_input]["can_edit"]
                    st.rerun()
                else:
                    st.error("❌ Identifiants incorrects.")
    st.stop()

current_username = st.session_state["user"]["username"]

# ==========================================
# 3. CHARGEMENT DYNAMIQUE DES VUES
# ==========================================
try:
    from views import essai_Plaque
except ImportError:
    essai_Plaque = None

try:
    from views import essai_teneur_eau
except ImportError:
    essai_teneur_eau = None

try:
    from views import essai_compacite
except ImportError:
    essai_compacite = None

try:
    from views import historique_pvs
except ImportError:
    historique_pvs = None

try:
    from views import pv_granulats
except ImportError:
    pv_granulats = None

try:
    from views import essai_identification_materiaux
except ImportError:
    essai_identification_materiaux = None

# ==========================================
# 4. BARRE LATÉRALE DE NAVIGATION (SIDEBAR)
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png.jpg"):
        st.image("logo.png.jpg", use_container_width=True)
    elif os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)

    st.title("Smart Control Béton")
    st.caption(f"👤 Connecté : **{current_username}**")
    st.markdown("---")

    # Dictionnaire des modules conservés (sans suivi bétonnage, contrôle béton, ni synthèse plaque)
    menu_options = {
        "🚜 Essai à la Plaque": essai_Plaque,
        "💧 Teneur en Eau": essai_teneur_eau,
        "🏗️ Compacité": essai_compacite,
        "🪨 Granulats pour Béton": pv_granulats,
        "🔬 Identification Matériau": essai_identification_materiaux,
        "📜 Historique & Audit": historique_pvs,
    }

    st.session_state.setdefault("page_widget_seed", 0)
    st.session_state.setdefault("selected_page", list(menu_options.keys())[0])

    page_par_defaut = st.session_state.get("selected_page")
    if page_par_defaut not in menu_options:
        page_par_defaut = list(menu_options.keys())[0]

    selected_page_label = st.radio(
        "📍 Navigation",
        options=list(menu_options.keys()),
        index=list(menu_options.keys()).index(page_par_defaut),
        key=f"menu_radio_{st.session_state['page_widget_seed']}",
    )
    st.session_state["selected_page"] = selected_page_label

    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state["user"] = None
        st.session_state["role"] = None
        st.session_state["can_edit"] = False
        st.rerun()

    st.caption("LPEE - CTR Casablanca | LGV CASA SUD")

# ==========================================
# 5. RENDU DE LA VUE SÉLECTIONNÉE
# ==========================================
def render_view(module, supabase_client):
    if module is None:
        st.error("⚠️ Module non chargé ou fichier de vue manquant.")
        return
    try:
        module.show(supabase_client)
    except Exception as e:
        st.error(f"Erreur d'affichage du module : {e}")

module_a_afficher = menu_options.get(selected_page_label)
render_view(module_a_afficher, supabase)
