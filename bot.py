# bot.py

from dotenv import load_dotenv
import os
import socket
import certifi
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.helpers import escape_markdown

# == Import de tes modules Dragon ==
from Dragon.bundle import check_bundle
from Dragon.bulkWallet import get_bulk_wallet_stats
from Dragon.holders import get_top_holders
from Dragon.traders import get_top_traders

# == MongoDB ==
from pymongo import MongoClient

# Charge les variables d'environnement
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def test_dns_resolution(hostname="mongodb.railway.internal"):
    """
    Teste si le nom d'hôte MongoDB est résolu correctement (optionnel).
    """
    print("\n### DNS Resolution Test ###")
    try:
        resolved_ip = socket.gethostbyname(hostname)
        print(f"DNS résolu avec succès : {hostname} -> {resolved_ip}")
    except Exception as e:
        print(f"Erreur DNS : {e}")

def get_mongo_client(mongo_uri: str) -> MongoClient:
    """
    Renvoie un client MongoDB selon qu'on soit sur Railway (sans TLS) ou autre (avec TLS).
    """
    if "railway.internal" in mongo_uri:
        # Railway interne -> DNS interne -> souvent pas de TLS
        print("Connexion avec TLS désactivé (Railway internal host)...")
        return MongoClient(mongo_uri, tls=False)
    else:
        # Mongo Atlas ou autre -> TLS activé
        print("Connexion avec TLS activé (hors Railway)...")
        return MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())

# ================== Connexion MongoDB ======================
try:
    if "railway.internal" in MONGO_URI:
        test_dns_resolution("mongodb.railway.internal")

    client = get_mongo_client(MONGO_URI)
    print(client.server_info())  # Vérifie la connexion
    print("Connexion réussie à MongoDB")
except Exception as e:
    print(f"Erreur de connexion : {e}")

db = client.WhalesX  # Nom de ta database
users_collection = db.botUsers  # Collection pour tes utilisateurs
try:
    users_collection.create_index("user_id", unique=True)
except Exception as e:
    print(f"Erreur lors de la création de l'index : {e}")

# ================== Variables globales ======================
# Pour stocker le dernier token analysé par chat
LAST_ANALYZED_TOKEN = {}

# ================== Fonctions DB utilisateur =================
def is_user_registered(user_id: int) -> bool:
    return users_collection.find_one({"user_id": user_id}) is not None

def upsert_user(user_id: int, email=None, referrals=None, position=None, fees_earned=0.0):
    update_data = {}
    if email is not None:
        update_data["email"] = email
    if referrals is not None:
        update_data["referrals"] = referrals
    if position is not None:
        update_data["position"] = position
    if fees_earned is not None:
        update_data["fees_earned"] = fees_earned

    users_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )

def get_user(user_id: int):
    return users_collection.find_one({"user_id": user_id})

def count_whitelist_users():
    return users_collection.count_documents({})

# ================== Handlers de commande =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start : Accueil et enregistrement (email) si besoin.
    """
    user = update.effective_user
    user_id = user.id

    keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Enregistre l'utilisateur s'il n'existe pas
    if not is_user_registered(user_id):
        upsert_user(user_id)

    await update.message.reply_text(
        "🐋 *Bienvenue sur Whalesx_tracker!*\n\n",
        parse_mode="Markdown"
    )
    
    # Si l'email est déjà renseigné, on propose direct de démarrer l'analyse
    if get_user(user_id).get("email"):
        await update.message.reply_text(
            "Cliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        # Sinon, on demande l'email
        await update.message.reply_text(
            "✉️ *Pour rejoindre la whitelist, veuillez fournir votre email.*",
            parse_mode="Markdown"
        )

async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Récupère l'email de l'utilisateur et enregistre en DB.
    """
    user = update.effective_user
    user_id = user.id
    email = update.message.text.strip()

    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Veuillez d'abord démarrer avec /start.")
        return

    # Simple validation "@" pour l'email
    if "@" in email:
        position = count_whitelist_users()
        upsert_user(user_id, email=email, position=position)

        user_data = get_user(user_id)
        # ===== Lien de parrainage mis à jour pour @WhalesX_Tracker_bot =====
        referral_link = escape_markdown(f"https://t.me/WhalesX_Tracker_bot?start={user_id}")
        email_escaped = escape_markdown(email)

        await update.message.reply_text(
            f"✅ Your email {email_escaped} has been registered!\n"
            f"📋 You are at position #{position} in the whitelist.\n"
            f"🔗 Invite friends with this link: {referral_link}",
            parse_mode="Markdown",
        )

        keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "✅ Inscription terminée !\nCliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Veuillez fournir un email valide.", parse_mode="Markdown")


# ================== Bouton "Démarrer l'analyse" =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback quand l'utilisateur clique sur "Démarrer l'analyse".
    """
    query = update.callback_query
    await query.answer()
    context.user_data["ready_for_analysis"] = True
    
    await query.edit_message_text(
        "📝 *Please enter the token address (contract) you want to analyse:*",
        parse_mode="Markdown"
    )

# ================== Menu interactif final =====================
async def send_menu(update: Update) -> None:
    """
    Affiche le menu de navigation (Bulk Wallet, Top Holders, etc.).
    """
    keyboard = [
        [InlineKeyboardButton("📊 Bulk Wallet", callback_data="bulkwallet")],
        [InlineKeyboardButton("🏆 Top Holders", callback_data="topholders")],
        [InlineKeyboardButton("📈 Top Traders", callback_data="toptraders")],
        [InlineKeyboardButton("🚀 Analyser un autre token", callback_data="start_analysis")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "❓ *Que voulez-vous faire maintenant ?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ================== Réception du token & analyse =====================
async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Quand l'utilisateur envoie un token (texte simple),
    on fait l'analyse du bundle + on prépare holders/traders en coulisses.
    """
    if not context.user_data.get("ready_for_analysis"):
        return  # L'utilisateur n'a pas cliqué sur "Démarrer l'analyse", on ignore

    global LAST_ANALYZED_TOKEN
    token_address = update.message.text.strip() if update.message.text else None
    LAST_ANALYZED_TOKEN[update.effective_chat.id] = token_address

    if not token_address:
        await update.message.reply_text("❌ *Aucune adresse de token valide fournie.*", parse_mode="Markdown")
        return

    # ----- (1) Analyse du bundle (affiché à l'utilisateur) -----
    await update.message.reply_text(
        f"🔍 *Analyse en cours pour le token :* `{escape_markdown(token_address)}`",
        parse_mode="Markdown"
    )

    try:
        bundles = check_bundle(token_address)
        if not bundles:
            await update.message.reply_text("❌ Aucun bundle trouvé pour ce contrat.", parse_mode="Markdown")
        else:
            formatted_results = "✅ *Bundle Analysis Results*:\n\n"
            for idx, (tx_hash, quote_amount) in enumerate(bundles, start=1):
                tx_hash = escape_markdown(tx_hash or "N/A")
                quote_amount = quote_amount or 0.0  
                formatted_results += f"{idx}️⃣ Transaction: `{tx_hash}`\n   Amount: {quote_amount:.4f} SOL\n\n"
            formatted_results += f"📊 *Total Transactions Analyzed*: {len(bundles)}"
            await update.message.reply_text(formatted_results, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Erreur (bundle):* {escape_markdown(str(e))}",
            parse_mode="Markdown"
        )

    # ----- (2) Pré-récupération des Top Holders & Top Traders (en coulisses) -----
    try:
        holders = get_top_holders(token_address)
        traders = get_top_traders(token_address)
        # On stocke dans context.user_data pour réutiliser plus tard
        context.user_data["top_holders"] = holders
        context.user_data["top_traders"] = traders
    except Exception as e:
        print(f"[Warn] Impossible de récupérer holders/traders : {e}")
        context.user_data["top_holders"] = []
        context.user_data["top_traders"] = []

    # ----- (3) Afficher le menu final -----
    await send_menu(update)


# ================== Callback quand on clique sur un bouton du menu =====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_ANALYZED_TOKEN
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    token_address = LAST_ANALYZED_TOKEN.get(chat_id)

    if not token_address:
        await query.edit_message_text(
            "❌ Aucun token analysé récemment. Veuillez entrer une adresse pour commencer l'analyse.",
            parse_mode="Markdown"
        )
        return

    action = query.data

    if action == "bulkwallet":
        await query.edit_message_text("💼 *Bulk Wallet*: Analyse en cours...", parse_mode="Markdown")
        try:
            # On récupère la liste déjà chargée
            holders = context.user_data.get("top_holders", [])
            traders = context.user_data.get("top_traders", [])

            wallets = list(set(
                [h.get('wallet', 'N/A') for h in holders] +
                [t.get('wallet', 'N/A') for t in traders]
            ))

            bulk_stats = get_bulk_wallet_stats(wallets, token_address=token_address)
            await update.effective_chat.send_message(bulk_stats, parse_mode="Markdown")

        except Exception as e:
            await update.effective_chat.send_message(
                f"❌ *Erreur lors de l'analyse Bulk Wallet :* {escape_markdown(str(e))}",
                parse_mode="Markdown"
            )

    elif action == "topholders":
        await query.edit_message_text("🏆 *Top Holders*: ...", parse_mode="Markdown")
        holders = context.user_data.get("top_holders", [])
        if not holders:
            await update.effective_chat.send_message(
                "❌ Aucune liste Top Holders en mémoire.",
                parse_mode="Markdown"
            )
            return
        
        formatted_holders = "🏆 *Top Holders Analysis*:\n\n"
        for idx, holder in enumerate(holders, start=1):
            wallet = escape_markdown(holder.get('wallet', 'N/A'))
            amount = holder.get('amount', 0.0) or 0.0
            percentage = holder.get('percentage', 0.0) or 0.0
            formatted_holders += (
                f"{idx}️⃣ Wallet: `{wallet}`\n"
                f"   💰 Amount: {amount:.4f} Spl\n"
                f"   🎯 Owned %: {percentage:.2f}%\n\n"
            )
        await update.effective_chat.send_message(formatted_holders, parse_mode="Markdown")

    elif action == "toptraders":
        await query.edit_message_text("📈 *Top Traders*: ...", parse_mode="Markdown")
        traders = context.user_data.get("top_traders", [])
        if not traders:
            await update.effective_chat.send_message(
                "❌ Aucune liste Top Traders en mémoire.",
                parse_mode="Markdown"
            )
            return
        
        formatted_traders = "📈 *Top Traders Analysis*:\n\n"
        for idx, trader in enumerate(traders, start=1):
            wallet = escape_markdown(trader.get('wallet', 'N/A'))
            realized_profit = trader.get('realized_profit', 0.0)
            unrealized_profit = trader.get('unrealized_profit', 0.0)
            total_profit = trader.get('total_profit', 0.0)
            
            formatted_traders += (
                f"{idx}️⃣ Wallet: `{wallet}`\n"
                f"   💰 Realized Profit: {realized_profit:.2f} USD\n"
                f"   🔄 Unrealized Profit: {unrealized_profit:.2f} USD\n"
                f"   📊 Total PnL (unrealized + realized): {total_profit:.2f} USD\n\n"
            )
        await update.effective_chat.send_message(formatted_traders, parse_mode="Markdown")


# ================== Commande "referral" =====================
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /referral : Permet de gérer le parrainage (ex: /referral <ID>).
    """
    user = update.effective_user
    user_id = user.id

    args = context.args
    if args and args[0].isdigit():
        referrer_id = int(args[0])

        # Vérifier que le parrain existe et que ce n'est pas l'utilisateur lui-même
        referrer_data = get_user(referrer_id)
        if referrer_data and user_id != referrer_id:
            user_data = get_user(user_id)
            if user_data:
                referrals = referrer_data.get("referrals", [])
                if user_id not in referrals:
                    referrals.append(user_id)
                    upsert_user(referrer_id, referrals=referrals)

                    fees_earned = referrer_data.get("fees_earned", 0.0) + 1.0
                    upsert_user(referrer_id, fees_earned=fees_earned)

                    await update.message.reply_text(
                        f"Vous avez été référé par {referrer_data.get('email', 'un utilisateur inconnu')} !"
                    )
                    return

    await update.message.reply_text("Lien de parrainage invalide ou déjà utilisé.")


# ================== Commande "status" =====================
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status : Affiche la position whitelist, parrainages, fees, etc.
    """
    user = update.effective_user
    user_id = user.id

    user_data = get_user(user_id)
    if user_data:
        position = user_data.get("position", "Non classé")
        referrals = len(user_data.get("referrals", []))
        fees = user_data.get("fees_earned", 0.0)

        await update.message.reply_text(
            f"Position dans la whitelist : #{position}\n"
            f"Nombre de parrainages : {referrals}\n"
            f"Fees accumulés : {fees} unités"
        )
    else:
        await update.message.reply_text("Veuillez d'abord démarrer avec /start.")


# ================== main() : lancement du bot =====================
def main():
    # token à adapter
    application = Application.builder().token("8171737440:AAGTb434bzrTSakyREYxgmyuxEG-N5aNb7c").build()
    print("Le bot Whalesx_tracker fonctionne avec menu interactif et analyse automatique du token...")

    # === CommandHandlers ===
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", my_status))
    application.add_handler(CommandHandler("referral", referral))
    
    # Handler pour le mail (regex sur l'email)
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))

    # Handler texte simple -> on suppose que c'est l'adresse du token
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))

    # === CallbackQueryHandlers ===
    application.add_handler(CallbackQueryHandler(button_handler))  # start_analysis
    application.add_handler(CallbackQueryHandler(callback_handler)) # bulkwallet, topholders, toptraders

    # Démarrer en mode polling
    application.run_polling()

if __name__ == "__main__":
    main()
