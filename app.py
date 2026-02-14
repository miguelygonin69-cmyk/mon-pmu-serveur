from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# AJOUT CRUCIAL : Une route pour que Render voie que le serveur fonctionne
@app.route('/')
def home():
    return "Serveur Sentinel Operationnel", 200

@app.route('/flux/<r>/<c>')
def pmu(r, c):
    date = datetime.now().strftime('%d%m%Y')
    url = f"https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{date}/R{r}/C{c}/combinaisons?specialisation=INTERNET"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

if __name__ == "__main__":
    # Force l'utilisation du port Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
