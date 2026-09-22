import os
import time
import threading
import requests
import mysql.connector
from flask import Flask, request, jsonify
mysql_user = os.getenv("MYSQL_USER", "root")
mysql_pass = os.getenv("MYSQL_PASSWORD", "")
mysql_host = os.getenv("MYSQL_HOST", "localhost")
mysql_port = int(os.getenv("MYSQL_PORT", 3306))
mysql_db = os.getenv("MYSQL_DATABASE", "lab_db")
def iniciar_banco():
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db}")
    cursor.execute(f"USE {mysql_db}")
    cursor.execute("DROP TABLE IF EXISTS eventos_api")
    cursor.execute("""
    CREATE TABLE eventos_api (
        id INT AUTO_INCREMENT PRIMARY KEY,
        tipo VARCHAR(50),
        severidade VARCHAR(20),
        ip_origem VARCHAR(45),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    dados = [
        ("LOGIN_FAIL", "baixa", "192.168.1.15"),
        ("PORT_SCAN", "media", "192.168.1.20"),
        ("SQLI_ATTEMPT", "alta", "192.168.1.55"),
        ("BRUTE_FORCE", "critica", "192.168.1.99"),
        ("XSS_STORED", "alta", "192.168.1.102"),
        ("RCE_EXPLOIT", "critica", "192.168.1.200")
    ]
    cursor.executemany("INSERT INTO eventos_api (tipo, severidade, ip_origem) VALUES (%s, %s, %s)", dados)
    conn.commit()
    cursor.close()
    conn.close()
iniciar_banco()
app = Flask(__name__)
COLUNAS = {"data": "criado_em", "sev": "severidade", "ip": "ip_origem"}
ORDEM = {"asc": "ASC", "desc": "DESC"}
@app.route("/api/eventos", methods=["GET"])
def listar_eventos():
    param_col = request.args.get("ordenar_por", "data")
    param_ord = request.args.get("ordem", "desc").lower()
    param_tam = request.args.get("tamanho", "10")
    if param_col not in COLUNAS:
        return jsonify({"erro": "campo de ordenação inválido"}), 400

    if param_ord not in ORDEM:
        return jsonify({"erro": "direção de ordenação inválida"}), 400
    try:
        tamanho = int(param_tam)
        if tamanho <= 0:
            return jsonify({"erro": "tamanho deve ser maior que zero"}), 400
    except ValueError:
        return jsonify({"erro": "tamanho deve ser inteiro"}), 400
    limite = min(tamanho, 100)
    coluna_sql = COLUNAS[param_col]
    ordem_sql = ORDEM[param_ord]
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port,
        database=mysql_db
    )
    cursor = conn.cursor(dictionary=True)
    query = f"SELECT id, tipo, severidade, ip_origem, criado_em FROM eventos_api ORDER BY {coluna_sql} {ordem_sql} LIMIT %s"
    cursor.execute(query, (limite,))
    resultados = cursor.fetchall()
    for item in resultados:
        if item.get("criado_em"):
            item["criado_em"] = item["criado_em"].isoformat()
    cursor.close()
    conn.close()
    return jsonify({"total": len(resultados), "eventos": resultados}), 200
def rodar_servidor():
    app.run(port=5000, use_reloader=False)
def executar_testes():
    base_url = "http://127.0.0.1:5000/api/eventos"
    t1 = requests.get(f"{base_url}?ordenar_por=sev&ordem=desc&tamanho=5")
    print(f"GET ?ordenar_por=sev&ordem=desc&tamanho=5 -> {t1.status_code}")
    print(f"Total retornado: {len(t1.json().get('eventos', []))}\n")
    t2 = requests.get(f"{base_url}?ordenar_por=criado_em,(SELECT+1)&ordem=asc")
    print(f"GET ?ordenar_por=criado_em,(SELECT+1)&ordem=asc -> {t2.status_code}")
    print(f"Resposta: {t2.json()}\n")
    t3 = requests.get(f"{base_url}?tamanho=abc")
    print(f"GET ?tamanho=abc -> {t3.status_code}")
    print(f"Resposta: {t3.json()}\n")
    t4 = requests.get(f"{base_url}?tamanho=100000")
    print(f"GET ?tamanho=100000 -> {t4.status_code}")
    print(f"Total retornado (teto aplicado): {len(t4.json().get('eventos', []))}\n")
if __name__ == "__main__":
    t = threading.Thread(target=rodar_servidor, daemon=True)
    t.start()
    time.sleep(1.5)
    executar_testes()