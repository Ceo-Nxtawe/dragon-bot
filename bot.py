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


# ========== DNS Test (optional) & Mongo connection helpers ==========
def test_dns_resolution(hostname="mongodb.railway.internal"):
    print("\n### DNS Resolution Test ###")
    try:
        resolved_ip = socket.gethostbyname(hostname)
        print(f"DNS resolved successfully: {hostname} -> {resolved_ip}")
    except Exception as e:
        print(f"DNS resolution error: {e}")

def get_mongo_client(mongo_uri: str) -> MongoClient:
    if "railway.internal" in mongo_uri:
        print("Connecting with TLS disabled (Railway internal host)...")
        return MongoClient(mongo_uri, tls=False)
    else:
        print("Connecting with TLS enabled (non-Railway host)...")
        return MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())

# ========== Connect to MongoDB ==========
try:
    if MONGO_URI and "railway.internal" in MONGO_URI:
        test_dns_resolution("mongodb.railway.internal")

    client = get_mongo_client(MONGO_URI)
    print(client.server_info())  # Check connection
    print("Successfully connected to MongoDB")
except Exception as e:
    print(f"MongoDB connection error: {e}")

# Choose your database & collection
db = client.WhalesX  
users_collection = db.botUsers

try:
    users_collection.create_index("user_id", unique=True)
except Exception as e:
    print(f"Index creation error: {e}")

# ========== Global state ==========
LAST_ANALYZED_TOKEN = {}  # Remember the last token per chat

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
    """
    /start : Greet user and request email if needed.
    """
    user_id = update.effective_user.id

    keyboard = [[InlineKeyboardButton("🚀 Démarrer l'analyse", callback_data="start_analysis")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not is_user_registered(user_id):
        # Add the user to the database
        upsert_user(user_id)

    await update.message.reply_text(
        "🐋 *Welcome to WhalesX_Tracker!*\n\n",
        parse_mode="Markdown"
    )
    
    # If user already has an email, show analysis button
    user_data = get_user(user_id)
    if user_data and user_data.get("email"):
        keyboard = [[InlineKeyboardButton("🚀 Start analysis", callback_data="start_analysis")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click *Start analysis* to enter a token address.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        # Otherwise, request email
        await update.message.reply_text(
            "✉️ *Please provide your email address to join the whitelist.*",
            parse_mode="Markdown"
        )


# Function to register the email and complete the registration
async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Register the user's email.
    """
    user_id = update.effective_user.id
    email = update.message.text.strip()

    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Please /start first.")
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
        keyboard = [[InlineKeyboardButton("🚀 Start analysis", callback_data="start_analysis")]]
        await update.message.reply_text(
            "✅ Registration complete!\nClick *Start analysis* to enter a token address.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
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
    """
    Display the interactive menu (Bulk Wallet, Top Holders, etc.).
    """
    keyboard = [
        [InlineKeyboardButton("📊 Bulk Wallet", callback_data="bulkwallet")],
        [InlineKeyboardButton("🏆 Top Holders", callback_data="topholders")],
        [InlineKeyboardButton("📈 Top Traders", callback_data="toptraders")],
        [InlineKeyboardButton("🚀 Analyze another token", callback_data="start_analysis")]
    ]
    await update.message.reply_text(
        "❓ *What would you like to do next?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Reception and analysis of the token
async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    When user sends a token address, do bundle analysis + pre-fetch holders/traders in the background.
    """
    # Only proceed if user clicked "Start Analysis" first
    if not context.user_data.get("ready_for_analysis"):
        return

    user_input = update.message.text.strip()
    if not user_input:
        await update.message.reply_text("❌ *No valid token address provided.*", parse_mode="Markdown")
        return

    chat_id = update.effective_chat.id
    LAST_ANALYZED_TOKEN[chat_id] = user_input

    # 1) Bundle analysis
    await update.message.reply_text(
        f"🔍 *Analyzing token:* `{escape_markdown(user_input)}`",
        parse_mode="Markdown"
    )
    try:
        bundles = check_bundle(user_input)
        if not bundles:
            await update.message.reply_text("❌ No bundle found for this contract.", parse_mode="Markdown")
        else:
            response_text = "✅ *Bundle Analysis Results*:\n\n"
            for i, (tx_hash, quote_amount) in enumerate(bundles, start=1):
                tx_hash = escape_markdown(tx_hash or "N/A")
                quote_amount = quote_amount or 0.0
                response_text += f"{i}️⃣ Transaction: `{tx_hash}`\n   Amount: {quote_amount:.4f} SOL\n\n"
            response_text += f"📊 *Total Transactions Analyzed*: {len(bundles)}"
            await update.message.reply_text(response_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error (bundle):* {escape_markdown(str(e))}",
            parse_mode="Markdown"
        )

    # 2) Pre-fetch top holders/traders silently
    try:
        holders = get_top_holders(user_input)
        traders = get_top_traders(user_input)
        context.user_data["top_holders"] = holders
        context.user_data["top_traders"] = traders
    except Exception as e:
        context.user_data["top_holders"] = []
        context.user_data["top_traders"] = []
        print(f"[Warn] Could not fetch holders/traders: {e}")

    # 3) Show final menu
    await send_menu(update)

# Callback to handle automatic analysis with the current token
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all callback queries: start_analysis, bulkwallet, topholders, toptraders.
    """
    query = update.callback_query
    await query.answer()
    action = query.data

    # Get the last analyzed token
    chat_id = update.effective_chat.id
    token_address = LAST_ANALYZED_TOKEN.get(chat_id)
    
    if action == "start_analysis":
        # Mark user as ready to analyze
        context.user_data["ready_for_analysis"] = True
        await query.edit_message_text(
            "📝 *Please enter the token address (contract) you want to analyze:*",
            parse_mode="Markdown"
        )
        return
    
    if not token_address:
        await query.edit_message_text(
            "❌ Aucun token analysé récemment. Veuillez entrer une adresse pour commencer l'analyse.",
            parse_mode="Markdown"
        )
        return

    if action == "bulkwallet":
        await query.edit_message_text("💼 *Bulk Wallet*: analyzing wallets...", parse_mode="Markdown")

        try:
            holders = context.user_data.get("top_holders", [])
            traders = context.user_data.get("top_traders", [])
            wallets = list(set(
                [h.get('wallet', 'N/A') for h in holders] +
                [t.get('wallet', 'N/A') for t in traders]
            ))

            await query.edit_message_text(
                "📊 Wallet analysis has started. This may take some time depending on the number of wallets to analyse. Please wait...",
                parse_mode="Markdown"
            )
            bulk_stats = get_bulk_wallet_stats(wallets, token_address=token_address)
            await update.effective_chat.send_message(bulk_stats, parse_mode="Markdown")

        except Exception as e:
            await update.effective_chat.send_message(
                f"❌ *Bulk Wallet Error:* {escape_markdown(str(e))}",
                parse_mode="Markdown"
            )

    elif action == "topholders":
        await query.edit_message_text("🏆 *Top Holders*: loading...", parse_mode="Markdown")
        holders = context.user_data.get("top_holders", [])
        if not holders:
            await update.effective_chat.send_message("❌ No top holders data found.", parse_mode="Markdown")
            return

        holders_text = "🏆 *Top Holders Analysis*:\n\n"
        for idx, holder in enumerate(holders, start=1):
            wallet = escape_markdown(holder.get('wallet', 'N/A'))
            amount = holder.get('amount', 0)
            percentage = holder.get('percentage', 0)
            
            holders_text += (
                f"{idx}️⃣ Wallet: `{wallet}`\n"
                f"   💰 Amount: {amount:.4f} Spl\n"
                f"   🎯 Owned %: {percentage:.2f}%\n\n"
            )
        await update.effective_chat.send_message(holders_text, parse_mode="Markdown")

    elif action == "toptraders":
        await query.edit_message_text("📈 *Top Traders*: loading...", parse_mode="Markdown")
        traders = context.user_data.get("top_traders", [])
        if not traders:
            await update.effective_chat.send_message("❌ No top traders data found.", parse_mode="Markdown")
            return
        
        traders_text = "📈 *Top Traders Analysis*:\n\n"
        for idx, trader in enumerate(traders, start=1):            
            wallet = escape_markdown(trader.get('wallet', 'N/A'))
            realized_profit = trader.get('realized_profit', 0) or 0.0
            unrealized_profit = trader.get('unrealized_profit', 0) or 0.0
            total_profit = trader.get('total_profit', 0) or 0.0
            
            traders_text += (
                f"{idx}️⃣ Wallet: [`{wallet}`]\n"
                f"   💰 Realized Profit: {realized_profit:.2f} USD\n"
                f"   🔄 Unrealized Profit: {unrealized_profit:.2f} USD\n"
                f"   📊 Total PnL (unrealized + realized): {total_profit:.2f} USD\n\n"
            )
        await update.effective_chat.send_message(traders_text, parse_mode="Markdown")


# Command to handle referral links
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /referral: e.g. /referral 12345
    """
    user_id = update.effective_user.id
    args = context.args
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id != user_id:
            referrer_data = get_user(referrer_id)
            if referrer_data:
                user_data = get_user(user_id)
                if user_data:
                    referrals = referrer_data.get("referrals", [])
                    if user_id not in referrals:
                        referrals.append(user_id)
                        upsert_user(referrer_id, referrals=referrals)
                        fees_earned = referrer_data.get("fees_earned", 0.0) + 1.0
                        upsert_user(referrer_id, fees_earned=fees_earned)
                        await update.message.reply_text(
                            f"You have been referred by {referrer_data.get('email', 'Unknown user')}!"
                        )
                        return
    await update.message.reply_text("Invalid or already-used referral link.")
    
# Command to check the user's position and earnings
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status: Show whitelist position, referrals, fees, etc.
    """
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if user_data:
        position = user_data.get("position", "Unranked")
        referrals = len(user_data.get("referrals", []))
        fees = user_data.get("fees_earned", 0.0)

        await update.message.reply_text(
            f"Whitelist position: #{position}\n"
            f"Number of referrals: {referrals}\n"
            f"Accumulated fees: {fees}"
        )
    else:
        await update.message.reply_text("Please /start first.")


def main():
    bot_token = "7609416122:AAHVlEMtwBGbVrQBffz7UNNw630EiAnoxug"
    # bot_token = "8171737440:AAGTb434bzrTSakyREYxgmyuxEG-N5aNb7"
    application = Application.builder().token(bot_token).build()
                                              
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
