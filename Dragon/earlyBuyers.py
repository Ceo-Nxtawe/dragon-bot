from Dragon.proxy import get_data_with_proxy

def get_early_buyers(contract_address: str) -> str:
    """
    Récupère les 10 premiers early buyers pour un contrat Solana via GMGN,
    en se basant sur l'ordre chronologique des transactions de type 'buy',
    en affichant la `quote_amount` et en excluant ceux dont le balance est à 0.
    """
    try:
        # URL et headers pour la requête
        url = f"https://gmgn.ai/defi/quotation/v1/trades/sol/{contract_address}?revert=true"
        headers = {'referer': 'https://gmgn.ai/?chain=sol'}

        # Récupération des données depuis l'API
        response = get_data_with_proxy(url, headers=headers).json()

        # print("[DEBUG] Réponse JSON brute BUYERS :", response.get("data", []))

        # Récupération des données
        data = response.get("data", [])

        # Si data est une liste, on l'utilise directement
        if isinstance(data, list):
            buyers = data
        else:
            # Si data n'est pas une liste, on vSérifie la présence d'une clé "history"
            if not isinstance(data, dict) or "history" not in data:
                raise ValueError("Structure inattendue dans la réponse JSON : 'data' n'est pas une liste ni un dict contenant 'history'.")
            
            buyers = data["history"]
            if not isinstance(buyers, list):
                raise ValueError("Structure inattendue dans la réponse JSON : 'history' n'est pas une liste.")

        # Filtrer uniquement les transactions de type "buy" et celles ayant un balance != 0
        buy_transactions = [
            b for b in buyers 
            if b.get("event") == "buy"
            and "timestamp" in b
            and b.get("balance") != "0.00000000000000000000"
        ]

        # Trier les transactions d'achat par ordre chronologique (timestamp croissant)
        sorted_buyers = sorted(buy_transactions, key=lambda buyer: buyer["timestamp"])

        # On veut les 10 premiers acheteurs distincts par ordre d'apparition
        seen_makers = set()
        early_buyers_list = []

        for buyer in sorted_buyers:
            # On essaie d'abord "address", puis "maker" si "address" n'existe pas
            wallet_id = buyer.get('address') or buyer.get('maker')
            if wallet_id and wallet_id not in seen_makers:
                seen_makers.add(wallet_id)
                quote_amt = buyer.get('quote_amount', 0)
                early_buyers_list.append(
                    f"Address: {wallet_id} - Amount: {quote_amt} SOL - Timestamp: {buyer['timestamp']}"
                )
                if len(early_buyers_list) == 10:
                    break

        # Retourner les acheteurs formatés
        return "\n".join(early_buyers_list) if early_buyers_list else "Aucun early buyer trouvé."

    except Exception as e:
        return f"Erreur : {str(e)}"
