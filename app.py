import requests
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

# Configuration du Logging (Essentiel sur Render Payant pour le monitoring)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Autorisation complète pour ton frontend EquiStream

# --- MÉMOIRE INTERNE (STATE) ---
# Stocke les derniers enjeux pour calculer la vélocité (V) entre deux appels
# Structure: { "R1C2_4": 1250.50 }
last_stakes_cache = {}

# Configuration API PMU
PMU_BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61"
HEADERS = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- ROUTES ---

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    """Récupère l'intégralité des réunions d'une journée."""
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}"
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Programme {date_str}: {str(e)}")
        return jsonify({"error": "Inaccessible", "details": str(e)}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    """Récupère les détails (musique, driver) pour une course spécifique."""
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Participants R{r}C{c}: {str(e)}")
        return jsonify({"error": "Inaccessible", "details": str(e)}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    """
    ENDPOINT CRITIQUE: Récupère les enjeux et calcule la vélocité financière.
    """
    date_str = datetime.now().strftime('%d%m%Y')
    url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/E_SIMPLE_GAGNANT"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=3)
        response.raise_for_status()
        data = response.json()
        
        total_enjeu = data.get('totalEnjeu', 0)
        combis = data.get('listeCombinaisons', [])
        
        # Enrichissement des données avec les indicateurs "Sentinel"
        for cb in combis:
            horse_num = cb['combinaison'][0]
            horse_id = f"R{r}C{c}_{horse_num}"
            current_stake = cb['totalEnjeu']
            
            # 1. Calcul de la Vélocité (Delta d'argent entre T et T-1)
            # Formule: ΔE = E_actuel - E_précédent
            prev_stake = last_stakes_cache.get(horse_id, current_stake)
            cb['velocity'] = round(current_stake - prev_stake, 2)
            
            # Mémorisation pour le prochain appel
            last_stakes_cache[horse_id] = current_stake
            
            # 2. Part de Marché (Market Share)
            cb['market_share'] = round((current_stake / total_enjeu * 100), 2) if total_enjeu > 0 else 0

        logger.info(f"Flux traité pour R{r}C{c} - Total: {total_enjeu}€")
        return jsonify({
            "totalEnjeu": total_enjeu,
            "listeCombinaisons": combis,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Erreur Flux R{r}C{c}: {str(e)}")
        return jsonify({"error": "Flux momentanément indisponible"}), 500

if __name__ == "__main__":
    # Utilisation du port assigné par Render
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
