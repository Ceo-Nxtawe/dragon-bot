from Dragon.proxy import get_data_with_proxy

def get_top_holders(contract_address: str) -> list:
    try:
        url = f"https://gmgn.ai/defi/quotation/v1/tokens/top_holders/sol/{contract_address}"
        headers = {'referer': 'https://gmgn.ai/?chain=sol'}
        response = get_data_with_proxy(url, headers=headers).json()

        holders = response.get("data", [])
        if not isinstance(holders, list):
            raise ValueError("Structure inattendue dans la réponse JSON : 'data' n'est pas une liste.")

        return [
            {
                "wallet": h.get("address", "N/A"),
                "percentage": (h.get("amount_percentage", 0)) * 100,
                "amount": h.get("amount_cur", 0)
            }
            for h in holders[:10]
        ]
    except Exception as e:
        return [{"error": f"Erreur : {str(e)}"}]
