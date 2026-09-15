import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import json
import copy
import io
import os
import base64

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
    """Sélectionne le plus petit tamis normatif (mm) dont le passant atteint au moins le % cible"""
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
    """Calcule ou interpole linéairement le passant au tamis cible"""
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

def _blank_data_granulats():
    """Structure vierge des 4 fractions (GII/GI/SC/SD)."""
    sieves_gii = [40, 31.5, 25, 20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063]
    sieves_gi  = [20, 16, 14, 12.5, 10, 8, 6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063]
    sieves_sable = [6.3, 5, 4, 3.15, 2.5, 2, 1.6, 1.25, 1, 0.8, 0.63, 0.5, 0.4, 0.315, 0.25, 0.2, 0.16, 0.125, 0.1, 0.08, 0.063]

    def _blank_mat(nom, classe, sieves, fi=None, la=None, mb=None, mf=None, se=None):
        return {
            'nom': nom, 'classe': classe,
            'ref_client': '', 'date_prelevement': '', 'lieu_prelevement': '',
            'sieves': list(sieves),
            'refus': [0.0] * len(sieves),
            'M1': 0.0, 'M2': 0.0, 'P': 0.0,
            'passants': [],
            'fi': fi, 'la': la, 'mb': mb, 'mf': mf, 'se': se
        }

    return {
        'GII': _blank_mat('Gravillons GII', '10/20', sieves_gii),
        'GI':  _blank_mat('Gravillons GI', '4/10', sieves_gi),
        'SD':  _blank_mat('Sable fin', '0/0,63', sieves_sable),
        'SC':  _blank_mat('Sable grossier', '0/4', sieves_sable)
    }

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

def _find_lpee_logo_path():
    """Cherche le logo LPEE à quelques emplacements usuels du dépôt."""
    _candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'lpee_logo.png'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lpee_logo.png'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'lpee_logo.png'),
        '/mnt/user-data/uploads/lpee_logo.png',
        'logo.png.jpg'
    ]
    return next((p for p in _candidates if os.path.isfile(p)), None)

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

    _logo_path = _find_lpee_logo_path()
    _logo_b64 = None
    if _logo_path:
        try:
            with open(_logo_path, 'rb') as _lf:
                _logo_b64 = base64.b64encode(_lf.read()).decode('ascii')
        except Exception:
            _logo_b64 = None

    if _logo_b64:
        org_header_html = f"""
        <div class="lpee-org-header">
            <img src="data:image/png;base64,{_logo_b64}" alt="Logo LPEE" class="lpee-org-logo">
            <div class="lpee-org-text">
                LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES (LPEE)<br>
                <span>CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT BENI MELLAL</span>
            </div>
        </div>"""
    else:
        org_header_html = """
        <div class="lpee-org-header" style="justify-content:center;">
            <div class="lpee-org-text" style="text-align:center;">
                LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES (LPEE)<br>
                <span>CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT BENI MELLAL</span>
            </div>
        </div>"""

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
    .lpee-org-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 6px 4px 10px 4px;
        margin-bottom: 8px;
    }}
    .lpee-org-logo {{
        height: 48px;
        width: 48px;
        object-fit: contain;
        flex-shrink: 0;
    }}
    .lpee-org-text {{
        font-weight: bold;
        font-size: 14px;
        color: #1e3a8a;
        line-height: 1.4;
    }}
    .lpee-org-text span {{
        font-weight: normal;
        font-size: 11.5px;
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
</style>
</head>
<body>
    <div class="lpee-pv-card">
        {org_header_html}
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

        <table class="signature-box">
            <tr>
                <td><b>LE COORDINATEUR DES ESSAIS</b><br><br><span style="color:#64748b;">Nom: {pv_info.get('coord_essais', 'O.IKEN')}</span><br>Visa:</td>
                <td><b>LE CHEF DU LABORATOIRE</b><br><br><span style="color:#64748b;">Nom: {pv_info.get('chef_labo', 'H.BAALLAL')}</span><br>Visa:</td>
                <td><b>REÇU PAR LE CLIENT</b><br><br><span style="color:#64748b;">Nom:</span><br>Visa:</td>
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
    ax.tick_params(axis='both', which='major', labelsize=7)
    ax.set_title("COURBE GRANULOMETRIQUE GLOBALE", fontsize=9, fontweight='bold', pad=6)

    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        fontsize=6.5,
        handlelength=1.3,
        handletextpad=0.35,
        columnspacing=1.2,
        labelspacing=0.35,
        borderpad=0.4,
        frameon=True,
        framealpha=0.95
    )

    fig.subplots_adjust(top=0.88, bottom=0.30, left=0.09, right=0.97)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_pv_pdf(pv_info, info_p, data_granulats):
    """Génère le fichier PDF structuré du PV d'identification avec courbe intégrée."""
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

    _logo_path = _find_lpee_logo_path()
    org_style = ParagraphStyle(
        'PDFOrgHeader', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=13,
        textColor=colors.HexColor('#1e3a8a'), alignment=1
    )
    org_text = (
        "LABORATOIRE PUBLIC D'ESSAIS ET D'ÉTUDES (LPEE)<br/>"
        "<font size=8.5>CENTRE TECHNIQUE REGIONAL DE CASABLANCA-SETTAT BENI MELLAL</font>"
    )

    if _logo_path:
        org_header_table = Table(
            [[Image(_logo_path, width=48, height=48), Paragraph(org_text, org_style)]],
            colWidths=[58, 507]
        )
        org_header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
    else:
        org_header_table = Table([[Paragraph(org_text, org_style)]], colWidths=[565])
        org_header_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))

    story.append(org_header_table)
    story.append(Spacer(1, 2))

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
        t3_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "95-100", "85-99", "40 (±20)", "50 (±20)", "≤ 16", "2,4-4,0", "≥ 60"]]
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
        t4_row2 = [Paragraph("Caractéristique générale", cell_left)] + [Paragraph(v, cell_norm) for v in ["100", "95-100", "85-99", "40 (±20)", "50 (±25)", "≤ 10", "VSS 2", "-"]]
        flowables.append(build_mat_table(t4_cols, t4_row1, t4_row2))

        return flowables

    story.extend(build_adjustable_tables(0))
    story.append(Spacer(1, 4))

    # Courbe Granulométrique
    curve_buf = create_curve_image_buffer(data_granulats, ref_b, fig_width=7.8, fig_height=2.3)
    story.append(Image(curve_buf, width=565, height=166))
    story.append(Spacer(1, 4))

    # Commentaires et Signatures
    comm_txt = f"<b>COMMENTAIRES :</b><br/>{pv_info.get('commentaires', '')}"
    comm_table = Table([[Paragraph(comm_txt, cell_left)]], colWidths=[565])
    comm_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(comm_table)
    story.append(Spacer(1, 4))

    sig_data = [[
        Paragraph("<b>LE COORDINATEUR DES ESSAIS</b><br/><br/><font size=6.5 color='#64748b'>Nom: " + str(pv_info.get('coord_essais', 'O.IKEN')) + "</font><br/>Visa:", cell_bold),
        Paragraph("<b>LE CHEF DU LABORATOIRE</b><br/><br/><font size=6.5 color='#64748b'>Nom: " + str(pv_info.get('chef_labo', 'H.BAALLAL')) + "</font><br/>Visa:", cell_bold),
        Paragraph("<b>REÇU PAR LE CLIENT</b><br/><br/><font size=6.5 color='#64748b'>Nom:</font><br/>Visa:", cell_bold)
    ]]
    sig_table = Table(sig_data, colWidths=[188.33, 188.33, 188.33])
    sig_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 25),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
