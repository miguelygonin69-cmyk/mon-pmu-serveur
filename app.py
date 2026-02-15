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

# Mémoire vive pour la vélocité (cache simple)
last_stakes_cache = {}

# --- CONFIGURATION API ---
# CORRECTION MAJEURE ICI : Passage sur online.pmu.fr et client/1
PMU_BASE_URL = "https://offline.pmu.fr/rest/client/1"

HEADERS = {
    'Accept': 'application/json',
    'Accept-Language': 'fr-FR,fr;q=0.9',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Origin': 'https://www.pmu.fr',
    'Referer': 'https://www.pmu.fr/'
}

@app.route('/')
def health_check():
    """Route de santé pour Render."""
    return "Sentinel Engine: Online (Connected to PMU Online)", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    try:
        # Construction de l'URL propre
        url = f"{PMU_BASE_URL}/programme/{date_str}"
        logger.info(f"Fetching Programme: {url}")
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Erreur PMU {response.status_code}: {response.text}")
            return jsonify({"error": "PMU Refused", "details": response.text}), response.status_code
            
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Script Programme: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Erreur recuperation participants"}), response.status_code
    except Exception as e:
        logger.error(f"Erreur Script Participants: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    """
    Scanner multi-masses : cherche l'argent là où il se trouve.
    """
    # Calcul automatique de la date d'aujourd'hui pour le flux live
    date_str = datetime.now().strftime('%d%m%Y')
    
    # Ordre de priorité : on cherche d'abord les masses sur le Placé
    pari_types = ['E_SIMPLE_PLACE', 'SIMPLE_PLACE', 'E_TRIO', 'TRIO', 'E_SIMPLE_GAGNANT', 'SIMPLE_GAGNANT']
    
    found_data = False
    
    for p_type in pari_types:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                total = data.get('totalEnjeu', 0)
                combis = data.get('listeCombinaisons', [])
                
                # Si on a trouvé un pot avec de l'argent, on traite et on renvoie
                if total > 0 and combis:
                    for cb in combis:
                        # Gestion safe de la clé combinaison
                        horse_key = cb.get('combinaison', ['X'])[0]
                        hid = f"R{r}C{c}_{horse_key}"
                        
                        current = cb.get('totalEnjeu', 0)
                        
                        # Calcul Vélocité
                        prev = last_stakes_cache.get(hid, current)
                        velocity = round(current - prev, 2)
                        cb['velocity'] = velocity
                        
                        # Mise en cache
                        last_stakes_cache[hid] = current
                        
                        # Part de Marché
                        if total > 0:
                            cb['market_share'] = round((current / total * 100), 2)
                        else:
                            cb['market_share'] = 0
                    
                    logger.info(f"FLUX ACTIF ({p_type}): {total}E detectes.")
                    return jsonify(data), 200
                    
        except Exception as e:
            # On continue vers le prochain type de pari si celui-ci échoue
            logger.warning(f"Echec flux sur {p_type}: {e}")
            continue

    # Retour "Safe" si rien n'est trouvé
    return jsonify({
        "totalEnjeu": 0, 
        "listeCombinaisons": [], 
        "status": "Aucune donnée de flux disponible"
    }), 200

if __name__ == "__main__":
    # Configuration vitale pour Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

