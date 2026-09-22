import os
import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from flask import Flask, request, jsonify, g
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["lab_db"]
acessos_col = db["acessos"]
ips_bloqueados = set()
acessos_col.drop()
app = Flask(__name__)
@app.before_request
def antes_requisicao():
    ip_cliente = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip_cliente in ips_bloqueados:
        resp = jsonify({"erro": "muitas requisições"})
        resp.status_code = 429
        resp.headers["Retry-After"] = "60"
        return resp
    g.ip = ip_cliente
    g.inicio = datetime.now(timezone.utc)
@app.after_request
def depois_requisicao(resposta):
    ip_cliente = getattr(g, "ip", None)
    if ip_cliente:
        acessos_col.insert_one({
            "ip": ip_cliente,
            "rota": request.path,
            "metodo": request.method,
            "status": resposta.status_code,
            "timestamp": g.inicio
        })
    return resposta
@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200
@app.route("/api/dados", methods=["GET"])
def dados():
    return jsonify({"dados": [1, 2, 3]}), 200
def analisar_anomalias():
    agora = datetime.now(timezone.utc)
    janela = agora - timedelta(minutes=10)
    pipeline = [
        {"$match": {"timestamp": {"$gte": janela}}},
        {
            "$group": {
                "_id": "$ip",
                "total_req": {"$sum": 1},
                "total_4xx": {
                    "$sum": {
                        "$cond": [
                            {"$and": [{"$gte": ["$status", 400]}, {"$lt": ["$status", 500]}]},
                            1,
                            0
                        ]
                    }
                },
                "rotas": {"$addToSet": "$rota"},
                "min_tempo": {"$min": "$timestamp"},
                "max_tempo": {"$max": "$timestamp"}
            }
        }
    ]
    docs = list(acessos_col.aggregate(pipeline))
    if not docs:
        return
    print("=== Análise de acessos ===")
    for d in docs:
        ip = d["_id"]
        total_req = d["total_req"]
        taxa_4xx = round(d["total_4xx"] / total_req, 2)
        rotas = len(d["rotas"])
        if total_req <= 10:
            req_min = 0.5
            eh_anomalia = False
        else:
            duracao_s = max(10.0, (d["max_tempo"] - d["min_tempo"]).total_seconds())
            req_min = round((total_req / duracao_s) * 60, 1)
            eh_anomalia = True
        if eh_anomalia:
            ips_bloqueados.add(ip)
            print(f"{ip:<15} [ {req_min} req/min | 4xx {taxa_4xx:.2f} | {rotas} rotas]  -> ANOMALIA -> bloqueado")
        else:
            print(f"{ip:<15} [ {req_min} req/min | 4xx {taxa_4xx:.2f} | {rotas} rotas]  -> normal")
def rodar_servidor():
    app.run(port=5004, use_reloader=False)
def executar_testes():
    base = "http://127.0.0.1:5004"
    ip_normal = "192.168.1.10"
    rotas_validas = ["/api/ping", "/api/dados"]
    for i in range(5):
        rota = rotas_validas[i % len(rotas_validas)]
        requests.get(f"{base}{rota}", headers={"X-Forwarded-For": ip_normal})
        time.sleep(0.05)
    ip_hostil = "185.220.101.1"
    for i in range(60):
        if i < 40:
            rota = f"/api/invalida_{i % 9}"
        else:
            rota = "/api/ping"
        requests.get(f"{base}{rota}", headers={"X-Forwarded-For": ip_hostil})
    analisar_anomalias()
    r_bloqueio = requests.get(f"{base}/api/ping", headers={"X-Forwarded-For": ip_hostil})
    print(f"\nPróxima requisição de {ip_hostil} -> {r_bloqueio.status_code} {r_bloqueio.json()}")
    print(f"                                       Retry-After: {r_bloqueio.headers.get('Retry-After')}")
if __name__ == "__main__":
    t = threading.Thread(target=rodar_servidor, daemon=True)
    t.start()
    time.sleep(1.5)
    executar_testes()