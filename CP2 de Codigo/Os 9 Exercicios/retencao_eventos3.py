import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["lab_db"]
eventos = db["eventos"]
eventos.drop()
eventos.create_index("timestamp", expireAfterSeconds=604800)
agora = datetime.now(timezone.utc)
docs = []
tipos = ["FALHA", "FALHA", "FALHA", "SUCESSO"]
for _ in range(200):
    minutos_atras = random.randint(0, 1439)
    ts = agora - timedelta(minutes=minutos_atras)
    docs.append({
        "timestamp": ts,
        "status": random.choice(tipos),
        "ip_origem": f"192.168.1.{random.randint(10, 200)}"
    })
eventos.insert_many(docs)
limite_24h = agora - timedelta(hours=24)
pipeline = [
    {
        "$match": {
            "timestamp": {"$gte": limite_24h},
            "status": "FALHA"
        }
    },
    {
        "$group": {
            "_id": {"$hour": "$timestamp"},
            "total": {"$sum": 1}
        }
    },
    {
        "$sort": {"_id": 1}
    }
]
resultado = list(eventos.aggregate(pipeline))
pico_hora = None
pico_total = -1
for item in resultado:
    if item["total"] > pico_total:
        pico_total = item["total"]
        pico_hora = item["_id"]
print("=== Falhas por hora (últimas 24h) ===")
for item in resultado:
    hora_str = f"{item['_id']:02d}h"
    barra = "█" * (item["total"] // 2)
    sufixo = "   <- pico" if item["_id"] == pico_hora else ""
    print(f"{hora_str} | {barra} {item['total']}{sufixo}")
if pico_hora is not None:
    print(f"\nHora de pico: {pico_hora:02d}h ({pico_total} falhas)")
print("Índice TTL ativo: eventos com mais de 7 dias serão removidos automaticamente.")
client.close()