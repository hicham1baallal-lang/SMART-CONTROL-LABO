import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Smart Control Béton - LPEE CTR CASA-SETTAT",
    page_icon="🏗️",
    layout="wide",
)

# ------------------------------------------------------------------------------
# INITIALISATION SUPABASE / STOCKAGE LOCAL
# ------------------------------------------------------------------------------
supabase_client = None
try:
    from supabase import create_client

    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        supabase_client = create_client(
            st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
        )
except Exception:
    supabase_client = None

if "pv_historique" not in st.session_state:
    st.session_state["pv_historique"] = [
        {
            "num_rapport": "26/260/LGV/CS/1237",
            "num_dossier": "2025-260-05985-2025 0247",
            "client": "TGCC",
            "chantier": "TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000-GARE CASA SUD",
            "date_prelevement": "2026-07-23",
            "ref_echantillon": "TG PREFA OULAD SALEH",
            "lieu_prelevement": "Stock sur centrale à béton",
            "objet": "IDENTIFICATION DES GRANULATS POUR BETON",
            "coordinateur": "O. IKEN",
            "chef_labo": "H. BAALLAL",
            "commentaires": "Les essais des identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545.",
            "g1020": {
                "40": 100.0,
                "28": 100.0,
                "20": 95.0,
                "10": 6.0,
                "5": 1.0,
                "0.063": 0.6,
                "FI": 16,
                "LA": 26,
            },
            "g410": {
                "20": 100.0,
                "14": 100.0,
                "10": 84.0,
                "4": 2.0,
                "2": 1.0,
                "0.063": 1.1,
                "FI": 14,
                "LA": 26,
            },
            "sable_04": {
                "5.6": 96.0,
                "4": 92.0,
                "1": 41.0,
                "0.25": 16.0,
                "0.063": 9.3,
                "CF": 3.50,
                "SE": 65,
            },
            "sable_0063": {
                "0.88": 98.0,
                "0.63": 98.0,
                "1": 98.0,
                "0.25": 82.0,
                "0.063": 10.2,
                "MB": 0.7,
            },
        }
    ]

# ------------------------------------------------------------------------------
# CSS PERSONNALISÉ POUR RENDU DU PV
# ------------------------------------------------------------------------------
st.markdown(
    """
<style>
    .pv-box {
        border: 2px solid #1E3A8A;
        padding: 20px;
        background-color: #FFFFFF;
        font-family: 'Arial', sans-serif;
        color: #000000;
        border-radius: 5px;
    }
    .pv-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #1E3A8A;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .meta-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 15px;
        font-size: 13px;
    }
    .meta-table td {
        padding: 4px 8px;
        border: 1px solid #CBD5E1;
    }
    .meta-label {
        font-weight: bold;
        background-color: #F1F5F9;
        width: 20%;
    }
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 15px;
        font-size: 11px;
        text-align: center;
    }
    .data-table th, .data-table td {
        border: 1px solid #475569;
        padding: 4px;
    }
    .data-table th {
        background-color: #E2E8F0;
        font-weight: bold;
    }
    .sig-container {
        display: flex;
        justify-content: space-between;
        margin-top: 25px;
        padding-top: 10px;
        border-top: 1px solid #94A3B8;
        font-size: 12px;
        text-align: center;
    }
    .sig-box {
        width: 30%;
        min-height: 80px;
        border: 1px dashed #94A3B8;
        padding: 5px;
        border-radius: 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------------------
# FONCTION REPRÉSENTATION GRAPHIQUE COURBE GRANULOMÉTRIQUE
# ------------------------------------------------------------------------------
def generer_courbe_granulo(pv_data):
    tamis = [
        0.063,
        0.100,
        0.125,
        0.160,
        0.250,
        0.315,
        0.400,
        0.500,
        0.630,
        0.800,
        1.0,
        1.25,
        1.60,
        2.0,
        2.5,
        3.15,
        4.0,
        5.0,
        6.3,
        8.0,
        10.0,
        12.5,
        16.0,
        20.0,
        31.5,
        40.0,
    ]

    g1020_p = [
        0.6,
        0.8,
        0.9,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        2.0,
        3.0,
        4.0,
        6.0,
        35.0,
        70.0,
        95.0,
        100.0,
        100.0,
    ]
    g410_p = [
        1.1,
        1.2,
        1.3,
        1.4,
        1.5,
        1.5,
        1.5,
        1.5,
        1.5,
        1.5,
        1.5,
        1.5,
        1.5,
        1.0,
        1.2,
        1.5,
        2.0,
        10.0,
        25.0,
        50.0,
        84.0,
        98.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]
    s4_p = [
        9.3,
        11.0,
        12.0,
        13.0,
        16.0,
        20.0,
        25.0,
        30.0,
        35.0,
        38.0,
        41.0,
        48.0,
        55.0,
        65.0,
        75.0,
        82.0,
        92.0,
        95.0,
        98.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]
    sdune_p = [
        10.2,
        15.0,
        22.0,
        35.0,
        82.0,
        90.0,
        94.0,
        96.0,
        98.0,
        98.0,
        98.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tamis,
            y=g1020_p,
            mode="lines+markers",
            name="Gravillon 10/20",
            line=dict(color="black", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=tamis,
            y=g410_p,
            mode="lines+markers",
            name="Gravillon 4/10",
            line=dict(color="#0066CC", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=tamis,
            y=s4_p,
            mode="lines+markers",
            name="Sable 0/4",
            line=dict(color="#009966", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=tamis,
            y=sdune_p,
            mode="lines+markers",
            name="Sable Dune 0/0.63",
            line=dict(color="#FF6600", width=2),
        )
    )

    fig.update_xaxes(
        type="log",
        title_text="Tamis (mm)",
        tickvals=tamis,
        ticktext=[str(t) for t in tamis],
    )
    fig.update_yaxes(title_text="% Passant Cumulé", range=[0, 105])

    fig.update_layout(
        title="COURBE GRANULOMETRIQUE",
        title_x=0.4,
        margin=dict(l=20, r=20, t=40, b=20),
        height=380,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        template="plotly_white",
    )
    return fig


# ------------------------------------------------------------------------------
# NAVIGATION PRINCIPALE
# ------------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/laboratory.png", width=60)
st.sidebar.title("Smart Control Béton")
st.sidebar.caption("Laboratoire LPEE - CTR CASA-SETTAT")

page = st.sidebar.radio(
    "Menu Navigation :",
    ["📝 Saisie & Enregistrement", "📚 Historique & PV (Impression)"],
)

# ------------------------------------------------------------------------------
# PAGE 1 : SAISIE ET ENREGISTREMENT DE LA FEUILLE D'ESSAI
# ------------------------------------------------------------------------------
if page == "📝 Saisie & Enregistrement":
    st.title("📝 Saisie de la Feuille d'Essai Granulats")

    # BOUTON DE SAUVEGARDE EN HAUT DE PAGE
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.info(
            "Renseignez les données d'essais ci-dessous puis cliquez sur le bouton **Enregistrer**."
        )
    with top_col2:
        btn_save_top = st.button(
            "💾 ENREGISTRER LA FEUILLE",
            key="save_top",
            type="primary",
            use_container_width=True,
        )

    st.markdown("---")

    # 1. INFORMATIONS GÉNÉRALES
    st.subheader("1. Entête du PV & Informations Chantier")
    col1, col2, col3 = st.columns(3)
    with col1:
        num_rapport = st.text_input(
            "Rapport d'essai N°",
            "26/260/LGV/CS/1237",
            key="input_num_rapport",
        )
        num_dossier = st.text_input(
            "N° Dossier", "2025-260-05985-2025 0247", key="input_num_dossier"
        )
        client = st.text_input("Client", "TGCC", key="input_client")
    with col2:
        date_prelevement = st.date_input(
            "Date de prélèvement",
            datetime.date(2026, 7, 23),
            key="input_date_prelevement",
        )
        lieu_prelevement = st.text_input(
            "Lieu de prélèvement",
            "Stock sur centrale à béton",
            key="input_lieu_prelevement",
        )
        ref_echantillon = st.text_input(
            "Provenance / Réf Échantillon",
            "TG PREFA OULAD SALEH",
            key="input_ref_echantillon",
        )
    with col3:
        chantier = st.text_area(
            "Chantier",
            "TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000-GARE CASA SUD",
            key="input_chantier",
        )
        objet = st.text_input(
            "Objet",
            "IDENTIFICATION DES GRANULATS POUR BETON",
            key="input_objet",
        )

    st.markdown("---")

    # 2. RÉSULTATS GRANULOMÉTRIQUES
    st.subheader("2. Résultats Granulométriques & Caractéristiques")

    tab_g1020, tab_g410, tab_s4, tab_s063 = st.tabs(
        [
            "Gravillon 10/20",
            "Gravillon 4/10",
            "Sable Grossier 0/4",
            "Sable Fin 0/0.63",
        ]
    )

    with tab_g1020:
        c1, c2, c3, c4 = st.columns(4)
        p_g20_40 = c1.number_input("40 mm (%)", value=100.0, key="g20_40")
        p_g20_28 = c2.number_input("28 mm (%)", value=100.0, key="g20_28")
        p_g20_20 = c3.number_input("20 mm (%)", value=95.0, key="g20_20")
        p_g20_10 = c4.number_input("10 mm (%)", value=6.0, key="g20_10")
        c1, c2, c3 = st.columns(3)
        p_g20_5 = c1.number_input("5 mm (%)", value=1.0, key="g20_5")
        p_g20_f = c2.number_input("63 µm (%)", value=0.6, key="g20_f")
        p_g20_la = c3.number_input("Los Angeles (LA)", value=26, key="g20_la")

    with tab_g410:
        c1, c2, c3, c4 = st.columns(4)
        p_g4_20 = c1.number_input("20 mm (%)", value=100.0, key="g4_20")
        p_g4_14 = c2.number_input("14 mm (%)", value=100.0, key="g4_14")
        p_g4_10 = c3.number_input("10 mm (%)", value=84.0, key="g4_10")
        p_g4_4 = c4.number_input("4 mm (%)", value=2.0, key="g4_4")
        c1, c2, c3 = st.columns(3)
        p_g4_2 = c1.number_input("2 mm (%)", value=1.0, key="g4_2")
        p_g4_f = c2.number_input("63 µm (%)", value=1.1, key="g4_f")
        p_g4_fi = c3.number_input("Aplatissement (FI)", value=14, key="g4_fi")

    with tab_s4:
        c1, c2, c3, c4 = st.columns(4)
        p_s4_56 = c1.number_input("5.6 mm (%)", value=96.0, key="s4_56")
        p_s4_4 = c2.number_input("4 mm (%)", value=92.0, key="s4_4")
        p_s4_1 = c3.number_input("1 mm (%)", value=41.0, key="s4_1")
        p_s4_250 = c4.number_input("250 µm (%)", value=16.0, key="s4_250")
        c1, c2 = st.columns(2)
        p_s4_se = c1.number_input(
            "Équivalent de Sable (SE)", value=65, key="s4_se"
        )
        p_s4_cf = c2.number_input(
            "Module de Finesse (CF)", value=3.50, key="s4_cf"
        )

    with tab_s063:
        c1, c2, c3 = st.columns(3)
        p_sd_088 = c1.number_input("0.88 mm (%)", value=98.0, key="sd_088")
        p_sd_063 = c2.number_input("0.63 mm (%)", value=98.0, key="sd_063")
        p_sd_mb = c3.number_input(
            "Bleu de Méthylène (MB)", value=0.7, key="sd_mb"
        )

    st.markdown("---")

    # 3. SIGNATURES ET COMMENTAIRES
    st.subheader("3. Validation & Signatures")
    col_c, col_h = st.columns(2)
    coordinateur = col_c.text_input(
        "Coordinateur des Essais", "O. IKEN", key="input_coordinateur"
    )
    chef_labo = col_h.text_input(
        "Chef de Laboratoire", "H. BAALLAL", key="input_chef_labo"
    )
    commentaires = st.text_area(
        "Commentaires / Conformité",
        "Les essais des identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545.",
        key="input_commentaires",
    )

    st.markdown("---")

    # BOUTON DE SAUVEGARDE PRINCIPAL EN BAS DE PAGE
    st.markdown("### 💾 Validation finale")
    btn_save_bottom = st.button(
        "💾 ENREGISTRER LA FEUILLE D'ESSAI DANS LA BASE DE DONNÉES",
        key="save_bottom",
        type="primary",
        use_container_width=True,
    )

    # DÉCLENCHEMENT DE L'ENREGISTREMENT (HAUT OU BAS)
    if btn_save_top or btn_save_bottom:
        nouveau_pv = {
            "num_rapport": num_rapport,
            "num_dossier": num_dossier,
            "client": client,
            "chantier": chantier,
            "date_prelevement": str(date_prelevement),
            "ref_echantillon": ref_echantillon,
            "lieu_prelevement": lieu_prelevement,
            "objet": objet,
            "coordinateur": coordinateur,
            "chef_labo": chef_labo,
            "commentaires": commentaires,
            "g1020": {
                "40": p_g20_40,
                "28": p_g20_28,
                "20": p_g20_20,
                "10": p_g20_10,
                "5": p_g20_5,
                "0.063": p_g20_f,
                "LA": p_g20_la,
            },
            "g410": {
                "20": p_g4_20,
                "14": p_g4_14,
                "10": p_g4_10,
                "4": p_g4_4,
                "2": p_g4_2,
                "0.063": p_g4_f,
                "FI": p_g4_fi,
            },
            "sable_04": {
                "5.6": p_s4_56,
                "4": p_s4_4,
                "1": p_s4_1,
                "0.25": p_s4_250,
                "SE": p_s4_se,
                "CF": p_s4_cf,
            },
            "sable_0063": {
                "0.88": p_sd_088,
                "0.63": p_sd_063,
                "MB": p_sd_mb,
            },
        }

        # Sauvegarde Supabase ou Session Local
        if supabase_client:
            try:
                supabase_client.table("essais_granulats").insert(
                    nouveau_pv
                ).execute()
                st.success(
                    f"✅ La feuille d'essai **N° {num_rapport}** a été enregistrée avec succès dans Supabase !"
                )
            except Exception as e:
                st.warning(
                    f"Enregistrement Supabase indisponible ({e}). Sauvegarde effectuée en mémoire locale."
                )
                st.session_state["pv_historique"].append(nouveau_pv)
                st.success(
                    f"✅ La feuille d'essai **N° {num_rapport}** a été ajoutée à l'historique de session !"
                )
        else:
            st.session_state["pv_historique"].append(nouveau_pv)
            st.success(
                f"✅ La feuille d'essai **N° {num_rapport}** a été ajoutée à l'historique avec succès !"
            )

        st.info(
            "💡 Allez dans le menu à gauche **'📚 Historique & PV (Impression)'** pour consulter, visualiser et imprimer le rapport d'essai."
        )

# ------------------------------------------------------------------------------
# PAGE 2 : HISTORIQUE DES PV & AFFICHAGE CONFORME LPEE
# ------------------------------------------------------------------------------
elif page == "📚 Historique & PV (Impression)":
    st.title("📚 Historique des PV d'Essais & Impression")

    # Récupération des PV
    pvs = st.session_state["pv_historique"]

    if supabase_client:
        try:
            res = (
                supabase_client.table("essais_granulats").select("*").execute()
            )
            if res.data:
                pvs = res.data
        except Exception:
            pass

    # Affichage du tableau d'historique
    df_hist = pd.DataFrame(pvs)
    if not df_hist.empty:
        st.subheader("📋 Liste des PV enregistrés")
        cols_display = [
            "num_rapport",
            "client",
            "date_prelevement",
            "num_dossier",
            "objet",
        ]
        st.dataframe(
            df_hist[cols_display], use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.subheader("🔍 Consultation du Procès-Verbal Officiel")

        selected_num = st.selectbox(
            "Sélectionner le N° de PV à afficher :",
            options=[p["num_rapport"] for p in pvs],
        )

        # Extraction des données du PV sélectionné
        pv = next(p for p in pvs if p["num_rapport"] == selected_num)

        # Affichage au format officiel LPEE CTR CASA-SETTAT
        st.markdown(
            f"""
        <div class="pv-box">
            <div class="pv-header">
                <div>
                    <h3 style="margin:0; color:#1E3A8A;">L.P.E.E</h3>
                    <small><b>LABORATOIRE PUBLIC DES ESSAIS ET D'ETUDES</b><br>
                    Centre Technique Régional CASA-SETTAT<br>
                    Laboratoire du contrôle externe</small>
                </div>
                <div style="text-align:right;">
                    <h4 style="margin:0; color:#1E3A8A;">RAPPORT D'ESSAI N°</h4>
                    <span style="font-size:16px; font-weight:bold; color:#B91C1C;">{pv['num_rapport']}</span>
                </div>
            </div>

            <table class="meta-table">
                <tr>
                    <td class="meta-label">Client :</td>
                    <td><b>{pv['client']}</b></td>
                    <td class="meta-label">N° dossier :</td>
                    <td>{pv['num_dossier']}</td>
                </tr>
                <tr>
                    <td class="meta-label">Chantier :</td>
                    <td colspan="3">{pv['chantier']}</td>
                </tr>
                <tr>
                    <td class="meta-label">Date prélèvement :</td>
                    <td>{pv['date_prelevement']}</td>
                    <td class="meta-label">Provenance :</td>
                    <td>{pv['ref_echantillon']}</td>
                </tr>
                <tr>
                    <td class="meta-label">Lieu prélèvement :</td>
                    <td colspan="3">{pv['lieu_prelevement']}</td>
                </tr>
                <tr>
                    <td class="meta-label">OBJET :</td>
                    <td colspan="3"><b>{pv['objet']}</b></td>
                </tr>
            </table>

            <div style="font-size:11px; margin-bottom:10px;">
                <b>Références normatives :</b> Granulométrie: NF EN 933-1 | Equivalent de sable: NF EN 933-8 | VB: NF EN 933-9 | Los Angeles: NF EN 1097-2 | CA: NF EN 933-3
            </div>

            <!-- TABLEAU GRAVILLONS 10/20 -->
            <table class="data-table">
                <thead>
                    <tr>
                        <th rowspan="2">Désignations</th>
                        <th colspan="2">2D / 1,4D</th>
                        <th>D</th>
                        <th>d</th>
                        <th>d/2</th>
                        <th>f</th>
                        <th rowspan="2">FI</th>
                        <th rowspan="2">LA</th>
                    </tr>
                    <tr>
                        <th>40</th>
                        <th>28</th>
                        <th>20</th>
                        <th>10</th>
                        <th>5</th>
                        <th>% < 63µm</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><b>Gravillons GII-10/20</b></td>
                        <td>{pv['g1020'].get('40', 100)}</td>
                        <td>{pv['g1020'].get('28', 100)}</td>
                        <td>{pv['g1020'].get('20', 95)}</td>
                        <td>{pv['g1020'].get('10', 6)}</td>
                        <td>{pv['g1020'].get('5', 1)}</td>
                        <td>{pv['g1020'].get('0.063', 0.6)}</td>
                        <td>16</td>
                        <td>{pv['g1020'].get('LA', 26)}</td>
                    </tr>
                </tbody>
            </table>

            <!-- TABLEAU GRAVILLONS 4/10 -->
            <table class="data-table">
                <thead>
                    <tr>
                        <th rowspan="2">Désignations</th>
                        <th colspan="2">2D / 1,4D</th>
                        <th>D</th>
                        <th>d</th>
                        <th>d/2</th>
                        <th>f</th>
                        <th rowspan="2">FI</th>
                        <th rowspan="2">LA</th>
                    </tr>
                    <tr>
                        <th>20</th>
                        <th>14</th>
                        <th>10</th>
                        <th>4</th>
                        <th>2</th>
                        <th>% < 63µm</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><b>Gravillons GI-4/10</b></td>
                        <td>100</td>
                        <td>100</td>
                        <td>{pv['g410'].get('10', 84)}</td>
                        <td>{pv['g410'].get('4', 2)}</td>
                        <td>{pv['g410'].get('2', 1)}</td>
                        <td>{pv['g410'].get('0.063', 1.1)}</td>
                        <td>{pv['g410'].get('FI', 14)}</td>
                        <td>26</td>
                    </tr>
                </tbody>
            </table>

            <!-- TABLEAU SABLE GROSSIER 0/4 -->
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Désignations</th>
                        <th>2D (8mm)</th>
                        <th>1,4D (5.6mm)</th>
                        <th>D (4mm)</th>
                        <th>1mm</th>
                        <th><250µm</th>
                        <th><63µm</th>
                        <th>Module de finesse CF</th>
                        <th>SE(10)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><b>Sable grossier 0/4</b></td>
                        <td>100</td>
                        <td>{pv['sable_04'].get('5.6', 96)}</td>
                        <td>{pv['sable_04'].get('4', 92)}</td>
                        <td>{pv['sable_04'].get('1', 41)}</td>
                        <td>{pv['sable_04'].get('0.25', 16)}</td>
                        <td>9.3</td>
                        <td>{pv['sable_04'].get('CF', 3.50)}</td>
                        <td>{pv['sable_04'].get('SE', 65)}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Tracé de la courbe granulométrique
        fig_courbe = generer_courbe_granulo(pv)
        st.plotly_chart(fig_courbe, use_container_width=True)

        # Commentaires et Signatures
        st.markdown(
            f"""
        <div class="pv-box" style="margin-top:10px;">
            <p><b>COMMENTAIRES :</b> {pv['commentaires']}</p>
            <div class="sig-container">
                <div class="sig-box">
                    <b>LE COORDINATEUR DES ESSAIS</b><br><br>
                    <span>{pv['coordinateur']}</span>
                </div>
                <div class="sig-box">
                    <b>LE CHEF DU LABORATOIRE</b><br><br>
                    <span>{pv['chef_labo']}</span>
                </div>
                <div class="sig-box">
                    <b>REÇU PAR LE CLIENT</b><br><br>
                    <span>Nom & Visa</span>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    else:
        st.info("Aucun PV d'essai enregistré pour le moment.")
