import requests
import time
import telebot
import json
import os
import threading
from urllib.parse import urlparse

# ================== CONFIG ==================
BOT_TOKEN = "8624534058:AAFVp1nm4xCGD-NfpcqusmH-ok8_0Q90fAk"
OPENSEA_API_KEY = "f42388ddfd5845"
ADMIN_ID = 1890133465   # ← তোমার Chat ID বসাও

bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "opensea_monitor.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "approved_users" not in data: data["approved_users"] = []
                if "banned_users" not in data: data["banned_users"] = []
                if "users" not in data: data["users"] = {}
                return data
        except:
            return {"approved_users": [], "banned_users": [], "users": {}}
    return {"approved_users": [], "banned_users": [], "users": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def is_approved(user_id):
    uid = str(user_id)
    if uid in data.get("banned_users", []): return False
    return uid in data.get("approved_users", []) or int(user_id) == ADMIN_ID

def get_slug(url):
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        parts = path.split('/')
        if len(parts) > 1 and parts[0] == 'collection':
            return parts[1]
    except:
        pass
    return None

def get_eth_usd_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=10)
        if r.status_code == 200:
            return float(r.json()["ethereum"]["usd"])
    except:
        pass
    return None

def get_floor_price(slug):
    url = f"https://api.opensea.io/api/v2/collections/{slug}/stats"
    try:
        headers = {'accept': '*/*', 'X-API-KEY': OPENSEA_API_KEY}
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            js = r.json()
            total = js.get('total', {})
            eth_price = total.get('floor_price')
            if eth_price is not None:
                usd_rate = get_eth_usd_price()
                usd_price = round(eth_price * usd_rate, 2) if usd_rate else None
                return float(eth_price), 'ETH', usd_price
        return None, None, None
    except:
        return None, None, None

# ================== START ==================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    if user_id not in data["users"]:
        data["users"][user_id] = {"collections": {}}
        save_data(data)
    
    if is_approved(user_id):
        bot.reply_to(message, "👋 **Floor Alert Bot** is active!\n\n"
                              "/add <link> → Add Project\n"
                              "/list → View your list\n"
                              "/remove <slug> → Remove project\n\n"
                              "🔧 Developed by @SK1Z0V41")
    else:
        bot.reply_to(message, f"👋 Welcome!\n\n"
                              "You need admin approval.\n\n"
                              f"Your ID:\n```{user_id}```\n\n"
                              "Tap above to copy.\n\n"
                              "📞 **Contact Developer:** @SK1Z0V41")

# ================== ADMIN ==================
@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "❌ Only admin can use this command.")
        return
    try:
        user_id = message.text.split(maxsplit=1)[1].strip()
        if user_id not in data["approved_users"]:
            data["approved_users"].append(user_id)
            if user_id in data.get("banned_users", []):
                data["banned_users"].remove(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User `{user_id}` approved.")
    except:
        bot.reply_to(message, "Usage: /approve <user_id>")

# ================== ADD (Fixed with Price) ==================
@bot.message_handler(commands=['add'])
def add_collection(message):
    if not is_approved(message.chat.id):
        bot.reply_to(message, "❌ You are not approved.")
        return
    user_id = str(message.chat.id)
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        slug = get_slug(url)
        if not slug:
            bot.reply_to(message, "❌ Invalid OpenSea link.")
            return
            
        price, symbol, usd_price = get_floor_price(slug)
        usd_str = f" (${usd_price:,})" if usd_price else ""
        
        if price is None:
            bot.reply_to(message, f"✅ `{slug}` added!\n(Price not available yet)")
        else:
            bot.reply_to(message, f"✅ **{slug}** added successfully!\nFloor: `{price}` {symbol}{usd_str}")
        
        data["users"][user_id]["collections"][slug] = {"last_price": price or 0, "symbol": symbol or "ETH", "url": url}
        save_data(data)
    except:
        bot.reply_to(message, "Usage: /add https://opensea.io/collection/...")

# ================== LIST & REMOVE ==================
@bot.message_handler(commands=['list'])
def list_collections(message):
    if not is_approved(message.chat.id):
        bot.reply_to(message, "❌ You are not approved.")
        return
    user_id = str(message.chat.id)
    if not data["users"][user_id]["collections"]:
        bot.reply_to(message, "📭 No projects added.")
        return
    text = "📋 **Your Projects**\n\n"
    for slug in data["users"][user_id]["collections"]:
        text += f"• `{slug}`\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['remove'])
def remove_collection(message):
    if not is_approved(message.chat.id):
        bot.reply_to(message, "❌ You are not approved.")
        return
    user_id = str(message.chat.id)
    try:
        slug = message.text.split(maxsplit=1)[1].strip()
        if slug in data["users"][user_id]["collections"]:
            del data["users"][user_id]["collections"][slug]
            save_data(data)
            bot.reply_to(message, f"🗑️ `{slug}` removed.")
        else:
            bot.reply_to(message, f"❌ `{slug}` not found.")
    except:
        bot.reply_to(message, "Usage: /remove <slug>")

# ================== MONITORING ==================
def monitor_loop():
    while True:
        time.sleep(60)
        for user_id, user_data in data["users"].items():
            if not is_approved(user_id): continue
            for slug, info in list(user_data["collections"].items()):
                try:
                    price, symbol, usd_price = get_floor_price(slug)
                    if price is None: continue
                    usd_str = f" (${usd_price:,})" if usd_price else ""
                    last = info.get("last_price")
                    change_str = ""
                    if last and last > 0:
                        pct = ((price - last) / last * 100)
                        direction = "📈" if price > last else "📉"
                        change_str = f"\nChange: {direction} {pct:+.2f}%"
                    msg = f"📈 **Floor Alert**\n\nFloor: `{price}` {symbol}{usd_str}{change_str}\n[{slug}](https://opensea.io/collection/{slug})\n\n🔧 @SK1Z0V41"
                    bot.send_message(int(user_id), msg, parse_mode='Markdown', disable_web_page_preview=True)
                    user_data["collections"][slug]["last_price"] = price
                    save_data(data)
                except:
                    pass

if __name__ == "__main__":
    print("🚀 Bot Started...")
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    threading.Thread(target=monitor_loop, daemon=True).start()
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except:
            time.sleep(10)