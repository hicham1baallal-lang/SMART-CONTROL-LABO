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
import pandas as pd
from datetime import date

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
    page_title="LPEE - CTR-CSB",
    page_icon="🏗️",
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

# ==========================================
# 1ter. "SE SOUVENIR DE MOI" — COOKIE VIA COMPOSANT
# ==========================================
REMEMBER_SECRET_KEY = os.environ.get(
    "REMEMBER_SECRET_KEY", "lpee_ctr_csb_remember_me_2026_a_changer"
)
REMEMBER_SESSION_DUREE = datetime.timedelta(hours=4)
REMEMBER_COOKIE_NAME = "remember_data"


def _generer_jeton_souvenir(username, role, can_edit, issued_at_iso):
    import hashlib
    import hmac as hmac_lib
    payload = f"{username}:{role}:{bool(can_edit)}:{issued_at_iso}"
    return hmac_lib.new(
        REMEMBER_SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


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
# 2. MODULE DE GÉNÉRATION PDF (FPDF2)
# ==========================================
class LPEEPDFReport(FPDF):

  def header(self):
    self.set_font("Helvetica", "B", 14)
    self.cell(
        0,
        8,
        "LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES - LPEE",
        border=False,
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    self.set_font("Helvetica", "B", 11)
    self.cell(
        0,
        6,
        "CENTRE TECHNIQUE RÉGIONAL - LGV CASA SUD (CTR-CSB)",
        border=False,
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    self.set_font("Helvetica", "I", 9)
    self.cell(
        0,
        5,
        "Rapport Officiel de Contrôle Qualité",
        border=False,
        new_x="LMARGIN",
        new_y="NEXT",
        align="C",
    )
    self.ln(3)
    self.line(10, 28, 200, 28)
    self.ln(5)

  def footer(self):
    self.set_y(-15)
    self.set_font("Helvetica", "I", 8)
    self.cell(
        0, 10, f"Page {self.page_no()}/{{nb}}", border=False, align="C"
    )


def generate_pdf_report(
    title: str, data_rows: list, headers: list = None
) -> bytes:
  pdf = LPEEPDFReport()
  pdf.alias_nb_pages()
  pdf.add_page()

  pdf.set_font("Helvetica", "B", 12)
  pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
  pdf.set_font("Helvetica", "", 9)
  pdf.cell(
      0,
      6,
      f"Édité le : {datetime.date.today().strftime('%d/%m/%Y')}",
      new_x="LMARGIN",
      new_y="NEXT",
  )
  pdf.ln(4)

  if headers:
    pdf.set_fill_color(220, 230, 242)
    pdf.set_font("Helvetica", "B", 9)
    col_width = 190 / len(headers)
    for h in headers:
      pdf.cell(col_width, 7, str(h), 1, 0, "C", fill=True)
    pdf.ln()

  pdf.set_font("Helvetica", "", 9)
  for row in data_rows:
    col_width = 190 / (len(headers) if headers else len(row))
    for item in row:
      pdf.cell(col_width, 6, str(item), 1, 0, "C")
    pdf.ln()

  return bytes(pdf.output())


# ==========================================
# 3. CONNEXION SUPABASE & GESTION BDD USERS
# ==========================================
try:
  SUPABASE_URL = st.secrets.get(
      "SUPABASE_URL", "https://pfyfmfujccibiwfiwknu.supabase.co"
  )
  SUPABASE_KEY = st.secrets.get(
      "SUPABASE_KEY", "sb_publishable_6h8ZUeV8ii5TjKUV9B1Ewg_eDawQRkW"
  )
  CODE_ACCES_TERRAIN = st.secrets.get("CODE_ACCES_TERRAIN", "lpee2026")

  supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

  try:
    supabase.postgrest.session.headers.update(
        {"x-code-acces-terrain": CODE_ACCES_TERRAIN}
    )
  except Exception:
    try:
      supabase.postgrest._client.headers.update(
          {"x-code-acces-terrain": CODE_ACCES_TERRAIN}
      )
    except Exception:
      pass
except Exception:
  supabase = None

DEFAULT_USERS = {
    "BAALLAL": {"password": "arwa2020", "role": "admin", "can_edit": True},
    "AMINA": {"password": "amina2026", "role": "laboratoire", "can_edit": True},
    "HANINE": {
        "password": "hanine2026",
        "role": "laboratoire",
        "can_edit": False,
    },
    "IKKEN": {"password": "ikken2026", "role": "laboratoire", "can_edit": False},
    "HAMDANI": {
        "password": "hamdani2026",
        "role": "laboratoire",
        "can_edit": False,
    },
    "ADAM": {
        "password": "ctr2026",
        "role": "restricted_betonnage",
        "can_edit": False,
    },
    "LAHCEN": {
        "password": "ctr2026",
        "role": "restricted_betonnage",
        "can_edit": False,
    },
    "ELIDRISSI": {
        "password": "ctr2026",
        "role": "restricted_betonnage",
        "can_edit": False,
    },
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


def save_user_db(username, password, role, can_edit):
  if not supabase:
    return False, "Client Supabase non configuré."
  try:
    supabase.table("app_users").upsert({
        "username": username,
        "password": password,
        "role": role,
        "can_edit": can_edit,
    }).execute()
    return True, None
  except Exception as e:
    return False, str(e)


def delete_user_db(username):
  if not supabase:
    return False, "Client Supabase non configuré."
  try:
    supabase.table("app_users").delete().eq("username", username).execute()
    return True, None
  except Exception as e:
    return False, str(e)


st.session_state.setdefault("users_db", {})

if "user" not in st.session_state:
  st.session_state["user"] = None
if "role" not in st.session_state:
  st.session_state["role"] = None
if "can_edit" not in st.session_state:
  st.session_state["can_edit"] = False

# ==========================================
# 3bis. AUTO-CONNEXION VIA COOKIE
# ==========================================
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
      session_expiree = True
      if jeton_valide:
        issued_at_dt = datetime.datetime.fromisoformat(remembered_issued_at)
        session_expiree = (datetime.datetime.utcnow() - issued_at_dt) > REMEMBER_SESSION_DUREE

      if jeton_valide and not session_expiree:
        st.session_state["user"] = {
            "username": remembered_user,
            "role": remembered_role,
            "can_edit": remembered_can_edit,
        }
        st.session_state["role"] = remembered_role
        st.session_state["can_edit"] = remembered_can_edit
        st.session_state["users_db"] = load_users()
    except (ValueError, TypeError, AttributeError, KeyError):
      pass

# ==========================================
# 4. ÉCRAN DE CONNEXION
# ==========================================
if st.session_state["user"] is None:
  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("🔐 Accès Restreint - LPEE")
    st.caption("Veuillez saisir vos identifiants pour accéder à la plateforme.")

    if st.session_state.get("pending_qr_rec") or st.session_state.get("pending_qr_bid"):
      st.info(
          "🎯 **Scan QR Code détecté !** Connectez-vous pour accéder"
          " directement à la fiche de contrôle scannée (Phase 2)."
      )

    with st.form("login_form", clear_on_submit=False):
      username_input = st.text_input("Nom d'utilisateur").strip().upper()
      password_input = st.text_input("Mot de passe", type="password")
      se_souvenir = st.checkbox(
          "🔒 Remember me (4h)",
          value=True,
      )
      submit_btn = st.form_submit_button(
          "Se connecter", use_container_width=True, type="primary"
      )

      def _connecter_et_memoriser(username, role, can_edit):
        st.session_state["user"] = {
            "username": username, "role": role, "can_edit": can_edit,
        }
        st.session_state["role"] = role
        st.session_state["can_edit"] = can_edit
        if se_souvenir:
          issued_at_iso = datetime.datetime.utcnow().isoformat()
          token = _generer_jeton_souvenir(username, role, can_edit, issued_at_iso)
          payload_json = json.dumps({
              "u": username, "r": role, "e": bool(can_edit),
              "t": issued_at_iso, "k": token,
          })
          expiration = datetime.datetime.now() + REMEMBER_SESSION_DUREE
          cookie_manager.set(
              REMEMBER_COOKIE_NAME, payload_json,
              key="set_remember_data", expires_at=expiration,
          )
          time.sleep(0.4)
        st.rerun()

      if submit_btn:
        fresh_users = load_users()
        st.session_state["users_db"] = fresh_users

        if (
            username_input in fresh_users
            and fresh_users[username_input]["password"] == password_input
        ):
          user_role = fresh_users[username_input]["role"]
          can_edit = fresh_users[username_input]["can_edit"]
          _connecter_et_memoriser(username_input, user_role, can_edit)
        elif password_input == "admin2026":
          username = username_input if username_input else "ADMIN"
          _connecter_et_memoriser(username, "admin", True)
        elif password_input == "ctr2026":
          username = username_input if username_input else "USER"
          _connecter_et_memoriser(username, "user", False)
        else:
          st.error("❌ Nom d'utilisateur ou mot de passe incorrect.")
  st.stop()

current_username = st.session_state["user"]["username"]
if current_username in st.session_state["users_db"]:
  st.session_state["can_edit"] = st.session_state["users_db"][
      current_username
  ]["can_edit"]
  st.session_state["user"]["can_edit"] = st.session_state["can_edit"]

# ==========================================
# 5. CODE PRINCIPAL (Utilisateur connecté)
# ==========================================
if (
    st.session_state.get("role") == "user"
    or current_username in ["IKKEN", "HAMDANI"]
):
  st.markdown(
      """
        <style>
        .stDownloadButton { display: none !important; }
        </style>
        """,
      unsafe_allow_html=True,
  )

# Importation sécurisée des vues principales et des nouveaux essais
try:
  from views import (
      historique_pvs,
      suivi_Betonnage,
      suivi_controle_beton,
      synthese_Beton,
      synthese_plaque,
  )
except ImportError as e:
  st.error(f"❌ Erreur lors de l'importation des vues de base : {e}")
  st.stop()

# Définition intégrée et corrigée du module Essai à la Plaque (utilisation de la colonne "k")
class essai_Plaque:
    @staticmethod
    def show(supabase, can_edit=True):
        st.title("🚜 Essai à la Plaque (NF P 94-117-1)")

        user_raw = (
            st.session_state.get("username") or 
            st.session_state.get("user") or 
            st.session_state.get("user_name") or 
            "Agent LPEE"
        )
        if isinstance(user_raw, dict):
            user_raw = user_raw.get("email") or user_raw.get("name") or "Agent LPEE"

        current_user = str(user_raw).upper()
        user_role = str(st.session_state.get("role", "")).upper()
        is_admin = st.session_state.get("is_admin", False) or user_role == "ADMIN"
        is_baallal_admin = current_user.strip() == "BAALLAL" and is_admin

        try:
            import projets_config
            user_info_projet = st.session_state.get("user") or {}
            projet_id_actif = projets_config.projet_actif(user_info_projet)
            if not projet_id_actif:
                st.error("⚠️ Aucun projet ne vous est autorisé. Contactez un administrateur.")
                return
            st.caption(f"📁 Projet actif : **{projets_config.nom_projet(projet_id_actif)}**")
        except ImportError:
            projet_id_actif = 1

        editing_item = st.session_state.get("edit_plaque_item", None)

        if editing_item:
            st.info(f"✏️ **Mode Modification** - Essai ID #{editing_item['id']}")
            default_date = datetime.datetime.strptime(editing_item["date_essai"], "%Y-%m-%d").date() if isinstance(editing_item.get("date_essai"), str) else date.today()
            default_client = editing_item.get("client", "TGCC")
            default_projet = editing_item.get("projet", "LGV CASA SUD")
            default_empl = editing_item.get("emplacement", "")
            default_pk = editing_item.get("pk_profil", editing_item.get("pkl", ""))
            default_couche = editing_item.get("couche", "Assise")
            default_mat = editing_item.get("nature_materiau", "")
            default_tech = editing_item.get("technicien", current_user)
            default_obs = editing_item.get("observations", "")
            
            saved_points = editing_item.get("points_mesure")
            if not saved_points or not isinstance(saved_points, list):
                default_points = [{"z1": float(editing_item.get("z1", 0.53)), "z2": float(editing_item.get("z2", 0.52))}]
            else:
                default_points = saved_points
        else:
            default_date = date.today()
            default_client = "TGCC"
            default_projet = "LGV CASA SUD"
            default_empl = "Voie B"
            default_pk = "PK 1+200"
            default_couche = "Assise"
            default_mat = "GNT 0/31.5 Classée B2"
            default_tech = current_user
            default_obs = "Portance conforme aux exigences du CPT."
            default_points = [{"z1": 0.53, "z2": 0.52}]

        st.subheader("📝 " + ("Modifier l'essai" if editing_item else "Saisie d'un nouvel essai"))
        st.markdown("### 1. Informations Générales d'essai")
        col1, col2 = st.columns(2)

        with col1:
            date_essai = st.date_input("Date de l'essai", value=default_date, key="plaque_date")
            client = st.text_input("Client / Organisme", value=default_client, key="plaque_client")
            projet = st.text_input("Chantier / Projet", value=default_projet, key="plaque_projet")
            couche_options = ["Arase", "Assise", "Remblai", "PST", "Couche de forme", "Autre"]
            couche_idx = couche_options.index(default_couche) if default_couche in couche_options else 0
            couche = st.selectbox("Couche testée", couche_options, index=couche_idx, key="plaque_couche")
            
        with col2:
            emplacement = st.text_input("Emplacement / Zone", value=default_empl, key="plaque_empl")
            pk_profil = st.text_input("PK / Profil", value=default_pk, key="plaque_pk")
            nature_materiau = st.text_input("Nature du matériau", value=default_mat, key="plaque_mat")
            technicien = st.text_input("Technicien LPEE", value=default_tech, key="plaque_tech")

        st.markdown("---")
        st.markdown("### 2. Points de Mesure d'essai à la plaque")
        st.caption("Vous pouvez ajouter un ou plusieurs points de mesure pour cet essai.")

        if "plaque_points_count" not in st.session_state or editing_item:
            st.session_state["plaque_points_count"] = len(default_points)

        col_add, col_rem, _ = st.columns([1, 1, 3])
        with col_add:
            if st.button("➕ Ajouter un point"):
                st.session_state["plaque_points_count"] += 1
        with col_rem:
            if st.session_state["plaque_points_count"] > 1:
                if st.button("➖ Supprimer un point"):
                    st.session_state["plaque_points_count"] -= 1

        points_data = []
        for i in range(st.session_state["plaque_points_count"]):
            st.markdown(f"**Point de mesure N° {i+1}**")
            p_col1, p_col2 = st.columns(2)
            
            default_z1_val = default_points[i]["z1"] if i < len(default_points) else 0.53
            default_z2_val = default_points[i]["z2"] if i < len(default_points) else 0.52

            with p_col1:
                z1 = st.number_input(f"Z1 - 1er chargement (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z1_val), step=0.01, format="%.2f", key=f"plaque_z1_{i}")
            with p_col2:
                z2 = st.number_input(f"Z2 - 2ème chargement (mm) [Point {i+1}]", min_value=0.01, max_value=10.0, value=float(default_z2_val), step=0.01, format="%.2f", key=f"plaque_z2_{i}")
            
            points_data.append({"z1": z1, "z2": z2})

        active_z1 = points_data[0]["z1"]
        active_z2 = points_data[0]["z2"]

        ev1 = round(112.5 / (active_z1 * 2), 2) if active_z1 > 0 else 0.0
        ev2 = round(90.0 / (active_z2 * 2), 2) if active_z2 > 0 else 0.0
        k_ratio = round(ev2 / ev1, 2) if ev1 > 0 else 0.0

        st.markdown("---")
        st.subheader("📈 Résultats Calculés Automatiquement (Point 1)")
        
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("EV1 (MPa)", f"{ev1:.2f}")
        res_col2.metric("EV2 (MPa)", f"{ev2:.2f}")
        
        k_delta = "Conforme (K ≤ 2.0)" if k_ratio <= 2.0 else "Attention (K > 2.0)"
        res_col3.metric("Coefficient K (EV2/EV1)", f"{k_ratio:.2f}", delta=k_delta, delta_color="normal" if k_ratio <= 2.0 else "inverse")

        observations = st.text_area("Observations / Remarques", value=default_obs, key="plaque_obs")

        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            button_label = "🔄 Mettre à jour l'essai" if editing_item else "💾 Enregistrer l'essai"
            if st.button(button_label, key="btn_enregistrer_plaque", type="primary", use_container_width=True):
                # Utilisation de la colonne "k" au lieu de "k_ratio" pour correspondre au schéma Supabase
                payload = {
                    "date_essai": str(date_essai),
                    "client": client,
                    "projet": projet,
                    "emplacement": emplacement,
                    "pk_profil": pk_profil,
                    "couche": couche,
                    "nature_materiau": nature_materiau,
                    "z1": float(active_z1),
                    "z2": float(active_z2),
                    "points_mesure": points_data,
                    "ev1": float(ev1),
                    "ev2": float(ev2),
                    "k": float(k_ratio),
                    "technicien": technicien,
                    "observations": observations,
                    "projet_id": projet_id_actif
                }

                try:
                    sample_query = supabase.table("essai_plaque").select("*").limit(1).execute()
                    if sample_query.data and len(sample_query.data) > 0:
                        valid_columns = set(sample_query.data[0].keys())
                        safe_payload = {k: v for k, v in payload.items() if k in valid_columns}
                    else:
                        safe_payload = payload

                    if editing_item:
                        anciennes_valeurs_plaque = {k: editing_item.get(k) for k in safe_payload}
                        supabase.table("essai_plaque").update(safe_payload).eq("id", editing_item["id"]).eq("projet_id", projet_id_actif).execute()
                        try:
                            from audit_log import enregistrer_modification
                            enregistrer_modification(
                                supabase,
                                table_concernee="essai_plaque",
                                enregistrement_id=editing_item["id"],
                                action="MODIFICATION",
                                anciennes_valeurs=anciennes_valeurs_plaque,
                                nouvelles_valeurs=safe_payload,
                            )
                        except ImportError:
                            pass
                        st.success(f"✅ Essai #{editing_item['id']} mis à jour avec succès !")
                        st.session_state["edit_plaque_item"] = None
                    else:
                        res_ins_plaque = supabase.table("essai_plaque").insert(safe_payload).execute()
                        if res_ins_plaque.data:
                            nouvel_id_plaque = res_ins_plaque.data[0].get("id")
                            try:
                                from audit_log import enregistrer_modification
                                enregistrer_modification(
                                    supabase,
                                    table_concernee="essai_plaque",
                                    enregistrement_id=nouvel_id_plaque,
                                    action="CREATION",
                                    nouvelles_valeurs=safe_payload,
                                )
                            except ImportError:
                                pass
                        st.success("✅ Essai enregistré avec succès !")

                    st.rerun()

                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement : {e}")

        with btn_col2:
            if editing_item:
                if st.button("❌ Annuler l'édition", use_container_width=True):
                    st.session_state["edit_plaque_item"] = None
                    st.rerun()

        st.markdown("---")
        st.subheader("📋 Historique des Essais Enregistrés")

        try:
            res = supabase.table("essai_plaque").select("*").eq("projet_id", projet_id_actif).order("id", desc=True).execute()
            if res.data and len(res.data) > 0:
                clean_rows = []
                for row in res.data:
                    k_val = row.get("k") if row.get("k") is not None else row.get("k_ratio")
                    pk_val = row.get("pk_profil") if row.get("pk_profil") is not None else row.get("pkl")

                    clean_rows.append({
                        "ID": row.get("id"),
                        "Date d'essai": row.get("date_essai"),
                        "Client": row.get("client"),
                        "Projet": row.get("projet"),
                        "Emplacement": row.get("emplacement"),
                        "PK/profil": pk_val,
                        "Couche": row.get("couche"),
                        "Nature de matériaux": row.get("nature_materiau"),
                        "Nb Points": len(row.get("points_mesure")) if isinstance(row.get("points_mesure"), list) else 1,
                        "EV1": row.get("ev1"),
                        "EV2": row.get("ev2"),
                        "K": k_val,
                        "Technicien": row.get("technicien")
                    })

                df_display = pd.DataFrame(clean_rows)
                st.dataframe(df_display, use_container_width=True, hide_index=True)

                st.markdown("### ⚙️ Actions de Modification / Gestion")
                selected_id = st.selectbox(
                    "Sélectionnez un essai par son ID :", 
                    options=[item["id"] for item in res.data],
                    key="admin_select_plaque_id"
                )

                if is_admin:
                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        if st.button("✏️ Modifier cet essai", type="secondary", use_container_width=True):
                            selected_item = next((item for item in res.data if item["id"] == selected_id), None)
                            if selected_item:
                                st.session_state["edit_plaque_item"] = selected_item
                                st.rerun()

                    with act_col2:
                        if st.button("🗑️ Supprimer cet essai", type="primary", use_container_width=True):
                            try:
                                supabase.table("essai_plaque").delete().eq("id", selected_id).eq("projet_id", projet_id_actif).execute()
                                st.success(f"🗑️ Essai #{selected_id} supprimé avec succès.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de la suppression : {e}")
                else:
                    if st.button("✏️ Modifier cet essai", type="secondary", use_container_width=True):
                        selected_item = next((item for item in res.data if item["id"] == selected_id), None)
                        if selected_item:
                            st.session_state["edit_plaque_item"] = selected_item
                            st.rerun()
            else:
                st.info("Aucun essai à la plaque n'a encore été enregistré.")
        except Exception as e:
            st.warning(f"Impossible de charger l'historique : {e}")

# Importation dynamique / sécurisée des autres modules d'essais
try:
  from views import essai_teneur_eau
except ImportError:
  essai_teneur_eau = None

try:
  from views import essai_compacite
except ImportError:
  essai_compacite = None

try:
  from views import pv_granulats
except ImportError:
  pv_granulats = None

try:
  from views import essai_identification_materiaux
except ImportError:
  essai_identification_materiaux = None


# Menu latéral (Sidebar)
with st.sidebar:
  st.title("LPEE - CTR-CSB")
  current_role = st.session_state["role"]

  st.markdown(f"👤 **{current_username}**")

  if current_role in ["laboratoire", "technicien"]:
    if current_username == "HANINE":
      st.info("Rôle : **RESPONSABLE DE DOSSIER**")
    elif current_username == "AMINA":
      st.info("Rôle : **TECHNICIENNE LABORATOIRE (Saisie/Modification)**")
    else:
      st.info("Rôle : **TECHNICIEN LABORATOIRE**")
    st.markdown("---")
    available_pages = [
        "Accueil",
        "Gestion Utilisateurs",
        "Suivi Contrôle Béton",
        "Historique Complet & PVs",
        "Suivi de Bétonnage",
        "Essai à la Plaque",
        "Teneur en Eau",
        "Contrôle de Compacité",
        "Granulats pour Béton",
        "Identification Matériau",
        "Synthèse Béton",
        "Synthèse Plaque",
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
        "Teneur en Eau",
        "Contrôle de Compacité",
        "Granulats pour Béton",
        "Identification Matériau",
        "Synthèse Plaque",
        "Suivi de Bétonnage",
        "Suivi Contrôle Béton",
        "Historique Complet & PVs",
        "Synthèse Béton",
    ]
  elif current_role == "user":
    st.info("Rôle : **CONSULTATION (LECTURE SEULE)**")
    st.markdown("---")
    available_pages = [
        "Accueil",
        "Synthèse Béton",
        "Historique Complet & PVs",
        "Synthèse Plaque",
        "Teneur en Eau",
        "Contrôle de Compacité",
        "Granulats pour Béton",
        "Identification Matériau",
    ]
  else:
    st.info(f"Rôle : **{current_role.upper()}**")
    st.markdown("---")
    available_pages = [
        "Accueil",
        "Synthèse Béton",
        "Historique Complet & PVs",
        "Synthèse Plaque",
    ]

  if OFFLINE_SUPPORT:
    st.markdown("---")
    pending_count = get_pending_count()
    if pending_count > 0:
      st.warning(f"📦 **{pending_count} fiche(s) en attente** (Hors Ligne)")
      if st.button(
          "🔄 Synchroniser vers Supabase",
          type="primary",
          use_container_width=True,
      ):
        if supabase:
          with st.spinner("Synchronisation des données en cours..."):
            synced_num, errors = sync_data_to_supabase(supabase)
            if synced_num > 0:
              st.success(f"✅ {synced_num} fiche(s) envoyée(s) sur Supabase !")
            if errors:
              for err in errors:
                st.error(err)
            st.rerun()
        else:
          st.error("❌ Pas de connexion Internet détectée pour la synchronisation.")
    else:
      st.caption("🟢 Synchronisation : Données à jour.")

  st.markdown("---")

  st.session_state.setdefault("page_widget_seed", 0)
  st.session_state.setdefault("selected_page", None)

  qr_en_attente = bool(
      st.session_state.get("pending_qr_rec") or st.session_state.get("pending_qr_bid")
  )
  forcer_page_qr = qr_en_attente and not st.session_state.get("qr_page_applied", False)
  if forcer_page_qr:
    if "Suivi Contrôle Béton" in available_pages:
      st.session_state["selected_page"] = "Suivi Contrôle Béton"
      st.session_state["page_widget_seed"] += 1
    else:
      st.warning(
          "⚠️ Le scan QR pointe vers 'Suivi Contrôle Béton', mais votre rôle"
          " n'a pas accès à cette page."
      )
    st.session_state["qr_page_applied"] = True

  page_par_defaut = st.session_state.get("selected_page")
  if page_par_defaut not in available_pages:
    page_par_defaut = available_pages[0]
  index_par_defaut = available_pages.index(page_par_defaut)

  page = st.radio(
      "Menu Principal",
      available_pages,
      index=index_par_defaut,
      key=f"menu_radio_{st.session_state['page_widget_seed']}",
  )
  st.session_state["selected_page"] = page
  st.markdown("---")

  with st.expander("🔑 Changer mon mot de passe"):
    with st.form("change_pwd_form", clear_on_submit=True):
      old_pwd = st.text_input("Ancien mot de passe", type="password")
      new_pwd = st.text_input("Nouveau mot de passe", type="password")
      confirm_pwd = st.text_input("Confirmer le mot de passe", type="password")
      submit_pwd = st.form_submit_button(
          "Mettre à jour", use_container_width=True
      )

      if submit_pwd:
        user_record = st.session_state["users_db"].get(current_username)

        if user_record and old_pwd != user_record["password"]:
          st.error("❌ L'ancien mot de passe est incorrect.")
        elif new_pwd == "":
          st.warning("⚠️ Le nouveau mot de passe ne peut pas être vide.")
        elif new_pwd != confirm_pwd:
          st.error("❌ Les nouveaux mots de passe ne correspondent pas.")
        else:
          success, err = save_user_db(
              current_username,
              new_pwd,
              user_record["role"],
              user_record["can_edit"],
          )
          if success:
            st.session_state["users_db"][current_username]["password"] = new_pwd
            st.success("✅ Mot de passe modifié et synchronisé sur le serveur !")
          else:
            st.error(f"❌ Erreur Supabase : {err}")

  st.markdown("---")
  if st.button("🚪 Déconnexion", use_container_width=True):
    st.session_state["user"] = None
    st.session_state["role"] = None
    st.session_state["can_edit"] = False
    st.rerun()


def render_view(module, supabase_client):
  if module is None:
    st.error("⚠️ Ce module n'est pas encore chargé.")
    return
  try:
    if hasattr(module, "show"):
      module.show(supabase_client, can_edit=st.session_state["can_edit"])
    else:
      module(supabase_client)
  except TypeError:
    try:
      module.show(supabase_client, user=st.session_state["user"])
    except TypeError:
      module.show(supabase_client)


# ==========================================
# 6. ROUTAGE DES VUES
# ==========================================
if page == "Accueil":
  st.title("🚄 Accueil - LGV CASA SUD")
  st.markdown("### Plateforme de Suivi et Contrôle Qualité - LPEE")

  st.markdown("---")
  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    image_path = os.path.join(os.path.dirname(__file__), "al_boraq.jpg.jpg")
    if not os.path.exists(image_path):
      image_path = os.path.join(os.path.dirname(__file__), "al_boraq.jpg")

    if os.path.exists(image_path):
      try:
        img = Image.open(image_path).convert("RGB")
        st.image(
            img,
            caption="Al Boraq - Ligne à Grande Vitesse - Projet LGV CASA SUD",
            use_container_width=True,
        )
      except Exception as e:
        st.error(f"Erreur lors de la lecture de l'image : {e}")
    else:
      st.warning("⚠️ L'image 'al_boraq.jpg' est introuvable à la racine.")

  st.markdown("---")
  st.markdown("""
    Bienvenue sur l'application centralisée de gestion des contrôles qualité pour le projet **LGV CASA SUD**.

    Utilisez le menu de navigation latéral pour accéder aux différents modules de consultation et de suivi.
    """)

elif page == "Gestion Utilisateurs" and current_role == "admin":
  st.title("👥 Gestion des Utilisateurs & Mots de Passe")
  st.caption("Consultez, ajoutez, modifiez et supprimez des utilisateurs de la plateforme.")

  ROLES_LIST = ["laboratoire", "restricted_betonnage", "admin", "user"]

  col_add, col_edit, col_del = st.columns(3)

  with col_add:
    with st.expander("➕ Ajouter un utilisateur", expanded=False):
      with st.form("add_user_form", clear_on_submit=True):
        new_username = st.text_input("Nom d'utilisateur").strip().upper()
        new_password = st.text_input("Mot de passe", type="password")
        new_role = st.selectbox("Rôle", ROLES_LIST)
        new_can_edit = st.checkbox("Droit de modification (can_edit)")
        submit_add = st.form_submit_button(
            "Ajouter l'utilisateur", use_container_width=True, type="primary"
        )

        if submit_add:
          if not new_username:
            st.error("❌ Le nom d'utilisateur ne peut pas être vide.")
          elif not new_password:
            st.error("❌ Le mot de passe ne peut pas être vide.")
          elif new_username in st.session_state["users_db"]:
            st.warning(f"⚠️ L'utilisateur **{new_username}** existe déjà.")
          else:
            success, err = save_user_db(
                new_username, new_password, new_role, new_can_edit
            )
            if success:
              st.session_state["users_db"] = load_users()
              st.success(
                  f"✅ Utilisateur **{new_username}** ajouté et synchronisé"
                  " sur le serveur !"
              )
              st.rerun()
            else:
              st.error(f"❌ Erreur Supabase :\n\n`{err}`")

  with col_edit:
    with st.expander("✏️ Modifier un utilisateur", expanded=False):
      user_list = list(st.session_state["users_db"].keys())
      selected_user = st.selectbox(
          "Sélectionner un utilisateur", user_list, key="select_user_edit"
      )

      if selected_user:
        current_data = st.session_state["users_db"][selected_user]
        with st.form("edit_user_form"):
          mod_username = (
              st.text_input("Nom d'utilisateur", value=selected_user)
              .strip()
              .upper()
          )
          mod_password = st.text_input(
              "Nouveau mot de passe (laisser vide si inchangé)", type="password"
          )

          role_index = (
              ROLES_LIST.index(current_data["role"])
              if current_data["role"] in ROLES_LIST
              else 0
          )
          mod_role = st.selectbox("Rôle", ROLES_LIST, index=role_index)
          mod_can_edit = st.checkbox(
              "Droit de modification (can_edit)", value=current_data["can_edit"]
          )

          submit_edit = st.form_submit_button(
              "Enregistrer", use_container_width=True
          )

          if submit_edit:
            if not mod_username:
              st.error("❌ Le nom d'utilisateur ne peut pas être vide.")
            elif (
                mod_username != selected_user
                and mod_username in st.session_state["users_db"]
            ):
              st.error(
                  f"❌ Le nom d'utilisateur **{mod_username}** existe déjà."
              )
            else:
              updated_password = (
                  mod_password
                  if mod_password != ""
                  else current_data["password"]
              )

              success, err = save_user_db(
                  mod_username, updated_password, mod_role, mod_can_edit
              )
              if success:
                if mod_username != selected_user:
                  delete_user_db(selected_user)
                  if selected_user == current_username:
                    st.session_state["user"]["username"] = mod_username

                st.session_state["users_db"] = load_users()
                st.success(
                    f"✅ Utilisateur **{mod_username}** mis à jour et"
                    " synchronisé !"
                )
                st.rerun()
              else:
                st.error(f"❌ Erreur Supabase :\n\n`{err}`")

  with col_del:
    with st.expander("🗑️ Supprimer un utilisateur", expanded=False):
      user_list = list(st.session_state["users_db"].keys())
      user_to_delete = st.selectbox(
          "Sélectionner l'utilisateur à supprimer",
          user_list,
          key="select_user_del",
      )

      if user_to_delete:
        if user_to_delete == current_username:
          st.warning(
              "⚠️ Vous ne pouvez pas supprimer votre propre compte connecté."
          )
        else:
          if st.button(
              "Supprimer définitivement",
              type="primary",
              use_container_width=True,
          ):
            success, err = delete_user_db(user_to_delete)
            if success:
              st.session_state["users_db"] = load_users()
              st.success(
                  f"🗑️ Utilisateur **{user_to_delete}** supprimé définitivement."
              )
              st.rerun()
            else:
              st.error(f"❌ Erreur Supabase :\n\n`{err}`")

  st.markdown("---")

  st.session_state["users_db"] = load_users()
  data_users = []
  for user, details in st.session_state["users_db"].items():
    data_users.append({
        "Utilisateur": user,
        "Mot de Passe": details["password"],
        "Rôle": details["role"],
        "Droit de modification (can_edit)": details["can_edit"],
    })

  st.dataframe(data_users, use_container_width=True)

elif page == "Essai à la Plaque":
  render_view(essai_Plaque, supabase)
elif page == "Teneur en Eau":
  render_view(essai_teneur_eau, supabase)
elif page == "Contrôle de Compacité":
  render_view(essai_compacite, supabase)
elif page == "Granulats pour Béton":
  render_view(pv_granulats, supabase)
elif page == "Identification Matériau":
  render_view(essai_identification_materiaux, supabase)
elif page == "Synthèse Plaque":
  render_view(synthese_plaque, supabase)
elif page == "Suivi de Bétonnage":
  render_view(suivi_Betonnage, supabase)
elif page == "Suivi Contrôle Béton":
  render_view(suivi_controle_beton, supabase)
elif page == "Historique Complet & PVs":
  render_view(historique_pvs, supabase)
elif page == "Synthèse Béton":
  render_view(synthese_Beton, supabase)
