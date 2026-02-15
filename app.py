import requests
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# --- CONFIGURATION DU LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Mémoire vive
last_stakes_cache = {}

# --- LISTE DES PORTES D'ENTRÉE (Le Passe-Partout) ---
# On va tester ces adresses une par une jusqu'à en trouver une qui n'est pas bloquée
PMU_CANDIDATES = [
    "https://online.pmu.fr/rest/client/1",      # Officielle (souvent bloquée Cloud)
    "https://tapi.pmu.fr/rest/client/1",        # Tablette API (souvent oubliée)
    "https://api.pmu.fr/rest/client/v1",        # Mobile API (ancienne)
    "https://www.pmu.fr/rest/client/1"          # Site Web (redirige souvent)
]

# Variable pour se souvenir de l'adresse qui marche
CURRENT_WORKING_URL = None

HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'fr-FR,fr;q=0.9',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Origin': 'https://www.pmu.fr',
    'Referer': 'https://www.pmu.fr/'
}

def get_best_url():
    """Trouve une URL qui n'est pas bloquée par le DNS."""
    global CURRENT_WORKING_URL
    if CURRENT_WORKING_URL:
        return CURRENT_WORKING_URL
    
    logger.info("Recherche d'une porte d'entrée PMU ouverte...")
    
    for base_url in PMU_CANDIDATES:
        try:
            # Test léger pour voir si ça répond (DNS check)
            test_url = f"{base_url}/programme/{datetime.now().strftime('%d%m%Y')}"
            logger.info(f"Test de connection vers : {base_url} ...")
            resp = requests.get(test_url, headers=HEADERS, timeout=3)
            if resp.status_code == 200:
                logger.info(f"VICTOIRE ! Connecté via {base_url}")
                CURRENT_WORKING_URL = base_url
                return base_url
        except Exception as e:
            logger.warning(f"Echec sur {base_url}: {e}")
            continue
            
    logger.error("TOUTES LES PORTES SONT BLOQUEES PAR LE PMU.")
    return PMU_CANDIDATES[0] # On retourne la première par défaut pour éviter le crash total

@app.route('/')
def health_check():
    return "Sentinel Engine: Online (Ready to scan)", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    base_url = get_best_url()
    try:
        url = f"{base_url}/programme/{date_str}"
        response = requests.get(url, headers=HEADERS, timeout=8)
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Programme: {e}")
        # Message d'erreur clair pour l'interface
        return jsonify({"error": "BLOCAGE PMU", "details": str(e)}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    base_url = get_best_url()
    try:
        url = f"{base_url}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=8)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    base_url = get_best_url()
    date_str = datetime.now().strftime('%d%m%Y')
    pari_types = ['E_SIMPLE_PLACE', 'SIMPLE_PLACE', 'E_TRIO', 'TRIO', 'E_SIMPLE_GAGNANT', 'SIMPLE_GAGNANT']
    
    for p_type in pari_types:
        url = f"{base_url}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get('totalEnjeu', 0)
                combis = data.get('listeCombinaisons', [])
                
                if total > 0 and combis:
                    for cb in combis:
                        horse_key = cb.get('combinaison', ['X'])[0]
                        hid = f"R{r}C{c}_{horse_key}"
                        current = cb.get('totalEnjeu', 0)
                        
                        prev = last_stakes_cache.get(hid, current)
                        cb['velocity'] = round(current - prev, 2)
                        last_stakes_cache[hid] = current
                        
                        cb['market_share'] = round((current / total * 100), 2) if total > 0 else 0
                    
                    return jsonify(data), 200
        except:
            continue

    return jsonify({"totalEnjeu": 0, "listeCombinaisons": [], "status": "No Data"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
