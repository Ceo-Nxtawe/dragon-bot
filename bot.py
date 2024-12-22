from dotenv import load_dotenv
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.helpers import escape_markdown
from Dragon.bundle import check_bundle
from Dragon.bulkWallet import get_bulk_wallet_stats
from Dragon.holders import get_top_holders
from Dragon.traders import get_top_traders
import certifi
from pymongo import MongoClient

# Charger les variables d'environnement
load_dotenv()

# Configuration MongoDB
MONGO_URI = os.getenv("MONGO_URI")
BOT_TOKEN = os.getenv("BOT_TOKEN")

try:
    # Connexion sécurisée à MongoDB sur le réseau privé de Railway
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),  # Vérifie les certificats racines
        tlsAllowInvalidCertificates=False  # Assure la validation TLS
    )
    print(client.server_info())  # Vérifie la connexion
    print("Connexion réussie à MongoDB via le réseau privé Railway")
except Exception as e:
    print(f"Erreur de connexion à MongoDB : {e}")

# Accès à la base de données et aux collections
try:
    db = client.WhalesX  # Nom de la base de données
    users_collection = db.botUsers  # Collection des utilisateurs
    users_collection.create_index("user_id", unique=True)
    print("Index sur 'user_id' créé ou déjà existant.")
except Exception as e:
    print(f"Erreur lors de l'accès ou de la configuration de la base de données : {e}")

# État pour suivre le dernier token analysé
LAST_ANALYZED_TOKEN = {}

# Fonction pour vérifier si un utilisateur est enregistré
def is_user_registered(user_id: int) -> bool:
    try:
        return users_collection.find_one({"user_id": user_id}) is not None
    except Exception as e:
        print(f"Erreur lors de la vérification de l'utilisateur {user_id} : {e}")
        return False

# Fonction pour ajouter ou mettre à jour un utilisateur dans MongoDB
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

    try:
        users_collection.update_one(
            {"user_id": user_id},  # Condition
            {"$set": update_data},  # Données à mettre à jour
            upsert=True  # Crée un document si inexistant
        )
    except Exception as e:
        print(f"Erreur lors de la mise à jour ou de l'ajout d'un utilisateur : {e}")

# Fonction pour récupérer les données d'un utilisateur
def get_user(user_id: int):
    try:
        return users_collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"Erreur lors de la récupération de l'utilisateur {user_id} : {e}")
        return None

# Fonction pour compter les utilisateurs enregistrés
def count_whitelist_users():
    try:
        return users_collection.count_documents({})
    except Exception as e:
        print(f"Erreur lors du comptage des utilisateurs : {e}")
        return 0

# Fonction pour démarrer le bot et enregistrer l'utilisateur
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if not is_user_registered(user_id):
        # Ajouter l'utilisateur à la base de données
        upsert_user(user_id)

    await update.message.reply_text(
        "🐋 *Bienvenue sur Whalesx_tracker!*\n\n",
        parse_mode="Markdown"
    )
    if get_user(user_id) and get_user(user_id).get("email"):
        await update.message.reply_text(
            "Cliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        # Demander l'email pour l'inscription
        await update.message.reply_text(
            "✉️ *Pour rejoindre la whitelist, veuillez fournir votre email.*", parse_mode="Markdown"
        )

# Fonction pour enregistrer l'email de l'utilisateur
async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    email = update.message.text.strip()

    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Veuillez d'abord démarrer avec /start.")
        return

    # Validation simple de l'email
    if "@" in email:
        position = count_whitelist_users()
        upsert_user(user_id, email=email, position=position)

        referral_link = escape_markdown(f"https://t.me/WhalesX_bot?start={user_id}")
        await update.message.reply_text(
            f"✅ Votre email `{email}` a été enregistré !\n"
            f"📋 Vous êtes en position #{position} dans la whitelist.\n"
            f"🔗 Invitez vos amis avec ce lien : {referral_link}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Veuillez fournir un email valide.", parse_mode="Markdown")

# Fonction pour analyser un token
async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    token_address = update.message.text.strip() if update.message.text else None
    if not token_address:
        await update.message.reply_text("❌ Adresse du token invalide.", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 Analyse en cours pour le token : `{token_address}`", parse_mode="Markdown")
    try:
        bundles = check_bundle(token_address)
        if not bundles:
            await update.message.reply_text("❌ Aucun bundle trouvé.", parse_mode="Markdown")
        else:
            formatted_results = "✅ *Résultats de l'analyse*:\n\n"
            for idx, (tx_hash, quote_amount) in enumerate(bundles, start=1):
                formatted_results += f"{idx}️⃣ Transaction: `{tx_hash}`\n   Amount: {quote_amount:.4f} SOL\n\n"
            await update.message.reply_text(formatted_results, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}", parse_mode="Markdown")

# Lancer le bot
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))
    print("Bot en cours d'exécution...")
    application.run_polling()

if __name__ == "__main__":
    main()
