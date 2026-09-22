import os
from datetime import datetime, timezone
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
    port=mysql_port,
    autocommit=False
)
cursor = conn.cursor()
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db}")
cursor.execute(f"USE {mysql_db}")

cursor.execute("DROP TABLE IF EXISTS usuarios")
cursor.execute("""
CREATE TABLE usuarios (
    id INT PRIMARY KEY,
    nome VARCHAR(50),
    email VARCHAR(100),
    nivel_acesso INT
)
""")
usuarios = [
    (1, "ana", "ana@x.com", 5),
    (2, "bruno", "bruno@x.com", 2),
    (3, "caio", "caio@x.com", 1)
]
cursor.executemany("INSERT INTO usuarios (id, nome, email, nivel_acesso) VALUES (%s, %s, %s, %s)", usuarios)
conn.commit()
mongo_client = MongoClient(mongo_uri)
mongo_db = mongo_client["lab_db"]
auditoria = mongo_db["auditoria"]
auditoria.drop()
def alterar_nivel(admin_id, alvo_id, novo_nivel):
    conn.start_transaction()
    resultado = "RECUSADO"
    motivo = ""
    nivel_anterior = None
    cursor.execute("SELECT nivel_acesso, nome FROM usuarios WHERE id = %s", (admin_id,))
    admin = cursor.fetchone()
    cursor.execute("SELECT nivel_acesso, nome FROM usuarios WHERE id = %s", (alvo_id,))
    alvo = cursor.fetchone()
    if alvo:
        nivel_anterior = alvo[0]

    if admin_id == alvo_id:
        motivo = "auto-promoção"
        conn.rollback()
    elif not admin or admin[0] < 5:
        motivo = "admin sem privilégio"
        conn.rollback()
    elif not alvo:
        motivo = "alvo inexistente"
        conn.rollback()
    else:
        try:
            cursor.execute("UPDATE usuarios SET nivel_acesso = %s WHERE id = %s", (novo_nivel, alvo_id))
            conn.commit()
            resultado = "SUCESSO"
        except Exception:
            conn.rollback()
            motivo = "erro de banco"
    doc_auditoria = {
        "quem": admin_id,
        "alvo": alvo_id,
        "nivel_anterior": nivel_anterior,
        "nivel_novo": novo_nivel,
        "resultado": resultado,
        "motivo": motivo,
        "timestamp": datetime.now(timezone.utc)
    }
    auditoria.insert_one(doc_auditoria)
    if resultado == "SUCESSO":
        print(f"alterar_nivel({admin_id}, {alvo_id}, {novo_nivel}) -> OK. commit. {alvo[1].capitalize()}: {nivel_anterior} -> {novo_nivel}")
    else:
        nome_alvo = f" {alvo[1].capitalize()}: {nivel_anterior}" if alvo else ""
        print(f"alterar_nivel({admin_id}, {alvo_id}, {novo_nivel}) -> RECUSADO ({motivo}). rollback.{nome_alvo}")
alterar_nivel(1, 2, 4)
alterar_nivel(2, 3, 5)
alterar_nivel(1, 1, 9)
alterar_nivel(1, 99, 3)
total_docs = auditoria.count_documents({})
total_recusados = auditoria.count_documents({"resultado": "RECUSADO"})
total_sucesso = auditoria.count_documents({"resultado": "SUCESSO"})
print(f"\nTrilha de auditoria ao final: {total_docs} documentos ({total_sucesso} sucesso, {total_recusados} recusas)")
print(f'db.auditoria.count_documents({{"resultado":"RECUSADO"}}) -> {total_recusados}')
cursor.close()
conn.close()
mongo_client.close()