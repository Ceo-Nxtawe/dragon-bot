from Dragon.proxy import get_data_with_proxy
from telegram.helpers import escape_markdown

def get_token_info(token_address: str) -> list:
    # Si un token_address est fourni, récupérer ses informations
    if token_address:
        try:
            token_url = f"https://api.dexscreener.io/latest/dex/tokens/{token_address}"
            token_response = get_data_with_proxy(token_url).json()
            token_data = token_response.get("pairs", [{}])[0]  # Première paire associée

            if token_data:
                symbol = escape_markdown(token_data.get('baseToken', {}).get('symbol', 'N/A'))
                price_usd = token_data.get('priceUsd', 0) or 0.0
                liquidity_usd = token_data.get('liquidity', {}).get('usd', 0) or 0.0

                formatted_results += (
                    f"🔹 *Token Analyzed*: `{escape_markdown(token_address)}`\n"
                    f"   🪙 Symbol: {symbol}\n"
                    f"   💵 Price: {price_usd:.2f} USD\n"
                    f"   💧 Liquidity: {liquidity_usd:.2f} USD\n\n"
                )
            else:
                formatted_results += f"❌ Aucune information trouvée pour le token `{escape_markdown(token_address)}`.\n\n"
        except Exception as e:
            formatted_results += f"❌ Erreur lors de la récupération des données pour le token : {escape_markdown(str(e))}\n\n"
