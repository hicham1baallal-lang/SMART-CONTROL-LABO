"""Vue Streamlit : synthèse globale mensuelle des essais."""

from io import BytesIO
import json

import pandas as pd
import streamlit as st


COLONNES = [
    "Date", "Type d'essai", "Référence", "Emplacement / origine",
    "Matériau / couche", "Résultat", "Observation",
]


def _texte(valeur, defaut="—"):
    """Retourne une valeur texte affichable sans jamais produire NaN."""
    if valeur is None or pd.isna(valeur):
        return defaut
    texte = str(valeur).strip()
    return texte if texte else defaut


def _dict(valeur):
    """Convertit une colonne JSON Supabase éventuelle en dictionnaire."""
    if isinstance(valeur, dict):
        return valeur
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except (TypeError, json.JSONDecodeError):
            return {}
    return {}


def _charger(supabase, table):
    """Charge une table sans interrompre la synthèse si elle est absente."""
    try:
        reponse = supabase.table(table).select("*").execute()
        return reponse.data or []
    except Exception as erreur:
        st.warning(f"Table '{table}' non chargée : {erreur}")
        return []


def _statut(valeur):
    """Uniformise les libellés Conforme / Non conforme / À vérifier."""
    texte = _texte(valeur, "").lower()
    if "non conforme" in texte or texte in {"non", "non admise", "non admis"}:
        return "Non conforme"
    if "conforme" in texte or texte in {"oui", "admis", "admise"}:
        return "Conforme"
    return "À vérifier"


def _ligne(date, famille, reference="—", lieu="—", materiau="—", resultat="", observation=""):
    return {
        "Date": pd.to_datetime(date, errors="coerce"),
        "Type d'essai": famille,
        "Référence": _texte(reference),
        "Emplacement / origine": _texte(lieu),
        "Matériau / couche": _texte(materiau),
        "Résultat": _statut(resultat),
        "Observation": _texte(observation),
    }


def charger_plaque(supabase):
    lignes = []
    for essai in _charger(supabase, "essai_plaque"):
        # Le module Plaque ne stocke pas toujours une colonne conformité.
        # L'observation reste donc visible et le statut est « À vérifier »
        # lorsque la conclusion n'est pas enregistrée dans Supabase.
        conclusion = essai.get("conformite") or essai.get("resultat") or essai.get("observation")
        lignes.append(_ligne(
            essai.get("date_essai") or essai.get("created_at"),
            "Essai à la plaque",
            essai.get("reference") or essai.get("ref_essai"),
            essai.get("emplacement") or essai.get("pk_profil"),
            essai.get("couche") or essai.get("nature_materiau"),
            conclusion,
            essai.get("observations"),
        ))
    return lignes


def charger_compacite(supabase):
    lignes = []
    # Un enregistrement de pv_compacite correspond à un rapport, sans
    # répéter chaque point de mesure dans la synthèse mensuelle.
    for pv in _charger(supabase, "pv_compacite"):
        lignes.append(_ligne(
            pv.get("date_prelevement") or pv.get("created_at"),
            "Essai de compacité",
            pv.get("num_rapport"),
            pv.get("lieu_prelevement"),
            pv.get("type_materiau"),
            pv.get("conformite") or pv.get("observation"),
            pv.get("exigence_str"),
        ))
    return lignes


def charger_teneur_eau(supabase):
    lignes = []
    for pv in _charger(supabase, "pv_teneur_eau"):
        lignes.append(_ligne(
            pv.get("date_prelevement") or pv.get("created_at"),
            "Essai teneur en eau",
            pv.get("num_rapport"),
            pv.get("lieu_prelevement") or pv.get("pk_zone"),
            pv.get("nature_materiau"),
            pv.get("conformite") or pv.get("observation"),
            f"Type Proctor : {_texte(pv.get('type_proctor'), '')}".strip(),
        ))
    return lignes


def charger_granulats(supabase):
    lignes, references_vues = [], set()
    # Certaines versions de votre application utilisent historique_pv comme
    # sauvegarde de secours. On déduplique avec la référence de PV.
    for table in ("pv_granulats", "historique_pv"):
        for pv in _charger(supabase, table):
            donnees = _dict(pv.get("pv_data") or pv.get("data") or pv.get("payload"))
            info = _dict(pv.get("pv_info")) or _dict(donnees.get("pv_info"))
            prelevement = _dict(pv.get("info_prelevement")) or _dict(donnees.get("info_prelevement"))

            reference = pv.get("ref_pv") or info.get("ref_pv") or pv.get("reference")
            cle = _texte(reference, "").lower()
            if cle and cle in references_vues:
                continue
            if cle:
                references_vues.add(cle)

            date = (pv.get("date_prelevement") or info.get("date") or
                    prelevement.get("date_prelevement") or pv.get("date_creation"))
            lieu = (pv.get("lieu_prelevement") or prelevement.get("lieu_prelevement") or
                    info.get("projet") or pv.get("projet"))
            observation = (info.get("commentaires") or pv.get("commentaires") or
                           "Identification des granulats pour béton")
            lignes.append(_ligne(
                date, "Granulats pour béton", reference, lieu,
                "Granulats pour béton", pv.get("conformite") or info.get("conformite"), observation,
            ))
    return lignes


def charger_identification_materiaux(supabase):
    lignes = []
    for pv in _charger(supabase, "pv_identification_materiaux"):
        details = _dict(pv.get("details"))
        resultat = (pv.get("conformite") or pv.get("observation") or
                    details.get("Conforme CPC"))
        lignes.append(_ligne(
            pv.get("date_essai") or pv.get("created_at"),
            "Identification matériaux",
            pv.get("num_rapport"),
            pv.get("lieu") or pv.get("pk"),
            pv.get("type_materiau") or pv.get("code_materiau"),
            resultat,
            pv.get("observation") or details.get("Observation"),
        ))
    return lignes


def charger_synthese(supabase):
    """Assemble toutes les familles dans un DataFrame unique."""
    lignes = []
    lignes.extend(charger_plaque(supabase))
    lignes.extend(charger_compacite(supabase))
    lignes.extend(charger_teneur_eau(supabase))
    lignes.extend(charger_granulats(supabase))
    lignes.extend(charger_identification_materiaux(supabase))
    return pd.DataFrame(lignes, columns=COLONNES)


def exporter_excel(dataframe):
    sortie = BytesIO()
    with pd.ExcelWriter(sortie, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Synthèse mensuelle")
        feuille = writer.sheets["Synthèse mensuelle"]
        for colonne in feuille[1]:
            colonne.font = colonne.font.copy(bold=True, color="FFFFFF")
            colonne.fill = colonne.fill.copy(fgColor="1F4E78", fill_type="solid")
        for colonne in feuille.columns:
            lettre = colonne[0].column_letter
            largeur = min(max(len(str(cell.value or "")) for cell in colonne) + 2, 40)
            feuille.column_dimensions[lettre].width = largeur
    sortie.seek(0)
    return sortie.getvalue()


def show(supabase_client):
    st.title("📊 Synthèse globale mensuelle")
    st.caption("Récapitulatif des essais à la plaque, compacité, teneur en eau, granulats et identification matériaux.")

    if supabase_client is None:
        st.error("Connexion Supabase indisponible.")
        return

    if st.button("🔄 Actualiser les données"):
        st.rerun()

    synthese = charger_synthese(supabase_client)
    if synthese.empty:
        st.info("Aucun essai enregistré dans les tables de la synthèse.")
        return

    synthese = synthese.dropna(subset=["Date"]).copy()
    if synthese.empty:
        st.info("Des essais existent, mais aucune date exploitable n'a été trouvée.")
        return

    synthese["Mois"] = synthese["Date"].dt.strftime("%Y-%m")
    mois_options = sorted(synthese["Mois"].unique(), reverse=True)
    mois_choisi = st.selectbox("📅 Choisir le mois", mois_options)

    familles = ["Tous"] + sorted(synthese["Type d'essai"].unique())
    famille_choisie = st.selectbox("Type d'essai", familles)

    resultat_options = ["Tous", "Conforme", "Non conforme", "À vérifier"]
    resultat_choisi = st.selectbox("Résultat", resultat_options)

    resultat = synthese[synthese["Mois"] == mois_choisi].copy()
    if famille_choisie != "Tous":
        resultat = resultat[resultat["Type d'essai"] == famille_choisie]
    if resultat_choisi != "Tous":
        resultat = resultat[resultat["Résultat"] == resultat_choisi]
    resultat = resultat.sort_values("Date", ascending=False)

    total = len(resultat)
    conformes = (resultat["Résultat"] == "Conforme").sum()
    non_conformes = (resultat["Résultat"] == "Non conforme").sum()
    a_verifier = (resultat["Résultat"] == "À vérifier").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Essais du mois", total)
    c2.metric("Conformes", conformes)
    c3.metric("Non conformes", non_conformes)
    c4.metric("À vérifier", a_verifier)

    st.subheader("Répartition par famille d'essai")
    repartition = resultat.groupby("Type d'essai").size().reset_index(name="Nombre d'essais")
    st.bar_chart(repartition.set_index("Type d'essai"))

    st.subheader("Détail des essais")
    affichage = resultat[COLONNES].copy()
    affichage["Date"] = affichage["Date"].dt.strftime("%d/%m/%Y")
    st.dataframe(affichage, use_container_width=True, hide_index=True)

    st.download_button(
        "📥 Télécharger la synthèse Excel",
        data=exporter_excel(affichage),
        file_name=f"Synthese_globale_{mois_choisi}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
