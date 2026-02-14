from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
    app.run()