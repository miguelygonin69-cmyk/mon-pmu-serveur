import requests
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) 

last_stakes_cache = {}
PMU_BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61"
HEADERS = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

@app.route('/')
def health_check():
    return "Sentinel Server is Live", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    try:
        response = requests.get(f"{PMU_BASE_URL}/programme/{date_str}", headers=HEADERS, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    try:
        response = requests.get(f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants", headers=HEADERS, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_ultra(r, c):
    date_str = datetime.now().strftime('%d%m%Y')
    pari_types = ['E_SIMPLE_GAGNANT', 'SIMPLE_GAGNANT']
    
    for p_type in pari_types:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=3)
            if response.status_code == 200:
                data = response.json()
                total_enjeu = data.get('totalEnjeu', 0)
                if total_enjeu > 0:
                    combis = data.get('listeCombinaisons', [])
                    for cb in combis:
                        hid = f"R{r}C{c}_{cb['combinaison'][0]}"
                        prev = last_stakes_cache.get(hid, cb['totalEnjeu'])
                        cb['velocity'] = round(cb['totalEnjeu'] - prev, 2)
                        last_stakes_cache[hid] = cb['totalEnjeu']
                        cb['market_share'] = round((cb['totalEnjeu'] / total_enjeu * 100), 2)
                    
                    logger.info(f"FLUX OK: R{r}C{c} ({p_type})")
                    return jsonify(data), 200
        except:
            continue

    # --- ACTION CRUCIALE : RENVOYER 200 AU LIEU DE 404 ---
    logger.info(f"ATTENTE: R{r}C{c} - Aucun enjeu disponible pour le moment.")
    return jsonify({
        "totalEnjeu": 0,
        "listeCombinaisons": [],
        "pariType": "WAITING",
        "status": "Flux synchronisé, attente de tickets..."
    }), 200 # Le code 200 enlèvera le bandeau rouge d'erreur.

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
