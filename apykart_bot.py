#!/usr/bin/env python3
"""
Apykart Telegram Bot — Complete Admin Control
Version 4.0 | Secure với Environment Variables
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================
# CONFIGURATION — Environment Variables Se
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set")

ALLOWED_USER_IDS_str = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = [int(x.strip()) for x in ALLOWED_USER_IDS_str.split(",") if x.strip()]

FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "apykart-firebase-key.json")

# Optional APIs
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ============================================
# FIREBASE SETUP
# ============================================
cred = credentials.Certificate(FIREBASE_KEY_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

logging.basicConfig(level=logging.INFO)

# ============================================
# AUTHORIZATION
# ============================================

async def is_authorized(update: Update):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ Unauthorized access. This bot is for personal use only.")
        return False
    return True

# ============================================
# DASHBOARD STATS FUNCTIONS
# ============================================

async def get_dashboard_stats():
    """Complete dashboard data"""
    try:
        orders = db.collection('orders').get()
        total_orders = len(orders)
        
        total_revenue = 0
        pending_orders = 0
        delivered_orders = 0
        for order in orders:
            data = order.to_dict()
            total_revenue += data.get('total', 0)
            status = data.get('status', '')
            if status == 'pending':
                pending_orders += 1
            elif status == 'delivered':
                delivered_orders += 1
        
        products = db.collection('products').get()
        total_products = len(products)
        active_products = sum(1 for p in products if p.to_dict().get('status') == 'active')
        
        users = db.collection('users').get()
        total_users = len(users)
        banned_users = sum(1 for u in users if u.to_dict().get('banned'))
        
        sellers = db.collection('sellers').get()
        total_sellers = len(sellers)
        verified_sellers = sum(1 for s in sellers if s.to_dict().get('status') == 'active')
        
        videos = db.collection('videos').where('status', '==', 'pending').get()
        pending_videos = len(videos)
        
        withdrawals = db.collection('withdrawals').where('status', '==', 'pending').get()
        pending_withdrawals = len(withdrawals)
        
        today = datetime.now().date()
        today_orders = 0
        for order in orders:
            created = order.to_dict().get('createdAt')
            if created and isinstance(created, datetime) and created.date() == today:
                today_orders += 1
        
        message = (
            f"🏪 *APYKART ADMIN DASHBOARD*\n\n"
            f"📦 *Orders:* `{total_orders}`\n"
            f"   ├ Pending: `{pending_orders}`\n"
            f"   ├ Delivered: `{delivered_orders}`\n"
            f"   └ Today: `{today_orders}`\n\n"
            f"💰 *Revenue:* `₹{total_revenue:,.0f}`\n\n"
            f"🛍️ *Products:* `{total_products}`\n"
            f"   ├ Active: `{active_products}`\n"
            f"   └ Inactive: `{total_products - active_products}`\n\n"
            f"👥 *Users:* `{total_users}`\n"
            f"   ├ Banned: `{banned_users}`\n"
            f"   └ Active: `{total_users - banned_users}`\n\n"
            f"🏪 *Sellers:* `{total_sellers}`\n"
            f"   ├ Verified: `{verified_sellers}`\n"
            f"   └ Pending: `{total_sellers - verified_sellers}`\n\n"
            f"📹 *Pending Videos:* `{pending_videos}`\n"
            f"💸 *Pending Withdrawals:* `{pending_withdrawals}`"
        )
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def get_recent_orders(limit=10):
    try:
        orders = db.collection('orders').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit).get()
        if not orders:
            return "📦 No orders found."
        
        message = "📋 *RECENT ORDERS*\n\n"
        for order in orders:
            data = order.to_dict()
            order_id = order.id[:12]
            customer = data.get('customerName', 'Guest')
            total = data.get('total', 0)
            status = data.get('status', 'pending')
            payment = data.get('payment', 'COD')
            
            status_emoji = {'placed': '🟡', 'confirmed': '🔵', 'shipped': '🚚',
                           'delivered': '✅', 'cancelled': '❌', 'returned': '↩️'}.get(status, '⚪')
            
            message += f"{status_emoji} *{order_id}*\n"
            message += f"   👤 {customer}\n"
            message += f"   💰 ₹{total} | 💳 {payment}\n"
            message += f"   📌 {status}\n\n"
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def get_order_details(order_id):
    try:
        doc_ref = db.collection('orders').document(order_id)
        doc = doc_ref.get()
        if not doc.exists:
            return f"❌ Order `{order_id}` not found."
        
        data = doc.to_dict()
        items_text = ""
        for item in data.get('items', []):
            items_text += f"   • {item.get('name', 'Item')} x{item.get('quantity', 1)} = ₹{item.get('price', 0)}\n"
        
        return (
            f"📦 *ORDER DETAILS*\n🆔 `{order_id}`\n\n"
            f"👤 *Customer:* {data.get('customerName', 'N/A')}\n"
            f"📞 *Phone:* {data.get('customerPhone', 'N/A')}\n"
            f"📍 *Address:* {data.get('address', 'N/A')}\n\n"
            f"🛍️ *Items:*\n{items_text}\n"
            f"💰 *Total:* ₹{data.get('total', 0)}\n"
            f"💳 *Payment:* {data.get('payment', 'COD')}\n"
            f"📌 *Status:* {data.get('status', 'pending')}"
        )
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def update_order_status(order_id, new_status):
    valid_statuses = ['placed', 'confirmed', 'shipped', 'delivered', 'cancelled', 'returned', 'refunded']
    if new_status not in valid_statuses:
        return f"❌ Invalid status. Valid: {', '.join(valid_statuses)}"
    
    try:
        doc_ref = db.collection('orders').document(order_id)
        if not doc_ref.get().exists:
            return f"❌ Order `{order_id}` not found."
        
        doc_ref.update({'status': new_status, 'updatedAt': datetime.now()})
        return f"✅ Order `{order_id}` updated to *{new_status}*"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def get_products(limit=20):
    try:
        products = db.collection('products').limit(limit).get()
        if not products:
            return "🛍️ No products found."
        
        message = "🛍️ *PRODUCTS*\n\n"
        for product in products:
            data = product.to_dict()
            name = data.get('name', 'Unknown')[:25]
            price = data.get('price', 0)
            status = data.get('status', 'inactive')
            stock = data.get('stock', 0)
            
            status_icon = '✅' if status == 'active' else '❌'
            stock_icon = '📦' if stock > 0 else '⚠️'
            
            message += f"{status_icon} `{product.id[:8]}` *{name}*\n"
            message += f"   💰 ₹{price} | {stock_icon} Stock: {stock}\n\n"
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def add_product(name, price, category="General", stock=100):
    try:
        product_data = {
            'name': name, 'price': float(price), 'category': category,
            'status': 'active', 'approvalStatus': 'approved', 'stock': stock,
            'createdAt': datetime.now(), 'images': [], 'description': f"{name} - ₹{price}"
        }
        doc_ref = db.collection('products').add(product_data)
        return f"✅ Product *{name}* added at ₹{price}\n🆔 `{doc_ref[1].id}`"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# COMMAND HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data='stats'),
         InlineKeyboardButton("📦 Orders", callback_data='orders')],
        [InlineKeyboardButton("🛍️ Products", callback_data='products'),
         InlineKeyboardButton("👥 Users", callback_data='users')],
        [InlineKeyboardButton("🏪 Sellers", callback_data='sellers'),
         InlineKeyboardButton("💰 Revenue", callback_data='revenue')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *APYKART ADMIN BOT* 🔥\n\n"
        "*Commands:*\n"
        "📊 `/stats` - Dashboard\n"
        "📦 `/orders` - Orders\n"
        "🛍️ `/products` - Products\n"
        "➕ `/add Name Price` - Add product\n"
        "🔄 `/update ORDER_ID status` - Update order\n"
        "❓ `/help` - All commands",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("📊 Fetching dashboard...")
    msg = await get_dashboard_stats()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("📦 Fetching orders...")
    msg = await get_recent_orders()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("🛍️ Fetching products...")
    msg = await get_products()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/add Name Price`\nExample: `/add Hoodie 1299`", parse_mode='Markdown')
        return
    price = context.args[-1]
    name = ' '.join(context.args[:-1])
    await update.message.reply_text(f"➕ Adding *{name}*...", parse_mode='Markdown')
    msg = await add_product(name, price)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/update ORDER_ID status`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"🔄 Updating order `{context.args[0]}`...", parse_mode='Markdown')
    msg = await update_order_status(context.args[0], context.args[1])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text(
        "📋 *COMMANDS*\n\n"
        "/stats - Dashboard\n"
        "/orders - Orders\n"
        "/products - Products\n"
        "/add Name Price - Add product\n"
        "/update ID status - Update order\n"
        "/start - Main menu",
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'stats':
        msg = await get_dashboard_stats()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'orders':
        msg = await get_recent_orders()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'products':
        msg = await get_products()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'help':
        await query.edit_message_text(
            "📋 /stats - Dashboard\n/orders - Orders\n/products - Products\n/add Name Price - Add product\n/update ID status - Update order",
            parse_mode='Markdown'
        )

def main():
    print("🤖 Apykart Admin Bot Starting...")
    print(f"🔥 Authorized users: {ALLOWED_USER_IDS}")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("products", products_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
