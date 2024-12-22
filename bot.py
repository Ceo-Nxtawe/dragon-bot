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

# MongoDB configuration
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BOT_TOKEN = os.getenv("BOT_TOKEN")

try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    print(client.server_info())  # Vérifie la connexion
    print("Connexion réussie à MongoDB Atlas")
except Exception as e:
    print(f"Erreur de connexion : {e}")
    
db = client.WhalesX  # database name
users_collection = db.botUsers  # User collection
try:
    users_collection.create_index("user_id", unique=True)
except Exception as e:
    print(f"Erreur lors de la création de l'index : {e}")

# State to keep track of the last analyzed token
LAST_ANALYZED_TOKEN = {}

# Function to check if a user is registered
def is_user_registered(user_id: int) -> bool:
    return users_collection.find_one({"user_id": user_id}) is not None

# Function to add or update a user in MongoDB
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
        {"user_id": user_id},  # Condition
        {"$set": update_data},  # Data to update
        upsert=True  # Creates a new document if it doesn't exist
    )

# Function to get a user
def get_user(user_id: int):
    return users_collection.find_one({"user_id": user_id})

# Function to count the number of users in the whitelist
def count_whitelist_users():
    return users_collection.count_documents({})


# Function to welcome the user and start the registration process
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not is_user_registered(user_id):
        # Add the user to the database
        upsert_user(user_id)

    await update.message.reply_text(
        "🐋 *Bienvenue sur Whalesx_tracker!*\n\n",
        parse_mode="Markdown"
    )
    
    if get_user(user_id).get("email"):
        keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Cliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        # Ask for the email to register
        await update.message.reply_text(
            "✉️ *Pour rejoindre la whitelist, veuillez fournir votre email.*", parse_mode="Markdown"
        )

# Function to register the email and complete the registration
async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    email = update.message.text.strip()

    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Veuillez d'abord démarrer avec /start.")
        return

    # Simple email validation
    if "@" in email:
        position = count_whitelist_users()
        upsert_user(user_id, email=email, position=position)

        user_data = get_user(user_id)
        referral_link = escape_markdown(f"https://t.me/WhalesX_bot?start={user_id}")
        email_escaped = escape_markdown(email)

        await update.message.reply_text(
            f"✅ Your email {email_escaped} has been registered!\n"
            f"📋 You are at position #{position} in the whitelist.\n"
            f"🔗 Invite friends with this link: {referral_link}",
            parse_mode="Markdown",
        )

        # Once registered, offer the main menu
        keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "✅ Inscription terminée !\nCliquez sur *Démarrer l'analyse* pour entrer un token à analyser.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Veuillez fournir un email valide.", parse_mode="Markdown")


# Handler for the "Start Analysis" button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # Définir que l'utilisateur est prêt pour l'analyse
    context.user_data["ready_for_analysis"] = True
    
    await query.edit_message_text(
        "📝 *Please enter the token address (contract) you want to analyse:*",
        parse_mode="Markdown"
    )


# Interactive menu at the end of each command
async def send_menu(update: Update) -> None:
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

# Reception and analysis of the token
async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("ready_for_analysis"):
        # Ignorer les messages si l'utilisateur n'est pas prêt pour l'analyse
        return

    global LAST_ANALYZED_TOKEN
    token_address = update.message.text.strip() if update.message.text else None
    LAST_ANALYZED_TOKEN[update.effective_chat.id] = token_address

    if not token_address:
        await update.message.reply_text("❌ *Aucune adresse de token valide fournie.*", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 *Analyse en cours pour le token :* `{escape_markdown(token_address or 'N/A')}`", parse_mode="Markdown")

    try:
        # Analysis of the bundles
        bundles = check_bundle(token_address)

        if not bundles:
            await update.message.reply_text("❌ Aucun bundle trouvé pour ce contrat.", parse_mode="Markdown")
        else:
            formatted_results = "✅ *Bundle Analysis Results*:\n\n"
            for idx, (tx_hash, quote_amount) in enumerate(bundles, start=1):
                tx_hash = escape_markdown(tx_hash or "N/A")
                quote_amount = quote_amount or 0.0  # Par défaut 0.0 si None
                formatted_results += f"{idx}️⃣ Transaction: `{tx_hash}`\n   Amount: {quote_amount:.4f} SOL\n\n"

            formatted_results += f"📊 *Total Transactions Analyzed*: {len(bundles)}"
            await update.message.reply_text(formatted_results, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ *Erreur :* {escape_markdown(str(e))}", parse_mode="Markdown")

    await send_menu(update)

# Callback to handle automatic analysis with the current token
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global LAST_ANALYZED_TOKEN
    query = update.callback_query
    await query.answer()

    # Get the last analyzed token
    chat_id = update.effective_chat.id
    token_address = LAST_ANALYZED_TOKEN.get(chat_id)

    if not token_address:
        await query.edit_message_text(
            "❌ Aucun token analysé récemment. Veuillez entrer une adresse pour commencer l'analyse.",
            parse_mode="Markdown"
        )
        return

    # Identifier l'action à effectuer
    action = query.data

    if action == "bulkwallet":
        await query.edit_message_text("💼 *Bulk Wallet*: Analyse des wallets des Top Holders et Top Traders...", parse_mode="Markdown")

        try:
            holders = get_top_holders(token_address)
            traders = get_top_traders(token_address)

            # Extract unique wallets
            wallets = list(set([
                escape_markdown(holder.get('wallet', 'N/A')) for holder in holders
            ] + [
                escape_markdown(trader.get('wallet', 'N/A')) for trader in traders
            ]))

            bulk_stats = get_bulk_wallet_stats(wallets, token_address=token_address)

            await update.effective_chat.send_message(bulk_stats, parse_mode="Markdown")

        except Exception as e:
            await update.effective_chat.send_message(f"❌ *Erreur lors de l'analyse Bulk Wallet :* {escape_markdown(str(e))}", parse_mode="Markdown")

    elif action == "topholders":
        await query.edit_message_text("🏆 *Top Holders*: Fetching the largest token holders...", parse_mode="Markdown")
        holders = get_top_holders(token_address)
        formatted_holders = "🏆 *Top Holders Analysis*:\n\n"
        for idx, holder in enumerate(holders, start=1):
            wallet = escape_markdown(holder.get('wallet', 'N/A'))
            amount = holder.get('amount', 0) or 0.0
            percentage = holder.get('percentage', 0) or 0.0
            
            formatted_holders += (
                f"{idx}️⃣ Wallet: `{wallet}`\n"
                f"   💰 Amount: {amount:.4f} Spl\n"
                f"   🎯 Owned %: {percentage:.2f}%\n\n"
            )
        await update.effective_chat.send_message(formatted_holders, parse_mode="Markdown")

    elif action == "toptraders":
        await query.edit_message_text("📈 *Top Traders*: Retrieving the most successful traders...", parse_mode="Markdown")
        traders = get_top_traders(token_address)
        formatted_traders = "📈 *Top Traders Analysis*:\n\n"
        for idx, trader in enumerate(traders, start=1):            
            wallet = escape_markdown(trader.get('wallet', 'N/A'))
            realized_profit = trader.get('realized_profit', 0) or 0.0
            unrealized_profit = trader.get('unrealized_profit', 0) or 0.0
            total_profit = trader.get('total_profit', 0) or 0.0
            
            formatted_traders += (
                f"{idx}️⃣ Wallet: `{wallet}`\n"
                f"   💰 Realized Profit: {realized_profit:.2f} USD\n"
                f"   🔄 Unrealized Profit: {unrealized_profit:.2f} USD\n"
                f"   📊 Total PnL (unrealized + realized): {total_profit:.2f} USD\n\n"
            )
        await update.effective_chat.send_message(formatted_traders, parse_mode="Markdown")


# Command to handle referral links
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    # Extract the referrer ID from the start command arguments
    args = context.args
    if args and args[0].isdigit():
        referrer_id = int(args[0])

        # Check if the referrer exists and is not the current user
        referrer_data = get_user(referrer_id)
        if referrer_data and user_id != referrer_id:
            # Fetch the current user data
            user_data = get_user(user_id)

            # Check if the current user is already a referral of the referrer
            if user_data:
                referrals = referrer_data.get("referrals", [])
                if user_id not in referrals:
                    # Add the current user to the referrer's referrals
                    referrals.append(user_id)
                    upsert_user(referrer_id, referrals=referrals)

                    # Reward the referrer (e.g., advance position or add fees)
                    fees_earned = referrer_data.get("fees_earned", 0.0) + 1.0
                    upsert_user(referrer_id, fees_earned=fees_earned)

                    await update.message.reply_text(
                        f"Vous avez été référé par {referrer_data.get('email', 'un utilisateur inconnu')} !"
                    )
                    return

    await update.message.reply_text("Lien de parrainage invalide ou déjà utilisé.")


# Command to check the user's position and earnings
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    # application = Application.builder().token("7609416122:AAHVlEMtwBGbVrQBffz7UNNw630EiAnoxug").build()
                                               
    # Handler for the /start command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))  # Regex pour l'email
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))
    application.add_handler(CommandHandler("status", my_status))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CallbackQueryHandler(button_handler))  # Gère les callbacks


    # Handlers for the interactions
    application.add_handler(CallbackQueryHandler(callback_handler))  # Gère tous les callbacks

    # Launch the bot
    print("Le bot Whalesx_tracker fonctionne avec menu interactif et analyse automatique du token...")
    application.run_polling()

if __name__ == "__main__":
    main()
