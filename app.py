import requests
import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# Configuration du Logging pour le monitoring Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Autorise la communication avec ton interface EquiStream

# --- MÉMOIRE INTERNE ---
# Stocke les enjeux précédents pour calculer la vélocité (Δ)
last_stakes_cache = {}

# Configuration API PMU
PMU_BASE_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61"
HEADERS = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.pmu.fr/turf/'
}

# --- ROUTES ---

@app.route('/')
def health_check():
    """Route vitale pour Render : confirme que le serveur écoute sur le bon port."""
    return "Sentinel Server Live - Mode Placé/Trio Actif", 200

@app.route('/programme/<date_str>', methods=['GET'])
def get_programme(date_str):
    """Récupère le calendrier complet des courses."""
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}"
        response = requests.get(url, headers=HEADERS, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Programme: {e}")
        return jsonify({"error": "Inaccessible"}), 500

@app.route('/programme/<date_str>/R<int:r>/C<int:c>/participants', methods=['GET'])
def get_participants(date_str, r, c):
    """Récupère les noms des chevaux, drivers et musiques."""
    try:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/participants"
        response = requests.get(url, headers=HEADERS, timeout=5)
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Erreur Participants: {e}")
        return jsonify({"error": "Inaccessible"}), 500

@app.route('/flux/<int:r>/<int:c>', methods=['GET'])
def get_flux_sentinel(r, c):
    """
    ENDPOINT PRO : Priorité au jeu PLACÉ pour la détection de Smart Money.
    Scanne les masses Online et Masse Commune pour éviter les flux à 0€.
    """
    date_str = datetime.now().strftime('%d%m%Y')
    
    # Stratégie : On cherche d'abord le Placé (ton jeu principal)
    # puis le Trio pour l'analyse de masse.
    pari_types = ['E_SIMPLE_PLACE', 'SIMPLE_PLACE', 'E_TRIO', 'TRIO']
    
    for p_type in pari_types:
        url = f"{PMU_BASE_URL}/programme/{date_str}/R{r}/C{c}/combinaisons/{p_type}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=3)
            if response.status_code == 200:
                data = response.json()
                total = data.get('totalEnjeu', 0)
                combis = data.get('listeCombinaisons', [])
                
                if total > 0 and combis:
                    for cb in combis:
                        # Identifiant unique du cheval pour cette course
                        horse_id = f"R{r}C{c}_{cb['combinaison'][0]}"
                        current_stake = cb['totalEnjeu']
                        
                        # CALCUL SENTINEL : Vélocité (Δ argent frais)
                        prev_stake = last_stakes_cache.get(horse_id, current_stake)
                        cb['velocity'] = round(current_stake - prev_stake, 2)
                        last_stakes_cache[horse_id] = current_stake
                        
                        # CALCUL SENTINEL : Part de marché (Poids réel)
                        cb['market_share'] = round((current_stake / total * 100), 2)
                    
                    logger.info(f"FLUX OK: {p_type} pour R{r}C{c} - Total: {total}€")
                    return jsonify(data), 200
        except Exception as e:
            continue

    # Si aucun enjeu n'est trouvé, on renvoie un succès 200 avec total 0
    # pour éviter le bandeau d'erreur rouge sur le frontend.
    return jsonify({
        "totalEnjeu": 0,
        "listeCombinaisons": [],
        "status": "Attente d'ouverture des masses PMU"
    }), 200

if __name__ == "__main__":
    # Render définit automatiquement le PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
