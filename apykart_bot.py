#!/usr/bin/env python3
"""
Apykart Telegram Bot — Secure Production Version
Render Deploy Ready | No Hardcoded Secrets
"""

import os
import sys
import json
import logging
import traceback
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================
# DEBUG: Catch all errors (Logs mein dikhega)
# ============================================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("=" * 50)
    print("UNHANDLED EXCEPTION:")
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("=" * 50)

sys.excepthook = global_exception_handler

# ============================================
# LOGGING SETUP
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION — Environment Variables Se
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set")
    sys.exit(1)

ALLOWED_USER_IDS_STR = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = []
if ALLOWED_USER_IDS_STR:
    try:
        ALLOWED_USER_IDS = [int(x.strip()) for x in ALLOWED_USER_IDS_STR.split(",") if x.strip()]
    except ValueError:
        logger.error(f"Invalid ALLOWED_USER_IDS format: {ALLOWED_USER_IDS_STR}")
        sys.exit(1)

FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "apykart-firebase-key.json")

logger.info(f"Authorized users: {ALLOWED_USER_IDS}")
logger.info(f"Firebase key path: {FIREBASE_KEY_PATH}")

# ============================================
# FIREBASE SETUP
# ============================================
try:
    # Check if file exists
    if not os.path.exists(FIREBASE_KEY_PATH):
        logger.error(f"Firebase key file not found at: {FIREBASE_KEY_PATH}")
        # List current directory files for debugging
        logger.info(f"Current directory files: {os.listdir('.')}")
        sys.exit(1)
    
    with open(FIREBASE_KEY_PATH, 'r') as f:
        firebase_config = json.load(f)
        logger.info(f"Firebase config loaded: project_id={firebase_config.get('project_id')}")
    
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization failed: {str(e)}")
    sys.exit(1)

# ============================================
# AUTHORIZATION
# ============================================
async def is_authorized(update: Update):
    user_id = update.effective_user.id
    if not ALLOWED_USER_IDS or user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ Unauthorized access.")
        return False
    return True

# ============================================
# DASHBOARD STATS
# ============================================
async def get_dashboard_stats():
    try:
        orders = list(db.collection('orders').stream())
        total_orders = len(orders)
        
        total_revenue = 0
        pending_orders = 0
        for order in orders:
            data = order.to_dict()
            total_revenue += data.get('total', 0)
            if data.get('status') == 'pending':
                pending_orders += 1
        
        products = list(db.collection('products').stream())
        users = list(db.collection('users').stream())
        sellers = list(db.collection('sellers').stream())
        
        return (
            f"🏪 *APYKART DASHBOARD*\n\n"
            f"📦 Orders: `{total_orders}`\n"
            f"💰 Revenue: `₹{total_revenue:,.0f}`\n"
            f"🛍️ Products: `{len(products)}`\n"
            f"👥 Users: `{len(users)}`\n"
            f"🏪 Sellers: `{len(sellers)}`\n"
        )
    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")
        return f"❌ Error: {str(e)}"

async def get_recent_orders(limit=5):
    try:
        orders = db.collection('orders').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit).stream()
        orders_list = list(orders)
        if not orders_list:
            return "📦 No orders found."
        
        message = "📋 *Recent Orders*\n\n"
        for order in orders_list:
            data = order.to_dict()
            order_id = order.id[:8]
            customer = data.get('customerName', 'Guest')
            total = data.get('total', 0)
            status = data.get('status', 'pending')
            message += f"🆔 `{order_id}` | {customer} | ₹{total} | {status}\n"
        return message
    except Exception as e:
        logger.error(f"Recent orders error: {str(e)}")
        return f"❌ Error: {str(e)}"

async def update_order_status(order_id, new_status):
    valid_statuses = ['placed', 'confirmed', 'shipped', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        return f"❌ Invalid. Valid: {', '.join(valid_statuses)}"
    try:
        doc_ref = db.collection('orders').document(order_id)
        if not doc_ref.get().exists:
            return f"❌ Order `{order_id}` not found."
        doc_ref.update({'status': new_status, 'updatedAt': datetime.now()})
        return f"✅ Order `{order_id}` updated to *{new_status}*"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def add_product(name, price):
    try:
        data = {
            'name': name,
            'price': float(price),
            'status': 'active',
            'approvalStatus': 'approved',
            'stock': 100,
            'createdAt': datetime.now()
        }
        doc = db.collection('products').add(data)
        return f"✅ Product *{name}* added at ₹{price}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# COMMAND HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data='stats'),
         InlineKeyboardButton("📦 Orders", callback_data='orders')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    await update.message.reply_text(
        "🤖 *Apykart Admin Bot*\n\n"
        "/stats - Dashboard\n"
        "/orders - Recent orders\n"
        "/update ID status - Update order\n"
        "/add Name Price - Add product\n"
        "/help - Commands",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text(
        "*Commands:*\n"
        "/stats - Dashboard\n"
        "/orders - Recent orders\n"
        "/update ORDER_ID status - Update order\n"
        "/add Name Price - Add product\n"
        "/start - Main menu",
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("📊 Fetching...")
    msg = await get_dashboard_stats()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("📦 Fetching orders...")
    msg = await get_recent_orders()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/update ORDER_ID status`", parse_mode='Markdown')
        return
    msg = await update_order_status(context.args[0], context.args[1])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/add Name Price`", parse_mode='Markdown')
        return
    price = context.args[-1]
    name = ' '.join(context.args[:-1])
    await update.message.reply_text(f"➕ Adding *{name}*...", parse_mode='Markdown')
    msg = await add_product(name, price)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'stats':
        msg = await get_dashboard_stats()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'orders':
        msg = await get_recent_orders()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'help':
        await query.edit_message_text(
            "/stats - Dashboard\n/orders - Orders\n/update ID status - Update order\n/add Name Price - Add product",
            parse_mode='Markdown'
        )

# ============================================
# MAIN
# ============================================
def main():
    logger.info("Starting Apykart Admin Bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Bot is polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
