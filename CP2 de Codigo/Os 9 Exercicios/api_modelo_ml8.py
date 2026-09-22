import os
import time
import math
import random
import threading
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from flask import Flask, request, jsonify
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["lab_db"]
previsoes_col = db["previsoes"]
previsoes_col.drop()
random.seed(42)
dados_treino = []
for _ in range(200):
    falhas = random.randint(0, 3)
    portas = random.randint(1, 3)
    bytes_s = random.randint(500, 3000)
    hora = random.randint(8, 18)
    dados_treino.append(([falhas, portas, bytes_s, hora], 0))
for _ in range(50):
    falhas = random.randint(10, 25)
    portas = random.randint(5, 12)
    bytes_s = random.randint(60000, 100000)
    hora = random.randint(0, 5)
    dados_treino.append(([falhas, portas, bytes_s, hora], 1))
random.shuffle(dados_treino)
split_idx = int(len(dados_treino) * 0.7)
treino = dados_treino[:split_idx]
teste = dados_treino[split_idx:]
def sigmoid(z):
    if z < -700:
        return 0.0
    if z > 700:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))
pesos = [0.0, 0.0, 0.0, 0.0]
bias = 0.0
taxa_aprendizado = 0.001
for _ in range(300):
    for x, y in treino:
        z = bias + sum(w * xi for w, xi in zip(pesos, [x[0], x[1], x[2] / 10000.0, x[3]]))
        pred = sigmoid(z)
        erro = y - pred
        bias += taxa_aprendizado * erro
        for i in range(len(pesos)):
            xi = [x[0], x[1], x[2] / 10000.0, x[3]][i]
            pesos[i] += taxa_aprendizado * erro * xi
def classificar(features):
    z = bias + sum(w * xi for w, xi in zip(pesos, [features[0], features[1], features[2] / 10000.0, features[3]]))
    prob_ataque = sigmoid(z)
    if prob_ataque >= 0.5:
        return 1, round(prob_ataque, 2)
    return 0, round(1.0 - prob_ataque, 2)
vp = vn = fp = fn = 0
for x, y in teste:
    pred, _ = classificar(x)
    if y == 1 and pred == 1:
        vp += 1
    elif y == 0 and pred == 0:
        vn += 1
    elif y == 0 and pred == 1:
        fp += 1
    elif y == 1 and pred == 0:
        fn += 1
precisao = round(vp / (vp + fp), 2) if (vp + fp) > 0 else 0.0
recall = round(vp / (vp + fn), 2) if (vp + fn) > 0 else 0.0
f1 = round(2 * (precisao * recall) / (precisao + recall), 2) if (precisao + recall) > 0 else 0.0
metricas_modelo = {
    "precisao": precisao,
    "recall": recall,
    "f1": f1,
    "matriz": [[vn, fp], [fn, vp]],
    "aviso": "A acuracia foi omitida por ser enganosa em bases desbalanceadas, onde prever sempre a classe majoritaria gera alta taxa de acerto mas ignora os ataques."
}
app = Flask(__name__)
@app.route("/api/triagem", methods=["POST"])
def triagem():
    dados = request.get_json(silent=True)
    if dados is None:
        return jsonify({"erro": "corpo da requisicao vazio ou invalido"}), 400
    features = dados.get("features")
    if features is None:
        return jsonify({"erro": "campo features obrigatorio"}), 400
    if not isinstance(features, list):
        return jsonify({"erro": "features deve ser uma lista"}), 400
    if len(features) != 4:
        return jsonify({"erro": f"esperadas 4 features, recebidas {len(features)}"}), 400
    for item in features:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            return jsonify({"erro": "features devem ser numéricas"}), 400
    classe, confianca = classificar(features)
    risco = "alto" if classe == 1 else "baixo"
    doc = {
        "entrada": features,
        "saida": risco,
        "confianca": confianca,
        "timestamp": datetime.now(timezone.utc)
    }
    previsoes_col.insert_one(doc)
    return jsonify({"risco": risco, "confianca": confianca}), 200
@app.route("/api/modelo/metricas", methods=["GET"])
def obter_metricas():
    return jsonify(metricas_modelo), 200
def rodar_servidor():
    app.run(port=5003, use_reloader=False)
def executar_testes():
    base = "http://127.0.0.1:5003"
    t1 = requests.post(f"{base}/api/triagem", json={"features": [12, 7, 90000, 3]})
    print(f"POST [12,7,90000,3] -> {t1.status_code} {t1.json()}")
    t2 = requests.post(f"{base}/api/triagem", json={"features": [0, 1, 1200, 14]})
    print(f"POST [0,1,1200,14]  -> {t2.status_code} {t2.json()}")
    t3 = requests.post(f"{base}/api/triagem", json={"features": [12, 7, 90000]})
    print(f"POST [3 features]   -> {t3.status_code} {t3.json()}")
    t4 = requests.post(f"{base}/api/triagem", json={"features": ["12", "sete", 0, 3]})
    print(f"POST [invalidas]    -> {t4.status_code} {t4.json()}")
    t5 = requests.post(f"{base}/api/triagem", headers={"Content-Type": "application/json"})
    print(f"POST [sem corpo]    -> {t5.status_code}")
    t6 = requests.get(f"{base}/api/modelo/metricas")
    print(f"GET  /metricas      -> {t6.status_code} {t6.json()}\n")
    total_gravado = previsoes_col.count_documents({})
    print(f"db.previsoes.count_documents({{}}) -> {total_gravado}")
if __name__ == "__main__":
    t = threading.Thread(target=rodar_servidor, daemon=True)
    t.start()
    time.sleep(1.5)
    executar_testes()