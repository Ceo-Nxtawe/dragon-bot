from pymongo import MongoClient
import socket
import certifi

# MongoDB URI
MONGO_URI = "mongodb://mongo:BFjOprOMuynYLutfypLbKFscmGpWDzcN@mongodb.railway.internal:27017"

def test_dns_resolution():
    """
    Teste si le nom d'hôte MongoDB est résolu correctement.
    """
    print("\n### DNS Resolution Test ###")
    try:
        resolved_ip = socket.gethostbyname('mongodb.railway.internal')
        print(f"DNS résolu avec succès : mongodb.railway.internal -> {resolved_ip}")
    except Exception as e:
        print(f"Erreur DNS : {e}")

def test_mongo_connection(tls_enabled=True):
    """
    Teste la connexion MongoDB avec ou sans TLS.
    """
    print("\n### MongoDB Connection Test ###")
    try:
        if tls_enabled:
            print("Connexion avec TLS activé...")
            client = MongoClient(
                MONGO_URI,
                tls=True,
                tlsCAFile=certifi.where()
            )
        else:
            print("Connexion avec TLS désactivé...")
            client = MongoClient(
                MONGO_URI,
                tls=False
            )

        # Vérifie la connexion au serveur
        server_info = client.server_info()
        print(f"Connexion réussie : {server_info}")
    except Exception as e:
        print(f"Erreur de connexion MongoDB : {e}")

if __name__ == "__main__":
    print("=== Débogage MongoDB ===")

    # Étape 1 : Tester la résolution DNS
    test_dns_resolution()

    # Étape 2 : Tester la connexion avec TLS activé
    test_mongo_connection(tls_enabled=True)

    # Étape 3 : Tester la connexion avec TLS désactivé (si nécessaire)
    test_mongo_connection(tls_enabled=False)
