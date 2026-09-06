import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import io

# ------------------------------------------------------------------------------
# CONSTANTES & FONCTIONS UTILES
# ------------------------------------------------------------------------------
STANDARD_SIEVES = [0.063, 0.08, 0.1, 0.125, 0.16, 0.2, 0.25, 0.315, 0.4, 0.5, 0.63, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.15, 4.0, 5.0, 5.6, 6.3, 8.0, 10.0, 12.5, 14.0, 16.0, 20.0, 25.0, 28.0, 31.5, 40.0]

def update_passants(mat_data):
    """Calcule les passants à partir des masses (Méthode NF EN 933-1)"""
    M1 = mat_data.get('M1', 1000.0)
    refus = mat_data.get('refus', [0.0]*len(mat_data['sieves']))
    
    if M1 > 0:
        pct_refus = [(r / M1) * 100 for r in refus]
        pct_refus_cum = np.cumsum(pct_refus)
        passants = [100.0 - c for c in pct_refus_cum]
        
        # Application de la règle d'arrondi (Nota de la norme) :
        # Entier le plus proche sauf pour le tamis 0.063 mm (1 décimale)
        passants_fmt = []
        for s, p in zip(mat_data['sieves'], passants):
            if s == 0.063:
                passants_fmt.append(max(0.0, round(p, 1)))
            else:
                passants_fmt.append(max(0.0, round(p)))
        mat_data['passants'] = passants_fmt
    else:
        mat_data['passants'] = [100.0] * len(mat_data['sieves'])

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
    
    closest_idx = (np.abs(p_arr - 95.0)).argmin()
    return round(float(s_arr[closest_idx]), 2)

# ------------------------------------------------------------------------------
# FONCTION PRINCIPALE
# ------------------------------------------------------------------------------
def show(supabase_client=None, can_edit=False, is_admin=False, **kwargs):
    # INITIALISATION DU SESSION STATE
    if 'data_granulats' not in st.session_state:
        st.session_state['data_granulats'] = {
            'GII': {
                'nom': 'Gravillons GII - 10/20',
                'classe': '10/20',
                # Données exactes tirées de la feuille de calcul LPEE (11/04/2025)
                'sieves': [100, 80, 63, 50, 40, 31.5, 25, 20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063],
                'refus': [0, 0, 0, 0, 0, 0, 0, 199.7, 2200.3, 732.7, 308.7, 424, 163.2, 45, 6.9, 2.1, 0.2, 0.1, 0.2, 0.2, 0.1, 0, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0, 0.2, 0.1, 0.1, 0.1, 0.1],
                'M1': 4110.5, 'M2': 4095.2, 'P': 1.3,
                'passants': [], # Calculé dynamiquement
                'fi': 16.0, 'la': 26.0, 'mb': None, 'mf': None, 'se': None
            },
            'GI': {
                'nom': 'Gravillons GI - 4/10',
                'classe': '4/10',
                'sieves': [20.0, 14.0, 10.0, 4.0, 2.0, 0.063],
                'refus': [0.0, 0.0, 320.0, 1640.0, 20.0, 10.0], # Calculé pour simuler l'ancien PV
                'M1': 2000.0, 'M2': 1990.0, 'P': 0.0,
                'passants': [], 
                'fi': 14.0, 'la': 26.0, 'mb': None, 'mf': None, 'se': None
            },
            'SD': {
                'nom': 'Sable fin 0/0,630 (Dune)',
                'classe': '0/0,63',
                'sieves': [1.26, 1.0, 0.88, 0.63, 0.25, 0.063],
                'refus': [10.0, 10.0, 0.0, 0.0, 160.0, 718.0],
                'M1': 1000.0, 'M2': 900.0, 'P': 2.0,
                'passants': [],
                'fi': None, 'la': None, 'mb': 0.7, 'mf': None, 'se': None
            },
            'SC': {
                'nom': 'Sable grossier 0/4 (Concassé)',
                'classe': '0/4',
                'sieves': [8.0, 5.6, 4.0, 1.0, 0.25, 0.063],
                'refus': [0.0, 40.0, 40.0, 510.0, 250.0, 67.0],
                'M1': 1000.0, 'M2': 910.0, 'P': 3.0,
                'passants': [],
                'fi': None, 'la': None, 'mb': None, 'mf': 3.50, 'se': 65.0
            }
        }

    # S'assurer que les passants sont à jour pour tous les matériaux au chargement
    for k in st.session_state['data_granulats'].keys():
        update_passants(st.session_state['data_granulats'][k])

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

    st.title("🏗️ Module Identification des Granulats pour Béton")
    
    if not can_edit:
        st.info("👁️ **Mode Consultation** : Vous êtes en lecture seule.")

    tabs = st.tabs([
        "1️⃣ Feuilles d'Essais Complets",
        "2️⃣ PV d'Identification / Synthèse",
        "3️⃣ Historique & Téléchargement de PV"
    ])

    # ------------------------------------------------------------------------------
    # FENÊTRE 1 : FEUILLES D'ESSAIS COMPLETS (ADAPTÉE AU FORMAT LABORATOIRE)
    # ------------------------------------------------------------------------------
    with tabs[0]:
        st.header("Feuilles d'Analyse Granulométrique et Caractéristiques")
        
        selected_mat = st.radio(
            "Sélectionner la fraction d'échantillon :",
            ["GII (10/20)", "GI (4/10)", "SD (0/0,63)", "SC (0/4)"],
            horizontal=True
        )
        
        mat_key_map = {"GII (10/20)": "GII", "GI (4/10)": "GI", "SD (0/0,63)": "SD", "SC (0/4)": "SC"}
        key = mat_key_map[selected_mat]
        mat_data = st.session_state['data_granulats'][key]
        
        col1, col2 = st.columns([1.1, 0.9])
        
        with col1:
            st.subheader(f"Données de l'essai : {mat_data['nom']}")
            
            # --- BLOC 1 : PESÉES ---
            st.markdown("##### ⚖️ Pesées (Procédé : Lavage et tamisage)")
            c_m1, c_m2, c_p = st.columns(3)
            new_M1 = c_m1.number_input("Masse totale M1 (g)", value=float(mat_data.get('M1', 1000.0)), step=10.0, disabled=not can_edit)
            new_M2 = c_m2.number_input("Masse après lavage M2 (g)", value=float(mat_data.get('M2', 1000.0)), step=10.0, disabled=not can_edit)
            new_P  = c_p.number_input("Matériau au fond P (g)", value=float(mat_data.get('P', 0.0)), step=0.1, disabled=not can_edit)
            
            # --- BLOC 2 : TABLEAU D'ANALYSE ---
            st.markdown("##### 📊 Analyse par tamisage (Saisie des refus en g)")
            
            # Préparation du dataframe d'affichage
            df_display = pd.DataFrame({
                "Tamis (mm)": mat_data['sieves'],
                "Masse de refus Ri (g)": mat_data.get('refus', [0.0]*len(mat_data['sieves']))
            })
            
            # Calculs dynamiques pour l'affichage (Lecture seule dans le tableau)
            temp_pct = (df_display["Masse de refus Ri (g)"] / new_M1) * 100 if new_M1 > 0 else 0
            temp_cum = temp_pct.cumsum()
            df_display["% Refus"] = temp_pct
            df_display["% Refus Cumulés"] = temp_cum
            
            # Fonction d'arrondi normatif
            def calc_passant(row):
                p = 100.0 - row["% Refus Cumulés"]
                if row["Tamis (mm)"] == 0.063:
                    return max(0.0, round(p, 1))
                return max(0.0, round(p))
                
            df_display["% Passants"] = df_display.apply(calc_passant, axis=1)

            # Editeur de données : seule la colonne "Masse de refus Ri (g)" est éditable
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "Tamis (mm)": st.column_config.NumberColumn(disabled=True),
                    "Masse de refus Ri (g)": st.column_config.NumberColumn(disabled=not can_edit, min_value=0.0, format="%.1f"),
                    "% Refus": st.column_config.NumberColumn(disabled=True, format="%.1f %%"),
                    "% Refus Cumulés": st.column_config.NumberColumn(disabled=True, format="%.1f %%"),
                    "% Passants": st.column_config.NumberColumn(disabled=True, format="%.1f %%")
                },
                hide_index=True,
                use_container_width=True,
                height=450
            )

            # --- SAUVEGARDE ET RECALCUL EN TEMPS RÉEL ---
            if can_edit:
                st.session_state['data_granulats'][key]['M1'] = new_M1
                st.session_state['data_granulats'][key]['M2'] = new_M2
                st.session_state['data_granulats'][key]['P'] = new_P
                st.session_state['data_granulats'][key]['refus'] = edited_df["Masse de refus Ri (g)"].tolist()
                # Met à jour la liste officielle des passants utilisée par Tab 2
                update_passants(st.session_state['data_granulats'][key]) 

            # --- BLOC 3 : NOTA / VÉRIFICATIONS ---
            st.markdown("##### 🔍 Vérifications et Validations (NF EN 933-1)")
            refus_array = edited_df["Masse de refus Ri (g)"].values
            somme_Ri = sum(refus_array)
            masse_calc = somme_Ri + new_P
            perte_fraction = 100 * (new_M2 - masse_calc) / new_M2 if new_M2 > 0 else 0
            fines_f = 100 * ((new_M1 - new_M2) + new_P) / new_M1 if new_M1 > 0 else 0
            
            c_v1, c_v2 = st.columns(2)
            c_v1.info(f"**ΣRi + P :** {masse_calc:.1f} g\n\n**% Tamisat fines (f) :** {fines_f:.2f} %")
            
            if perte_fraction < 1.0:
                c_v2.success(f"**Pertes de tamisage :** {perte_fraction:.2f} %\n\n✅ Essai Valide (< 1%)")
            else:
                c_v2.error(f"**Pertes de tamisage :** {perte_fraction:.2f} %\n\n❌ Rejeter l'essai (> 1%)")

        with col2:
            st.subheader("Courbe Granulométrique Individuelle")
            
            # Utilise les passants mis à jour
            d95 = compute_D95(mat_data['sieves'], mat_data['passants'])
            st.metric(label="Tamis D (95% de passant calculé)", value=f"{d95} mm")
            
            fig_ind = go.Figure()
            s_sorted, p_sorted = zip(*sorted(zip(mat_data['sieves'], mat_data['passants'])))
            
            fig_ind.add_trace(go.Scatter(
                x=s_sorted, y=p_sorted,
                mode='lines+markers',
                name=mat_data['nom'],
                line=dict(color='blue', width=2)
            ))
            
            fig_ind.update_layout(
                xaxis=dict(type="log", title="Tamis (mm)", tickvals=[0.063, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 31.5, 63]),
                yaxis=dict(title="% Passants Cumulés", range=[0, 105]),
                height=400,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_ind, use_container_width=True)

            st.markdown("---")
            st.subheader("Caractéristiques complémentaires")
            st.info("Laissez à 0.0 si l'essai n'est pas applicable pour cette fraction.")
            
            col_a, col_b = st.columns(2)
            with col_a:
                fi_val = st.number_input("Coeff. Aplatissement (FI)", value=float(mat_data.get('fi') or 0.0), step=0.1, disabled=not can_edit)
                la_val = st.number_input("Los Angeles (LA)", value=float(mat_data.get('la') or 0.0), step=0.1, disabled=not can_edit)
                mb_val = st.number_input("Valeur de Bleu (MB)", value=float(mat_data.get('mb') or 0.0), step=0.1, disabled=not can_edit)
            with col_b:
                mf_val = st.number_input("Module de Finesse (MF)", value=float(mat_data.get('mf') or 0.0), step=0.01, disabled=not can_edit)
                se_val = st.number_input("Équivalent de Sable (SE 10)", value=float(mat_data.get('se') or 0.0), step=0.1, disabled=not can_edit)
                
            if can_edit:
                st.session_state['data_granulats'][key]['fi'] = fi_val if fi_val > 0 else None
                st.session_state['data_granulats'][key]['la'] = la_val if la_val > 0 else None
                st.session_state['data_granulats'][key]['mb'] = mb_val if mb_val > 0 else None
                st.session_state['data_granulats'][key]['mf'] = mf_val if mf_val > 0 else None
                st.session_state['data_granulats'][key]['se'] = se_val if se_val > 0 else None

    # ------------------------------------------------------------------------------
    # FENÊTRE 2 : PV D'IDENTIFICATION / SYNTHÈSE (Reste inchangée et auto-alimentée)
    # ------------------------------------------------------------------------------
    with tabs[1]:
        st.header("PV d'Identification des Granulats pour Béton")
        
        with st.expander("📝 Entête & Informations du Procès-Verbal", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            projet_val = c1.text_input("Projet / Chantier", st.session_state['pv_info']['projet'], disabled=not can_edit)
            client_val = c2.text_input("Client", st.session_state['pv_info']['client'], disabled=not can_edit)
            ref_val = c3.text_input("Référence PV", st.session_state['pv_info']['ref_pv'], disabled=not can_edit)
            date_val = c4.text_input("Date", st.session_state['pv_info']['date'], disabled=not can_edit)

            if can_edit:
                st.session_state['pv_info']['projet'] = projet_val
                st.session_state['pv_info']['client'] = client_val
                st.session_state['pv_info']['ref_pv'] = ref_val
                st.session_state['pv_info']['date'] = date_val

        gii_data = st.session_state['data_granulats']['GII']
        gi_data  = st.session_state['data_granulats']['GI']
        sd_data  = st.session_state['data_granulats']['SD']
        sc_data  = st.session_state['data_granulats']['SC']

        D_gii = compute_D95(gii_data['sieves'], gii_data['passants'])
        D_gi  = compute_D95(gi_data['sieves'], gi_data['passants'])
        D_sd  = compute_D95(sd_data['sieves'], sd_data['passants'])
        D_sc  = compute_D95(sc_data['sieves'], sc_data['passants'])

        st.markdown("""
        <style>
        .pv-container { background-color: #f8fafc; border: 2px solid #1e3a8a; padding: 10px; border-radius: 5px; }
        .pv-header { background-color: #3b82f6; color: white; text-align: center; font-weight: bold; font-size: 16px; padding: 6px; }
        .pv-sub-header { background-color: #60a5fa; color: white; text-align: center; font-weight: bold; font-size: 13px; padding: 4px; }
        .pv-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 12px; }
        .pv-table th, .pv-table td { border: 1px solid #475569; padding: 4px; text-align: center; }
        .pv-bg-gray { background-color: #e2e8f0; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)

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
            </table>
        </div>
        """
        st.markdown(pv_html, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
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
            xaxis=dict(type="log", title="Tamis (mm)", tickvals=[0.063, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 31.5, 63]),
            yaxis=dict(title="% Passants Cumulés", range=[0, 105]),
            height=450,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_global, use_container_width=True)
        
        st.subheader("COMMENTAIRES & CONCLUSION")
        commentaires_val = st.text_area(
            "Commentaires sur la conformité :",
            value=st.session_state['pv_info']['commentaires'],
            height=70,
            disabled=not can_edit
        )
        if can_edit:
            st.session_state['pv_info']['commentaires'] = commentaires_val

    # ------------------------------------------------------------------------------
    # FENÊTRE 3 : HISTORIQUE ET TÉLÉCHARGEMENT DE PV
    # ------------------------------------------------------------------------------
    with tabs[2]:
        st.header("Historique et Sauvegarde des PV")
        
        col_btn1, col_btn2 = st.columns([1, 2])
        
        with col_btn1:
            if can_edit:
                if st.button("💾 Enregistrer le PV", use_container_width=True):
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
            else:
                st.info("⚠️ L'enregistrement de nouveaux PV est réservé au laboratoire.")

        st.markdown("---")
        st.subheader("📋 Historique des Procès-Verbaux Enregistrés")
        
        if len(st.session_state['historique_pv']) > 0:
            df_hist = pd.DataFrame(st.session_state['historique_pv'])
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.info("Aucun PV enregistré pour le moment.")

        st.markdown("---")
        st.subheader("📥 Téléchargement & Exportation")
        
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
            output_excel = io.BytesIO()
            with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                for k, v in st.session_state['data_granulats'].items():
                    # Export the full lab data to excel
                    df_ex = pd.DataFrame({
                        "Tamis (mm)": v['sieves'], 
                        "Refus (g)": v.get('refus', []),
                        "% Passants": v.get('passants', [])
                    })
                    df_ex.to_excel(writer, sheet_name=k, index=False)
            
            st.download_button(
                label="📊 Télécharger les Données Granulométriques (Excel)",
                data=output_excel.getvalue(),
                file_name=f"donnees_granulats_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
