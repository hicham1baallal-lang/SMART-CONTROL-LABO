"""
Module de secours hors-ligne : file d'attente locale (SQLite) pour les
écritures Supabase qui échouent temporairement (timeout, coupure réseau,
passerelle lente...), avec synchronisation différée dès que la connexion
est rétablie.

Principe :
- Quand un enregistrement Supabase échoue à cause d'un problème réseau
  transitoire, la vue appelante (ex: essai_Plaque.py) appelle `insert_safe`
  pour stocker temporairement les données en local (SQLite), au lieu de les
  perdre.
- Ces enregistrements en attente sont ensuite envoyés à Supabase dès que
  possible via `sync_data_to_supabase`, appelée soit manuellement (bouton
  dans la barre latérale), soit automatiquement au prochain démarrage.

⚠️ LIMITE IMPORTANTE (hébergement Streamlit Cloud) :
Le système de fichiers de Streamlit Cloud est ÉPHÉMÈRE : il peut être
réinitialisé à tout redémarrage/redéploiement de l'application, ce qui
effacerait alors le fichier SQLite et les données en attente non encore
synchronisées. Ce mécanisme protège donc contre de courtes coupures
réseau pendant qu'une session est active, mais NE REMPLACE PAS une vraie
sauvegarde durable. Il est recommandé de synchroniser (bouton dans la
barre latérale) dès que possible après un passage en mode local, et de ne
pas compter sur ce stockage local au-delà de quelques heures.

Utilisation type (voir aussi app.py et les modules de vues comme
essai_Plaque.py) :

    from offline_manager import (
        init_offline_db, insert_safe, get_pending_count, sync_data_to_supabase
    )

    init_offline_db()                          # une fois, au démarrage
    insert_safe("essai_plaque", payload_dict)   # en cas d'échec réseau
    n = get_pending_count()                     # nombre en attente
    resume = sync_data_to_supabase(supabase)    # tente d'envoyer la file
"""

import datetime
import json
import os
import sqlite3
import threading

# Base SQLite stockée à côté de ce module (répertoire de l'application).
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offline_queue.sqlite3")

# SQLite + Streamlit (multi-thread) : un verrou process-local suffit ici car
# chaque instance de l'application a son propre fichier SQLite.
_LOCK = threading.Lock()


def _get_connection():
    conn = sqlite3.connect(_DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_offline_db():
    """Crée la base et la table de file d'attente si elles n'existent pas
    encore. Idempotent : peut être appelée plusieurs fois sans effet de
    bord, y compris à chaque redémarrage de l'application."""
    with _LOCK:
        conn = _get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    synced INTEGER NOT NULL DEFAULT 0,
                    synced_at TEXT,
                    last_error TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()


def insert_safe(table_name, payload):
    """Met en file d'attente locale un enregistrement destiné à la table
    Supabase `table_name`, pour envoi différé.

    - table_name : nom de la table Supabase cible (ex: "essai_plaque").
    - payload : dict JSON-sérialisable des valeurs à insérer — exactement
      les mêmes que celles qui auraient été envoyées à
      `supabase.table(table_name).insert(payload)`.

    Ne touche jamais Supabase : stockage purement local. Peut lever une
    exception si l'écriture locale elle-même échoue (disque plein, etc.) —
    à l'appelant de gérer ce cas comme un échec de sauvegarde complet.
    """
    init_offline_db()  # sécurité si appelé sans init_offline_db() explicite au préalable
    with _LOCK:
        conn = _get_connection()
        try:
            conn.execute(
                "INSERT INTO offline_queue (table_name, payload, created_at, synced) VALUES (?, ?, ?, 0)",
                (
                    table_name,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    datetime.datetime.utcnow().isoformat(),
                )
            )
            conn.commit()
        finally:
            conn.close()


def get_pending_count(table_name=None):
    """Nombre d'enregistrements en attente de synchronisation (pas encore
    envoyés avec succès à Supabase). `table_name` permet de filtrer sur une
    table précise ; sans argument, compte sur toutes les tables."""
    init_offline_db()
    with _LOCK:
        conn = _get_connection()
        try:
            if table_name:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM offline_queue WHERE synced = 0 AND table_name = ?",
                    (table_name,)
                )
            else:
                cur = conn.execute("SELECT COUNT(*) FROM offline_queue WHERE synced = 0")
            return cur.fetchone()[0]
        finally:
            conn.close()


def sync_data_to_supabase(supabase_client):
    """Tente d'envoyer à Supabase tous les enregistrements actuellement en
    attente dans la file locale, table par table, dans leur ordre de
    création.

    - Chaque enregistrement réussi est marqué `synced = 1` (jamais
      supprimé de la base locale, pour garder une trace/traçabilité).
    - Chaque échec reste en attente (avec le détail de l'erreur enregistré
      dans `last_error`) pour une prochaine tentative — aucune donnée n'est
      perdue tant qu'elle n'a pas été confirmée synchronisée.

    Retourne un résumé : {"total": n, "synced": n, "failed": n}.
    """
    if supabase_client is None:
        return {"total": 0, "synced": 0, "failed": 0}

    init_offline_db()
    resume = {"synced": 0, "failed": 0}

    with _LOCK:
        conn = _get_connection()
        try:
            rows = conn.execute(
                "SELECT id, table_name, payload FROM offline_queue WHERE synced = 0 ORDER BY id ASC"
            ).fetchall()
        finally:
            conn.close()

    for row_id, table_name, payload_json in rows:
        try:
            payload = json.loads(payload_json)
            supabase_client.table(table_name).insert(payload).execute()
            with _LOCK:
                conn = _get_connection()
                try:
                    conn.execute(
                        "UPDATE offline_queue SET synced = 1, synced_at = ?, last_error = NULL WHERE id = ?",
                        (datetime.datetime.utcnow().isoformat(), row_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
            resume["synced"] += 1
        except Exception as e:
            with _LOCK:
                conn = _get_connection()
                try:
                    conn.execute(
                        "UPDATE offline_queue SET last_error = ? WHERE id = ?",
                        (str(e), row_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
            resume["failed"] += 1

    resume["total"] = len(rows)
    return resume
