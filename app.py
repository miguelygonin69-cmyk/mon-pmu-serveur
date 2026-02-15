import requests
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# Configuration du Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Mémoire vive pour la vélocité
last_stakes_cache = {}

# --- CONFIGURATION API MOBILE (Plus robuste contre les blocages) ---
PMU_BASE_URL = "https://api.pmu.fr/rest/client/v1"
HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'fr-FR,fr;q=0.9',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Origin': 'https://www.pmu.fr',
    'Referer': 'https://www.pmu.fr/turf/'
}

@app.route('/')
def health_check():
    """Indispensable pour que Render ne coupe pas le serveur."""
    return "Sentinel Engine: Online", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}"
        response = requests.get(url, headers=HEADERS, timeout=7)
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Programme: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=7)
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Participants: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    """
    Scanner multi-masses : cherche l'argent là où il se trouve.
    Priorité : Placé (ton jeu) -> Trio -> Gagnant.
    """
    date_str = datetime.now().strftime('%d%m%Y')
    
    # On ratisse large pour être sûr de ne pas avoir 0€
    pari_types = ['E_SIMPLE_PLACE', 'SIMPLE_PLACE', 'E_TRIO', 'TRIO', 'E_SIMPLE_GAGNANT', 'SIMPLE_GAGNANT']
    
    for p_type in pari_types:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get('totalEnjeu', 0)
                combis = data.get('listeCombinaisons', [])
                
                if total > 0 and combis:
                    for cb in combis:
                        # On gère les chevaux seuls (Simple) ou les groupes (Trio)
                        horse_key = cb['combinaison'][0]
                        hid = f"R{r}C{c}_{horse_key}"
                        current = cb['totalEnjeu']
                        
                        # Calcul de la Vélocité
                        prev = last_stakes_cache.get(hid, current)
                        cb['velocity'] = round(current - prev, 2)
                        last_stakes_cache[hid] = current
                        
                        # Part de Marché
                        cb['market_share'] = round((current / total * 100), 2)
                    
                    logger.info(f"FLUX ACTIF ({p_type}): {total}€ détectés.")
                    return jsonify(data), 200
        except:
            continue

    # Retour "Safe" pour le frontend si le PMU fait écran noir
    return jsonify({
        "totalEnjeu": 0, 
        "listeCombinaisons": [], 
        "status": "Attente de données PMU"
    }), 200

if __name__ == "__main__":
    # Forcer le port 10000 pour Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
