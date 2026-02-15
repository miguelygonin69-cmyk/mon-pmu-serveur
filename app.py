import requests
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# Configuration du Logging pour Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# CORS est vital pour la communication avec ton frontend EquiStream
CORS(app) 

# --- MÉMOIRE INTERNE ---
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

@app.route('/')
def health_check():
    """Route vitale pour que Render valide le port HTTP et ne tue pas le serveur."""
    return "Sentinel Server is Live and Healthy", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}"
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Programme {date_str}: {str(e)}")
        return jsonify({"error": "Programme indisponible"}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Participants R{r}C{c}: {str(e)}")
        return jsonify({"error": "Participants indisponibles"}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    """Récupère les enjeux avec basculement automatique entre Online et Masse Commune."""
    date_str = datetime.now().strftime('%d%m%Y')
    
    # On teste d'abord E_SIMPLE_GAGNANT (Online), puis SIMPLE_GAGNANT (Standard)
    pari_types = ['E_SIMPLE_GAGNANT', 'SIMPLE_GAGNANT']
    
    for p_type in pari_types:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=3)
            if response.status_code == 200:
                data = response.json()
                total_enjeu = data.get('totalEnjeu', 0)
                combis = data.get('listeCombinaisons', [])
                
                # Si on a des données, on les traite
                if total_enjeu > 0 and combis:
                    for cb in combis:
                        horse_id = f"R{r}C{c}_{cb['combinaison'][0]}"
                        current_stake = cb['totalEnjeu']
                        
                        # Calcul Vélocité
                        prev_stake = last_stakes_cache.get(horse_id, current_stake)
                        cb['velocity'] = round(current_stake - prev_stake, 2)
                        last_stakes_cache[horse_id] = current_stake
                        
                        # Part de Marché
                        cb['market_share'] = round((current_stake / total_enjeu * 100), 2)
                    
                    logger.info(f"Flux {p_type} validé pour R{r}C{c}: {total_enjeu}€")
                    return jsonify({
                        "totalEnjeu": total_enjeu,
                        "listeCombinaisons": combis,
                        "pariType": p_type,
                        "timestamp": datetime.now().isoformat()
                    })
        except Exception as e:
            logger.warning(f"Échec sur {p_type}: {e}")
            continue

    return jsonify({"error": "Aucun enjeu détecté (Course non ouverte ou finie)"}), 404

if __name__ == "__main__":
    # Render utilise la variable d'environnement PORT
    port = int(os.environ.get("PORT", 10000))
    # On force l'écoute sur 0.0.0.0 pour être visible par Render
    app.run(host='0.0.0.0', port=port)
