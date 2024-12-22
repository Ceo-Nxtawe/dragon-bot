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
client = None

def connect_to_mongo():
    """
    Connexion sécurisée à MongoDB avec gestion des erreurs et TLS.
    """
    global client
    try:
        client = MongoClient(
            MONGO_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000  # Timeout pour éviter les blocages
        )
        # Test de connexion
        client.server_info()
        print("Connexion réussie à MongoDB.")
    except Exception as e:
        print(f"Erreur de connexion à MongoDB : {e}")
        client = None

# Initialiser la connexion à MongoDB
connect_to_mongo()

# Accès à la base de données
if client:
    db = client.WhalesX
    users_collection = db.botUsers
    try:
        users_collection.create_index("user_id", unique=True)
    except Exception as e:
        print(f"Erreur lors de la création de l'index : {e}")
else:
    print("MongoDB indisponible. Le bot fonctionnera en mode limité.")

# État pour suivre le dernier token analysé
LAST_ANALYZED_TOKEN = {}

# Vérifier si un utilisateur est enregistré
def is_user_registered(user_id: int) -> bool:
    if not client:
        return False
    try:
        return users_collection.find_one({"user_id": user_id}) is not None
    except Exception as e:
        print(f"Erreur lors de la vérification de l'utilisateur {user_id} : {e}")
        return False

# Ajouter ou mettre à jour un utilisateur
def upsert_user(user_id: int, email=None, referrals=None, position=None, fees_earned=0.0):
    if not client:
        print("MongoDB indisponible. Impossible de mettre à jour l'utilisateur.")
        return

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

# Récupérer les données d'un utilisateur
def get_user(user_id: int):
    if not client:
        return None
    try:
        return users_collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"Erreur lors de la récupération de l'utilisateur {user_id} : {e}")
        return None

# Fonction pour démarrer le bot et enregistrer l'utilisateur
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if not is_user_registered(user_id):
        upsert_user(user_id)

    await update.message.reply_text(
        "🐋 *Bienvenue sur Whalesx_tracker!*\n\n",
        parse_mode="Markdown"
    )

    user_data = get_user(user_id)
    if user_data and user_data.get("email"):
        await update.message.reply_text(
            "Cliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
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

    if "@" in email:
        position = count_whitelist_users()
        upsert_user(user_id, email=email, position=position)

        user_data = get_user(user_id)
        referral_link = escape_markdown(f"https://t.me/WhalesX_bot?start={user_id}")
        email_escaped = escape_markdown(email)

        await update.message.reply_text(
            f"✅ Votre email `{email_escaped}` a été enregistré !\n"
            f"📋 Vous êtes en position #{position} dans la whitelist.\n"
            f"🔗 Invitez vos amis avec ce lien : {referral_link}",
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

def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # Handlers pour les commandes et interactions
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))  # Regex pour l'email

    print("Le bot Whalesx_tracker fonctionne avec MongoDB...")
    application.run_polling()

if __name__ == "__main__":
    main()
