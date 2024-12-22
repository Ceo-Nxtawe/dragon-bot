from pymongo import MongoClient
import certifi

MONGO_URI = "mongodb://mongo:BFjOprOMuynYLutfypLbKFscmGpWDzcN@mongodb.railway.internal:27017"

try:
    client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    print(client.server_info())
    print("Connexion réussie à MongoDB")
except Exception as e:
    print(f"Erreur de connexion : {e}")
