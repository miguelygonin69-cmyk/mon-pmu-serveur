from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# 1. ACCUEIL (Pour Render)
@app.route('/')
def home():
    return "Sentinel Engine Online", 200

# 2. PROGRAMME AUTOMATIQUE (Pour remplir tes menus React)
@app.route('/programme')
def get_programme():
    date = datetime.now().strftime('%d%m%Y')
    url = f"https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{date}?specialisation=INTERNET"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. FLUX LIVE (Pour tes graphiques)
@app.route('/flux/<r>/<c>')
def get_flux(r, c):
    date = datetime.now().strftime('%d%m%Y')
    url = f"https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{date}/R{r}/C{c}/combinaisons?specialisation=INTERNET"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
