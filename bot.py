from dotenv import load_dotenv
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.helpers import escape_markdown
from Dragon.bundle import check_bundle
from Dragon.bulkWallet import get_bulk_wallet_stats
from Dragon.holders import get_top_holders
from Dragon.traders import get_top_traders
from pymongo import MongoClient
import certifi
import traceback

# Charger les variables d'environnement
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
client = None  # Déclare le client global MongoDB

def connect_to_mongo():
    """
    Gère la connexion à MongoDB avec des options de tolérance.
    """
    global client
    try:
        if client is None:
            client = MongoClient(
                MONGO_URI,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=5000  # Timeout après 5 secondes
            )
        # Tester la connexion
        client.server_info()  # Vérifie la connectivité
        print("Connexion réussie à MongoDB")
    except Exception as e:
        print(f"Erreur lors de la connexion à MongoDB : {e}")
        print(traceback.format_exc())
        client = None

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
    try:
        return users_collection.find_one({"user_id": user_id}) is not None
    except Exception as e:
        print(f"Erreur lors de la vérification de l'utilisateur : {e}")
        return False

# Ajouter ou mettre à jour un utilisateur
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

# Récupérer les données d'un utilisateur
def get_user(user_id: int):
    try:
        return users_collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"Erreur lors de la récupération de l'utilisateur {user_id} : {e}")
        return None

# Compter les utilisateurs enregistrés
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

# Autres fonctionnalités comme `register_email`, `receive_token`, etc., restent similaires.

def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
                                               
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))  # Regex pour l'email
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))
    application.add_handler(CallbackQueryHandler(button_handler))  # Gère les callbacks

    print("Le bot est prêt et connecté à MongoDB...")
    application.run_polling()

if __name__ == "__main__":
    main()

