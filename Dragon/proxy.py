import requests
import urllib3

# Désactiver les avertissements liés à SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration du proxy Bright Data avec les nouvelles informations
BRIGHT_DATA_PROXY = {
    "http": "http://brd-customer-hl_961a5843-zone-gmgnscrapper:a4ypx1ve1qcr@brd.superproxy.io:33335",
    "https": "http://brd-customer-hl_961a5843-zone-gmgnscrapper:a4ypx1ve1qcr@brd.superproxy.io:33335"
}

def get_data_with_proxy(url: str, headers: dict = None, json_payload: dict = None, timeout: int = 60) -> requests.Response:
    """
    Effectue une requête HTTP avec un proxy Bright Data et SSL désactivé.
    
    Args:
        url (str): URL cible de la requête.
        headers (dict, optional): En-têtes HTTP pour la requête.
        json_payload (dict, optional): Payload JSON pour les requêtes POST.
        timeout (int): Timeout de la requête en secondes.
    
    Returns:
        requests.Response: Réponse de l'API.
    
    Raises:
        RuntimeError: En cas d'échec de la requête.
    """
    try:
        # Créer une session avec le proxy
        session = requests.Session()
        session.proxies.update(BRIGHT_DATA_PROXY)

        # Effectuer une requête GET ou POST
        if json_payload is not None:
            # POST avec un payload JSON
            response = session.post(url, headers=headers, json=json_payload, verify=False, timeout=timeout)
        else:
            # GET classique
            response = session.get(url, headers=headers, verify=False, timeout=timeout)
        
        response.raise_for_status()  # Vérifie les erreurs HTTP
        return response
    except requests.Timeout:
        raise RuntimeError(f"Timeout atteint lors de la requête à {url}.")
    except requests.RequestException as e:
        raise RuntimeError(f"Erreur HTTP lors de la requête à {url} : {str(e)}")

