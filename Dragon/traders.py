from Dragon.proxy import get_data_with_proxy

def get_top_traders(contract_address: str) -> list:
    try:
        url = f"https://gmgn.ai/defi/quotation/v1/tokens/top_traders/sol/{contract_address}"
        headers = {'referer': 'https://gmgn.ai/?chain=sol', 'Connection': 'keep-alive'}
        response = get_data_with_proxy(url, headers=headers).json()
        traders = response.get("data", [])

        if not isinstance(traders, list):
            raise ValueError("Structure inattendue dans la réponse JSON : 'data' n'est pas une liste.")

        traders_sorted = sorted(traders, key=lambda t: t.get('realized_profit', 0), reverse=True)
        return [
            {
                "wallet": t.get("address", "N/A"),
                "realized_profit": t.get("realized_profit", 0),
                "unrealized_profit": t.get("unrealized_profit", 0),
                "total_profit": t.get("profit", 0),
            }
            for t in traders_sorted[:20]
        ]
    except Exception as e:
        return [{"error": f"Erreur : {str(e)}"}]
