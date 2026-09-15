import io
from docx import Document
import streamlit as st
# Supposons que vous récupérez vos données de Supabase dans un DataFrame pandas
# import pandas as pd


def generer_document_synthese(df_essais):
  doc = Document()

  # Titre du document
  doc.add_heading("Rapport de Synthèse - Smart Control Béton", level=1)
  doc.add_paragraph(
      "Ce document présente la synthèse globale de tous les essais enregistrés"
      " dans l'application."
  )

  # Ajout d'un tableau récapitulatif
  doc.add_heading("Liste des Essais", level=2)

  # Création du tableau dans Word
  table = doc.add_table(rows=1, cols=len(df_essais.columns))
  hdr_cells = table.rows[0].cells
  for i, column_name in enumerate(df_essais.columns):
    hdr_cells[i].text = str(column_name)

  # Remplissage des lignes
  for _, row in df_essais.iterrows():
    row_cells = table.add_row().cells
    for i, val in enumerate(row):
      row_cells[i].text = str(val)

  # Sauvegarde dans un buffer mémoire (évite de créer un fichier physique sur le serveur)
  buffer = io.BytesIO()
  doc.save(buffer)
  buffer.seek(0)
  return buffer


# --- Intégration dans l'interface Streamlit ---
st.subheader("📄 Export de la Synthèse Globale")

# Exemple de DataFrame (à remplacer par vos requêtes Supabase)
# df_global = fetch_data_from_supabase()

if (
    st.button("Générer le fichier Word de synthèse")
    # and not df_global.empty
):
  # Appel de la fonction de génération
  # file_buffer = generer_document_synthese(df_global)

  # st.download_button(
  #     label="📥 Télécharger le fichier Word (.docx)",
  #     data=file_buffer,
  #     file_name="Synthese_Essais_SmartControlBeton.docx",
  #     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  # )
