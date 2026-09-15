import io
import datetime
import pandas as pd
from docx import Document
import streamlit as st


def generer_document_synthese(dict_dfs_filtres, mois_annee_str):
  """Génère un fichier Word en mémoire contenant un rapport structuré

  avec des tableaux propres et bien mis en page pour chaque type d'essai.
  """
  doc = Document()

  # En-tête du document
  doc.add_heading("Rapport de Synthèse Mensuelle - Smart Control Béton", level=1)
  doc.add_paragraph(
      f"Synthèse globale des essais enregistrés pour la période : {mois_annee_str}"
  )
  doc.add_paragraph(
      "Ce rapport présente les extraits des tableaux de synthèse par type"
      " d'essai."
  )

  donnees_presentes = False

  for nom_type, df in dict_dfs_filtres.items():
    if not df.empty:
      donnees_presentes = True
      doc.add_heading(f"Type d'essai : {nom_type}", level=2)
      doc.add_paragraph(f"Nombre d'enregistrements : {len(df)}")

      # Nettoyage des colonnes pour ne garder que les informations pertinentes
      colonnes_a_afficher = [
          c
          for c in df.columns
          if not c.startswith("_") and c.lower() not in ["user_id"]
      ]
      if not colonnes_a_afficher:
        colonnes_a_afficher = list(df.columns)

      df_to_show = df[colonnes_a_afficher]

      # Création du tableau Word avec un style de grille propre
      table = doc.add_table(rows=1, cols=len(df_to_show.columns))
      table.style = "Table Grid"

      hdr_cells = table.rows[0].cells
      for i, column_name in enumerate(df_to_show.columns):
        hdr_cells[i].text = str(column_name)

      # Remplissage des lignes avec protection contre les textes trop longs
      for _, row in df_to_show.iterrows():
        row_cells = table.add_row().cells
        for i, val in enumerate(row):
          val_str = "" if pd.isna(val) else str(val)
          if len(val_str) > 40:
            val_str = val_str[:37] + "..."
          row_cells[i].text = val_str

      doc.add_paragraph("")  # Espacement entre les tableaux

  if not donnees_presentes:
    doc.add_paragraph("Aucun essai disponible pour cette période.")

  # Sauvegarde dans un buffer mémoire
  buffer = io.BytesIO()
  doc.save(buffer)
  buffer.seek(0)
  return buffer


def afficher_vue(supabase_client=None):
  st.subheader("📜 Historique & Synthèse Mensuelle Globale")
  st.write(
      "Consultez les synthèses mensuelles par type d'essai (Plaque, Teneur en"
      " eau, Compacité, etc.) filtrées par mois."
  )

  # Définition des tables à interroger dans Supabase
  tables_essais = [
      ("Essai à la Plaque", "essais_plaque"),
      ("Teneur en Eau", "essais_teneur_eau"),
      ("Compacité", "essais_compacite"),
      ("Granulats pour Béton", "pv_granulats"),
      ("Identification Matériau", "essais_identification"),
  ]

  dict_dfs_bruts = {}

  if supabase_client:
    for nom_type, table_name in tables_essais:
      try:
        res = supabase_client.table(table_name).select("*").execute()
        if res.data:
          dict_dfs_bruts[nom_type] = pd.DataFrame(res.data)
      except Exception:
        pass

  # Données de démonstration si aucune connexion ou tables vides
  if not dict_dfs_bruts:
    dict_dfs_bruts = {
        "Essai à la Plaque": pd.DataFrame({
            "ID": [1, 2],
            "Date": ["2026-09-05", "2026-08-20"],
            "Ouvrage": ["PRA 0500", "PRO 0636"],
            "Module_K": [120, 110],
            "Statut": ["Validé", "En attente"],
        }),
        "Compacité": pd.DataFrame({
            "ID": [1, 2, 3],
            "Date": ["2026-09-01", "2026-09-15", "2026-06-10"],
            "Ouvrage": ["PRO 0636", "PRO 0745", "PRO 0636"],
            "Densite_Seche": [2.35, 2.40, 2.28],
            "Statut": ["Validé", "Validé", "Validé"],
        }),
        "Teneur en Eau": pd.DataFrame({
            "ID": [1],
            "Date": ["2026-09-10"],
            "Ouvrage": ["PRO 0745"],
            "Teneur_Eau_pct": [5.2],
            "Statut": ["Validé"],
        }),
    }

  # --- Sélecteur d'année et de mois ---
  st.markdown("### 🔍 Sélection de la Période")
  col1, col2 = st.columns(2)

  toutes_les_dates = []
  for df in dict_dfs_bruts.values():
    col_date_cands = [c for c in df.columns if "date" in c.lower() or "created" in c.lower()]
    if col_date_cands:
      parsed = pd.to_datetime(df[col_date_cands[0]], errors="coerce")
      toutes_les_dates.extend(parsed.dropna().tolist())

  if toutes_les_dates:
    s_dates = pd.Series(toutes_les_dates)
    annees_dispo = sorted(s_dates.dt.year.unique().tolist(), reverse=True)
  else:
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

  mois_annee_str = f"{mois_noms[selected_month_num]} {selected_year}"

  st.markdown("---")
  st.markdown(f"### 📊 Synthèse par Type d'Essai pour : **{mois_annee_str}**")

  dict_dfs_filtres = {}
  total_essais_mois = 0

  for nom_type, df in dict_dfs_bruts.items():
    if df.empty:
      continue
    
    col_date_cands = [c for c in df.columns if "date" in c.lower() or "created" in c.lower()]
    if col_date_cands:
      c_date = col_date_cands[0]
      df_copy = df.copy()
      df_copy[c_date] = pd.to_datetime(df_copy[c_date], errors="coerce")
      df_f = df_copy[
          (df_copy[c_date].dt.year == selected_year) &
          (df_copy[c_date].dt.month == selected_month_num)
      ].copy()
      df_f[c_date] = df_f[c_date].dt.strftime("%Y-%m-%d")
    else:
      df_f = df.copy()

    dict_dfs_filtres[nom_type] = df_f
    total_essais_mois += len(df_f)

    with st.expander(f"📌 {nom_type} ({len(df_f)} essai(s))", expanded=len(df_f) > 0):
      if not df_f.empty:
        st.dataframe(df_f, use_container_width=True)
      else:
        st.info(f"Aucun enregistrement pour {nom_type} en {mois_annee_str}.")

  st.markdown("---")
  st.markdown(f"**Total général des essais pour le mois :** {total_essais_mois}")

  # --- Section Export Word ---
  st.markdown("### 📥 Exporter le Rapport de Synthèse Mensuelle")
  st.write(
      f"Téléchargez le rapport Word (.docx) structuré contenant les extraits"
      f" distincts de chaque tableau pour **{mois_annee_str}**."
  )

  if total_essais_mois > 0:
    word_buffer = generer_document_synthese(dict_dfs_filtres, mois_annee_str)

    st.download_button(
        label=f"📄 Télécharger le Rapport Mensuel ({mois_annee_str})",
        data=word_buffer,
        file_name=f"Rapport_Synthese_Mensuelle_{selected_month_num}_{selected_year}.docx",
        mime=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
  else:
    st.warning("Aucune donnée disponible pour générer un rapport sur cette période.")


def show(supabase_client=None):
  afficher_vue(supabase_client)


if __name__ == "__main__":
  afficher_vue()
