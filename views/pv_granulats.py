import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import json
import copy
import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ------------------------------------------------------------------------------
# CONSTANTES & SUFFIXES DES MATÉRIAUX
# ------------------------------------------------------------------------------
STANDARD_SIEVES = [0.063, 0.08, 0.1, 0.125, 0.16, 0.2, 0.25, 0.315, 0.4, 0.5, 0.63, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.15, 4.0, 5.0, 5.6, 6.3, 8.0, 10.0, 12.5, 14.0, 16.0, 20.0, 25.0, 28.0, 31.5, 40.0]

SUFFIX_MAP = {
    'GII': '/1',
    'GI': '/2',
    'SC': '/3',
    'SD': '/4'
}

SIEVE_TICKVALS = [0.063, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 31.5, 63]
SIEVE_TICKTEXT = ["0,063", "0,125", "0,25", "0,5", "1", "2", "4", "8", "16", "31,5", "63"]

def clean_html(html_str):
    """Supprime les espaces en début de ligne pour éviter le rendu en bloc de code Markdown dans Streamlit."""
    return "\n".join([line.strip() for line in html_str.splitlines() if line.strip()])

def get_tamis_D(df: pd.DataFrame) -> float:
    """Trouve le tamis dont le % passant est le plus proche de 95%."""
    if df is None or df.empty or "% Passants" not in df.columns:
        return None
    diffs = (df["% Passants"] - 95.0).abs()
    idx_closest = diffs.idxmin()
    val = df.loc[idx_closest, "Tamis (mm)"]
    return int(val) if float(val).is_integer() else float(val)

def update_passants(mat_data):
    """Calcule les passants à partir des masses enregistrées (Méthode NF EN 933-1)"""
    M1 = float(mat_data.get('M1', 1000.0))
    sieves = mat_data.get('sieves', [])
    refus = [float(r) for r in mat_data.get('refus', [0.0] * len(sieves))]
    
    if M1 > 0 and len(sieves) > 0:
        pct_refus = [(r / M1) * 100 for r in refus]
        pct_refus_cum = np.cumsum(pct_refus)
        passants = [100.0 - c for c in pct_refus_cum]
        
        passants_fmt = []
        for s, p in zip(sieves, passants):
            passants_fmt.append(max(0.0, round(p, 1)))
        mat_data['passants'] = passants_fmt
    else:
        mat_data['passants'] = [100.0] * len(sieves)

def compute_sieve_at_passant(sieves, passings, target_passant):
    """ Sélectionne le plus petit tamis normatif (mm) dont le passant atteint au moins le % cible """
    if not sieves or not passings or len(sieves) != len(passings):
        return 0.0
        
    s_arr = np.array(sieves, dtype=float)
    p_arr = np.array(passings, dtype=float)
    
    idx_sort = np.argsort(s_arr)
    s_arr = s_arr[idx_sort]
    p_arr = p_arr[idx_sort]
    
    valid_sieves = s_arr[p_arr >= target_passant]
    if len(valid_sieves) > 0:
        val = valid_sieves[0]
        return int(val) if float(val).is_integer() else float(val)
        
    val = s_arr[-1]
    return int(val) if float(val).is_integer() else float(val)

def get_d_D_from_material(mat_data):
    """Détermine d et D à partir de la classe granulaire ou par calcul."""
    sieves = mat_data.get('sieves', [])
    passants = mat_data.get('passants', [])

    d_val = None
    D_val = None
    classe_str = mat_data.get('classe', '')
    if '/' in classe_str:
        try:
            parts = classe_str.replace(',', '.').split('/')
            d_val = float(parts[0])
            D_val = float(parts[1])
        except (ValueError, IndexError):
            pass

    if sieves and passants and len(sieves) == len(passants):
        diffs = [abs(p - 95.0) for p in passants]
        min_idx = diffs.index(min(diffs))
        D_calc = sieves[min_idx]
        
        if D_val is None:
            D_val = D_calc
        if d_val is None:
            d_val = compute_sieve_at_passant(sieves, passants, 5.0)
        return float(d_val), float(D_val)

    return float(d_val or 0.0), float(D_val or 0.0)

def get_passant_at_sieve(sieves, passings, target_sieve):
    """ Calcule ou interpole linéairement le passant au tamis cible """
    if target_sieve is None or target_sieve <= 0:
        return 0.0
    if not sieves or not passings or len(sieves) != len(passings):
        return 0.0
        
    s_arr = np.array(sieves, dtype=float)
    p_arr = np.array(passings, dtype=float)
    
    idx_sort = np.argsort(s_arr)
    s_arr = s_arr[idx_sort]
    p_arr = p_arr[idx_sort]
    
    if target_sieve >= s_arr[-1]:
        return 100.0
    if target_sieve <= s_arr[0]:
        return float(p_arr[0])
        
    return float(np.interp(target_sieve, s_arr, p_arr))

def calculate_characteristic_data(mat_data, tamis_D=None):
    """Déduit la liste des tamis caractéristiques (2D, 1.4D, D, d, d/2)"""
    d, D_calc = get_d_D_from_material(mat_data)
    D = float(tamis_D) if (tamis_D is not None and tamis_D > 0) else D_calc
    
    def fmt_sieve(val):
        if val is None or val == 0:
            return 0
        val_r = round(val, 2)
        return int(val_r) if float(val_r).is_integer() else val_r

    sieves_dict = {
        '2D': fmt_sieve(2 * D),
        '1.4D': fmt_sieve(1.4 * D),
        'D': fmt_sieve(D),
        'd': fmt_sieve(d),
        'd/2': fmt_sieve(d / 2)
    }
    
    passants_dict = {}
    for key, sieve_size in sieves_dict.items():
        val = get_passant_at_sieve(mat_data.get('sieves', []), mat_data.get('passants', []), sieve_size)
        passants_dict[key] = val

    return sieves_dict, passants_dict

def compute_MF(sieves, passings):
    """Calcule le Module de Finesse (MF) selon NF EN 12620"""
    if not sieves or not passings:
        return 0.0
    target_sieves = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125]
    sum_refus_cum = 0.0
    for ts in target_sieves:
        passant = get_passant_at_sieve(sieves, passings, ts)
        if not np.isnan(passant):
            sum_refus_cum += (100.0 - passant)
    return round(sum_refus_cum / 100.0, 2)

def generate_pv_html(pv_info, info_p, data_granulats):
    """Génère le document HTML complet et autonome du PV pour impression / téléchargement."""
    gii_data = data_granulats.get('GII', {})
    gi_data  = data_granulats.get('GI', {})
    sc_data  = data_granulats.get('SC', {})
    sd_data  = data_granulats.get('SD', {})

    ref_b = info_p.get('num_rapport', info_p.get('ref_base', '26/260/LGV/CS/1237'))

    empty_char = ({'2D': 0, '1.4D': 0, 'D': 0, 'd': 0, 'd/2': 0}, {'2D': 0.0, '1.4D': 0.0, 'D': 0.0, 'd': 0.0, 'd/2': 0.0})
    gii_sieves, gii_passants = calculate_characteristic_data(gii_data) if gii_data else empty_char
    gi_sieves, gi_passants   = calculate_characteristic_data(gi_data) if gi_data else empty_char
    sc_sieves, sc_passants   = calculate_characteristic_data(sc_data) if sc_data else empty_char
    sd_sieves, sd_passants   = calculate_characteristic_data(sd_data) if sd_data else empty_char

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>PV Identification Granulats - {pv_info.get('ref_pv', '')}</title>
<style>
    body {{
        font-family: Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        margin: 0;
        padding: 20px;
    }}
    .lpee-pv-card {{
        background-color: #ffffff;
        border: 2px solid #1e3a8a;
        border-radius: 8px;
        padding: 20px;
        max-width: 1000px;
        margin: 0 auto;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    .lpee-header-title {{
        background-color: #1e3a8a;
        color: #ffffff;
        text-align: center;
        font-weight: bold;
        font-size: 16px;
        padding: 10px;
        border-radius: 4px;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
    }}
    .lpee-info-grid {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 15px;
        font-size: 12px;
    }}
    .lpee-info-grid td {{
        border: 1px solid #cbd5e1;
        padding: 6px 10px;
        vertical-align: top;
    }}
    .lpee-info-label {{
        font-weight: bold;
        color: #0f172a;
        width: 18%;
        background-color: #f8fafc;
    }}
    .lpee-norm-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
        margin-bottom: 15px;
    }}
    .lpee-norm-table td {{
        border: 1px solid #cbd5e1;
        padding: 4px 8px;
    }}
    .lpee-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 15px;
        font-size: 12px;
    }}
    .lpee-table th {{
        background-color: #2563eb;
        color: #ffffff;
        border: 1px solid #1d4ed8;
        padding: 6px;
        text-align: center;
        font-weight: bold;
    }}
    .lpee-table td {{
        border: 1px solid #cbd5e1;
        padding: 5px;
        text-align: center;
    }}
    .row-designation {{
        background-color: #f1f5f9;
        font-weight: bold;
        text-align: left !important;
    }}
    .row-limite {{
        background-color: #fafafa;
        font-size: 11px;
        color: #475569;
    }}
    .comments-box {{
        margin-top: 15px;
        padding: 10px;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        background-color: #f8fafc;
        font-size: 12px;
    }}
    .signature-box {{
        margin-top: 20px;
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }}
    .signature-box td {{
        width: 33.33%;
        border: 1px solid #cbd5e1;
        padding: 8px;
        text-align: center;
        height: 80px;
        vertical-align: top;
    }}
    @media print {{
        body {{ padding: 0; }}
        .lpee-pv-card {{ border: none; box-shadow: none; padding: 0; }}
    }}
</style>
</head>
<body>
    <div class="lpee-pv-card">
        <div class="lpee-header-title">
            RAPPORT D'ESSAI N° : {pv_info.get('ref_pv', '')}<br>
            <span style="font-size:13px; font-weight:normal;">OBJET : IDENTIFICATION DES GRANULATS POUR BETON</span>
        </div>

        <table class="lpee-info-grid">
            <tr>
                <td class="lpee-info-label">Client :</td>
                <td><b>{pv_info.get('client', '')}</b></td>
                <td class="lpee-info-label">N° Dossier :</td>
                <td>{info_p.get('dossier_no', '-')}</td>
            </tr>
            <tr>
                <td class="lpee-info-label">Chantier :</td>
                <td colspan="3">{pv_info.get('projet', '')}</td>
            </tr>
            <tr>
                <td class="lpee-info-label">Date du prélèvement :</td>
                <td>{pv_info.get('date', '')}</td>
                <td class="lpee-info-label">Provenance :</td>
                <td>{info_p.get('provenance', '-')}</td>
            </tr>
            <tr>
                <td class="lpee-info-label">Lieu de prélèvement :</td>
                <td>{info_p.get('lieu_prelevement', '-')}</td>
                <td class="lpee-info-label">Réf. Échantillon :</td>
                <td><b>{ref_b}</b></td>
            </tr>
        </table>

        <table class="lpee-norm-table">
            <tr style="background-color:#f1f5f9; font-weight:bold; text-align:center;">
                <td colspan="5">Référence Normative</td>
            </tr>
            <tr>
                <td><b>A.G :</b> NF EN 933-1</td>
                <td><b>Équivalent de sable :</b> NF EN 933-8</td>
                <td><b>VB :</b> NF EN 933-9</td>
                <td><b>LOS ANGELES :</b> NF EN 1097-2</td>
                <td><b>CA :</b> NF EN 933-3</td>
            </tr>
        </table>

        <!-- TABLEAU 1 : GRAVILLONS GII -->
        <table class="lpee-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Désignations</th>
                    <th>2D</th><th>1,4D</th><th>D</th><th>d</th><th>d/2</th><th>f</th><th>FI</th><th>LA</th>
                </tr>
                <tr>
                    <th>{gii_sieves['2D']}</th>
                    <th>{gii_sieves['1.4D']}</th>
                    <th>{gii_sieves['D']}</th>
                    <th>{gii_sieves['d']}</th>
                    <th>{gii_sieves['d/2']}</th>
                    <th>% &lt; 63µm</th><th>-</th><th>-</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="row-designation">{gii_data.get('nom', 'GII')} - ({ref_b}/1)</td>
                    <td>{gii_passants['2D']:.0f}</td>
                    <td>{gii_passants['1.4D']:.0f}</td>
                    <td>{gii_passants['D']:.0f}</td>
                    <td>{gii_passants['d']:.0f}</td>
                    <td>{gii_passants['d/2']:.0f}</td>
                    <td>{get_passant_at_sieve(gii_data.get('sieves', []), gii_data.get('passants', []), 0.063):.1f}</td>
                    <td>{gii_data.get('fi', '-') if gii_data.get('fi') is not None else '-'}</td>
                    <td>{gii_data.get('la', '-') if gii_data.get('la') is not None else '-'}</td>
                </tr>
                <tr class="row-limite">
                    <td class="row-designation">Caractéristique générale de granularité</td>
                    <td>100</td><td>98 - 100</td><td>85 - 99</td><td>0 - 20</td><td>0 - 5</td><td>&lt; 1,5</td><td>FI 20</td><td>&lt; 30</td>
                </tr>
            </tbody>
        </table>

        <!-- TABLEAU 2 : GRAVILLONS GI -->
        <table class="lpee-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Désignations</th>
                    <th>2D</th><th>1,4D</th><th>D</th><th>d</th><th>d/2</th><th>f</th><th>FI</th><th>LA</th>
                </tr>
                <tr>
                    <th>{gi_sieves['2D']}</th>
                    <th>{gi_sieves['1.4D']}</th>
                    <th>{gi_sieves['D']}</th>
                    <th>{gi_sieves['d']}</th>
                    <th>{gi_sieves['d/2']}</th>
                    <th>% &lt; 63µm</th><th>-</th><th>-</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="row-designation">{gi_data.get('nom', 'GI')} - ({ref_b}/2)</td>
                    <td>{gi_passants['2D']:.0f}</td>
                    <td>{gi_passants['1.4D']:.0f}</td>
                    <td>{gi_passants['D']:.0f}</td>
                    <td>{gi_passants['d']:.0f}</td>
                    <td>{gi_passants['d/2']:.0f}</td>
                    <td>{get_passant_at_sieve(gi_data.get('sieves', []), gi_data.get('passants', []), 0.063):.1f}</td>
                    <td>{gi_data.get('fi', '-') if gi_data.get('fi') is not None else '-'}</td>
                    <td>{gi_data.get('la', '-') if gi_data.get('la') is not None else '-'}</td>
                </tr>
                <tr class="row-limite">
                    <td class="row-designation">Caractéristique générale de granularité</td>
                    <td>100</td><td>98 - 100</td><td>80 - 99</td><td>0 - 20</td><td>0 - 5</td><td>&lt; 1,5</td><td>FI 20</td><td>&lt; 30</td>
                </tr>
            </tbody>
        </table>

        <!-- TABLEAU 3 : SABLE GROSSIER -->
        <table class="lpee-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Désignations</th>
                    <th>2D</th><th>1,4D</th><th>D</th><th>% &lt; 1mm</th><th>% &lt; 250µm</th><th>% &lt; 63µm</th><th>MF</th><th>SE (10)</th>
                </tr>
                <tr>
                    <th>{sc_sieves['2D']}</th>
                    <th>{sc_sieves['1.4D']}</th>
                    <th>{sc_sieves['D']}</th>
                    <th>-</th><th>-</th><th>-</th><th>CF</th><th>-</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="row-designation">{sc_data.get('nom', 'SC')} - ({ref_b}/3)</td>
                    <td>{sc_passants['2D']:.0f}</td>
                    <td>{sc_passants['1.4D']:.0f}</td>
                    <td>{sc_passants['D']:.0f}</td>
                    <td>{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 1.0):.0f}</td>
                    <td>{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 0.25):.0f}</td>
                    <td>{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 0.063):.1f}</td>
                    <td>{sc_data.get('mf', '-') if sc_data.get('mf') is not None else '-'}</td>
                    <td>{sc_data.get('se', '-') if sc_data.get('se') is not None else '-'}</td>
                </tr>
                <tr class="row-limite">
                    <td class="row-designation">Caractéristique générale de granularité</td>
                    <td>100</td><td>95 - 100</td><td>85 - 99</td><td>40 (&plusmn;20)</td><td>50 (&plusmn;20)</td><td>&le; 16</td><td>2,4 - 4,0</td><td>&ge; 60</td>
                </tr>
            </tbody>
        </table>

        <!-- TABLEAU 4 : SABLE FIN -->
        <table class="lpee-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Désignations</th>
                    <th>2D</th><th>1,4D</th><th>D</th><th>% &lt; 1mm</th><th>% &lt; 250µm</th><th>% &lt; 63µm</th><th>MB</th>
                </tr>
                <tr>
                    <th>{sd_sieves['2D']}</th>
                    <th>{sd_sieves['1.4D']}</th>
                    <th>{sd_sieves['D']}</th>
                    <th>-</th><th>-</th><th>-</th><th>-</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="row-designation">{sd_data.get('nom', 'SD')} - ({ref_b}/4)</td>
                    <td>{sd_passants['2D']:.0f}</td>
                    <td>{sd_passants['1.4D']:.0f}</td>
                    <td>{sd_passants['D']:.0f}</td>
                    <td>{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 1.0):.0f}</td>
                    <td>{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 0.25):.0f}</td>
                    <td>{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 0.063):.1f}</td>
                    <td>{sd_data.get('mb', '-') if sd_data.get('mb') is not None else '-'}</td>
                </tr>
                <tr class="row-limite">
                    <td class="row-designation">Caractéristique générale de granularité</td>
                    <td>100</td><td>95 - 100</td><td>85 - 99</td><td>40 (&plusmn;20)</td><td>50 (&plusmn;25)</td><td>&le; 10</td><td>VSS 2</td>
                </tr>
            </tbody>
        </table>

        <div class="comments-box">
            <b>COMMENTAIRES :</b><br>
            {pv_info.get('commentaires', '')}
        </div>

        <!-- SIGNATURES -->
        <table class="signature-box">
            <tr>
                <td><b>LE COORDINATEUR DES ESSAIS</b><br><br><span style="color:#64748b;">Nom: {pv_info.get('coord_essais', 'O.IKEN')}</span><br>Visa:</td>
                <td><b>LE CHEF DU LABORATOIRE</b><br><br><span style="color:#64748b;">Nom: {pv_info.get('chef_labo', 'H.BAALLAL')}</span><br>Visa:</td>
                <td><b>RE&Ccedil;U PAR LE CLIENT</b><br><br><span style="color:#64748b;">Nom:</span><br>Visa:</td>
            </tr>
        </table>
    </div>
</body>
</html>"""
    return html

def create_curve_image_buffer(data_granulats, ref_b, fig_width=8, fig_height=3.2):
    """Génère un buffer image PNG haute définition de la courbe granulométrique pour le PDF."""
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=200)
    colors_map = {'GII': '#1e40af', 'GI': '#0284c7', 'SC': '#16a34a', 'SD': '#ea580c'}
    
    for k in ['GII', 'GI', 'SC', 'SD']:
        d = data_granulats.get(k, {})
        if d.get('sieves') and d.get('passants') and len(d['sieves']) == len(d['passants']):
            s_s, p_s = zip(*sorted(zip(d['sieves'], d['passants'])))
            label_str = f"{d.get('nom', k)} ({ref_b}{SUFFIX_MAP.get(k, '')})" if ref_b else d.get('nom', k)
            ax.plot(s_s, p_s, marker='o', markersize=3.5, label=label_str, color=colors_map.get(k, '#000000'), linewidth=1.5)

    ax.set_xscale('log')
    ax.set_xlim(0.063, 63)
    ax.xaxis.set_major_locator(FixedLocator(SIEVE_TICKVALS))
    ax.xaxis.set_major_formatter(FixedFormatter(SIEVE_TICKTEXT))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("Tamis (mm)", fontsize=8, fontweight='bold')
    ax.set_ylabel("% Passants Cumulés", fontsize=8, fontweight='bold')
    ax.set_ylim(-2, 105)
    ax.grid(True, which="both", ls="--", lw=0.4, alpha=0.7)
    ax.legend(loc='lower left', fontsize=7, framealpha=0.9)
    ax.tick_params(axis='both', which='major', labelsize=7)
    ax.set_title("COURBE GRANULOMETRIQUE GLOBALE", fontsize=9, fontweight='bold', pad=6)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_pv_pdf(pv_info, info_p, data_granulats):
    """Génère le fichier PDF structuré du PV d'identification."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("La bibliothèque ReportLab n'est pas installée. Veuillez lancer 'pip install reportlab'.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15,
        rightMargin=15,
        topMargin=15,
        bottomMargin=15
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'PDFTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=13,
        textColor=colors.white, alignment=1
    )
    cell_bold = ParagraphStyle('PDFCellBold', fontName='Helvetica-Bold', fontSize=7, leading=9, alignment=1)
    cell_norm = ParagraphStyle('PDFCellNorm', fontName='Helvetica', fontSize=7, leading=9, alignment=1)
    cell_left = ParagraphStyle('PDFCellLeft', fontName='Helvetica', fontSize=7, leading=9, alignment=0)
    cell_left_bold = ParagraphStyle('PDFCellLeftBold', fontName='Helvetica-Bold', fontSize=7, leading=9, alignment=0)
    
    ref_b = info_p.get('num_rapport', info_p.get('ref_base', '26/260/LGV/CS/1237'))

    header_text = f"RAPPORT D'ESSAI N° : {pv_info.get('ref_pv', '')}<br/><font size=7.5>OBJET : IDENTIFICATION DES GRANULATS POUR BETON</font>"
    header_table = Table([[Paragraph(header_text, title_style)]], colWidths=[565])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1e3a8a')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))

    def build_adjustable_tables(pad_extra):
        flowables = []

        info_data = [
            [Paragraph("Client :", cell_left_bold), Paragraph(str(pv_info.get('client', '')), cell_left_bold),
             Paragraph("N° Dossier :", cell_left_bold), Paragraph(str(info_p.get('dossier_no', '-')), cell_left)],
            [Paragraph("Chantier :", cell_left_bold), Paragraph(str(pv_info.get('projet', '')), cell_left),
             Paragraph("Provenance :", cell_left_bold), Paragraph(str(info_p.get('provenance', '-')), cell_left)],
            [Paragraph("Date prélèvement :", cell_left_bold), Paragraph(str(pv_info.get('date', '')), cell_left),
             Paragraph("Lieu prélèvement :", cell_left_bold), Paragraph(str(info_p.get('lieu_prelevement', '-')), cell_left)],
            [Paragraph("Réf. Échantillon :", cell_left_bold), Paragraph(f"<b>{ref_b}</b>", cell_left),
             Paragraph("", cell_left), Paragraph("", cell_left)]
        ]
        info_table = Table(info_data, colWidths=[90, 192.5, 90, 192.5])
        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f8fafc')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2 + pad_extra),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2 + pad_extra),
        ]))
        flowables.append(info_table)
        flowables.append(Spacer(1, 4))

        norm_data = [
            [Paragraph("Référence Normative", cell_bold), "", "", "", ""],
            [Paragraph("<b>A.G :</b> NF EN 933-1", cell_norm),
             Paragraph("<b>Équivalent de sable :</b> NF EN 933-8", cell_norm),
             Paragraph("<b>VB :</b> NF EN 933-9", cell_norm),
             Paragraph("<b>LOS ANGELES :</b> NF EN 1097-2", cell_norm),
             Paragraph("<b>CA :</b> NF EN 933-3", cell_norm)]
        ]
        norm_table = Table(norm_data, colWidths=[113]*5)
        norm_table.setStyle(TableStyle([
            ('SPAN', (0,0), (4,0)),
            ('BACKGROUND', (0,0), (4,0), colors.HexColor('#f1f5f9')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 2 + pad_extra),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2 + pad_extra),
        ]))
        flowables.append(norm_table)
        flowables.append(Spacer(1, 4))

        def build_mat_table(title_cols, row_data_vals, row_lim_vals):
            t_data = [
                [Paragraph("<b>Désignations</b>", cell_bold)] + [Paragraph(f"<b>{c}</b>", cell_bold) for c in title_cols[0]],
                [""] + [Paragraph(f"<b>{c}</b>", cell_bold) for c in title_cols[1]],
                row_data_vals,
                row_lim_vals
            ]
            col_w = [165] + [50]*8
            t = Table(t_data, colWidths=col_w)
            t.setStyle(TableStyle([
                ('SPAN', (0,0), (0,1)),
                ('BACKGROUND', (0,0), (-1,1), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0,0), (-1,1), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0,2), (0,2), colors.HexColor('#f1f5f9')),
                ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#fafafa')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 1.5 + pad_extra),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1.5 + pad_extra),
            ]))
            return t

        empty_char = ({'2D': 0, '1.4D': 0, 'D': 0, 'd': 0, 'd/2': 0}, {'2D': 0.0, '1.4D': 0.0, 'D': 0.0, 'd': 0.0, 'd/2': 0.0})
        gii_data = data_granulats.get('GII', {})
        gi_data  = data_granulats.get('GI', {})
        sc_data  = data_granulats.get('SC', {})
        sd_data  = data_granulats.get('SD', {})

        gii_s, gii_p = calculate_characteristic_data(gii_data) if gii_data else empty_char
        gi_s, gi_p   = calculate_characteristic_data(gi_data) if gi_data else empty_char
        sc_s, sc_p   = calculate_characteristic_data(sc_data) if sc_data else empty_char
        sd_s, sd_p   = calculate_characteristic_data(sd_data) if sd_data else empty_char

        t1_cols = [
            ["2D", "1,4D", "D", "d", "d/2", "f", "FI", "LA"],
            [str(gii_s['2D']), str(gii_s['1.4D']), str(gii_s['D']), str(gii_s['d']), str(gii_s['d/2']), "% < 63µm", "-", "-"]
        ]
        t1_row1 = [
            Paragraph(f"<b>{gii_data.get('nom', 'GII')} - ({ref_b}/1)</b>", cell_left),
            Paragraph(f"{gii_p['2D']:.0f}", cell_norm), Paragraph(f"{gii_p['1.4D']:.0f}", cell_norm), Paragraph(f"{gii_p['D']:.0f}", cell_norm),
            Paragraph(f"{gii_p['d']:.0f}", cell_norm), Paragraph(f"{gii_p['d/2']:.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(gii_data.get('sieves', []), gii_data.get('passants', []), 0.063):.1f}", cell_norm),
            Paragraph(f"{gii_data.get('fi', '-') if gii_data.get('fi') is not None else '-'}", cell_norm),
            Paragraph(f"{gii_data.get('la', '-') if gii_data.get('la') is not None else '-'}", cell_norm)
        ]
        t1_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "98-100", "85-99", "0-20", "0-5", "< 1,5", "FI 20", "< 30"]]
        flowables.append(build_mat_table(t1_cols, t1_row1, t1_row2))
        flowables.append(Spacer(1, 3))

        t2_cols = [
            ["2D", "1,4D", "D", "d", "d/2", "f", "FI", "LA"],
            [str(gi_s['2D']), str(gi_s['1.4D']), str(gi_s['D']), str(gi_s['d']), str(gi_s['d/2']), "% < 63µm", "-", "-"]
        ]
        t2_row1 = [
            Paragraph(f"<b>{gi_data.get('nom', 'GI')} - ({ref_b}/2)</b>", cell_left),
            Paragraph(f"{gi_p['2D']:.0f}", cell_norm), Paragraph(f"{gi_p['1.4D']:.0f}", cell_norm), Paragraph(f"{gi_p['D']:.0f}", cell_norm),
            Paragraph(f"{gi_p['d']:.0f}", cell_norm), Paragraph(f"{gi_p['d/2']:.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(gi_data.get('sieves', []), gi_data.get('passants', []), 0.063):.1f}", cell_norm),
            Paragraph(f"{gi_data.get('fi', '-') if gi_data.get('fi') is not None else '-'}", cell_norm),
            Paragraph(f"{gi_data.get('la', '-') if gi_data.get('la') is not None else '-'}", cell_norm)
        ]
        t2_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "98-100", "80-99", "0-20", "0-5", "< 1,5", "FI 20", "< 30"]]
        flowables.append(build_mat_table(t2_cols, t2_row1, t2_row2))
        flowables.append(Spacer(1, 3))

        t3_cols = [
            ["2D", "1,4D", "D", "% < 1mm", "% < 250µm", "% < 63µm", "MF", "SE (10)"],
            [str(sc_s['2D']), str(sc_s['1.4D']), str(sc_s['D']), "-", "-", "-", "CF", "-"]
        ]
        t3_row1 = [
            Paragraph(f"<b>{sc_data.get('nom', 'SC')} - ({ref_b}/3)</b>", cell_left),
            Paragraph(f"{sc_p['2D']:.0f}", cell_norm), Paragraph(f"{sc_p['1.4D']:.0f}", cell_norm), Paragraph(f"{sc_p['D']:.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 1.0):.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 0.25):.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sc_data.get('sieves', []), sc_data.get('passants', []), 0.063):.1f}", cell_norm),
            Paragraph(f"{sc_data.get('mf', '-') if sc_data.get('mf') is not None else '-'}", cell_norm),
            Paragraph(f"{sc_data.get('se', '-') if sc_data.get('se') is not None else '-'}", cell_norm)
        ]
        t3_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "95-100", "85-99", "40(±20)", "50(±20)", "≤ 16", "2.4-4.0", "≥ 60"]]
        flowables.append(build_mat_table(t3_cols, t3_row1, t3_row2))
        flowables.append(Spacer(1, 3))

        t4_cols = [
            ["2D", "1,4D", "D", "% < 1mm", "% < 250µm", "% < 63µm", "MB", "-"],
            [str(sd_s['2D']), str(sd_s['1.4D']), str(sd_s['D']), "-", "-", "-", "-", "-"]
        ]
        t4_row1 = [
            Paragraph(f"<b>{sd_data.get('nom', 'SD')} - ({ref_b}/4)</b>", cell_left),
            Paragraph(f"{sd_p['2D']:.0f}", cell_norm), Paragraph(f"{sd_p['1.4D']:.0f}", cell_norm), Paragraph(f"{sd_p['D']:.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 1.0):.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 0.25):.0f}", cell_norm),
            Paragraph(f"{get_passant_at_sieve(sd_data.get('sieves', []), sd_data.get('passants', []), 0.063):.1f}", cell_norm),
            Paragraph(f"{sd_data.get('mb', '-') if sd_data.get('mb') is not None else '-'}", cell_norm),
            Paragraph("-", cell_norm)
        ]
        t4_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "95-100", "85-99", "40(±20)", "50(±25)", "≤ 10", "VSS 2", "-"]]
        flowables.append(build_mat_table(t4_cols, t4_row1, t4_row2))
        flowables.append(Spacer(1, 4))

        return flowables

    ADJUSTABLE_ROWS = 4 + 2 + (4 * 4)
    baseline_tables = build_adjustable_tables(0)

    comm_text = f"<b>COMMENTAIRES :</b><br/>{pv_info.get('commentaires', '')}"
    comm_p = Paragraph(comm_text, cell_left)
    comm_table = Table([[comm_p]], colWidths=[565])
    comm_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    comm_spacer = Spacer(1, 4)

    sig_data = [
        [
            Paragraph(f"<b>LE COORDINATEUR DES ESSAIS</b><br/><br/><font color='#64748b'>Nom: {pv_info.get('coord_essais', 'O.IKEN')}</font><br/>Visa:", cell_norm),
            Paragraph(f"<b>LE CHEF DU LABORATOIRE</b><br/><br/><font color='#64748b'>Nom: {pv_info.get('chef_labo', 'H.BAALLAL')}</font><br/>Visa:", cell_norm),
            Paragraph("<b>REÇU PAR LE CLIENT</b><br/><br/><font color='#64748b'>Nom:</font><br/>Visa:", cell_norm)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[188.3, 188.3, 188.3])
    sig_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 16),
    ]))

    def _flowable_height(flowable, avail_w=565):
        try:
            return flowable.wrap(avail_w, 100000)[1]
        except Exception:
            return 0

    FRAME_PADDING = 12
    page_height = A4[1] - doc.topMargin - doc.bottomMargin - FRAME_PADDING
    CHART_HEIGHT = 220
    CHART_BOTTOM_SPACER = 4
    SAFETY_MARGIN = 6

    fixed_height = sum(_flowable_height(f) for f in story)
    fixed_height += _flowable_height(comm_table) + _flowable_height(comm_spacer) + _flowable_height(sig_table)
    baseline_height = sum(_flowable_height(f) for f in baseline_tables)

    leftover = page_height - fixed_height - baseline_height - CHART_HEIGHT - CHART_BOTTOM_SPACER - SAFETY_MARGIN
    raw_pad = leftover / (2 * ADJUSTABLE_ROWS)
    pad_extra = max(0.0, min(raw_pad, 12.0))

    chart_height = CHART_HEIGHT
    if raw_pad > 12.0:
        chart_height += (raw_pad - 12.0) * 2 * ADJUSTABLE_ROWS
        chart_height = min(chart_height, 420)
    elif raw_pad < 0:
        chart_height = max(180, CHART_HEIGHT + leftover)

    final_tables = build_adjustable_tables(pad_extra) if pad_extra > 0 else baseline_tables
    story.extend(final_tables)

    chart_buf = create_curve_image_buffer(
        data_granulats, ref_b,
        fig_width=565 / 72.0,
        fig_height=chart_height / 72.0
    )
    img = Image(chart_buf, width=565, height=chart_height)
    story.append(KeepTogether([
        img,
        Spacer(1, CHART_BOTTOM_SPACER)
    ]))

    story.append(comm_table)
    story.append(comm_spacer)
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ------------------------------------------------------------------------------
# FONCTIONS DE PERSISTANCE BD / SUPABASE
# ------------------------------------------------------------------------------
def fetch_pvs_from_supabase(supabase_client):
    """Charge l'historique des PV depuis la base de données Supabase."""
    if not supabase_client:
        return None
    for table_name in ['pv_granulats', 'historique_pv']:
        try:
            res = supabase_client.table(table_name).select('*').execute()
            if res and hasattr(res, 'data') and res.data:
                loaded = []
                for row in res.data:
                    if 'data' in row and isinstance(row['data'], dict):
                        item = copy.deepcopy(row['data'])
                        if 'id' in row: item['id'] = row['id']
                        loaded.append(item)
                    elif 'pv_data' in row and isinstance(row['pv_data'], dict):
                        item = copy.deepcopy(row['pv_data'])
                        if 'id' in row: item['id'] = row['id']
                        loaded.append(item)
                    else:
                        loaded.append(row)
                return loaded
        except Exception:
            continue
    return None

def save_pv_to_supabase(supabase_client, pv_snapshot):
    """Sauvegarde ou met à jour un PV sur la base de données Supabase."""
    if not supabase_client:
        return
    payload = {
        'ref_pv': pv_snapshot.get('ref_pv'),
        'client': pv_snapshot.get('client'),
        'projet': pv_snapshot.get('projet'),
        'date_creation': pv_snapshot.get('date_creation'),
        'data': pv_snapshot
    }
    for table_name in ['pv_granulats', 'historique_pv']:
        try:
            supabase_client.table(table_name).upsert(payload, on_conflict='ref_pv').execute()
            return
        except Exception:
            continue

def delete_pv_from_supabase(supabase_client, pv_ref):
    """Supprime un PV de la base de données Supabase."""
    if not supabase_client or not pv_ref:
        return
    for table_name in ['pv_granulats', 'historique_pv']:
        try:
            supabase_client.table(table_name).delete().eq('ref_pv', pv_ref).execute()
            return
        except Exception:
            continue

# ------------------------------------------------------------------------------
# FONCTION PRINCIPALE STREAMLIT
# ------------------------------------------------------------------------------
def show(supabase_client=None, can_edit=True, is_admin=False, **kwargs):
    if 'info_prelevement' not in st.session_state:
        st.session_state['info_prelevement'] = {}

    default_num_rapport = '26/260/LGV/CS/1237'
    info_defaults = {
        'chantier': "TRAVAUX D'EXECUTION DE TERRASSEMENT, OUVRAGES D'ART ET RETABLISSEMENTS DE COMMUNICATION ENTRE PK 5+450 et PK 10+000-GARE CASA SUD",
        'client': 'TGCC',
        'dossier_no': '2025-260-05985-2025 0247',
        'date_prelevement': '23/07/2026',
        'lieu_prelevement': 'Stock sur centrale à béton',
        'provenance': 'TG PREFA OULAD SALEH',
        'num_rapport': default_num_rapport,
        'ref_base': default_num_rapport
    }
    for k, v in info_defaults.items():
        st.session_state['info_prelevement'].setdefault(k, v)

    if 'data_granulats' not in st.session_state:
        st.session_state['data_granulats'] = {
            'GII': {
                'nom': 'Gravillons GII',
                'classe': '10/20',
                'ref_client': '', 'date_prelevement': '', 'lieu_prelevement': '',
                'sieves': [40, 31.5, 25, 20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063],
                'refus': [0.0, 0.0, 0.0, 199.7, 2200.3, 732.7, 308.7, 424.0, 163.2, 45.0, 6.9, 2.1, 0.2, 0.1, 0.2, 0.2, 0.1, 0.0, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.2, 0.1, 0.1, 0.1, 0.1],
                'M1': 4110.5, 'M2': 4095.2, 'P': 1.3,
                'passants': [], 
                'fi': 16.0, 'la': 26.0, 'mb': None, 'mf': None, 'se': None
            },
            'GI': {
                'nom': 'Gravillons GI',
                'classe': '4/10',
                'ref_client': '', 'date_prelevement': '', 'lieu_prelevement': '',
                'sieves': [20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063],
                'refus': [199.7, 2200.3, 732.7, 308.7, 424.0, 163.2, 45.0, 6.9, 2.1, 0.2, 0.1, 0.2, 0.2, 0.1, 0.0, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.2, 0.1, 0.1, 0.1, 0.1],
                'M1': 2000.0, 'M2': 1990.0, 'P': 0.0,
                'passants': [], 
                'fi': 14.0, 'la': 26.0, 'mb': None, 'mf': None, 'se': None
            },
            'SD': {
                'nom': 'Sable fin',
                'classe': '0/0,63',
                'ref_client': '', 'date_prelevement': '', 'lieu_prelevement': '',
                'sieves': [6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063],
                'refus': [45.0, 6.9, 2.1, 0.2, 0.1, 0.2, 0.2, 0.1, 0.0, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.2, 0.1, 0.1, 0.1, 0.1],
                'M1': 1000.0, 'M2': 900.0, 'P': 2.0,
                'passants': [],
                'fi': None, 'la': None, 'mb': 0.7, 'mf': None, 'se': None
            },
            'SC': {
                'nom': 'Sable grossier',
                'classe': '0/4',
                'ref_client': '', 'date_prelevement': '', 'lieu_prelevement': '',
                'sieves': [6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063],
                'refus': [45.0, 6.9, 2.1, 0.2, 0.1, 0.2, 0.2, 0.1, 0.0, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.2, 0.1, 0.1, 0.1, 0.1],
                'M1': 1000.0, 'M2': 910.0, 'P': 3.0,
                'passants': [],
                'fi': None, 'la': None, 'mb': None, 'mf': 3.50, 'se': 65.0
            }
        }

    for k in st.session_state['data_granulats'].keys():
        if not st.session_state['data_granulats'][k]['passants']:
            update_passants(st.session_state['data_granulats'][k])
        if k in ['SC', 'SD']:
            st.session_state['data_granulats'][k]['mf'] = compute_MF(
                st.session_state['data_granulats'][k]['sieves'],
                st.session_state['data_granulats'][k]['passants']
            )

    if 'historique_pv' not in st.session_state:
        st.session_state['historique_pv'] = []

    # Chargement initial depuis la base de données Supabase si reconnecté
    if supabase_client and not st.session_state.get('pvs_loaded_from_db', False):
        db_pvs = fetch_pvs_from_supabase(supabase_client)
        if db_pvs is not None:
            st.session_state['historique_pv'] = db_pvs
        st.session_state['pvs_loaded_from_db'] = True

    if 'pv_info' not in st.session_state:
        st.session_state['pv_info'] = {}

    pv_defaults = {
        'projet': st.session_state['info_prelevement'].get('chantier', ''),
        'client': st.session_state['info_prelevement'].get('client', ''),
        'ref_pv': st.session_state['info_prelevement'].get('num_rapport', default_num_rapport),
        'date': st.session_state['info_prelevement'].get('date_prelevement', ''),
        'commentaires': "Les essais d'identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545",
        'coord_essais': 'O.IKEN',
        'chef_labo': 'H.BAALLAL'
    }
    for k, v in pv_defaults.items():
        st.session_state['pv_info'].setdefault(k, v)

    if 'success_msg' in st.session_state:
        st.success(st.session_state['success_msg'])
        del st.session_state['success_msg']

    # --------------------------------------------------------------------------
    # IDENTIFICATION DE L'UTILISATEUR
    # --------------------------------------------------------------------------
    user_tokens = []
    for _uk in ('username', 'user', 'user_name', 'current_user', 'user_email', 'email', 'nom_utilisateur', 'role'):
        _uv = kwargs.get(_uk) or st.session_state.get(_uk)
        if _uv:
            if isinstance(_uv, dict):
                user_tokens.extend([str(_uv.get(k, '')) for k in ('username', 'email', 'role', 'name')])
            else:
                user_tokens.append(str(_uv))
    
    combined_user_str = " ".join(user_tokens).lower()
    is_baallal_admin = bool(is_admin) or ('baallal' in combined_user_str) or st.session_state.get('is_admin', False) or (st.session_state.get('role') == 'admin')

    def _build_pv_snapshot():
        """Construit un instantané complet du PV courant pour l'historique."""
        existing_ids = [p.get('id', 0) for p in st.session_state['historique_pv']]
        next_id = (max(existing_ids) + 1) if existing_ids else 1
        return {
            'id': next_id,
            'date_creation': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ref_pv': st.session_state['pv_info'].get('ref_pv', '').strip(),
            'projet': st.session_state['pv_info'].get('projet', ''),
            'client': st.session_state['pv_info'].get('client', ''),
            'info_prelevement': copy.deepcopy(st.session_state['info_prelevement']),
            'pv_info': copy.deepcopy(st.session_state['pv_info']),
            'data_granulats': copy.deepcopy(st.session_state['data_granulats'])
        }

    st.title("🏗️ Module Identification des Granulats pour Béton")
    
    if not can_edit:
        st.info("👁️ **Mode Consultation** : Vous êtes en lecture seule.")

    saved_num_rapports = [
        pv.get('ref_pv', '').strip().lower() 
        for pv in st.session_state.get('historique_pv', []) 
        if pv.get('ref_pv')
    ]

    tabs = st.tabs([
        "1️⃣ Feuilles d'Essais Complets",
        "2️⃣ PV d'Identification / Synthèse",
        "3️⃣ Historique & Téléchargement de PV"
    ])

    # ------------------------------------------------------------------------------
    # FENÊTRE 1 : FEUILLES D'ESSAIS COMPLETS
    # ------------------------------------------------------------------------------
    with tabs[0]:
        st.header("Feuilles d'Analyse Granulométrique et Caractéristiques")
        
        st.markdown("##### 📍 Informations de prélèvement (Communes à tous les matériaux)")
        c1, c2, c3 = st.columns(3)
        c4, c5, c6 = st.columns(3)
        
        info_p = st.session_state['info_prelevement']
        
        new_client       = c1.text_input("Client", value=info_p.get('client', 'TGCC'), disabled=not can_edit, key="common_client")
        new_chantier     = c2.text_input("Chantier", value=info_p.get('chantier', ''), disabled=not can_edit, key="common_chantier")
        new_dossier      = c3.text_input("N° Dossier", value=info_p.get('dossier_no', ''), disabled=not can_edit, key="common_dossier")
        new_date_prelev  = c4.text_input("Date de prélèvement", value=info_p.get('date_prelevement', '23/07/2026'), disabled=not can_edit, key="common_date_prelev")
        new_lieu_prelev  = c5.text_input("Lieu de prélèvement", value=info_p.get('lieu_prelevement', 'Stock sur centrale à béton'), disabled=not can_edit, key="common_lieu_prelev")
        new_provenance   = c6.text_input("Provenance échantillon", value=info_p.get('provenance', 'TG PREFA OULAD SALEH'), disabled=not can_edit, key="common_provenance")
        
        new_num_rapport  = st.text_input("N° RAPPORT D'ESSAI N°", value=info_p.get('num_rapport', default_num_rapport), disabled=not can_edit, key="common_num_rapport")
        new_ref_base     = new_num_rapport.strip()

        st.text_input(
            "Référence labo (Base) - Identique au N° Rapport", 
            value=new_ref_base, 
            disabled=True, 
            key="common_ref_base_disp",
            help="La Référence labo (Base) reprend automatiquement le numéro du rapport d'essai."
        )

        is_duplicate = new_num_rapport.strip().lower() in saved_num_rapports if new_num_rapport.strip() else False
        if is_duplicate:
            st.error(f"⛔ **ATTENTION : DUPLICATA DÉTECTÉ !** Le N° Rapport d'essai `{new_num_rapport}` a déjà été enregistré dans l'historique.")

        if can_edit:
            st.session_state['info_prelevement']['chantier'] = new_chantier
            st.session_state['info_prelevement']['client'] = new_client
            st.session_state['info_prelevement']['dossier_no'] = new_dossier
            st.session_state['info_prelevement']['date_prelevement'] = new_date_prelev
            st.session_state['info_prelevement']['lieu_prelevement'] = new_lieu_prelev
            st.session_state['info_prelevement']['provenance'] = new_provenance
            st.session_state['info_prelevement']['num_rapport'] = new_num_rapport
            st.session_state['info_prelevement']['ref_base'] = new_ref_base
            
            st.session_state['pv_info']['projet'] = new_chantier
            st.session_state['pv_info']['client'] = new_client
            st.session_state['pv_info']['ref_pv'] = new_num_rapport

        st.markdown("---")

        selected_mat = st.radio(
            "Sélectionner la fraction d'échantillon à saisir / modifier :",
            ["GII (10/20)", "GI (4/10)", "SC (0/4)", "SD (0/0,63)"],
            horizontal=True
        )
        
        mat_key_map = {"GII (10/20)": "GII", "GI (4/10)": "GI", "SC (0/4)": "SC", "SD (0/0,63)": "SD"}
        key = mat_key_map[selected_mat]
        mat_data = st.session_state['data_granulats'][key]
        
        sub_ref = f"{new_ref_base}{SUFFIX_MAP[key]}" if new_ref_base else SUFFIX_MAP[key]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"Saisie des données : {mat_data['nom']}")
            st.caption(f"Sous-référence Labo générée : {sub_ref}")

            st.markdown("##### ⚖️ Pesées (Procédé : Lavage et tamisage)")
            c_m1, c_m2, c_p = st.columns(3)
            new_M1 = c_m1.number_input("Masse totale M1 (g)", value=float(mat_data.get('M1', 1000.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"m1_{key}")
            new_M2 = c_m2.number_input("Masse après lavage M2 (g)", value=float(mat_data.get('M2', 1000.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"m2_{key}")
            new_P  = c_p.number_input("Matériau au fond P (g)", value=float(mat_data.get('P', 0.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"p_{key}")
            
            st.subheader("Analyse par tamisage (Saisie des refus en g)")
            
            df_display = pd.DataFrame({
                "Tamis (mm)": mat_data['sieves'],
                "Masse de refus Ri (g)": [round(float(r), 1) for r in mat_data.get('refus', [0.0]*len(mat_data['sieves']))]
            })
            
            saved_M1 = float(new_M1) if new_M1 > 0 else 1.0
            pct_r = (df_display["Masse de refus Ri (g)"] / saved_M1) * 100
            pct_r_cum = pct_r.cumsum()
            df_display["% Refus"] = pct_r.round(1)
            df_display["% Refus Cumulés"] = pct_r_cum.round(1)
            df_display["% Passants"] = (100.0 - pct_r_cum).clip(lower=0.0).round(1)

            edited_df = st.data_editor(
                df_display,
                key=f"editor_{key}",
                column_config={
                    "Tamis (mm)": st.column_config.NumberColumn(disabled=True),
                    "Masse de refus Ri (g)": st.column_config.NumberColumn(
                        disabled=not can_edit, 
                        min_value=0.0, 
                        step=0.1, 
                        format="%.1f"
                    ),
                    "% Refus": st.column_config.NumberColumn(disabled=True, format="%.1f %%"),
                    "% Refus Cumulés": st.column_config.NumberColumn(disabled=True, format="%.1f %%"),
                    "% Passants": st.column_config.NumberColumn(disabled=True, format="%.1f %%")
                },
                hide_index=True,
                use_container_width=True,
                height=350
            )

            if new_M1 > 0:
                pct_r_edit = (edited_df["Masse de refus Ri (g)"] / new_M1) * 100
                pct_cum_edit = pct_r_edit.cumsum()
                edited_df["% Refus"] = pct_r_edit.round(1)
                edited_df["% Refus Cumulés"] = pct_cum_edit.round(1)
                edited_df["% Passants"] = (100.0 - pct_cum_edit).clip(lower=0.0).round(1)

                mat_data['M1'] = new_M1
                mat_data['refus'] = [round(float(r), 1) for r in edited_df["Masse de refus Ri (g)"].tolist()]
                update_passants(mat_data)

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

            calculated_mf = compute_MF(mat_data['sieves'], mat_data['passants'])

            st.markdown("---")
            st.subheader(f"Caractéristiques de {mat_data['classe']}")
            
            col_a, col_b = st.columns(2)
            
            if key in ["GII", "GI"]:
                with col_a:
                    fi_val = st.number_input("Coeff. Aplatissement (FI)", value=float(mat_data.get('fi') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"fi_{key}")
                with col_b:
                    la_val = st.number_input("Los Angeles (LA)", value=float(mat_data.get('la') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"la_{key}")
                mb_val, mf_val, se_val = 0.0, 0.0, 0.0
            else:
                with col_a:
                    mb_val = st.number_input("Valeur de Bleu (MB)", value=float(mat_data.get('mb') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"mb_{key}")
                with col_b:
                    mf_val = st.number_input(
                        "Module de Finesse (MF - Calculé Auto)", 
                        value=float(calculated_mf), 
                        disabled=True, 
                        help="FM = Σ(Refus cumulés sur 4, 2, 1, 0.5, 0.25, 0.125 mm) / 100",
                        key=f"mf_{key}"
                    )
                    se_val = st.number_input("Équivalent de Sable (SE 10)", value=float(mat_data.get('se') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"se_{key}")
                fi_val, la_val = 0.0, 0.0

            if can_edit:
                st.session_state['data_granulats'][key]['M1'] = new_M1
                st.session_state['data_granulats'][key]['M2'] = new_M2
                st.session_state['data_granulats'][key]['P'] = new_P
                st.session_state['data_granulats'][key]['refus'] = [round(float(r), 1) for r in edited_df["Masse de refus Ri (g)"].tolist()]
                
                st.session_state['data_granulats'][key]['fi'] = fi_val if fi_val > 0 else None
                st.session_state['data_granulats'][key]['la'] = la_val if la_val > 0 else None
                st.session_state['data_granulats'][key]['mb'] = mb_val if mb_val > 0 else None
                st.session_state['data_granulats'][key]['se'] = se_val if se_val > 0 else None

                update_passants(st.session_state['data_granulats'][key])
                if key in ["SC", "SD"]:
                    st.session_state['data_granulats'][key]['mf'] = compute_MF(
                        st.session_state['data_granulats'][key]['sieves'],
                        st.session_state['data_granulats'][key]['passants']
                    )

        with col2:
            st.subheader("Synthèse des Tamis Caractéristiques")

            tamis_D = get_tamis_D(edited_df)
            char_sieves, char_passants = calculate_characteristic_data(mat_data, tamis_D=tamis_D)

            col_m1, col_m2 = st.columns([1, 1.5])
            with col_m1:
                st.markdown(f"**Tamis D (~95%)**")
                st.markdown(f"# {tamis_D if tamis_D is not None else '-'} mm")

            with col_m2:
                df_char_mat = pd.DataFrame({
                    "Grandeur": ["2D", "1.4D", "D", "d", "d/2"],
                    "Tamis (mm)": [char_sieves['2D'], char_sieves['1.4D'], char_sieves['D'], char_sieves['d'], char_sieves['d/2']],
                    "% Passant": [
                        f"{char_passants['2D']:.1f} %",
                        f"{char_passants['1.4D']:.1f} %",
                        f"{char_passants['D']:.1f} %",
                        f"{char_passants['d']:.1f} %",
                        f"{char_passants['d/2']:.1f} %"
                    ]
                })
                st.markdown(f"**Tamis normatifs : {mat_data['nom']}**")
                st.dataframe(df_char_mat, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.subheader("Courbe Granulométrique Globale")

            fig = go.Figure()
            colors = {'GII': 'navy', 'GI': '#0284c7', 'SC': '#16a34a', 'SD': '#ea580c'}
            
            for k, d in st.session_state['data_granulats'].items():
                if d.get('sieves') and d.get('passants') and len(d['sieves']) == len(d['passants']):
                    s_s, p_s = zip(*sorted(zip(d['sieves'], d['passants'])))
                    line_width = 2.5 if k == key else 1.5
                    opacity = 1.0 if k == key else 0.4
                    
                    fig.add_trace(go.Scatter(
                        x=s_s, y=p_s,
                        mode="lines+markers",
                        name=f"{d['nom']} ({new_ref_base}{SUFFIX_MAP[k]})" if new_ref_base else d['nom'],
                        line=dict(color=colors[k], width=line_width),
                        marker=dict(size=6),
                        opacity=opacity
                    ))

            fig.update_layout(
                xaxis=dict(
                    title="Tamis (mm)",
                    type="log",
                    tickmode="array",
                    tickvals=SIEVE_TICKVALS,
                    ticktext=SIEVE_TICKTEXT
                ),
                yaxis=dict(
                    title="% Passants Cumulés",
                    range=[0, 105]
                ),
                margin=dict(l=20, r=20, t=30, b=20),
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Validation Globale de tous les Échantillons (GII, GI, SC, SD)")

        if is_duplicate:
            st.error(f"⛔ **VALIDATION BLOQUÉE :** Le N° Rapport d'essai `{new_num_rapport}` est un doublon. Veuillez saisir un numéro unique avant de valider.")
            st.button("✅ Valider et enregistrer l'ensemble des essais", type="primary", use_container_width=True, disabled=True, key="btn_validate_all_disabled")
        else:
            if can_edit:
                if st.button("✅ Valider et enregistrer l'ensemble des essais", type="primary", use_container_width=True, key="btn_validate_all"):
                    for mat_k in st.session_state['data_granulats'].keys():
                        update_passants(st.session_state['data_granulats'][mat_k])
                        if mat_k in ["SC", "SD"]:
                            st.session_state['data_granulats'][mat_k]['mf'] = compute_MF(
                                st.session_state['data_granulats'][mat_k]['sieves'],
                                st.session_state['data_granulats'][mat_k]['passants']
                            )

                    snapshot = _build_pv_snapshot()
                    st.session_state['historique_pv'].append(snapshot)
                    
                    # Persistance dans la BD Supabase
                    save_pv_to_supabase(supabase_client, snapshot)

                    st.session_state['success_msg'] = f"✅ L'ensemble des essais pour le Rapport N° '{new_num_rapport}' a été enregistré dans la base de données !"
                    st.rerun()

    # ------------------------------------------------------------------------------
    # FENÊTRE 2 : PV D'IDENTIFICATION / SYNTHÈSE
    # ------------------------------------------------------------------------------
    with tabs[1]:
        st.header("PV d'Identification des Granulats pour Béton")
        
        pv_info_dict = st.session_state['pv_info']
        
        if is_duplicate:
            st.error(f"⚠️ **Attention :** Le N° RAPPORT D'ESSAI `{pv_info_dict.get('ref_pv', '')}` existe déjà dans l'historique.")

        with st.expander("⚙️ Modifier les entêtes et signataires du PV", expanded=False):
            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)
            
            projet_val   = c1.text_input("Chantier / Projet", pv_info_dict.get('projet', ''), disabled=not can_edit, key="pv_proj")
            client_val   = c2.text_input("Client", pv_info_dict.get('client', ''), disabled=not can_edit, key="pv_cli")
            ref_val      = c3.text_input(
                "N° RAPPORT D'ESSAI N°",
                st.session_state['info_prelevement'].get('num_rapport', default_num_rapport),
                disabled=True,
                key="pv_ref",
                help="Identique au N° Rapport d'essai de la feuille d'essais."
            )
            date_val     = c4.text_input("Date du prélèvement", pv_info_dict.get('date', ''), disabled=not can_edit, key="pv_dt")
            coord_val    = c5.text_input("Coordinateur des essais", pv_info_dict.get('coord_essais', 'O.IKEN'), disabled=not can_edit, key="pv_coo")
            chef_val     = c6.text_input("Chef du laboratoire", pv_info_dict.get('chef_labo', 'H.BAALLAL'), disabled=not can_edit, key="pv_che")

            st.session_state['pv_info']['ref_pv'] = st.session_state['info_prelevement'].get('num_rapport', default_num_rapport)

            if can_edit:
                st.session_state['pv_info']['projet'] = projet_val
                st.session_state['pv_info']['client'] = client_val
                st.session_state['pv_info']['date'] = date_val
                st.session_state['pv_info']['coord_essais'] = coord_val
                st.session_state['pv_info']['chef_labo'] = chef_val

        current_pv_html = generate_pv_html(
            st.session_state['pv_info'],
            st.session_state['info_prelevement'],
            st.session_state['data_granulats']
        )

        st.markdown(clean_html(current_pv_html), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_dl_pdf1, col_dl_pdf2 = st.columns(2)
        
        with col_dl_pdf1:
            st.download_button(
                label="📄 Télécharger le Rapport PV (Format HTML Imprimable)",
                data=current_pv_html,
                file_name=f"PV_Granulats_{st.session_state['pv_info'].get('ref_pv', 'rapport').replace('/', '_')}.html",
                mime="text/html",
                use_container_width=True,
                type="secondary"
            )

        with col_dl_pdf2:
            if REPORTLAB_AVAILABLE:
                try:
                    pdf_bytes = generate_pv_pdf(
                        st.session_state['pv_info'],
                        st.session_state['info_prelevement'],
                        st.session_state['data_granulats']
                    )
                    st.download_button(
                        label="🔴 Télécharger le Rapport PV avec Courbe (Format PDF)",
                        data=pdf_bytes,
                        file_name=f"PV_Granulats_{st.session_state['pv_info'].get('ref_pv', 'rapport').replace('/', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Erreur lors de la création du PDF : {e}")
            else:
                st.warning("⚠️ Pour activer le téléchargement PDF, installez ReportLab : `pip install reportlab`")

        st.markdown("---")
        st.subheader("COURBE GRANULOMETRIQUE GLOBALE DU PV")
        fig_global_tab2 = go.Figure()
        
        colors = {'GII': '#1e40af', 'GI': '#0284c7', 'SC': '#16a34a', 'SD': '#ea580c'}
        ref_b = st.session_state['info_prelevement'].get('num_rapport', default_num_rapport)
        
        for k, d in st.session_state['data_granulats'].items():
            if d.get('sieves') and d.get('passants') and len(d['sieves']) == len(d['passants']):
                s_s, p_s = zip(*sorted(zip(d['sieves'], d['passants'])))
                fig_global_tab2.add_trace(go.Scatter(
                    x=s_s, y=p_s,
                    mode='lines+markers',
                    name=f"{d['nom']} ({ref_b}{SUFFIX_MAP[k]})" if ref_b else d['nom'],
                    line=dict(color=colors[k], width=2)
                ))
            
        fig_global_tab2.update_layout(
            xaxis=dict(type="log", title="Tamis (mm)", tickmode="array", tickvals=SIEVE_TICKVALS, ticktext=SIEVE_TICKTEXT),
            yaxis=dict(title="% Passants Cumulés", range=[0, 105]),
            height=440,
            margin=dict(l=30, r=30, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_global_tab2, use_container_width=True)

        comm_input = st.text_area("COMMENTAIRES :", value=st.session_state['pv_info'].get('commentaires', ''), disabled=not can_edit, height=80)
        if can_edit:
            st.session_state['pv_info']['commentaires'] = comm_input

    # ------------------------------------------------------------------------------
    # FENÊTRE 3 : HISTORIQUE, CONSULTATION ET GESTION DES PV
    # ------------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("📥 Re-télécharger un Procès-Verbal")

        historique = st.session_state.get('historique_pv', [])

        col_search1, col_search2 = st.columns(2)
        with col_search1:
            search_query = st.text_input(
                "🔍 Rechercher (réf, ouvrage, classe...)",
                placeholder="Ex: gare casa sud, B/394...",
                key="hist_search_query"
            )
        with col_search2:
            search_date = st.text_input(
                "📅 Rechercher par Date d'écrasement",
                placeholder="Ex: 2026-08-08",
                key="hist_search_date"
            )

        filtered_pvs = []
        for item in historique:
            pv_ref = str(item.get('ref_pv', '')).lower()
            pv_inf = item.get('pv_info', {})
            inf_p = item.get('info_prelevement', {})
            projet = str(pv_inf.get('projet', '') or inf_p.get('chantier', '')).lower()
            client = str(pv_inf.get('client', '') or inf_p.get('client', '')).lower()
            date_val = str(pv_inf.get('date', '') or inf_p.get('date_prelevement', '') or item.get('date_creation', '')).lower()

            match_q = True
            if search_query.strip():
                q = search_query.strip().lower()
                match_q = (q in pv_ref) or (q in projet) or (q in client)

            match_d = True
            if search_date.strip():
                d = search_date.strip().lower()
                match_d = (d in date_val)

            if match_q and match_d:
                filtered_pvs.append(item)

        st.markdown("<br><b>Sélectionnez le PV à consulter :</b>", unsafe_allow_html=True)

        if not filtered_pvs:
            st.warning("⚠️ Aucun PV trouvé selon vos critères de recherche.")
        else:
            def format_pv_label(item):
                p_ref = item.get('ref_pv', 'Sans Réf')
                p_inf = item.get('pv_info', {})
                inf_p = item.get('info_prelevement', {})
                proj = p_inf.get('projet', inf_p.get('chantier', '-'))
                client = p_inf.get('client', inf_p.get('client', '-'))
                date_str = p_inf.get('date', inf_p.get('date_prelevement', item.get('date_creation', '-')))
                pv_id = item.get('id', '-')
                return f"Référence : {p_ref} | Client : {client} | Ouvrage : {proj} | Échéance / Date : {date_str} | Lot ID #{pv_id}"

            selected_pv = st.selectbox(
                "Sélectionnez le PV à consulter :",
                options=filtered_pvs,
                format_func=format_pv_label,
                label_visibility="collapsed",
                key="hist_selected_pv_dropdown"
            )

            if selected_pv:
                sel_pv_info = selected_pv.get('pv_info', {})
                sel_info_p = selected_pv.get('info_prelevement', {})
                sel_data_granulats = selected_pv.get('data_granulats', {})
                ref_pv_clean = selected_pv.get('ref_pv', 'rapport').replace('/', '_')

                if REPORTLAB_AVAILABLE:
                    try:
                        pdf_data = generate_pv_pdf(sel_pv_info, sel_info_p, sel_data_granulats)
                        st.download_button(
                            label=f"📄 Télécharger le PV (PV_{ref_pv_clean}.pdf)",
                            data=pdf_data,
                            file_name=f"PV_{ref_pv_clean}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="primary"
                        )
                    except Exception as e:
                        st.error(f"Erreur de génération PDF : {e}")
                else:
                    html_data = generate_pv_html(sel_pv_info, sel_info_p, sel_data_granulats)
                    st.download_button(
                        label=f"📄 Télécharger le PV (PV_{ref_pv_clean}.html)",
                        data=html_data,
                        file_name=f"PV_{ref_pv_clean}.html",
                        mime="text/html",
                        use_container_width=True,
                        type="primary"
                    )

        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.subheader("📊 Base de données globale")

        col_db1, col_db2 = st.columns(2)
        with col_db1:
            db_ref_query = st.text_input(
                "🔍 Recherche par Réf. Contrôle",
                placeholder="Ex: REF-123-GARE CASA SUD",
                key="db_ref_query"
            )
        with col_db2:
            db_date_query = st.text_input(
                "📅 Recherche par Date de coulée",
                placeholder="Ex: 2026-08-24",
                key="db_date_query"
            )

        rows_data = []
        for item in historique:
            pv_ref = item.get('ref_pv', '')
            p_inf = item.get('pv_info', {})
            inf_p = item.get('info_prelevement', {})
            dt_create = item.get('date_creation', '')
            dt_prelev = p_inf.get('date', inf_p.get('date_prelevement', dt_create))

            match_ref = True
            if db_ref_query.strip():
                match_ref = (db_ref_query.strip().lower() in str(pv_ref).lower()) or (db_ref_query.strip().lower() in str(inf_p.get('chantier', '')).lower())

            match_dt = True
            if db_date_query.strip():
                match_dt = db_date_query.strip().lower() in str(dt_prelev).lower()

            if match_ref and match_dt:
                rows_data.append({
                    "id": item.get('id', '-'),
                    "betonnage_id": item.get('id', '-'),
                    "ref_controle": pv_ref,
                    "repere_eprouvette": f"/{item.get('id', 1)}",
                    "num_bl": inf_p.get('dossier_no', '-'),
                    "ouvrage": p_inf.get('projet', inf_p.get('chantier', '-')),
                    "classe_beton": "C25/30",
                    "statut_validation": "Validé",
                    "date_coulee": dt_prelev,
                    "affaissement_mm": 150,
                    "temp_beton_C": 20,
                    "echeance": "28 jours",
                    "date_ecrasement": dt_prelev
                })

        if rows_data:
            df_global = pd.DataFrame(rows_data)
            st.dataframe(df_global, use_container_width=True, hide_index=True)

            if is_baallal_admin or is_admin or can_edit:
                with st.expander("🗑️ Supprimer un PV de la base de données", expanded=False):
                    pv_to_del_ref = st.selectbox("Choisir le PV à supprimer :", options=[r['ref_controle'] for r in rows_data if r['ref_controle']])
                    if st.button("❌ Supprimer définitivement ce PV", type="secondary"):
                        st.session_state['historique_pv'] = [p for p in st.session_state['historique_pv'] if p.get('ref_pv') != pv_to_del_ref]
                        delete_pv_from_supabase(supabase_client, pv_to_del_ref)
                        st.success(f"PV '{pv_to_del_ref}' supprimé avec succès !")
                        st.rerun()
        else:
            st.info("Aucune donnée disponible dans la base de données globale.")
