import io
import datetime
import pandas as pd
from docx import Document
import streamlit as st


def generer_document_synthese(df_essais, mois_annee_str):
  """Génère un fichier Word en mémoire contenant la synthèse globale filtrée."""
  doc = Document()

  # En-tête du document
  doc.add_heading("Rapport de Synthèse Mensuelle - Smart Control Béton", level=1)
  doc.add_paragraph(
      f"Synthèse globale des essais enregistrés pour la période : {mois_annee_str}"
  )

  doc.add_heading("Tableau Récapitulatif des Essais", level=2)

  # Création du tableau dans le document Word
  if not df_essais.empty:
    table = doc.add_table(rows=1, cols=len(df_essais.columns))
    hdr_cells = table.rows[0].cells
    for i, column_name in enumerate(df_essais.columns):
      hdr_cells[i].text = str(column_name)

    # Remplissage des lignes du tableau
    for _, row in df_essais.iterrows():
      row_cells = table.add_row().cells
      for i, val in enumerate(row):
        row_cells[i].text = str(val)
  else:
    doc.add_paragraph("Aucun essai disponible pour cette période.")

  # Sauvegarde dans un buffer mémoire
  buffer = io.BytesIO()
  doc.save(buffer)
  buffer.seek(0)
  return buffer


def afficher_vue(supabase_client=None):
  st.subheader("📜 Historique & Synthèse Mensuelle Globale")
  st.write(
      "Consultez et filtrez la synthèse consolidée de tous les essais (Plaques,"
      " Teneur en eau, Compacité, etc.) par mois."
  )

  # --- 1. Récupération des données depuis Supabase (ou simulation) ---
  dfs = []
  
  # Tables typiques à interroger (ajustez les noms selon votre base Supabase)
  tables_essais = [
      ("Essai Plaque", "essais_plaque"),
      ("Teneur en Eau", "essais_teneur_eau"),
      ("Compacité", "essais_compacite"),
      ("Granulats", "pv_granulats"),
      ("Identification Matériau", "essais_identification"),
  ]

  if supabase_client:
    for nom_type, table_name in tables_essais:
      try:
        res = supabase_client.table(table_name).select("*").execute()
        if res.data:
          df_temp = pd.DataFrame(res.data)
          df_temp["Type_Essai"] = nom_type
          dfs.append(df_temp)
      except Exception:
        # Table potentiellement inexistante ou vide
        pass

  # Si aucune donnée récupérée de Supabase (ou mode hors connexion), données de démonstration
  if not dfs:
    data_demo = {
        "ID": [1, 2, 3, 4],
        "Type_Essai": ["Compacité", "Teneur en Eau", "Essai Plaque", "Compacité"],
        "Date": ["2026-08-01", "2026-08-15", "2026-07-20", "2026-08-28"],
        "Ouvrage_Structure": ["PRO 0636", "PRO 0745", "PRA 0500", "PRO 0636"],
        "Statut": ["Validé", "Validé", "En attente", "Validé"],
    }
    df_global = pd.DataFrame(data_demo)
  else:
    df_global = pd.concat(dfs, ignore_index=True)

  # Normalisation de la colonne date pour le filtrage
  # Cherche une colonne de date courante (date, created_at, etc.)
  col_date_candidates = [c for c in df_global.columns if "date" in c.lower() or "created" in c.lower()]
  col_date = col_date_candidates[0] if col_date_candidates else None

  if col_date:
    df_global[col_date] = pd.to_datetime(df_global[col_date], errors="coerce")
    
    # --- 2. Filtres par Mois et Année ---
    st.markdown("### 🔍 Options de Filtrage")
    col1, col2 = st.columns(2)
    
    annees_dispo = sorted(df_global[col_date].dt.year.dropna().unique(), reverse=True)
    if not annees_dispo:
      annees_dispo = [datetime.date.today().year]
      
    with col1:
      selected_year = st.selectbox("Sélectionner l'Année", options=annees_dispo)
      
    mois_noms = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
        5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
        9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
    }
    
    with col2:
      selected_month_num = st.selectbox(
          "Sélectionner le Mois",
          options=list(mois_noms.keys()),
          format_func=lambda x: mois_noms[x],
          index=datetime.date.today().month - 1
      )

    # Application du filtre
    df_filtered = df_global[
        (df_global[col_date].dt.year == selected_year) & 
        (df_global[col_date].dt.month == selected_month_num)
    ].copy()
    
    # Remettre la date en format string lisible pour l'affichage
    df_filtered[col_date] = df_filtered[col_date].dt.strftime("%Y-%m-%d")
    mois_annee_str = f"{mois_noms[selected_month_num]} {selected_year}"
  else:
    df_filtered = df_global
    mois_annee_str = "Global"
    st.info("ℹ️ Aucune colonne de date détectée pour affiner le filtre mensuel.")

  st.markdown("---")
  st.markdown(f"### 📊 Résultats pour : **{mois_annee_str}** ({len(df_filtered)} essai(s) trouvé(s))")

  # Affichage du tableau filtré dans Streamlit
  st.dataframe(df_filtered, use_container_width=True)

  st.markdown("---")

  # --- 3. Section Export Word ---
  st.markdown("### 📥 Exporter la synthèse mensuelle")
  st.write(
      f"Téléchargez le rapport Word (.docx) contenant la synthèse globale du mois de **{mois_annee_str}**."
  )

  if not df_filtered.empty:
    word_buffer = generer_document_synthese(df_filtered, mois_annee_str)

    st.download_button(
        label=f"📄 Télécharger la synthèse ({mois_annee_str})",
        data=word_buffer,
        file_name=f"Synthese_Mensuelle_{selected_month_num}_{selected_year}.docx" if col_date else "Synthese_Globale.docx",
        mime=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
  else:
    st.warning("Aucune donnée disponible pour générer un rapport sur cette période.")


# Point d'entrée standard appelé par app.py
def show(supabase_client=None):
  afficher_vue(supabase_client)


if __name__ == "__main__":
  afficher_vue()
