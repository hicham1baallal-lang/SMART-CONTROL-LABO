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
from xml.sax.saxutils import escape as xml_escape

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
    return float(val) if not np.isnan(val) else 0.0

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
            passants_fmt.append(max(0.0, round(float(p), 1)))
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
        return float(val)
        
    val = s_arr[-1]
    return float(val)

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
        return float(d_val or 0.0), float(D_val or 0.0)

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

def format_sieve_display(val):
    """Formate proprement un nombre de tamis pour l'affichage (évite les erreurs de type string/int)."""
    if val is None:
        return "0"
    try:
        val_f = float(val)
    except (TypeError, ValueError):
        return "0"
    if np.isnan(val_f):
        return "0"
    if val_f.is_integer():
        return str(int(val_f))
    return str(val_f).replace('.', ',')

def _safe_text(value, default=''):
    """Retourne toujours un texte exploitable, même si Supabase renvoie un nombre."""
    if value is None:
        return default
    return str(value)

def _next_snapshot_id(history):
    """Calcule un identifiant numérique sans additionner une chaîne et un entier.

    Les anciennes lignes peuvent contenir ``id`` sous forme de texte (par
    exemple ``"12"``).  ``max(existing_ids) + 1`` provoquait alors :
    ``can only concatenate str (not "int") to str``.
    """
    numeric_ids = []
    for item in history or []:
        raw_id = item.get('id') if isinstance(item, dict) else None
        try:
            if raw_id is not None and str(raw_id).strip() != '':
                numeric_ids.append(int(float(raw_id)))
        except (TypeError, ValueError):
            # Les identifiants non numériques (UUID, valeur vide, etc.) sont
            # ignorés pour le calcul du prochain identifiant local.
            continue
    return max(numeric_ids, default=0) + 1

def calculate_characteristic_data(mat_data, tamis_D=None):
    """Déduit la liste des tamis caractéristiques (2D, 1.4D, D, d, d/2)"""
    d, D_calc = get_d_D_from_material(mat_data)
    D = float(tamis_D) if (tamis_D is not None and tamis_D > 0) else D_calc
    
    sieves_dict = {
        '2D': float(2 * D),
        '1.4D': float(1.4 * D),
        'D': float(D),
        'd': float(d),
        'd/2': float(d / 2)
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
    ]
    return next((p for p in _candidates if os.path.isfile(p)), None)

def get_month_year_label(date_str):
    """Extrait un libellé 'Mois Année' (ex: 'Janvier 2026') à partir d'une chaîne de date."""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            months_fr = {
                1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
                5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
                9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
            }
            return f"{months_fr[dt.month]} {dt.year}"
        except ValueError:
            continue
    return None

def _generate_granulometry_plot_png(data_granulats, ref_b=''):
    """Génère une courbe granulométrique PNG autonome pour le HTML et le PDF."""
    colors_map = {'GII': '#0b1f5e', 'GI': '#0284c7', 'SC': '#16a34a', 'SD': '#ea580c'}
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=160)
    has_curve = False

    for key in ['GII', 'GI', 'SC', 'SD']:
        data = (data_granulats or {}).get(key, {})
        sieves = data.get('sieves', [])
        passants = data.get('passants', [])
        if not sieves or not passants or len(sieves) != len(passants):
            continue

        points = sorted(
            [(float(s), float(p)) for s, p in zip(sieves, passants) if float(s) > 0],
            key=lambda item: item[0]
        )
        if not points:
            continue

        has_curve = True
        x_values, y_values = zip(*points)
        suffix = SUFFIX_MAP.get(key, '')
        name = _safe_text(data.get('nom', key), key)
        label = f"{name} ({ref_b}{suffix})" if ref_b else name
        ax.plot(
            x_values,
            y_values,
            marker='o',
            markersize=3,
            linewidth=1.8,
            color=colors_map.get(key, '#334155'),
            label=label
        )

    ax.set_xscale('log')
    ax.set_xlabel('Tamis (mm)', fontsize=9)
    ax.set_ylabel('% Passants cumulés', fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(True, which='both', linestyle='--', linewidth=0.45, alpha=0.45)
    ax.set_title('Courbe granulométrique', fontsize=11, fontweight='bold')

    if has_curve:
        ax.legend(loc='best', fontsize=7, frameon=True)
    else:
        ax.text(
            0.5, 0.5, 'Aucune donnée granulométrique disponible',
            ha='center', va='center', transform=ax.transAxes, fontsize=10
        )
        ax.set_xlim(0.05, 50)

    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()

def generate_pv_html(pv_info, info_p, data_granulats):
    """Génère le document HTML complet et autonome du PV pour impression / téléchargement."""
    gii_data = data_granulats.get('GII', {})
    gi_data  = data_granulats.get('GI', {})
    sc_data  = data_granulats.get('SC', {})
    sd_data  = data_granulats.get('SD', {})

    ref_b = info_p.get('num_rapport', info_p.get('ref_base', '26/260/LGV/CS/1237'))
    curve_png = _generate_granulometry_plot_png(data_granulats, _safe_text(ref_b))
    curve_b64 = base64.b64encode(curve_png).decode('ascii') if curve_png else ''

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

    curve_html = (
        f"""
        <div class="curve-box">
            <div class="curve-title">COURBE GRANULOMÉTRIQUE</div>
            <img src="data:image/png;base64,{curve_b64}" alt="Courbe granulométrique" class="curve-image">
        </div>"""
        if curve_b64 else
        '<div class="curve-box"><div class="curve-title">COURBE GRANULOMÉTRIQUE</div><p>Aucune donnée disponible.</p></div>'
    )

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
    .curve-box {{
        margin-top: 18px;
        margin-bottom: 15px;
        padding: 10px;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        text-align: center;
        page-break-inside: avoid;
    }}
    .curve-title {{
        color: #1e3a8a;
        font-weight: bold;
        font-size: 13px;
        margin-bottom: 8px;
    }}
    .curve-image {{
        display: block;
        width: 100%;
        max-width: 780px;
        height: auto;
        margin: 0 auto;
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

        <!-- TABLEAU 1 : GRAVILLONS GII -->
        <table class="lpee-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Désignations</th>
                    <th>2D</th><th>1,4D</th><th>D</th><th>d</th><th>d/2</th><th>f</th><th>FI</th><th>LA</th>
                </tr>
                <tr>
                    <th>{format_sieve_display(gii_sieves['2D'])}</th>
                    <th>{format_sieve_display(gii_sieves['1.4D'])}</th>
                    <th>{format_sieve_display(gii_sieves['D'])}</th>
                    <th>{format_sieve_display(gii_sieves['d'])}</th>
                    <th>{format_sieve_display(gii_sieves['d/2'])}</th>
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
                    <th>{format_sieve_display(gi_sieves['2D'])}</th>
                    <th>{format_sieve_display(gi_sieves['1.4D'])}</th>
                    <th>{format_sieve_display(gi_sieves['D'])}</th>
                    <th>{format_sieve_display(gi_sieves['d'])}</th>
                    <th>{format_sieve_display(gi_sieves['d/2'])}</th>
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
                    <th>{format_sieve_display(sc_sieves['2D'])}</th>
                    <th>{format_sieve_display(sc_sieves['1.4D'])}</th>
                    <th>{format_sieve_display(sc_sieves['D'])}</th>
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
                    <th>{format_sieve_display(sd_sieves['2D'])}</th>
                    <th>{format_sieve_display(sd_sieves['1.4D'])}</th>
                    <th>{format_sieve_display(sd_sieves['D'])}</th>
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
            </tbody>
        </table>

        {curve_html}

        <div class="comments-box">
            <b>COMMENTAIRES :</b><br>
            {pv_info.get('commentaires', '')}
        </div>

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

def generate_pv_pdf(pv_info, info_p, data_granulats):
    """Génère le fichier PDF structuré du PV d'identification avec courbe intégrée."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("La bibliothèque ReportLab n'est pas installée.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'PDFTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=13,
        textColor=colors.white, alignment=1
    )
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
    else:
        org_header_table = Table([[Paragraph(org_text, org_style)]], colWidths=[565])

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
        return flowables

    pdf_section_style = ParagraphStyle(
        'PDFSectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor('#1e3a8a'),
        spaceBefore=4,
        spaceAfter=3
    )
    pdf_table_header = ParagraphStyle(
        'PDFTableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5.8,
        leading=6.8,
        textColor=colors.white,
        alignment=1
    )
    pdf_table_subheader = ParagraphStyle(
        'PDFTableSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.8,
        leading=6.8,
        textColor=colors.HexColor('#0f172a'),
        alignment=1
    )
    pdf_table_cell = ParagraphStyle(
        'PDFTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.2,
        leading=7.2,
        alignment=1
    )
    pdf_table_cell_left = ParagraphStyle(
        'PDFTableCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.2,
        leading=7.2,
        alignment=0
    )

    def pdf_paragraph(value, style=pdf_table_cell, default='-'):
        text = _safe_text(value, default)
        return Paragraph(xml_escape(text), style)

    def pdf_number(value, digits=0):
        try:
            number = float(value)
            return f"{number:.{digits}f}"
        except (TypeError, ValueError):
            return '-'

    def add_result_table(key, title, columns, subcolumns, values):
        """Ajoute au PDF un tableau de synthèse complet pour une fraction."""
        mat_data = (data_granulats or {}).get(key, {})
        table_width = 565
        designation_width = 125
        value_width = (table_width - designation_width) / len(columns)
        table_data = [
            [pdf_paragraph('Désignations', pdf_table_header)] +
            [pdf_paragraph(column, pdf_table_header) for column in columns],
            [pdf_paragraph('', pdf_table_subheader)] +
            [pdf_paragraph(column, pdf_table_subheader) for column in subcolumns],
            [pdf_paragraph(
                f"{_safe_text(mat_data.get('nom', key), key)} - ({_safe_text(ref_b)}/{SUFFIX_MAP.get(key, '').lstrip('/')})",
                pdf_table_cell_left
            )] +
            [pdf_paragraph(value) for value in values]
        ]
        result_table = Table(
            table_data,
            colWidths=[designation_width] + [value_width] * len(columns),
            repeatRows=2
        )
        result_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#eff6ff')),
            ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#f1f5f9')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('SPAN', (0, 0), (0, 1)),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        return KeepTogether([
            Paragraph(xml_escape(title), pdf_section_style),
            result_table,
            Spacer(1, 5)
        ])

    story.extend(build_adjustable_tables(0))

    # Les tableaux de résultats étaient absents de l'ancien générateur PDF.
    # Ils sont maintenant ajoutés avec les mêmes données que l'aperçu HTML.
    result_data = data_granulats or {}
    result_specs = [
        (
            'GII',
            'TABLEAU DES RÉSULTATS - GRAVILLONS GII',
            ['2D', '1,4D', 'D', 'd', 'd/2', 'f', 'FI', 'LA'],
            [
                format_sieve_display(calculate_characteristic_data(result_data.get('GII', {}))[0]['2D']),
                format_sieve_display(calculate_characteristic_data(result_data.get('GII', {}))[0]['1.4D']),
                format_sieve_display(calculate_characteristic_data(result_data.get('GII', {}))[0]['D']),
                format_sieve_display(calculate_characteristic_data(result_data.get('GII', {}))[0]['d']),
                format_sieve_display(calculate_characteristic_data(result_data.get('GII', {}))[0]['d/2']),
                '% < 63 µm', '-', '-'
            ],
            lambda d: [
                pdf_number(calculate_characteristic_data(d)[1]['2D']),
                pdf_number(calculate_characteristic_data(d)[1]['1.4D']),
                pdf_number(calculate_characteristic_data(d)[1]['D']),
                pdf_number(calculate_characteristic_data(d)[1]['d']),
                pdf_number(calculate_characteristic_data(d)[1]['d/2']),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.063), 1),
                _safe_text(d.get('fi'), '-'),
                _safe_text(d.get('la'), '-')
            ]
        ),
        (
            'GI',
            'TABLEAU DES RÉSULTATS - GRAVILLONS GI',
            ['2D', '1,4D', 'D', 'd', 'd/2', 'f', 'FI', 'LA'],
            None,
            lambda d: [
                pdf_number(calculate_characteristic_data(d)[1]['2D']),
                pdf_number(calculate_characteristic_data(d)[1]['1.4D']),
                pdf_number(calculate_characteristic_data(d)[1]['D']),
                pdf_number(calculate_characteristic_data(d)[1]['d']),
                pdf_number(calculate_characteristic_data(d)[1]['d/2']),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.063), 1),
                _safe_text(d.get('fi'), '-'),
                _safe_text(d.get('la'), '-')
            ]
        ),
        (
            'SC',
            'TABLEAU DES RÉSULTATS - SABLE GROSSIER',
            ['2D', '1,4D', 'D', '% < 1 mm', '% < 250 µm', '% < 63 µm', 'MF', 'SE (10)'],
            None,
            lambda d: [
                pdf_number(calculate_characteristic_data(d)[1]['2D']),
                pdf_number(calculate_characteristic_data(d)[1]['1.4D']),
                pdf_number(calculate_characteristic_data(d)[1]['D']),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 1.0)),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.25)),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.063), 1),
                _safe_text(d.get('mf'), '-'),
                _safe_text(d.get('se'), '-')
            ]
        ),
        (
            'SD',
            'TABLEAU DES RÉSULTATS - SABLE FIN',
            ['2D', '1,4D', 'D', '% < 1 mm', '% < 250 µm', '% < 63 µm', 'MB'],
            None,
            lambda d: [
                pdf_number(calculate_characteristic_data(d)[1]['2D']),
                pdf_number(calculate_characteristic_data(d)[1]['1.4D']),
                pdf_number(calculate_characteristic_data(d)[1]['D']),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 1.0)),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.25)),
                pdf_number(get_passant_at_sieve(d.get('sieves', []), d.get('passants', []), 0.063), 1),
                _safe_text(d.get('mb'), '-')
            ]
        )
    ]

    for key, title, columns, subcolumns, values_builder in result_specs:
        mat_data = result_data.get(key, {})
        char_sieves, _ = calculate_characteristic_data(mat_data)
        if subcolumns is None:
            subcolumns = [
                format_sieve_display(char_sieves['2D']),
                format_sieve_display(char_sieves['1.4D']),
                format_sieve_display(char_sieves['D'])
            ] + ['-', '-', '-', '-'][:len(columns) - 3]
        values = values_builder(mat_data) if callable(values_builder) else values_builder
        story.append(add_result_table(key, title, columns, subcolumns, values))

    curve_png = _generate_granulometry_plot_png(result_data, _safe_text(ref_b))
    story.append(Paragraph('COURBE GRANULOMÉTRIQUE', pdf_section_style))
    story.append(Image(io.BytesIO(curve_png), width=535, height=285))
    story.append(Spacer(1, 5))

    comments = xml_escape(_safe_text(pv_info.get('commentaires', ''), ''))
    story.append(Paragraph('COMMENTAIRES', pdf_section_style))
    story.append(Table(
        [[Paragraph(comments or '-', cell_left)]],
        colWidths=[565],
        style=TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ])
    ))
    signature_table = Table(
        [[
            Paragraph('<b>LE COORDINATEUR DES ESSAIS</b><br/><br/>Nom : ' +
                      xml_escape(_safe_text(pv_info.get('coord_essais', 'O.IKEN'))), cell_norm),
            Paragraph('<b>LE CHEF DU LABORATOIRE</b><br/><br/>Nom : ' +
                      xml_escape(_safe_text(pv_info.get('chef_labo', 'H.BAALLAL'))), cell_norm),
            Paragraph('<b>REÇU PAR LE CLIENT</b><br/><br/>Nom :', cell_norm)
        ]],
        colWidths=[188.3, 188.3, 188.3],
        rowHeights=[62]
    )
    signature_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 8))
    story.append(signature_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def fetch_pvs_from_supabase(supabase_client):
    """Charge l'historique complet des PV depuis la base de données Supabase."""
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
    """Sauvegarde ou met à jour de façon permanente un PV sur la base de données Supabase."""
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
    prefix = kwargs.get('key_prefix', 'pvg')

    if '_pending_pv_load' in st.session_state:
        _pending = st.session_state.pop('_pending_pv_load')
        st.session_state['info_prelevement'] = _pending.get('info_prelevement', {})
        st.session_state['pv_info'] = _pending.get('pv_info', {})
        st.session_state['data_granulats'] = _pending.get('data_granulats', {})

        _info_p_ld = st.session_state['info_prelevement']
        _pv_info_ld = st.session_state['pv_info']

        st.session_state[f"{prefix}_common_client"] = _info_p_ld.get('client', '')
        st.session_state[f"{prefix}_common_chantier"] = _info_p_ld.get('chantier', '')
        st.session_state[f"{prefix}_common_dossier"] = _info_p_ld.get('dossier_no', '')
        st.session_state[f"{prefix}_common_date_prelev"] = _info_p_ld.get('date_prelevement', '')
        st.session_state[f"{prefix}_common_lieu_prelev"] = _info_p_ld.get('lieu_prelevement', '')
        st.session_state[f"{prefix}_common_provenance"] = _info_p_ld.get('provenance', '')
        st.session_state[f"{prefix}_common_num_rapport"] = _info_p_ld.get('num_rapport', '')

        st.session_state[f"{prefix}_pv_proj"] = _pv_info_ld.get('projet', '')
        st.session_state[f"{prefix}_pv_cli"] = _pv_info_ld.get('client', '')
        st.session_state[f"{prefix}_pv_dt"] = _pv_info_ld.get('date', '')
        st.session_state[f"{prefix}_pv_coo"] = _pv_info_ld.get('coord_essais', 'O.IKEN')
        st.session_state[f"{prefix}_pv_che"] = _pv_info_ld.get('chef_labo', 'H.BAALLAL')
        st.session_state[f"{prefix}_pv_comm_input"] = _pv_info_ld.get('commentaires', '')

        st.session_state['success_msg'] = _pending.get('success_msg', "✅ PV chargé.")
        st.session_state['_pv_edit_mode'] = _pending.get('edit_ref')

    if st.session_state.pop('_pending_pv_reset', False):
        _kept_chantier = st.session_state.get('info_prelevement', {}).get('chantier', '')
        _kept_client = st.session_state.get('info_prelevement', {}).get('client', '')
        _kept_coord = st.session_state.get('pv_info', {}).get('coord_essais', 'O.IKEN')
        _kept_chef = st.session_state.get('pv_info', {}).get('chef_labo', 'H.BAALLAL')

        st.session_state['info_prelevement'] = {
            'chantier': _kept_chantier,
            'client': _kept_client,
            'dossier_no': '',
            'date_prelevement': '',
            'lieu_prelevement': '',
            'provenance': '',
            'num_rapport': '',
            'ref_base': ''
        }
        st.session_state['pv_info'] = {
            'projet': _kept_chantier,
            'client': _kept_client,
            'ref_pv': '',
            'date': '',
            'commentaires': "Les essais d'identifications des granulats pour béton sont conformes aux exigences de la norme NF EN 12620 et NF P 18-545",
            'coord_essais': _kept_coord,
            'chef_labo': _kept_chef
        }
        st.session_state['data_granulats'] = _blank_data_granulats()
        st.session_state['_pv_edit_mode'] = None

        for _wk in list(st.session_state.keys()):
            if _wk.startswith(f"{prefix}_"):
                del st.session_state[_wk]

        st.session_state['success_msg'] = "🆕 Nouveau prélèvement prêt."

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
        st.session_state['data_granulats'] = _blank_data_granulats()

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

    def _build_pv_snapshot():
        next_id = _next_snapshot_id(st.session_state.get('historique_pv', []))
        ref_pv = _safe_text(st.session_state['pv_info'].get('ref_pv', '')).strip()
        return {
            'id': next_id,
            'date_creation': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ref_pv': ref_pv,
            'projet': _safe_text(st.session_state['pv_info'].get('projet', '')),
            'client': _safe_text(st.session_state['pv_info'].get('client', '')),
            'info_prelevement': copy.deepcopy(st.session_state['info_prelevement']),
            'pv_info': copy.deepcopy(st.session_state['pv_info']),
            'data_granulats': copy.deepcopy(st.session_state['data_granulats'])
        }

    st.title("🏗️ Module Identification des Granulats pour Béton")
    
    if not can_edit:
        st.info("👁️ **Mode Consultation** : Vous êtes en lecture seule.")

    saved_num_rapports = [
        _safe_text(pv.get('ref_pv', '')).strip().lower()
        for pv in st.session_state.get('historique_pv', []) 
        if pv.get('ref_pv')
    ]

    tabs = st.tabs([
        "1️⃣ Feuilles d'Essais Complets",
        "2️⃣ PV d'Identification / Synthèse",
        "3️⃣ Historique & Téléchargement",
        "📊 Synthèse & Filtrage par Mois"
    ])

    # ------------------------------------------------------------------------------
    # FENÊTRE 1 : FEUILLES D'ESSAIS COMPLETS
    # ------------------------------------------------------------------------------
    with tabs[0]:
        st.header("Feuilles d'Analyse Granulométrique et Caractéristiques")

        if can_edit:
            col_new1, col_new2 = st.columns([1, 3])
            with col_new1:
                if st.button("➕ Ajouter un autre prélèvement", use_container_width=True, key=f"{prefix}_btn_new_prelevement"):
                    st.session_state['_pending_pv_reset'] = True
                    st.rerun()
            with col_new2:
                st.caption("Garde le Client et le Chantier actuels, mais vide le N° Rapport et les pesées.")

        st.markdown("##### 📍 Informations de prélèvement")
        c1, c2, c3 = st.columns(3)
        c4, c5, c6 = st.columns(3)
        
        info_p = st.session_state['info_prelevement']
        
        new_client       = c1.text_input("Client", value=info_p.get('client', 'TGCC'), disabled=not can_edit, key=f"{prefix}_common_client")
        new_chantier     = c2.text_input("Chantier", value=info_p.get('chantier', ''), disabled=not can_edit, key=f"{prefix}_common_chantier")
        new_dossier      = c3.text_input("N° Dossier", value=info_p.get('dossier_no', ''), disabled=not can_edit, key=f"{prefix}_common_dossier")
        new_date_prelev  = c4.text_input("Date de prélèvement", value=info_p.get('date_prelevement', '23/07/2026'), disabled=not can_edit, key=f"{prefix}_common_date_prelev")
        new_lieu_prelev  = c5.text_input("Lieu de prélèvement", value=info_p.get('lieu_prelevement', 'Stock sur centrale à béton'), disabled=not can_edit, key=f"{prefix}_common_lieu_prelev")
        new_provenance   = c6.text_input("Provenance échantillon", value=info_p.get('provenance', 'TG PREFA OULAD SALEH'), disabled=not can_edit, key=f"{prefix}_common_provenance")
        
        new_num_rapport  = st.text_input(
            "N° RAPPORT D'ESSAI N°",
            value=_safe_text(info_p.get('num_rapport', default_num_rapport)),
            disabled=not can_edit,
            key=f"{prefix}_common_num_rapport"
        )
        # Streamlit renvoie normalement une chaîne, mais cette normalisation
        # protège aussi les dossiers historiques dont la valeur est numérique.
        new_num_rapport = _safe_text(new_num_rapport).strip()
        new_ref_base     = new_num_rapport.strip()

        is_duplicate = new_num_rapport.lower() in saved_num_rapports if new_num_rapport else False
        _edit_mode_ref = _safe_text(st.session_state.get('_pv_edit_mode') or '').strip().lower()
        _new_num_norm = new_num_rapport.lower()
        is_authorized_edit = is_duplicate and bool(_edit_mode_ref) and _edit_mode_ref == _new_num_norm
        is_blocked_duplicate = is_duplicate and not is_authorized_edit

        if is_authorized_edit:
            st.info(f"✏️ **Mode modification :** édition du PV existant N° `{new_num_rapport}`.")
        elif is_blocked_duplicate:
            st.error(f"⛔ **Numéro de rapport en double !** Le N° `{new_num_rapport}` existe déjà dans l'historique.")

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
            horizontal=True,
            key=f"{prefix}_radio_selected_mat"
        )
        
        mat_key_map = {"GII (10/20)": "GII", "GI (4/10)": "GI", "SC (0/4)": "SC", "SD (0/0,63)": "SD"}
        key = mat_key_map[selected_mat]
        mat_data = st.session_state['data_granulats'][key]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"Saisie des données : {mat_data['nom']}")
            c_m1, c_m2, c_p = st.columns(3)
            new_M1 = c_m1.number_input("Masse totale M1 (g)", value=float(mat_data.get('M1', 1000.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_m1_{key}")
            new_M2 = c_m2.number_input("Masse après lavage M2 (g)", value=float(mat_data.get('M2', 1000.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_m2_{key}")
            new_P  = c_p.number_input("Matériau au fond P (g)", value=float(mat_data.get('P', 0.0)), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_p_{key}")
            
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
                key=f"{prefix}_editor_{key}",
                column_config={
                    "Tamis (mm)": st.column_config.NumberColumn(disabled=True),
                    "Masse de refus Ri (g)": st.column_config.NumberColumn(disabled=not can_edit, min_value=0.0, step=0.1, format="%.1f"),
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

            calculated_mf = compute_MF(mat_data['sieves'], mat_data['passants'])

            col_a, col_b = st.columns(2)
            if key in ["GII", "GI"]:
                with col_a:
                    fi_val = st.number_input("Coeff. Aplatissement (FI)", value=float(mat_data.get('fi') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_fi_{key}")
                with col_b:
                    la_val = st.number_input("Los Angeles (LA)", value=float(mat_data.get('la') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_la_{key}")
                mb_val, mf_val, se_val = 0.0, 0.0, 0.0
            else:
                with col_a:
                    mb_val = st.number_input("Valeur de Bleu (MB)", value=float(mat_data.get('mb') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_mb_{key}")
                with col_b:
                    mf_val = st.number_input("Module de Finesse (MF)", value=float(calculated_mf), disabled=True, key=f"{prefix}_mf_{key}")
                    se_val = st.number_input("Équivalent de Sable (SE 10)", value=float(mat_data.get('se') or 0.0), step=0.1, format="%.1f", disabled=not can_edit, key=f"{prefix}_se_{key}")
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
                    "% Passant": [f"{char_passants[k]:.1f} %" for k in ['2D', '1.4D', 'D', 'd', 'd/2']]
                })
                st.dataframe(df_char_mat, hide_index=True, use_container_width=True)

            fig = go.Figure()
            colors_map = {'GII': 'navy', 'GI': '#0284c7', 'SC': '#16a34a', 'SD': '#ea580c'}
            for k, d in st.session_state['data_granulats'].items():
                if d.get('sieves') and d.get('passants') and len(d['sieves']) == len(d['passants']):
                    s_s, p_s = zip(*sorted(zip(d['sieves'], d['passants'])))
                    fig.add_trace(go.Scatter(
                        x=s_s, y=p_s, mode="lines+markers",
                        name=f"{d['nom']} ({new_ref_base}{SUFFIX_MAP[k]})" if new_ref_base else d['nom'],
                        line=dict(color=colors_map[k], width=2.5 if k == key else 1.5)
                    ))
            fig.update_layout(
                xaxis=dict(type="log", title="Tamis (mm)", tickmode="array", tickvals=SIEVE_TICKVALS, ticktext=SIEVE_TICKTEXT),
                yaxis=dict(title="% Passants Cumulés", range=[0, 105]),
                height=380, margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        if can_edit:
            if st.button("✅ Valider et enregistrer l'ensemble des essais", type="primary", use_container_width=True, key=f"{prefix}_btn_validate_all", disabled=is_blocked_duplicate):
                for mat_k in st.session_state['data_granulats'].keys():
                    update_passants(st.session_state['data_granulats'][mat_k])
                    if mat_k in ["SC", "SD"]:
                        st.session_state['data_granulats'][mat_k]['mf'] = compute_MF(
                            st.session_state['data_granulats'][mat_k]['sieves'],
                            st.session_state['data_granulats'][mat_k]['passants']
                        )

                st.session_state['pv_info']['ref_pv'] = new_num_rapport
                st.session_state['pv_info']['projet'] = new_chantier
                st.session_state['pv_info']['client'] = new_client
                st.session_state['pv_info']['date'] = new_date_prelev

                snapshot = _build_pv_snapshot()
                existing_idx = None
                for idx_pv, p_item in enumerate(st.session_state['historique_pv']):
                    if _safe_text(p_item.get('ref_pv', '')).strip().lower() == new_num_rapport.lower():
                        existing_idx = idx_pv
                        break

                if existing_idx is not None:
                    st.session_state['historique_pv'][existing_idx] = snapshot
                else:
                    st.session_state['historique_pv'].append(snapshot)
                
                save_pv_to_supabase(supabase_client, snapshot)
                st.session_state['success_msg'] = f"✅ Rapport N° '{new_num_rapport}' validé et enregistré avec succès !"
                st.rerun()

    # ------------------------------------------------------------------------------
    # FENÊTRE 2 : PV D'IDENTIFICATION / SYNTHÈSE
    # ------------------------------------------------------------------------------
    with tabs[1]:
        st.header("PV d'Identification des Granulats pour Béton")
        pv_info_dict = st.session_state['pv_info']

        with st.expander("⚙️ Modifier les entêtes et signataires du PV", expanded=False):
            c1, c2, c3 = st.columns(3)
            c4, c5, c6 = st.columns(3)
            projet_val = c1.text_input("Chantier / Projet", pv_info_dict.get('projet', ''), disabled=not can_edit, key=f"{prefix}_pv_proj")
            client_val = c2.text_input("Client", pv_info_dict.get('client', ''), disabled=not can_edit, key=f"{prefix}_pv_cli")
            ref_val = c3.text_input("N° RAPPORT D'ESSAI N°", st.session_state['info_prelevement'].get('num_rapport', default_num_rapport), disabled=True, key=f"{prefix}_pv_ref")
            date_val = c4.text_input("Date du prélèvement", pv_info_dict.get('date', ''), disabled=not can_edit, key=f"{prefix}_pv_dt")
            coord_val = c5.text_input("Coordinateur des essais", pv_info_dict.get('coord_essais', 'O.IKEN'), disabled=not can_edit, key=f"{prefix}_pv_coo")
            chef_val = c6.text_input("Chef du laboratoire", pv_info_dict.get('chef_labo', 'H.BAALLAL'), disabled=not can_edit, key=f"{prefix}_pv_che")

            if can_edit:
                st.session_state['pv_info']['projet'] = projet_val
                st.session_state['pv_info']['client'] = client_val
                st.session_state['pv_info']['date'] = date_val
                st.session_state['pv_info']['coord_essais'] = coord_val
                st.session_state['pv_info']['chef_labo'] = chef_val

        current_pv_html = generate_pv_html(st.session_state['pv_info'], st.session_state['info_prelevement'], st.session_state['data_granulats'])
        st.markdown(clean_html(current_pv_html), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_dl_pdf1, col_dl_pdf2 = st.columns(2)
        with col_dl_pdf1:
            st.download_button(
                label="📄 Télécharger le Rapport PV (HTML)",
                data=current_pv_html,
                file_name=f"PV_Granulats_{st.session_state['pv_info'].get('ref_pv', 'rapport').replace('/', '_')}.html",
                mime="text/html", use_container_width=True, key=f"{prefix}_dl_html_tab2"
            )
        with col_dl_pdf2:
            if REPORTLAB_AVAILABLE:
                try:
                    pdf_bytes = generate_pv_pdf(st.session_state['pv_info'], st.session_state['info_prelevement'], st.session_state['data_granulats'])
                    st.download_button(
                        label="🔴 Télécharger le Rapport PV (PDF)",
                        data=pdf_bytes,
                        file_name=f"PV_Granulats_{st.session_state['pv_info'].get('ref_pv', 'rapport').replace('/', '_')}.pdf",
                        mime="application/pdf", use_container_width=True, type="primary", key=f"{prefix}_dl_pdf_tab2"
                    )
                except Exception as e:
                    st.error(f"Erreur PDF : {e}")
            else:
                st.warning("ReportLab non disponible pour le PDF.")

        comm_input = st.text_area("COMMENTAIRES :", value=st.session_state['pv_info'].get('commentaires', ''), disabled=not can_edit, height=80, key=f"{prefix}_pv_comm_input")
        if can_edit:
            st.session_state['pv_info']['commentaires'] = comm_input

    # ------------------------------------------------------------------------------
    # FENÊTRE 3 : HISTORIQUE & TÉLÉCHARGEMENT
    # ------------------------------------------------------------------------------
    with tabs[2]:
        st.header("Historique et Sauvegarde des PV")
        historique = st.session_state.get('historique_pv', [])

        if not historique:
            st.info("Aucun PV enregistré pour le moment dans l'historique.")
        else:
            df_hist = pd.DataFrame([
                {
                    "ID": item.get('id'),
                    "N° Rapport": item.get('ref_pv'),
                    "Client": item.get('client'),
                    "Chantier": item.get('projet'),
                    "Date de création": item.get('date_creation')
                } for item in historique
            ])
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

            st.markdown("### 🔍 Actions sur l'historique")
            selected_ref = st.selectbox("Sélectionner un PV par son N° de Rapport", [item.get('ref_pv') for item in historique], key=f"{prefix}_hist_select")
            
            selected_item = next((item for item in historique if item.get('ref_pv') == selected_ref), None)
            if selected_item:
                col_h1, col_h2, col_h3 = st.columns(3)
                with col_h1:
                    if st.button("📂 Charger ce PV", use_container_width=True, key=f"{prefix}_btn_load_hist"):
                        st.session_state['_pending_pv_load'] = {
                            'info_prelevement': selected_item.get('info_prelevement', {}),
                            'pv_info': selected_item.get('pv_info', {}),
                            'data_granulats': selected_item.get('data_granulats', {}),
                            'success_msg': f"✅ PV N° '{selected_ref}' chargé avec succès.",
                            'edit_ref': selected_item.get('ref_pv')
                        }
                        st.rerun()
                with col_h2:
                    if can_edit and st.button("🗑️ Supprimer ce PV", use_container_width=True, type="secondary", key=f"{prefix}_btn_del_hist"):
                        st.session_state['historique_pv'] = [it for it in historique if it.get('ref_pv') != selected_ref]
                        delete_pv_from_supabase(supabase_client, selected_ref)
                        st.success(f"🗑️ PV N° '{selected_ref}' supprimé.")
                        st.rerun()

    # ------------------------------------------------------------------------------
    # FENÊTRE 4 : SYNTHÈSE & FILTRAGE PAR MOIS
    # ------------------------------------------------------------------------------
    with tabs[3]:
        st.header("📊 Synthèse & Filtrage des PV par Mois")
        st.markdown("Recherchez et filtrez les rapports d'essais par mois de prélèvement ou de création (ex: *Janvier 2026*, *Février 2026*).")

        historique = st.session_state.get('historique_pv', [])
        
        if not historique:
            st.info("ℹ️ Aucun PV disponible dans l'historique pour effectuer une synthèse.")
        else:
            mois_disponibles = set()
            for item in historique:
                d_pv = item.get('pv_info', {}).get('date') or item.get('date_creation')
                m_label = get_month_year_label(d_pv)
                if m_label:
                    mois_disponibles.add(m_label)

            mois_list = sorted(list(mois_disponibles))
            
            if not mois_list:
                st.warning("⚠️ Impossible de déterminer les mois pour les PV enregistrés.")
            else:
                col_f1, col_f2 = st.columns([2, 2])
                with col_f1:
                    selected_month = st.selectbox("📅 Filtrer par mois :", ["Tous les mois"] + mois_list, key=f"{prefix}_synth_month_filter")
                
                if selected_month == "Tous les mois":
                    filtered_pvs = historique
                else:
                    filtered_pvs = []
                    for item in historique:
                        d_pv = item.get('pv_info', {}).get('date') or item.get('date_creation')
                        if get_month_year_label(d_pv) == selected_month:
                            filtered_pvs.append(item)

                st.markdown(f"### Résultats pour : **{selected_month}** ({len(filtered_pvs)} rapport(s) trouvé(s))")

                if not filtered_pvs:
                    st.info(f"Aucun PV trouvé pour le mois de {selected_month}.")
                else:
                    synth_rows = []
                    for item in filtered_pvs:
                        p_info = item.get('pv_info', {})
                        inf_p = item.get('info_prelevement', {})
                        synth_rows.append({
                            "N° Rapport": p_info.get('ref_pv', '-'),
                            "Date Prélèvement": p_info.get('date', '-'),
                            "Client": p_info.get('client', '-'),
                            "Chantier / Projet": p_info.get('projet', '-'),
                            "Lieu": inf_p.get('lieu_prelevement', '-'),
                            "Date Enregistrement": item.get('date_creation', '-')
                        })
                    
                    df_synth = pd.DataFrame(synth_rows)
                    st.dataframe(df_synth, use_container_width=True, hide_index=True)

                    csv_data = df_synth.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"📥 Télécharger la synthèse ({selected_month}) au format CSV",
                        data=csv_data,
                        file_name=f"Synthese_PV_{selected_month.replace(' ', '_')}.csv",
                        mime="text/csv",
                        key=f"{prefix}_dl_csv_synth"
                    )

                    st.markdown("---")
                    st.markdown("### 📋 Détail des rapports du mois sélectionné")
                    for item in filtered_pvs:
                        r_num = item.get('ref_pv', 'Sans ref')
                        r_client = item.get('client', 'Inconnu')
                        r_date = item.get('date', 'Date inconnue')
                        with st.expander(f"Rapport N° : {r_num} | Client : {r_client} | Date : {r_date}"):
                            st.json({
                                "Informations de Prélèvement": item.get('info_prelevement', {}),
                                "Détails PV": item.get('pv_info', {}),
                                "Date de création": item.get('date_creation', '-')
                            })
