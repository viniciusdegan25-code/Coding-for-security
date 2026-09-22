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
    cursor.execute("DROP TABLE IF EXISTS incidentes")
    cursor.execute("DROP TABLE IF EXISTS analistas")
    cursor.execute("""
    CREATE TABLE analistas (
        id INT PRIMARY KEY,
        nome VARCHAR(50),
        api_key VARCHAR(100) UNIQUE,
        nivel INT
    )
    """)
    cursor.execute("""
    CREATE TABLE incidentes (
        id INT PRIMARY KEY,
        dono_id INT,
        titulo VARCHAR(100),
        severidade VARCHAR(20),
        status VARCHAR(20) DEFAULT 'aberto',
        FOREIGN KEY (dono_id) REFERENCES analistas(id)
    )
    """)
    dados_analistas = [
        (1, "ana", "key-ana-001", 5),
        (2, "bruno", "key-bruno-002", 2)
    ]
    cursor.executemany("INSERT INTO analistas (id, nome, api_key, nivel) VALUES (%s, %s, %s, %s)", dados_analistas)
    dados_incidentes = [
        (1, 1, "Brute force SSH", "critica"),
        (2, 2, "Phishing no RH", "media")
    ]
    cursor.executemany("INSERT INTO incidentes (id, dono_id, titulo, severidade) VALUES (%s, %s, %s, %s)", dados_incidentes)
    conn.commit()
    cursor.close()
    conn.close()
iniciar_banco()
app = Flask(__name__)
def autenticar():
    key = request.headers.get("X-API-Key")
    if not key:
        return None
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port,
        database=mysql_db
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, nivel FROM analistas WHERE api_key = %s", (key,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()
    return usuario
@app.route("/api/incidentes", methods=["GET"])
def listar_incidentes():
    usuario = autenticar()
    if not usuario:
        return jsonify({"erro": "Não autenticado"}), 401
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port,
        database=mysql_db
    )
    cursor = conn.cursor(dictionary=True)
    if usuario["nivel"] >= 5:
        cursor.execute("SELECT id, dono_id, titulo, severidade, status FROM incidentes")
    else:
        cursor.execute("SELECT id, dono_id, titulo, severidade, status FROM incidentes WHERE dono_id = %s", (usuario["id"],))
    registros = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(registros), 200
@app.route("/api/incidentes/<int:incidente_id>", methods=["GET"])
def obter_incidente(incidente_id):
    usuario = autenticar()
    if not usuario:
        return jsonify({"erro": "Não autenticado"}), 401
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port,
        database=mysql_db
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, dono_id, titulo, severidade, status FROM incidentes WHERE id = %s", (incidente_id,))
    incidente = cursor.fetchone()
    cursor.close()
    conn.close()
    if not incidente:
        if usuario["nivel"] >= 5:
            return jsonify({"erro": "Incidente não encontrado"}), 404
        return jsonify({"erro": "Acesso negado"}), 403
    if usuario["nivel"] < 5 and incidente["dono_id"] != usuario["id"]:
        return jsonify({"erro": "Acesso negado"}), 403
    return jsonify(incidente), 200
@app.route("/api/incidentes/<int:incidente_id>", methods=["DELETE"])
def deletar_incidente(incidente_id):
    usuario = autenticar()
    if not usuario:
        return jsonify({"erro": "Não autenticado"}), 401
    if usuario["nivel"] < 5:
        return jsonify({"erro": "Acesso negado"}), 403
    conn = mysql.connector.connect(
        user=mysql_user,
        password=mysql_pass,
        host=mysql_host,
        port=mysql_port,
        database=mysql_db
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM incidentes WHERE id = %s", (incidente_id,))
    existe = cursor.fetchone()
    if not existe:
        cursor.close()
        conn.close()
        return jsonify({"erro": "Incidente não encontrado"}), 404
    cursor.execute("DELETE FROM incidentes WHERE id = %s", (incidente_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensagem": "Incidente removido com sucesso"}), 200
def rodar_servidor():
    app.run(port=5001, use_reloader=False)
def executar_testes():
    base = "http://127.0.0.1:5001/api/incidentes"
    t1 = requests.get(f"{base}/1", headers={"X-API-Key": "key-ana-001"})
    print(f"GET /1 [key-ana-001] -> {t1.status_code}")
    t2 = requests.get(f"{base}/1", headers={"X-API-Key": "key-bruno-002"})
    print(f"GET /1 [key-bruno-002] -> {t2.status_code} (IDOR barrado)")
    t3 = requests.get(f"{base}/1")
    print(f"GET /1 [sem header] -> {t3.status_code}")
    t4 = requests.get(f"{base}/1", headers={"X-API-Key": "key-inexistente"})
    print(f"GET /1 [key-inexistente] -> {t4.status_code}")
    t5 = requests.get(base, headers={"X-API-Key": "key-bruno-002"})
    ids = [i["id"] for i in t5.json()]
    print(f"GET /  [key-bruno-002] -> {t5.status_code}, incidentes visíveis: {ids}")
    t6 = requests.delete(f"{base}/2", headers={"X-API-Key": "key-ana-001"})
    print(f"DELETE /2 [key-ana-001] -> {t6.status_code}")
    t7 = requests.delete(f"{base}/1", headers={"X-API-Key": "key-bruno-002"})
    print(f"DELETE /1 [key-bruno-002] -> {t7.status_code}")
    t8 = requests.get(f"{base}/999", headers={"X-API-Key": "key-ana-001"})
    print(f"GET /999 [key-ana-001] -> {t8.status_code}")
if __name__ == "__main__":
    t = threading.Thread(target=rodar_servidor, daemon=True)
    t.start()
    time.sleep(1.5)
    executar_testes()