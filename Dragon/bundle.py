from Dragon.proxy import get_data_with_proxy

def check_bundle(contract_address: str) -> list:
    """
    Vérifie les bundles pour un contrat Solana via GMGN et retourne les 20 premiers sous forme de liste.
    """
    try:
        url = f"https://gmgn.ai/defi/quotation/v1/trades/sol/{contract_address}?limit=50"
        headers = {'referer': 'https://gmgn.ai/?chain=sol'}
        response = get_data_with_proxy(url, headers=headers).json()

        # Récupération des données
        data = response.get("data", [])

        # Si data est une liste, on l'utilise directement
        if isinstance(data, list):
            trades = data
        else:
            # Si data n'est pas une liste, on vérifie la présence d'une clé "history"
            if not isinstance(data, dict) or "history" not in data:
                raise ValueError("Structure inattendue dans la réponse JSON : 'data' n'est pas une liste ni un dict contenant 'history'.")
            
            trades = data["history"]
            if not isinstance(trades, list):
                raise ValueError("Structure inattendue dans la réponse JSON : 'history' n'est pas une liste.")

        # On prend les 20 premières transactions
        bundles = trades[:20]

        # Retourne une liste de tuples (tx_hash, quote_amount)
        return [(b['tx_hash'], b['quote_amount']) for b in bundles]

    except Exception as e:
        raise RuntimeError(f"Erreur lors de la récupération des bundles : {str(e)}")
