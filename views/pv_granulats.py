import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import io

# ------------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Granulats pour Béton - Essais & PV",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# INITIALISATION DU SESSION STATE
# ------------------------------------------------------------------------------
STANDARD_SIEVES = [0.063, 0.08, 0.1, 0.125, 0.16, 0.2, 0.25, 0.315, 0.4, 0.5, 0.63, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.15, 4.0, 5.0, 5.6, 6.3, 8.0, 10.0, 12.5, 14.0, 16.0, 20.0, 25.0, 28.0, 31.5, 40.0]

if 'data_granulats' not in st.session_state:
    # Données par défaut pré-remplies basées sur le PV modèle
    st.session_state['data_granulats'] = {
        'GII': {
            'nom': 'Gravillons GII - 10/20',
            'classe': '10/20',
            'sieves': [40.0, 28.0, 20.0, 10.0, 5.0, 0.063],
            'passants': [100.0, 100.0, 95.0, 6.0, 1.0, 0.6],
            'fi': 16.0,
            'la': 26.0,
            'mb': None,
            'mf': None,
            'se': None
        },
        'GI': {
            'nom': 'Gravillons GI - 4/10',
            'classe': '4/10',
            'sieves': [20.0, 14.0, 10.0, 4.0, 2.0, 0.063],
            'passants': [100.0, 100.0, 84.0, 2.0, 1.0, 1.1],
            'fi': 14.0,
            'la': 26.0,
            'mb': None,
            'mf': None,
            'se': None
        },
        'SD': {
            'nom': 'Sable fin 0/0,630 (Dune)',
            'classe': '0/0,63',
            'sieves': [1.26, 0.88, 0.63, 1.0, 0.25, 0.063],
            'passants': [99.0, 98.0, 98.0, 98.0, 82.0, 10.2],
            'fi': None,
            'la': None,
            'mb': 0.7,
            'mf': None,
            'se': None
        },
        'SC': {
            'nom': 'Sable grossier 0/4 (Concassé)',
            'classe': '0/4',
            'sieves': [8.0, 5.6, 4.0, 1.0, 0.25, 0.063],
            'passants': [100.0, 96.0, 92.0, 41.0, 16.0, 9.3],
            'fi': None,
            'la': None,
            'mb': None,
            'mf': 3.50,
            'se': 65.0
        }
    }

if 'historique_pv' not in st.session_state:
    st.session_state['historique_pv'] = []

if 'pv_info' not in st.session_state:
    st.session_state['pv_info'] = {
        'projet': 'CHANTIER LGV / OUVRAGES BETON',
        'client': 'CLIENT X',
        'ref_pv': f"PV-GRAN-{datetime.now().strftime('%Y%m%d-%H%M')}",
        'date': datetime.now().strftime('%d/%m/%Y'),
        'commentaires': "Les essais d'identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545"
    }

# ------------------------------------------------------------------------------
# FONCTIONS UTILES
# ------------------------------------------------------------------------------
def get_passant_at_sieve(sieves, passings, target_sieve):
    """ Calcule ou interpole le passant au tamis cible """
    if target_sieve is None:
        return np.nan
    s_arr = np.array(sieves)
    p_arr = np.array(passings)
    idx_sort = np.argsort(s_arr)
    s_arr = s_arr[idx_sort]
    p_arr = p_arr[idx_sort]
    
    if target_sieve in s_arr:
        return float(p_arr[np.where(s_arr == target_sieve)[0][0]])
    return float(np.interp(target_sieve, s_arr, p_arr))

def compute_D95(sieves, passings):
    """ Détermine D = tamis équivalent correspondant à 95% de passant """
    s_arr = np.array(sieves)
    p_arr = np.array(passings)
    idx_sort = np.argsort(s_arr)
    s_arr = s_arr[idx_sort]
    p_arr = p_arr[idx_sort]
    
    for i in range(len(p_arr) - 1):
        if p_arr[i] <= 95.0 <= p_arr[i+1]:
            if p_arr[i+1] == p_arr[i]:
                return float(s_arr[i])
            d_val = s_arr[i] + (95.0 - p_arr[i]) * (s_arr[i+1] - s_arr[i]) / (p_arr[i+1] - p_arr[i])
            return round(float(d_val), 2)
    
    # Si > 95% partout ou < 95% partout
    closest_idx = (np.abs(p_arr - 95.0)).argmin()
    return round(float(s_arr[closest_idx]), 2)

# ------------------------------------------------------------------------------
# TITRE ET NAVIGATION
# ------------------------------------------------------------------------------
st.title("🏗️ Module Identification des Granulats pour Béton")

tabs = st.tabs([
    "1️⃣ Feuilles d'Essais Complets (GII, GI, SC, SD)",
    "2️⃣ PV d'Identification / Synthèse",
    "3️⃣ Historique & Téléchargement de PV"
])

# ------------------------------------------------------------------------------
# FENÊTRE 1 : FEUILLES D'ESSAIS COMPLETS
# ------------------------------------------------------------------------------
with tabs[0]:
    st.header("Feuilles d'Analyse Granulométrique et Caractéristiques")
    
    selected_mat = st.radio(
        "Sélectionner la fraction d'échantillon :",
        ["GII (10/20)", "GI (4/10)", "SD (0/0,63)", "SC (0/4)"],
        horizontal=True
    )
    
    mat_key_map = {
        "GII (10/20)": "GII",
        "GI (4/10)": "GI",
        "SD (0/0,63)": "SD",
        "SC (0/4)": "SC"
    }
    key = mat_key_map[selected_mat]
    mat_data = st.session_state['data_granulats'][key]
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader(f"Données de l'essai : {mat_data['nom']}")
        
        # Saisie du tableau d'analyse granulométrique
        df_input = pd.DataFrame({
            "Tamis (mm)": mat_data['sieves'],
            "% Passant Cumulé": mat_data['passants']
        })
        
        edited_df = st.data_editor(
            df_input,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{key}"
        )
        
        # Mettre à jour dans le state
        st.session_state['data_granulats'][key]['sieves'] = list(edited_df["Tamis (mm)"])
        st.session_state['data_granulats'][key]['passants'] = list(edited_df["% Passant Cumulé"])
        
        st.markdown("---")
        st.subheader("Caractéristiques complémentaires (Saisie Manuelle)")
        st.info("Laissez vide si l'essai n'est pas applicable pour cette fraction.")
        
        col_a, col_b = st.columns(2)
        with col_a:
            fi_val = st.number_input("Coefficient d'Aplatissement (FI)", value=float(mat_data['fi']) if mat_data['fi'] is not None else 0.0, step=0.1)
            la_val = st.number_input("Los Angeles (LA)", value=float(mat_data['la']) if mat_data['la'] is not None else 0.0, step=0.1)
            mb_val = st.number_input("Valeur de Bleu (MB)", value=float(mat_data['mb']) if mat_data['mb'] is not None else 0.0, step=0.1)
        with col_b:
            mf_val = st.number_input("Module de Finesse (MF)", value=float(mat_data['mf']) if mat_data['mf'] is not None else 0.0, step=0.01)
            se_val = st.number_input("Équivalent de Sable (SE 10)", value=float(mat_data['se']) if mat_data['se'] is not None else 0.0, step=0.1)
            
        # Sauvegarde des saisies manuelles
        st.session_state['data_granulats'][key]['fi'] = fi_val if fi_val > 0 else None
        st.session_state['data_granulats'][key]['la'] = la_val if la_val > 0 else None
        st.session_state['data_granulats'][key]['mb'] = mb_val if mb_val > 0 else None
        st.session_state['data_granulats'][key]['mf'] = mf_val if mf_val > 0 else None
        st.session_state['data_granulats'][key]['se'] = se_val if se_val > 0 else None

    with col2:
        st.subheader("Courbe Granulométrique Individuelle")
        
        d95 = compute_D95(mat_data['sieves'], mat_data['passants'])
        st.metric(label="Tamis D (95% de passant calculé)", value=f"{d95} mm")
        
        fig_ind = go.Figure()
        
        # Sort values
        s_sorted, p_sorted = zip(*sorted(zip(mat_data['sieves'], mat_data['passants'])))
        
        fig_ind.add_trace(go.Scatter(
            x=s_sorted, y=p_sorted,
            mode='lines+markers',
            name=mat_data['nom'],
            line=dict(color='blue', width=2)
        ))
        
        fig_ind.update_layout(
            title=f"Courbe Granulométrique - {mat_data['nom']}",
            xaxis=dict(type="log", title="Tamis (mm)", tickvals=STANDARD_SIEVES),
            yaxis=dict(title="% Passant Cumulé", range=[0, 105]),
            height=420,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_ind, use_container_width=True)

# ------------------------------------------------------------------------------
# FENÊTRE 2 : PV D'IDENTIFICATION / SYNTHÈSE (CONFORME À LA PHOTO)
# ------------------------------------------------------------------------------
with tabs[1]:
    st.header("PV d'Identification des Granulats pour Béton")
    
    # Metadonnées PV
    with st.expander("📝 Entête & Informations du Proces-Verbal", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        st.session_state['pv_info']['projet'] = c1.text_input("Projet / Chantier", st.session_state['pv_info']['projet'])
        st.session_state['pv_info']['client'] = c2.text_input("Client", st.session_state['pv_info']['client'])
        st.session_state['pv_info']['ref_pv'] = c3.text_input("Référence PV", st.session_state['pv_info']['ref_pv'])
        st.session_state['pv_info']['date'] = c4.text_input("Date", st.session_state['pv_info']['date'])

    # Calcul dynamique des paramètres D95
    gii_data = st.session_state['data_granulats']['GII']
    gi_data  = st.session_state['data_granulats']['GI']
    sd_data  = st.session_state['data_granulats']['SD']
    sc_data  = st.session_state['data_granulats']['SC']

    D_gii = compute_D95(gii_data['sieves'], gii_data['passants'])
    D_gi  = compute_D95(gi_data['sieves'], gi_data['passants'])
    D_sd  = compute_D95(sd_data['sieves'], sd_data['passants'])
    D_sc  = compute_D95(sc_data['sieves'], sc_data['passants'])

    # Construction du style du PV style Tableau Photo
    st.markdown("""
    <style>
    .pv-container { background-color: #f8fafc; border: 2px solid #1e3a8a; padding: 10px; border-radius: 5px; }
    .pv-header { background-color: #3b82f6; color: white; text-align: center; font-weight: bold; font-size: 16px; padding: 6px; }
    .pv-sub-header { background-color: #60a5fa; color: white; text-align: center; font-weight: bold; font-size: 13px; padding: 4px; }
    .pv-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 12px; }
    .pv-table th, .pv-table td { border: 1px solid #475569; padding: 4px; text-align: center; }
    .pv-bg-gray { background-color: #e2e8f0; font-weight: bold; }
    .pv-title-row { background-color: #cbd5e1; font-weight: bold; text-align: left; }
    </style>
    """, unsafe_allow_html=True)

    # Affichage du PV sous format HTML structuré comme la photo
    pv_html = f"""
    <div class="pv-container">
        <div class="pv-header">OBJET : IDENTIFICATION DES GRANULATS POUR BETON</div>
        <table class="pv-table">
            <tr style="background-color: #f1f5f9;">
                <td colspan="4"><b>Référence normative</b><br>
                A.G : NF EN 933-1 | Equivalent de sable : NF EN 933-8 | VB : NF EN 933-9<br>
                LOS ANGELES : NF EN 1097-2 | CA : NF EN 933-3</td>
                <td colspan="4"><b>Classe granulaire</b><br>
                Gravillon {gii_data['classe']} | Gravillon {gi_data['classe']}<br>
                Sable SC {sc_data['classe']} | Sable de dune {sd_data['classe']}</td>
            </tr>
            
            <!-- SECTION GII -->
            <tr class="pv-sub-header">
                <td>Désignations</td>
                <td>2D ({2*D_gii:.0f})</td>
                <td>1.4D ({1.4*D_gii:.0f})</td>
                <td>D ({D_gii:.0f})</td>
                <td>d ({D_gii/2:.0f})</td>
                <td>d/2 ({D_gii/4:.0f})</td>
                <td>f (%<63µm)</td>
                <td>FI</td>
                <td>LA</td>
            </tr>
            <tr class="pv-bg-gray">
                <td>Gravillons GII - {gii_data['classe']}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], 2*D_gii):.1f}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], 1.4*D_gii):.0f}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], D_gii):.0f}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], D_gii/2):.0f}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], D_gii/4):.0f}</td>
                <td>{get_passant_at_sieve(gii_data['sieves'], gii_data['passants'], 0.063):.1f}</td>
                <td>{gii_data['fi'] if gii_data['fi'] is not None else '-'}</td>
                <td>{gii_data['la'] if gii_data['la'] is not None else '-'}</td>
            </tr>
            <tr>
                <td>Caractéristique générale de granularité</td>
                <td>100</td>
                <td>98 - 100</td>
                <td>80 - 99</td>
                <td>0 - 20</td>
                <td>0 - 5</td>
                <td>&lt;1,5</td>
                <td>FI20 (Vss 20)</td>
                <td>&lt; 30</td>
            </tr>
            
            <!-- SECTION GI -->
            <tr class="pv-sub-header">
                <td>Désignations</td>
                <td>2D ({2*D_gi:.0f})</td>
                <td>1.4D ({1.4*D_gi:.0f})</td>
                <td>D ({D_gi:.0f})</td>
                <td>d ({D_gi/2.5:.0f})</td>
                <td>d/2 ({D_gi/5:.0f})</td>
                <td>f (%<63µm)</td>
                <td>FI</td>
                <td>LA</td>
            </tr>
            <tr class="pv-bg-gray">
                <td>Gravillons GI - {gi_data['classe']}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], 2*D_gi):.1f}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], 1.4*D_gi):.0f}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], D_gi):.0f}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], D_gi/2.5):.0f}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], D_gi/5):.0f}</td>
                <td>{get_passant_at_sieve(gi_data['sieves'], gi_data['passants'], 0.063):.1f}</td>
                <td>{gi_data['fi'] if gi_data['fi'] is not None else '-'}</td>
                <td>{gi_data['la'] if gi_data['la'] is not None else '-'}</td>
            </tr>
            <tr>
                <td>Caractéristique générale de granularité</td>
                <td>100</td>
                <td>98 - 100</td>
                <td>80 - 99</td>
                <td>0 - 20</td>
                <td>0 - 5</td>
                <td>&lt;1,5</td>
                <td>FI20 (Vss 20)</td>
                <td>&lt; 30</td>
            </tr>

            <!-- SECTION SABLE FIN SD -->
            <tr class="pv-sub-header">
                <td>Désignations</td>
                <td>2D (1,26)</td>
                <td>1,4D (0,88)</td>
                <td>D (0,63)</td>
                <td>% &lt; 1mm</td>
                <td>% &lt; 250µm</td>
                <td>fA (%&lt;63µm)</td>
                <td colspan="2">MB</td>
            </tr>
            <tr class="pv-bg-gray">
                <td>Sable fin {sd_data['classe']}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 1.26):.0f}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 0.88):.0f}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 0.63):.0f}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 1.0):.0f}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 0.25):.0f}</td>
                <td>{get_passant_at_sieve(sd_data['sieves'], sd_data['passants'], 0.063):.1f}</td>
                <td colspan="2">{sd_data['mb'] if sd_data['mb'] is not None else '-'}</td>
            </tr>
            <tr>
                <td>Caractéristique générale de granularité</td>
                <td>100</td>
                <td>95 - 100</td>
                <td>85 - 99</td>
                <td>e 40 (±20)</td>
                <td>e 50 (±25)</td>
                <td>Ls=10 / e 10 (±5)</td>
                <td colspan="2">VSS 2</td>
            </tr>

            <!-- SECTION SABLE GROSSIER SC -->
            <tr class="pv-sub-header">
                <td>Désignations</td>
                <td>2D (8)</td>
                <td>1,4D (5,6)</td>
                <td>D (4)</td>
                <td>% &lt; 1mm</td>
                <td>% &lt; 250µm</td>
                <td>fA (%&lt;63µm)</td>
                <td>Module Finesse CF</td>
                <td>SE (10)</td>
            </tr>
            <tr class="pv-bg-gray">
                <td>Sable grossier {sc_data['classe']}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 8.0):.0f}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 5.6):.0f}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 4.0):.0f}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 1.0):.0f}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 0.25):.0f}</td>
                <td>{get_passant_at_sieve(sc_data['sieves'], sc_data['passants'], 0.063):.1f}</td>
                <td>{sc_data['mf'] if sc_data['mf'] is not None else '-'}</td>
                <td>{sc_data['se'] if sc_data['se'] is not None else '-'}</td>
            </tr>
            <tr>
                <td>Caractéristique générale de granularité</td>
                <td>100</td>
                <td>95 - 100</td>
                <td>85 - 99</td>
                <td>e 40 (±20)</td>
                <td>e 50 (±20)</td>
                <td>Ls=16 / e 10 (±3)</td>
                <td>Li 2.4 / Ls 4.0</td>
                <td>Vsi 60</td>
            </tr>
        </table>
    </div>
    """
    st.markdown(pv_html, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Courbe globale synthétique
    st.subheader("COURBE GRANULOMETRIQUE GLOBALE")
    fig_global = go.Figure()
    
    colors = {'GII': 'blue', 'GI': 'black', 'SC': 'green', 'SD': 'orange'}
    
    for k, d in st.session_state['data_granulats'].items():
        s_s, p_s = zip(*sorted(zip(d['sieves'], d['passants'])))
        fig_global.add_trace(go.Scatter(
            x=s_s, y=p_s,
            mode='lines+markers',
            name=d['nom'],
            line=dict(color=colors[k], width=2)
        ))
        
    fig_global.update_layout(
        xaxis=dict(type="log", title="Tamis (mm)", tickvals=STANDARD_SIEVES),
        yaxis=dict(title="% Passant Cumulé", range=[0, 105]),
        height=450,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_global, use_container_width=True)
    
    # Section Commentaires & Conclusion
    st.subheader("COMMENTAIRES & CONCLUSION")
    st.session_state['pv_info']['commentaires'] = st.text_area(
        "Commentaires sur la conformité :",
        value=st.session_state['pv_info']['commentaires'],
        height=70
    )

# ------------------------------------------------------------------------------
# FENÊTRE 3 : HISTORIQUE ET TÉLÉCHARGEMENT DE PV
# ------------------------------------------------------------------------------
with tabs[2]:
    st.header("Historique et Sauvegarde des PV")
    
    col_btn1, col_btn2 = st.columns([1, 2])
    
    with col_btn1:
        if st.button("💾 Enregistrer le PV actuel dans l'historique", use_container_width=True):
            pv_snapshot = {
                'Ref_PV': st.session_state['pv_info']['ref_pv'],
                'Date': st.session_state['pv_info']['date'],
                'Projet': st.session_state['pv_info']['projet'],
                'Client': st.session_state['pv_info']['client'],
                'D_GII': D_gii,
                'D_GI': D_gi,
                'D_SD': D_sd,
                'D_SC': D_sc,
                'Commentaires': st.session_state['pv_info']['commentaires']
            }
            st.session_state['historique_pv'].append(pv_snapshot)
            st.success(f"PV {pv_snapshot['Ref_PV']} enregistré avec succès !")

    st.markdown("---")
    st.subheader("📋 Historique des Procès-Verbaux Enregistrés")
    
    if len(st.session_state['historique_pv']) > 0:
        df_hist = pd.DataFrame(st.session_state['historique_pv'])
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Aucun PV enregistré pour le moment.")

    st.markdown("---")
    st.subheader("📥 Téléchargement & Exportation")
    
    # Export au format HTML complet
    full_pv_html_export = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{st.session_state['pv_info']['ref_pv']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header-table {{ width: 100%; margin-bottom: 20px; }}
            {pv_html}
            .comments {{ margin-top: 20px; padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h2>PROCES VERBAL D'IDENTIFICATION DES GRANULATS</h2>
        <p><b>Référence PV :</b> {st.session_state['pv_info']['ref_pv']}</p>
        <p><b>Projet :</b> {st.session_state['pv_info']['projet']} | <b>Client :</b> {st.session_state['pv_info']['client']} | <b>Date :</b> {st.session_state['pv_info']['date']}</p>
        <hr>
        {pv_html}
        <div class="comments">
            <b>COMMENTAIRES :</b> {st.session_state['pv_info']['commentaires']}
        </div>
    </body>
    </html>
    """
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        st.download_button(
            label="📄 Télécharger le PV (Format HTML Imprimable / PDF)",
            data=full_pv_html_export,
            file_name=f"{st.session_state['pv_info']['ref_pv']}.html",
            mime="text/html",
            use_container_width=True
        )
        
    with col_dl2:
        # Export Excel des données granulométriques
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            for k, v in st.session_state['data_granulats'].items():
                df_ex = pd.DataFrame({"Tamis (mm)": v['sieves'], "% Passant": v['passants']})
                df_ex.to_excel(writer, sheet_name=k, index=False)
        
        st.download_button(
            label="📊 Télécharger les Données Granulométriques (Excel)",
            data=output_excel.getvalue(),
            file_name=f"donnees_granulats_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
