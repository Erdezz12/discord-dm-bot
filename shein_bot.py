import os, logging, re
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "8630597675:AAH_HEK-Yk9uvF8CDRXynMDnggt1r1PKu7M")
CANAL      = os.environ.get("CANAL", "@Bonsplanshein")
CODE_AFFIL = os.environ.get("CODE_AFFIL", "TU87V")
REMISE     = "60%"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
WAIT_PRICE = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def resolve_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        return r.url
    except Exception as e:
        logging.warning(f"Redirect error: {e}")
        return url

def extract_name_from_url(url: str) -> str:
    m = re.search(r'shein\.com/(?:[a-z]{2}/)?(.+?)-p-\d+', url)
    if m:
        return m.group(1).replace("-", " ").title()
    return "Produit Shein"

def scrape_shein(url: str):
    name, price, img = None, None, None
    try:
        session = requests.Session()
        session.get("https://fr.shein.com/", headers=HEADERS, timeout=8)
        r = session.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200 and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            og = lambda p: (soup.find("meta", property=p) or {}).get("content")
            name  = og("og:title")
            img   = og("og:image")
            price = og("product:price:amount")
            if not price:
                import json
                for s in soup.find_all("script", type="application/ld+json"):
                    try:
                        d = json.loads(s.string)
                        if isinstance(d, dict) and "offers" in d:
                            price = str(d["offers"].get("price", ""))
                            break
                    except Exception:
                        pass
    except Exception as e:
        logging.warning(f"Scraping error: {e}")

    if not name:
        name = extract_name_from_url(url)
    if price:
        price = re.sub(r'[^\d.,]', '', price).replace(",", ".").strip(".")

    return name or "Produit Shein", price, img

def build_caption(name: str, price: str, url: str) -> str:
    """Message style canal Telegram - comme l'exemple HACOO"""
    price_line = f"💸 Prix : {price} €" if price else ""
    return (
        f"❗👗 *{name.upper()}* 👗❗\n"
        f"\n"
        f"{price_line}\n"
        f"-{REMISE} coupon : `{CODE_AFFIL}`\n"
        f"\n"
        f"👉 {url}"
    )

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url   = context.user_data["url"]
    name  = context.user_data["name"]
    price = context.user_data.get("price")
    img   = context.user_data.get("img")
    caption = build_caption(name, price, url)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Publier dans le canal", callback_data="publish"),
        InlineKeyboardButton("❌ Annuler", callback_data="cancel"),
    ]])

    await update.message.reply_text("📋 *Aperçu du message :*", parse_mode="Markdown")

    if img:
        await update.message.reply_photo(
            photo=img,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=False
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    url_match = re.search(r'https?://[^\s]*(shein\.com|onelink\.shein\.com)[^\s]*', text)

    if not url_match:
        await update.message.reply_text(
            "👋 Envoyez-moi un lien Shein !\n\n"
            "✅ Les deux formats marchent :\n"
            "• `https://fr.shein.com/...`\n"
            "• `https://onelink.shein.com/...`\n\n"
            "💡 Vous pouvez ajouter le prix :\n"
            "`https://fr.shein.com/... 12.99`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    raw_url = url_match.group(0)

    # Prix manuel dans le message ?
    clean_text = text.replace(raw_url, "")
    price_match = re.search(r'\b(\d+[.,]\d{1,2})\b', clean_text)
    manual_price = price_match.group(1).replace(",", ".") if price_match else None

    await update.message.reply_text("⏳ Je récupère les infos du produit...")

    # Résoudre lien court
    if "onelink.shein.com" in raw_url:
        resolved = resolve_url(raw_url)
        url = resolved if "shein.com" in resolved and "onelink" not in resolved else raw_url
    else:
        url = raw_url

    name, scraped_price, img = scrape_shein(url)
    price = manual_price or scraped_price

    context.user_data.update({"url": url, "name": name, "price": price, "img": img})

    if price:
        await send_preview(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f"✅ Produit : *{name}*\n\n"
            f"💬 Prix non détecté automatiquement.\n"
            f"Quel est le prix ? (ex: `12.99`)\n"
            f"Tapez `0` pour ne pas afficher de prix.",
            parse_mode="Markdown"
        )
        return WAIT_PRICE

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "0":
        context.user_data["price"] = None
    else:
        m = re.search(r'(\d+[.,]\d{1,2})', text)
        if m:
            context.user_data["price"] = m.group(1).replace(",", ".")
        else:
            await update.message.reply_text("❌ Envoyez un nombre comme `12.99` ou `0`.", parse_mode="Markdown")
            return WAIT_PRICE
    await send_preview(update, context)
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        url     = context.user_data.get("url")
        name    = context.user_data.get("name")
        price   = context.user_data.get("price")
        img     = context.user_data.get("img")
        caption = build_caption(name, price, url)

        try:
            if img:
                await context.bot.send_photo(
                    chat_id=CANAL,
                    photo=img,
                    caption=caption,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=CANAL,
                    text=caption,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
            try:
                await query.edit_message_caption(caption="🎉 *Publié dans le canal !* 🚀", parse_mode="Markdown")
            except Exception:
                await query.edit_message_text("🎉 *Publié dans le canal !* 🚀", parse_mode="Markdown")

        except Exception as e:
            logging.error(f"Publish error: {e}")
            try:
                await query.edit_message_text(f"❌ Erreur : {e}")
            except Exception:
                pass
    else:
        try:
            await query.edit_message_caption(caption="❌ Annulé.")
        except Exception:
            await query.edit_message_text("❌ Annulé.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={WAIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Bot Shein H24 démarré !")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
