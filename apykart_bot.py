#!/usr/bin/env python3
"""
Apykart Telegram Bot — Complete Admin Control
Version 3.0 | All Features Working
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================
# CONFIGURATION (Apni details yahan daal)
# ============================================

TELEGRAM_TOKEN = "8309129292:AAGvtBFAKk2mbuMjjlrotLYiVKb9fUuaEZ0"  # BotFather se mila
ALLOWED_USER_IDS = [8660621615]  # @userinfobot se apna ID daal
FIREBASE_KEY_PATH = "apykart916-firebase-key.json"

# Optional: AI APIs (Agar hai toh daal, nahi toh chhod de)
OLLAMA_URL = "http://localhost:11434/api/generate"
CLAUDE_API_KEY = ""  # Agar hai toh daal
GROQ_API_KEY = ""  # Agar hai toh daal

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
        # Orders
        orders = db.collection('orders').get()
        total_orders = len(orders)
        
        # Revenue calculation
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
        
        # Products
        products = db.collection('products').get()
        total_products = len(products)
        active_products = 0
        for product in products:
            if product.to_dict().get('status') == 'active':
                active_products += 1
        
        # Users
        users = db.collection('users').get()
        total_users = len(users)
        banned_users = 0
        for user in users:
            if user.to_dict().get('banned'):
                banned_users += 1
        
        # Sellers
        sellers = db.collection('sellers').get()
        total_sellers = len(sellers)
        verified_sellers = 0
        for seller in sellers:
            if seller.to_dict().get('status') == 'active':
                verified_sellers += 1
        
        # Pending videos
        videos = db.collection('videos').where('status', '==', 'pending').get()
        pending_videos = len(videos)
        
        # Pending withdrawals
        withdrawals = db.collection('withdrawals').where('status', '==', 'pending').get()
        pending_withdrawals = len(withdrawals)
        
        # Today's orders
        today = datetime.now().date()
        today_orders = 0
        for order in orders:
            created = order.to_dict().get('createdAt')
            if created:
                if isinstance(created, datetime) and created.date() == today:
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
            f"💸 *Pending Withdrawals:* `{pending_withdrawals}`\n"
        )
        return message
    except Exception as e:
        return f"❌ Error fetching stats: {str(e)}"

async def get_recent_orders(limit=10):
    """Get recent orders with details"""
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
            
            status_emoji = {
                'placed': '🟡', 'confirmed': '🔵', 'shipped': '🚚',
                'delivered': '✅', 'cancelled': '❌', 'returned': '↩️'
            }.get(status, '⚪')
            
            message += f"{status_emoji} *{order_id}*\n"
            message += f"   👤 {customer}\n"
            message += f"   💰 ₹{total} | 💳 {payment}\n"
            message += f"   📌 {status}\n\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def get_order_details(order_id):
    """Get full order details"""
    try:
        doc_ref = db.collection('orders').document(order_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Order `{order_id}` not found."
        
        data = doc.to_dict()
        
        # Items list
        items_text = ""
        for item in data.get('items', []):
            items_text += f"   • {item.get('name', 'Item')} x{item.get('quantity', 1)} = ₹{item.get('price', 0)}\n"
        
        message = (
            f"📦 *ORDER DETAILS*\n"
            f"🆔 `{order_id}`\n\n"
            f"👤 *Customer:* {data.get('customerName', 'N/A')}\n"
            f"📞 *Phone:* {data.get('customerPhone', 'N/A')}\n"
            f"📍 *Address:* {data.get('address', 'N/A')}\n\n"
            f"🛍️ *Items:*\n{items_text}\n"
            f"💰 *Total:* ₹{data.get('total', 0)}\n"
            f"💳 *Payment:* {data.get('payment', 'COD')}\n"
            f"📌 *Status:* {data.get('status', 'pending')}\n"
            f"📅 *Date:* {data.get('createdAt', datetime.now())}\n"
        )
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def update_order_status(order_id, new_status):
    """Update order status"""
    valid_statuses = ['placed', 'confirmed', 'shipped', 'delivered', 'cancelled', 'returned', 'refunded']
    if new_status not in valid_statuses:
        return f"❌ Invalid status. Valid: {', '.join(valid_statuses)}"
    
    try:
        doc_ref = db.collection('orders').document(order_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Order `{order_id}` not found."
        
        doc_ref.update({'status': new_status, 'updatedAt': datetime.now()})
        return f"✅ Order `{order_id}` updated to *{new_status}*"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# PRODUCTS FUNCTIONS
# ============================================

async def get_products(limit=20):
    """Get product list"""
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
    """Add new product"""
    try:
        product_data = {
            'name': name,
            'price': float(price),
            'category': category,
            'status': 'active',
            'approvalStatus': 'approved',
            'stock': stock,
            'createdAt': datetime.now(),
            'images': [],
            'description': f"{name} - ₹{price}"
        }
        
        doc_ref = db.collection('products').add(product_data)
        return f"✅ Product *{name}* added at ₹{price}\n🆔 `{doc_ref[1].id}`"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def delete_product(product_id):
    """Delete product"""
    try:
        doc_ref = db.collection('products').document(product_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Product `{product_id}` not found."
        
        name = doc.to_dict().get('name', 'Unknown')
        doc_ref.delete()
        return f"✅ Product *{name}* deleted."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# USERS FUNCTIONS
# ============================================

async def get_users(limit=15):
    """Get user list"""
    try:
        users = db.collection('users').limit(limit).get()
        
        if not users:
            return "👥 No users found."
        
        message = "👥 *USERS*\n\n"
        for user in users:
            data = user.to_dict()
            name = data.get('name', 'Unknown')[:20]
            email = data.get('email', 'No email')[:25]
            phone = data.get('phone', 'No phone')
            coins = data.get('coins', 0)
            banned = data.get('banned', False)
            
            status_icon = '🚫' if banned else '✅'
            
            message += f"{status_icon} `{user.id[:8]}` *{name}*\n"
            message += f"   📧 {email}\n"
            message += f"   📞 {phone} | 🪙 {coins}\n\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def ban_user(user_id):
    """Ban/unban user"""
    try:
        doc_ref = db.collection('users').document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ User `{user_id}` not found."
        
        current = doc.to_dict().get('banned', False)
        new_status = not current
        doc_ref.update({'banned': new_status, 'updatedAt': datetime.now()})
        
        action = "banned" if new_status else "unbanned"
        return f"✅ User `{user_id}` {action}."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# SELLERS FUNCTIONS
# ============================================

async def get_sellers():
    """Get seller list"""
    try:
        sellers = db.collection('sellers').limit(15).get()
        
        if not sellers:
            return "🏪 No sellers found."
        
        message = "🏪 *SELLERS*\n\n"
        for seller in sellers:
            data = seller.to_dict()
            name = data.get('shopName', data.get('name', 'Unknown'))[:25]
            email = data.get('email', 'No email')
            status = data.get('status', 'pending')
            revenue = data.get('totalRevenue', 0)
            
            status_icon = {'active': '✅', 'pending': '🟡', 'rejected': '❌'}.get(status, '⚪')
            message += f"{status_icon} `{seller.id[:8]}` *{name}*\n"
            message += f"   📧 {email} | 💰 ₹{revenue}\n"
            message += f"   📌 Status: {status}\n\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def verify_seller(seller_id):
    """Approve seller KYC"""
    try:
        doc_ref = db.collection('sellers').document(seller_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Seller `{seller_id}` not found."
        
        doc_ref.update({
            'status': 'active',
            'verification.status': 'approved',
            'verifiedAt': datetime.now()
        })
        return f"✅ Seller `{seller_id}` verified and activated."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# WITHDRAWALS FUNCTIONS
# ============================================

async def get_withdrawals():
    """Get pending withdrawals"""
    try:
        withdrawals = db.collection('withdrawals').where('status', '==', 'pending').limit(15).get()
        
        if not withdrawals:
            return "💸 No pending withdrawals."
        
        message = "💸 *PENDING WITHDRAWALS*\n\n"
        for w in withdrawals:
            data = w.to_dict()
            seller = data.get('sellerName', 'Unknown')[:20]
            amount = data.get('amount', 0)
            requested = data.get('requestedAt', datetime.now())
            
            message += f"💰 `{w.id[:8]}` *{seller}* — ₹{amount}\n"
            message += f"   📅 {requested}\n\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def approve_withdrawal(withdrawal_id):
    """Approve withdrawal"""
    try:
        doc_ref = db.collection('withdrawals').document(withdrawal_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Withdrawal `{withdrawal_id}` not found."
        
        doc_ref.update({
            'status': 'approved',
            'approvedAt': datetime.now()
        })
        return f"✅ Withdrawal `{withdrawal_id}` approved."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# VIDEOS FUNCTIONS
# ============================================

async def get_videos():
    """Get pending videos"""
    try:
        videos = db.collection('videos').where('status', '==', 'pending').limit(15).get()
        
        if not videos:
            return "📹 No pending videos."
        
        message = "📹 *PENDING VIDEOS*\n\n"
        for v in videos:
            data = v.to_dict()
            title = data.get('title', 'Untitled')[:30]
            uploader = data.get('uploaderName', 'Unknown')[:20]
            
            message += f"🎬 `{v.id[:8]}` *{title}*\n"
            message += f"   👤 {uploader}\n\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def approve_video(video_id):
    """Approve video"""
    try:
        doc_ref = db.collection('videos').document(video_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return f"❌ Video `{video_id}` not found."
        
        doc_ref.update({
            'status': 'approved',
            'approvedAt': datetime.now()
        })
        return f"✅ Video `{video_id}` approved."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# REVENUE FUNCTIONS
# ============================================

async def get_revenue_stats():
    """Get revenue statistics"""
    try:
        # Last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        orders = db.collection('orders').where('createdAt', '>=', thirty_days_ago).get()
        
        total = 0
        by_status = {}
        daily = {}
        
        for order in orders:
            data = order.to_dict()
            amount = data.get('total', 0)
            status = data.get('status', 'unknown')
            created = data.get('createdAt')
            
            total += amount
            by_status[status] = by_status.get(status, 0) + 1
            
            if created:
                day = created.strftime('%d %b')
                daily[day] = daily.get(day, 0) + amount
        
        # Top 5 days
        top_days = sorted(daily.items(), key=lambda x: x[1], reverse=True)[:5]
        
        message = (
            f"💰 *REVENUE STATS*\n"
            f"📅 Last 30 days\n\n"
            f"💵 *Total Revenue:* `₹{total:,.0f}`\n"
            f"📦 *Total Orders:* `{len(orders)}`\n"
            f"📊 *Avg Order Value:* `₹{total/len(orders) if orders else 0:,.0f}`\n\n"
            f"*By Status:*\n"
        )
        
        for status, count in by_status.items():
            message += f"   📌 {status}: {count}\n"
        
        if top_days:
            message += f"\n*Top 5 Revenue Days:*\n"
            for day, amount in top_days:
                message += f"   📅 {day}: ₹{amount:,.0f}\n"
        
        return message
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================
# AI CHAT FUNCTION (OPTIONAL)
# ============================================

async def ask_ai(prompt):
    """Ask AI with fallback"""
    # Try Ollama first
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "deepseek-r1:1.5b",
            "prompt": prompt,
            "stream": False
        }, timeout=30)
        if response.status_code == 200:
            return response.json().get('response', "I'm here to help!")
    except:
        pass
    
    # Try Claude if available
    if CLAUDE_API_KEY:
        try:
            headers = {"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            data = {"model": "claude-3-haiku-20240307", "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]}
            response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                return response.json()["content"][0]["text"]
        except:
            pass
    
    # Try Groq if available
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
        except:
            pass
    
    return "AI is not available. Please check API keys or use other commands."

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
        [InlineKeyboardButton("💸 Withdrawals", callback_data='withdrawals'),
         InlineKeyboardButton("📹 Videos", callback_data='videos')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *APYKART ADMIN BOT* 🔥\n\n"
        "Your AI-powered admin panel is ready!\n\n"
        "*Commands:*\n"
        "📊 `/stats` - Dashboard stats\n"
        "📦 `/orders` - Recent orders\n"
        "🔍 `/order ORDER_ID` - Order details\n"
        "🔄 `/update ORDER_ID status` - Update order\n"
        "🛍️ `/products` - Product list\n"
        "➕ `/add Name Price` - Add product\n"
        "❌ `/delete PRODUCT_ID` - Delete product\n"
        "👥 `/users` - User list\n"
        "🚫 `/ban USER_ID` - Ban/unban user\n"
        "🏪 `/sellers` - Seller list\n"
        "✅ `/verify SELLER_ID` - Verify seller\n"
        "💸 `/withdrawals` - Pending withdrawals\n"
        "💰 `/revenue` - Revenue stats\n"
        "📹 `/videos` - Pending videos\n"
        "❓ `/help` - Help menu\n\n"
        "*Examples:*\n"
        "`/add Hoodie 1299`\n"
        "`/update ORD123 shipped`\n"
        "`/ban user123`",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    
    await update.message.reply_text(
        "📋 *APYKART ADMIN BOT COMMANDS*\n\n"
        "*📊 Dashboard*\n"
        "/stats - Complete dashboard\n\n"
        "*📦 Orders*\n"
        "/orders - Recent orders\n"
        "/order ORDER_ID - Order details\n"
        "/update ORDER_ID status - Update status\n\n"
        "*🛍️ Products*\n"
        "/products - Product list\n"
        "/add Name Price - Add product\n"
        "/delete PRODUCT_ID - Delete product\n\n"
        "*👥 Users*\n"
        "/users - User list\n"
        "/ban USER_ID - Ban/unban user\n\n"
        "*🏪 Sellers*\n"
        "/sellers - Seller list\n"
        "/verify SELLER_ID - Verify KYC\n\n"
        "*💰 Finance*\n"
        "/withdrawals - Pending withdrawals\n"
        "/revenue - Revenue stats\n\n"
        "*📹 Content*\n"
        "/videos - Pending videos\n\n"
        "*Valid Status:*\n"
        "placed, confirmed, shipped, delivered, cancelled, returned, refunded",
        parse_mode='Markdown'
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
    await update.message.reply_text("📦 Fetching recent orders...")
    msg = await get_recent_orders()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def order_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/order ORDER_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"🔍 Fetching order `{context.args[0]}`...", parse_mode='Markdown')
    msg = await get_order_details(context.args[0])
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
        await update.message.reply_text("❌ Usage: `/add ProductName Price`\nExample: `/add Hoodie 1299`", parse_mode='Markdown')
        return
    price = context.args[-1]
    name = ' '.join(context.args[:-1])
    await update.message.reply_text(f"➕ Adding *{name}*...", parse_mode='Markdown')
    msg = await add_product(name, price)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/delete PRODUCT_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"❌ Deleting product `{context.args[0]}`...", parse_mode='Markdown')
    msg = await delete_product(context.args[0])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("👥 Fetching users...")
    msg = await get_users()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/ban USER_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"🚫 Processing user `{context.args[0]}`...", parse_mode='Markdown')
    msg = await ban_user(context.args[0])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def sellers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("🏪 Fetching sellers...")
    msg = await get_sellers()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/verify SELLER_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"✅ Verifying seller `{context.args[0]}`...", parse_mode='Markdown')
    msg = await verify_seller(context.args[0])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def withdrawals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("💸 Fetching withdrawals...")
    msg = await get_withdrawals()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def approve_withdrawal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/approve_withdrawal WITHDRAWAL_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"💰 Approving withdrawal `{context.args[0]}`...", parse_mode='Markdown')
    msg = await approve_withdrawal(context.args[0])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("📹 Fetching pending videos...")
    msg = await get_videos()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def approve_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: `/approve_video VIDEO_ID`", parse_mode='Markdown')
        return
    await update.message.reply_text(f"✅ Approving video `{context.args[0]}`...", parse_mode='Markdown')
    msg = await approve_video(context.args[0])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def revenue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    await update.message.reply_text("💰 Fetching revenue stats...")
    msg = await get_revenue_stats()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update):
        return
    user_msg = update.message.text
    if user_msg.startswith('/'):
        return
    await update.message.chat.send_action(action='typing')
    response = await ask_ai(user_msg)
    await update.message.reply_text(response)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await is_authorized(update):
        await query.edit_message_text("⛔ Unauthorized")
        return
    
    if query.data == 'stats':
        msg = await get_dashboard_stats()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'orders':
        msg = await get_recent_orders()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'products':
        msg = await get_products()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'users':
        msg = await get_users()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'sellers':
        msg = await get_sellers()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'revenue':
        msg = await get_revenue_stats()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'withdrawals':
        msg = await get_withdrawals()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'videos':
        msg = await get_videos()
        await query.edit_message_text(msg, parse_mode='Markdown')
    elif query.data == 'help':
        await query.edit_message_text(
            "📋 *Commands*\n\n"
            "/stats - Dashboard\n"
            "/orders - Recent orders\n"
            "/order ID - Order details\n"
            "/update ID status - Update order\n"
            "/products - Product list\n"
            "/add Name Price - Add product\n"
            "/delete ID - Delete product\n"
            "/users - User list\n"
            "/ban ID - Ban/unban user\n"
            "/sellers - Seller list\n"
            "/verify ID - Verify seller\n"
            "/withdrawals - Pending withdrawals\n"
            "/revenue - Revenue stats\n"
            "/videos - Pending videos",
            parse_mode='Markdown'
        )

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    print("🤖 Apykart Admin Bot Starting...")
    print(f"🔥 Authorized users: {ALLOWED_USER_IDS}")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("order", order_detail_command))
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("products", products_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("sellers", sellers_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("withdrawals", withdrawals_command))
    app.add_handler(CommandHandler("approve_withdrawal", approve_withdrawal_command))
    app.add_handler(CommandHandler("videos", videos_command))
    app.add_handler(CommandHandler("approve_video", approve_video_command))
    app.add_handler(CommandHandler("revenue", revenue_command))
    
    # AI chat handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
    
    # Button handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot is running! Send /start in Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
