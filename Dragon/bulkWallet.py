from Dragon.proxy import get_data_with_proxy
import math
import time
from telegram.helpers import escape_markdown

HEADERS = {'referer': 'https://gmgn.ai/?chain=sol'}
# Timestamp il y a 1 mois (31 jours * 24h * 3600s)
ONE_MONTH = int(time.time()) - (31 * 24 * 3600)

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

        # Analyse des wallets
        for wallet in wallets:
            wallet_escaped = escape_markdown(wallet)
            try:
                url = f"https://gmgn.ai/defi/quotation/v1/wallet_activity/sol?type=buy&type=sell&wallet={wallet}&orderby=timestamp"

                wallet_response = get_data_with_proxy(url, headers=HEADERS).json()
                data = wallet_response.get("data", [])
                transactions = data["activities"]

                if not transactions:
                    formatted_results += f"❌ Wallet `{wallet_escaped}` : Aucune transaction trouvée.\n\n"
                    continue
                # Filtrer les transactions de moins d'un mois
                recentTrades = [trade for trade in transactions if trade.get("timestamp", 0) >= ONE_MONTH]

                # On va stocker les montants achetés/vendus par token
                token_data = {}
                                
                # Calcul des métriques
                pnl_realized = 0.0
                pnl_unrealized = 0.0
                total_trades = len(recentTrades)
                winning_trades = 0
                portfolio_returns = []
                liquidity = 0.0

                for tx in recentTrades:
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
                    
                # Calcul PnL + Winrate
                total_tokens_traded = 0
                portfolio_returns = []  # pour calculer la volatilité 
                
                for token_address, info in token_data.items():
                    total_tokens_traded += 1
                    print(f"\n{info["sells"]}\n")
                    print(f"\n{info["buys"]}\n")
                      
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
                    
                if total_tokens_traded > 0:
                    winrate = (winning_trades / total_tokens_traded) * 100
                else:
                    winrate = 0 

                # Calcul des ratios
                winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
                mean_return = sum(portfolio_returns) / len(portfolio_returns) if portfolio_returns else 0.0
                volatility = math.sqrt(
                    sum((r - mean_return) ** 2 for r in portfolio_returns) / len(portfolio_returns)
                ) if portfolio_returns else 0.0
                sharpe_ratio = (mean_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0

                # Calcul des 
                # Formater les résultats pour chaque wallet
                formatted_results += (
                    f"🔹 Wallet: `{wallet_escaped}`\n"
                    f"   📈 PnL Réalisé: {pnl_realized:.2f} USD\n"
                    f"   💵 PnL Non Réalisé: {pnl_unrealized:.2f} USD\n"
                    f"   🏆 Winrate: {winrate:.2f}%\n"
                    f"   📊 Sharpe Ratio: {sharpe_ratio:.2f}\n"
                    f"   🌊 Liquidity: {liquidity:.2f} USD\n\n"
                )
            except Exception as e:
                formatted_results += f"❌ Erreur pour le wallet `{wallet_escaped}` : {escape_markdown(str(e))}\n\n"

        return formatted_results.strip()

    except Exception as e:
        return f"❌ *Erreur lors de l'analyse des wallets :* {escape_markdown(str(e))}"
