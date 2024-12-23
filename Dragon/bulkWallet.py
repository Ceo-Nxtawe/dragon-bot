from Dragon.proxy import get_data_with_proxy
import math
import time
from telegram.helpers import escape_markdown

HEADERS = {'referer': 'https://gmgn.ai/?chain=sol'}
# Timestamp il y a 1 mois (31 jours * 24h * 3600s)
ONE_MONTH = int(time.time()) - (31 * 24 * 3600)
TELEGRAM_MESSAGE_LIMIT = 4096  # Limite de caractères pour un message Telegram


def split_message(message: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list:
    """
    Divise un message en parties plus petites pour respecter la limite de caractères de Telegram.
    
    Args:
        message (str): Message à diviser.
        limit (int): Limite maximale de caractères pour chaque partie.
    
    Returns:
        list: Liste des sous-messages.
    """
    lines = message.split("\n")
    parts = []
    current_part = ""

    for line in lines:
        if len(current_part) + len(line) + 1 > limit:
            parts.append(current_part)
            current_part = line
        else:
            current_part += "\n" + line if current_part else line

    if current_part:
        parts.append(current_part)
    
    return parts


def get_bulk_wallet_stats(wallets: list, token_address: str = None) -> str:
    """
    Récupère et analyse les données des wallets, incluant PnL réalisé, non réalisé, Winrate, et Sharpe Ratio.
    
    Args:
        wallets (list): Liste des adresses des wallets à analyser.
        token_address (str, optional): Adresse du token pour l'analyse.

    Returns:
        str: Résultats formatés des statistiques des wallets.
    """
    try:     
        if not wallets:
            return "❌ Aucun wallet fourni pour l'analyse."

        formatted_results = "💼 *Bulk Wallet Stats*\n\n"
        RISK_FREE_RATE = 0.02  # Exemple de taux sans risque pour le Sharpe Ratio
        
        # List to store results with winrate
        wallet_results = []

        # Analyse des wallets
        for wallet in wallets:
            wallet_escaped = escape_markdown(wallet)
            try:
                url = f"https://gmgn.ai/defi/quotation/v1/wallet_activity/sol?type=buy&type=sell&wallet={wallet}&orderby=timestamp"

                wallet_response = get_data_with_proxy(url, headers=HEADERS).json()
                data = wallet_response.get("data", [])
                transactions = data["activities"]

                if not transactions:
                    wallet_results.append({
                        "wallet": wallet_escaped,
                        "pnl_realized": 0.0,
                        "pnl_unrealized": 0.0,
                        "winrate": 0.0,
                        "sharpe_ratio": 0.0,
                        "liquidity": 0.0,
                    })
                    continue
                
                # Filter transactions from last month
                recent_trades = [tx for tx in transactions if tx.get("timestamp", 0) >= ONE_MONTH]
                if not recent_trades:
                    wallet_results.append({
                        "wallet": wallet_escaped,
                        "pnl_realized": 0.0,
                        "pnl_unrealized": 0.0,
                        "winrate": 0.0,
                        "sharpe_ratio": 0.0,
                        "liquidity": 0.0,
                    })
                    continue

                # To store token data
                token_data = {}

                # Metrics to calculate
                pnl_realized, pnl_unrealized, liquidity = 0.0, 0.0, 0.0
                total_trades = len(recent_trades)
                winning_trades = 0
                portfolio_returns = []

                for tx in recent_trades:
                    token_address = tx.get('token_address', 'N/A')
                    token_current = tx.get('token', {})
                    token_current_price = token_current.get('price', 'N/A')
                    
                    event_type = tx.get("event_type", "N/A")
                    cost_usd = tx.get("cost_usd", 0) or 0.0
                    token_amount = float(tx.get('token_amount', 0)) or 0.0
                    price_usd = tx.get('price_usd', 0)
                    
                    if token_address not in token_data:
                        token_data[token_address] = {"buys": 0, "sells": 0, "total_token_amount": 0, "token_current_price": 0, "trades": [], "returns": []}
                    
                    if token_data[token_address]["token_current_price"] == 0:
                        token_data[token_address]["token_current_price"] = token_current_price
                        
                    if event_type == "buy":
                        token_data[token_address]["buys"] += cost_usd
                        token_data[token_address]["total_token_amount"] += token_amount
                    elif event_type == "sell":
                        token_data[token_address]["sells"] += cost_usd
                        token_data[token_address]["total_token_amount"] -= token_amount
                    
                    token_data[token_address]["trades"].append({
                        "event_type": event_type,
                        "cost_usd": cost_usd,
                        "token_amount": token_amount,
                        "price_usd": price_usd,
                        "token_address": token_address
                    })


                for token_address, info in token_data.items():
                    # print(f"\n{info["sells"]}\n")
                    # print(f"\n{info["buys"]}\n")
                      
                    token_pnl_realized = info["sells"] - info["buys"]
                    token_pnl_unrealized = info["total_token_amount"] * info["token_current_price"] - info["buys"]
                    
                    pnl_unrealized += token_pnl_unrealized
                    pnl_realized += token_pnl_realized
                    if info["total_token_amount"] < 0:
                        info["total_token_amount"] = 0
                            
                    token_liquidity = info["total_token_amount"] * info["token_current_price"]
                    liquidity += token_liquidity
                    
                    if info["buys"] > 0:
                        token_return = token_pnl_realized / info["buys"] * 100  # Calcul du rendement en %
                    else:
                        token_return = 0
                        
                    portfolio_returns.append(token_return)  # Add to retunrs list
                    if token_pnl_realized > 0:
                        winning_trades += 1

                # Calcul des ratios
                winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
                mean_return = sum(portfolio_returns) / len(portfolio_returns) if portfolio_returns else 0.0
                volatility = math.sqrt(
                    sum((r - mean_return) ** 2 for r in portfolio_returns) / len(portfolio_returns)
                ) if portfolio_returns else 0.0
                sharpe_ratio = (mean_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0
                
                if winrate > 0:
                    wallet_results.append({
                        "wallet": wallet_escaped,
                        "pnl_realized": pnl_realized,
                        "pnl_unrealized": pnl_unrealized,
                        "winrate": winrate,
                        "sharpe_ratio": sharpe_ratio,
                        "liquidity": liquidity
                    })
                
            except Exception as e:
                wallet_results.append({
                    "wallet": wallet_escaped,
                    "error": str(e)
                })

        wallet_results.sort(key=lambda x: x.get("winrate", 0), reverse=True)
        
        for result in wallet_results:
            if "error" in result:
                formatted_results += f"❌ Error for wallet `{result['wallet']}`: {escape_markdown(result['error'])}\n\n"
            else:
                formatted_results += (
                    f"🔹 Wallet: `{result['wallet']}`\n"
                    f"   📈 PnL realized: {result['pnl_realized']:.2f} USD\n"
                    f"   💵 PnL unrealized: {result['pnl_unrealized']:.2f} USD\n"
                    f"   🏆 Winrate: {result['winrate']:.2f}%\n"
                    f"   📊 Sharpe Ratio: {result['sharpe_ratio']:.2f}\n"
                    f"   🌊 Liquidity: {result['liquidity']:.2f} USD\n"
                    f"   🔗 [Cielo](https://app.cielo.finance/profile/{result['wallet']})\n\n"
                    # https://gmgn.ai/sol/address/{result['wallet']}
                )

        return split_message(formatted_results.strip())

    except Exception as e:
        return f"❌ *Erreur lors de l'analyse des wallets :* {escape_markdown(str(e))}"
