import os
import time
import threading
import requests
from pymongo import MongoClient
from flask import Flask, render_template_string, make_response
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["lab_db"]
incidentes_col = db["incidentes_xss"]
incidentes_col.drop()
p1 = "<script>alert('xss1')</script>"
p2 = 'x" onerror="alert(\'xss2\')'
dados = [
    {"titulo": p1, "ativo": "SRV-PROD-01"},
    {"titulo": "Falha de Autenticação", "ativo": p2}
]
incidentes_col.insert_many(dados)
app = Flask(__name__)
TEMPLATE_SEGURO = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Seguro</title>
</head>
<body>
    <h1>Dashboard de Incidentes (Seguro)</h1>
    <table border="1">
        <tr>
            <th>Título</th>
            <th>Ativo</th>
            <th>Ícone</th>
        </tr>
        {% for item in incidentes %}
        <tr>
            <td>{{ item.titulo }}</td>
            <td>{{ item.ativo }}</td>
            <td><img src="/static/icone.png" alt="{{ item.ativo }}"></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""
TEMPLATE_INSEGURO = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Inseguro</title>
</head>
<body>
    <h1>Dashboard de Incidentes (Inseguro)</h1>
    <table border="1">
        <tr>
            <th>Título</th>
            <th>Ativo</th>
            <th>Ícone</th>
        </tr>
        {% for item in incidentes %}
        <tr>
            <td>{{ item.titulo | safe }}</td>
            <td>{{ item.ativo }}</td>
            <td><img src="/static/icone.png" alt="{{ item.ativo | safe }}"></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""
@app.after_request
def aplicar_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
@app.route("/dashboard", methods=["GET"])
def dashboard():
    incidentes = list(incidentes_col.find({}, {"_id": 0}))
    html = render_template_string(TEMPLATE_SEGURO, incidentes=incidentes)
    return make_response(html, 200)
@app.route("/dashboard-inseguro", methods=["GET"])
def dashboard_inseguro():
    incidentes = list(incidentes_col.find({}, {"_id": 0}))
    html = render_template_string(TEMPLATE_INSEGURO, incidentes=incidentes)
    return make_response(html, 200)
def rodar_servidor():
    app.run(port=5002, use_reloader=False)
def executar_testes():
    base = "http://127.0.0.1:5002"
    r_segura = requests.get(f"{base}/dashboard")
    print(f"GET /dashboard -> {r_segura.status_code}")
    print(f"Header CSP: {r_segura.headers.get('Content-Security-Policy')}")
    segura_escapou_p1 = "&lt;script&gt;alert(&#39;xss1&#39;)&lt;/script&gt;" in r_segura.text or "&lt;script&gt;" in r_segura.text
    segura_escapou_p2 = 'alt="x&#34; onerror=&#34;alert(&#39;xss2&#39;)"' in r_segura.text or "&quot;" in r_segura.text or "&#34;" in r_segura.text
    print(f"p1 escapado no corpo: {segura_escapou_p1}")
    print(f"p2 escapado no atributo alt: {segura_escapou_p2}\n")
    r_insegura = requests.get(f"{base}/dashboard-inseguro")
    print(f"GET /dashboard-inseguro -> {r_insegura.status_code}")
    insegura_vulneravel_p1 = "<script>alert('xss1')</script>" in r_insegura.text
    insegura_vulneravel_p2 = 'alt="x" onerror="alert(\'xss2\')"' in r_insegura.text
    print(f"p1 executável no HTML: {insegura_vulneravel_p1}")
    print(f"p2 quebrando o atributo alt: {insegura_vulneravel_p2}")
if __name__ == "__main__":
    t = threading.Thread(target=rodar_servidor, daemon=True)
    t.start()
    time.sleep(1.5)
    executar_testes()