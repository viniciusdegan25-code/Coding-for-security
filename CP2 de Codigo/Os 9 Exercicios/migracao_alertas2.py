import os
import mysql.connector
from pymongo import MongoClient
mysql_user = os.getenv("MYSQL_USER", "root")
mysql_pass = os.getenv("MYSQL_PASSWORD", "")
mysql_host = os.getenv("MYSQL_HOST", "localhost")
mysql_port = int(os.getenv("MYSQL_PORT", 3306))
mysql_db = os.getenv("MYSQL_DATABASE", "lab_db")
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
conn = mysql.connector.connect(
    user=mysql_user,
    password=mysql_pass,
    host=mysql_host,
    port=mysql_port
)
cursor = conn.cursor()
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db}")
cursor.execute(f"USE {mysql_db}")
cursor.execute("DROP TABLE IF EXISTS alertas")
cursor.execute("DROP TABLE IF EXISTS ativos")
cursor.execute("""
CREATE TABLE ativos (
    id INT PRIMARY KEY,
    nome VARCHAR(100),
    ip VARCHAR(45) UNIQUE,
    criticidade ENUM('baixa', 'media', 'alta')
)
""")
cursor.execute("""
CREATE TABLE alertas (
    id INT PRIMARY KEY,
    ativo_id INT,
    tipo VARCHAR(50),
    severidade VARCHAR(50),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ativo_id) REFERENCES ativos(id)
)
""")
ativos_dados = [
    (1, "SRV-WEB01", "192.168.1.10", "alta"),
    (2, "PC-RH03", "192.168.1.45", "baixa")
]
cursor.executemany("INSERT INTO ativos (id, nome, ip, criticidade) VALUES (%s, %s, %s, %s)", ativos_dados)
alertas_dados = [
    (1, 1, "BRUTE_FORCE", "critica"),
    (2, 1, "PORT_SCAN", "alta"),
    (3, 2, "XSS", "media")
]
cursor.executemany("INSERT INTO alertas (id, ativo_id, tipo, severidade) VALUES (%s, %s, %s, %s)", alertas_dados)
conn.commit()
query_join = """
SELECT al.tipo, al.severidade, at.nome, at.ip, at.criticidade
FROM alertas al
INNER JOIN ativos at ON al.ativo_id = at.id
WHERE at.id >= %s
"""
cursor.execute(query_join, (1,))
linhas = cursor.fetchall()
documentos = []
for tipo, severidade, nome, ip, criticidade in linhas:
    documentos.append({
        "tipo": tipo,
        "severidade": severidade,
        "ativo": {
            "nome": nome,
            "ip": ip,
            "criticidade": criticidade
        }
    })
client = MongoClient(mongo_uri)
db = client["lab_db"]
colecao = db["alertas"]
colecao.drop()
colecao.insert_many(documentos)
cursor.execute("SELECT COUNT(*) FROM alertas")
total_mysql = cursor.fetchone()[0]
total_mongo = colecao.count_documents({})
if total_mysql == total_mongo:
    print(f"MySQL: {total_mysql} alertas | MongoDB: {total_mongo} documentos -> MIGRAÇÃO ÍNTEGRA")
else:
    print(f"MySQL: {total_mysql} alertas | MongoDB: {total_mongo} documentos -> DIVERGÊNCIA")
filtro = {"ativo.criticidade": "alta"}
contagem_filtro = colecao.count_documents(filtro)
print(f'Consulta sem JOIN: db.alertas.find({{"ativo.criticidade":"alta"}}) -> {contagem_filtro} documentos')
cursor.close()
conn.close()
client.close()