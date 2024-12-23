# bot.py (English version, single callback handler)

from dotenv import load_dotenv
import os
import socket
import certifi
import time

from telegram import ( Update, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes)
from telegram.helpers import escape_markdown

# == Import your Dragon modules ==
from Dragon.bundle import check_bundle
from Dragon.bulkWallet import get_bulk_wallet_stats
from Dragon.holders import get_top_holders
from Dragon.traders import get_top_traders

# == MongoDB ==
from pymongo import MongoClient

# ========== Load environment variables ==========
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

# ========== Database user helpers ==========
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


# ========== Command handlers ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start : Greet user and request email if needed.
    """
    user_id = update.effective_user.id

    # Register user if needed
    if not is_user_registered(user_id):
        upsert_user(user_id)

    # Show greeting
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


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Register the user's email.
    """
    user_id = update.effective_user.id
    email = update.message.text.strip()

    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Please /start first.")
        return

    # Minimal email check
    if "@" in email:
        position = count_whitelist_users()
        upsert_user(user_id, email=email, position=position)

        referral_link = escape_markdown(f"https://t.me/WhalesX_Tracker_bot?start={user_id}")
        email_escaped = escape_markdown(email)

        await update.message.reply_text(
            f"✅ Your email `{email_escaped}` has been registered!\n"
            f"📋 You are at position #{position} in the whitelist.\n"
            f"🔗 Invite friends with this link: {referral_link}",
            parse_mode="Markdown"
        )

        # Prompt to analyze a token
        keyboard = [[InlineKeyboardButton("🚀 Start analysis", callback_data="start_analysis")]]
        await update.message.reply_text(
            "✅ Registration complete!\nClick *Start analysis* to enter a token address.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("❌ Please provide a valid email.", parse_mode="Markdown")


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


# ========== Receiving a token address (text) ==========

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


# ========== Send menu ==========

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
    if update.message:
        # If the update is a regular message
        await update.message.reply_text(
            "❓ *What would you like to do next?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif update.callback_query:
        # If the update is a callback query
        await update.callback_query.message.reply_text(
            "❓ *What would you like to do next?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ========== Single callback handler ==========

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all callback queries: start_analysis, bulkwallet, topholders, toptraders.
    """
    query = update.callback_query
    await query.answer()
    action = query.data

    chat_id = update.effective_chat.id
    token_address = LAST_ANALYZED_TOKEN.get(chat_id, None)

    # If user clicks "start_analysis"
    if action == "start_analysis":
        # Mark user as ready to analyze
        context.user_data["ready_for_analysis"] = True
        await query.edit_message_text(
            "📝 *Please enter the token address (contract) you want to analyze:*",
            parse_mode="Markdown"
        )
        return

    # If no token analyzed yet
    if not token_address:
        await query.edit_message_text(
            "❌ No recent token analyzed. Please enter a token address first.",
            parse_mode="Markdown"
        )
        return

    # Handle other actions
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
            result_text = get_bulk_wallet_stats(wallets, token_address=token_address)
            await update.effective_chat.send_message(result_text, parse_mode="Markdown")
        except Exception as e:
            await update.effective_chat.send_message(
                f"❌ *Bulk Wallet Error:* {escape_markdown(str(e))}",
                parse_mode="Markdown"
            )
        await send_menu(update)

    elif action == "topholders":
        await query.edit_message_text("🏆 *Top Holders*: loading...", parse_mode="Markdown")
        holders = context.user_data.get("top_holders", [])
        if not holders:
            await update.effective_chat.send_message("❌ No top holders data found.", parse_mode="Markdown")
            return
        else:          
            holders_text = "🏆 *Top Holders Analysis*:\n\n"
            for i, holder in enumerate(holders, start=1):
                wallet = escape_markdown(holder.get('wallet', 'N/A'))
                amount = holder.get('amount', 0.0)
                percentage = holder.get('percentage', 0.0)
                holders_text += (
                    f"{i}️⃣ Wallet: `{wallet}`\n"
                    f"   💰 Amount: {amount:.4f} Spl\n"
                    f"   🎯 Owned %: {percentage:.2f}%\n\n"
                )
            await update.effective_chat.send_message(holders_text, parse_mode="Markdown")
            
        await send_menu(update)

    elif action == "toptraders":
        await query.edit_message_text("📈 *Top Traders*: loading...", parse_mode="Markdown")
        traders = context.user_data.get("top_traders", [])
        if not traders:
            await update.effective_chat.send_message("❌ No top traders data found.", parse_mode="Markdown")
        else : 
            traders_text = "📈 *Top Traders Analysis*:\n\n"
            for i, trader in enumerate(traders, start=1):
                wallet = escape_markdown(trader.get('wallet', 'N/A'))
                realized_profit = trader.get('realized_profit', 0.0)
                unrealized_profit = trader.get('unrealized_profit', 0.0)
                total_profit = trader.get('total_profit', 0.0)
                traders_text += (
                    f"{i}️⃣ Wallet: `{wallet}`\n"
                    f"   💰 Realized Profit: {realized_profit:.2f} USD\n"
                    f"   🔄 Unrealized Profit: {unrealized_profit:.2f} USD\n"
                    f"   📊 Total PnL: {total_profit:.2f} USD\n\n"
                )
            await update.effective_chat.send_message(traders_text, parse_mode="Markdown")
            
        await send_menu(update)


# ========== Main entry point ==========

def main():
    """
    Launch the bot in polling mode.
    """
    # Replace with your real bot token
    # bot_token = "7609416122:AAHVlEMtwBGbVrQBffz7UNNw630EiAnoxug"
    bot_token = "8171737440:AAGTb434bzrTSakyREYxgmyuxEG-N5aNb7c"
    
    application = Application.builder().token(bot_token).build()
    print("WhalesX_Tracker bot running with a single callback handler...")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", my_status))
    application.add_handler(CommandHandler("referral", referral))

    # Register email via a simple regex
    application.add_handler(MessageHandler(filters.Regex(r".+@.+\..+"), register_email))

    # If user sends a text not recognized as command, assume it's a token address
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token))

    # Single callback handler for all query.data
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Start polling
    application.run_polling()

if __name__ == "__main__":
    main()
