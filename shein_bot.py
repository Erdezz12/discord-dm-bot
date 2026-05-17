import os
"""
Bot Telegram Shein - @Bonsplanshein
- Envoyez un lien Shein → le bot scrape automatiquement image, nom, prix
- Publie dans le canal avec le code TU87V
- Tourne H24 sur Railway
"""

import logging, re, asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN", "8630597675:AAH_HEK-Yk9uvF8CDRXynMDnggt1r1PKu7M")
CANAL           = os.environ.get("CANAL", "@Bonsplanshein")
CODE_AFFIL      = os.environ.get("CODE_AFFIL", "TU87V")
REMISE          = "60%"
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
WAIT_PRICE = 1

# ── Scraping Shein ────────────────────────────────────────────────────────────
def scrape_shein(url: str):
    """Récupère nom, prix, image depuis une page Shein."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://fr.shein.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }
    name, price, img = None, None, None
    try:
        session = requests.Session()
        session.get("https://fr.shein.com/", headers=headers, timeout=8)
        r = session.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            og = lambda p: (soup.find("meta", property=p) or {}).get("content")
            name  = og("og:title")
            img   = og("og:image")
            price = og("product:price:amount")
            # Fallback prix depuis JSON-LD
            if not price:
                for s in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        d = json.loads(s.string)
                        if isinstance(d, dict) and "offers" in d:
                            price = str(d["offers"].get("price", ""))
                            break
                    except Exception:
                        pass
            # Fallback prix depuis texte
            if not price:
                for sel in [".product-intro__head-price .from", ".from .price-num", "[class*=sale-price]", "[class*=price-now]"]:
                    el = soup.select_one(sel)
                    if el:
                        price = el.get_text(strip=True).replace("€","").strip()
                        break
    except Exception as e:
        logging.warning(f"Scraping error: {e}")

    # Fallback nom depuis URL
    if not name:
        m = re.search(r'shein\.com/(?:[a-z]{2}/)?(.+?)-p-\d+', url)
        if m:
            name = m.group(1).replace("-", " ").title()

    # Nettoyer le prix
    if price:
        price = re.sub(r'[^\d.,]', '', price).replace(",", ".").strip(".")

    return name or "Produit Shein", price, img

# ── Message formaté ───────────────────────────────────────────────────────────
def build_message(name: str, price: str, url: str) -> str:
    price_line = f"💰 Prix : *{price} €*" if price else "💰 Prix : *voir le lien*"
    return (
        f"╔══════════════════════╗\n"
        f"      🛍️ *BON PLAN SHEIN* 🛍️\n"
        f"╚══════════════════════╝\n\n"
        f"👗 *{name}*\n\n"
        f"{price_line}\n"
        f"🔥 *-{REMISE} pour les nouveaux utilisateurs !*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📲 *Comment profiter de la réduction ?*\n"
        f"1️⃣ Ouvrez l'appli *Shein*\n"
        f"2️⃣ Tapez `{CODE_AFFIL}` dans la 🔍 barre de recherche\n"
        f"3️⃣ Profitez de *-{REMISE}* sur votre commande ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 [👉 Voir le produit sur Shein]({url})\n\n"
        f"⚠️ *Offre réservée aux nouveaux utilisateurs Shein*\n\n"
        f"#Shein #BonPlan #CodePromo #Mode #Réduction #Promo"
    )

# ── Aperçu + boutons ──────────────────────────────────────────────────────────
async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url   = context.user_data["url"]
    name  = context.user_data["name"]
    price = context.user_data.get("price")
    img   = context.user_data.get("img")
    msg   = build_message(name, price, url)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Publier dans le canal", callback_data="publish"),
        InlineKeyboardButton("❌ Annuler",               callback_data="cancel"),
    ]])

    if img:
        await update.message.reply_photo(
            photo=img,
            caption=f"📋 *Aperçu de l'annonce :*\n\n{msg}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            f"📋 *Aperçu de l'annonce :*\n\n{msg}",
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=False
        )

# ── Handler principal ─────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url_match = re.search(r'https?://[^\s]*shein\.[^\s]+', text)

    if not url_match:
        await update.message.reply_text(
            "👋 Envoyez-moi un lien Shein !\n\n"
            "Exemple :\n`https://fr.shein.com/...`\n\n"
            "💡 Vous pouvez aussi ajouter le prix :\n"
            "`https://fr.shein.com/... 12.99`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    url = url_match.group(0)
    context.user_data["url"] = url

    # Prix dans le message ?
    clean_text = text.replace(url, "")
    price_match = re.search(r'\b(\d+[.,]\d{1,2})\b', clean_text)
    manual_price = price_match.group(1).replace(",", ".") if price_match else None

    await update.message.reply_text("⏳ Je récupère les infos du produit...")

    # Scraping
    name, scraped_price, img = scrape_shein(url)
    price = manual_price or scraped_price

    context.user_data.update({"name": name, "price": price, "img": img})

    if price:
        await send_preview(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f"✅ Produit trouvé : *{name}*\n\n"
            f"💬 Je n'ai pas pu détecter le prix automatiquement.\n"
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
            await update.message.reply_text("❌ Format non reconnu. Envoyez `12.99` ou `0`.", parse_mode="Markdown")
            return WAIT_PRICE
    await send_preview(update, context)
    return ConversationHandler.END

# ── Publication ───────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        url   = context.user_data.get("url")
        name  = context.user_data.get("name")
        price = context.user_data.get("price")
        img   = context.user_data.get("img")
        msg   = build_message(name, price, url)
        try:
            if img:
                await context.bot.send_photo(
                    chat_id=CANAL, photo=img,
                    caption=msg, parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=CANAL, text=msg,
                    parse_mode="Markdown", disable_web_page_preview=False
                )
            await query.edit_message_caption(
                caption="🎉 *Annonce publiée dans le canal !* 🚀",
                parse_mode="Markdown"
            ) if img else await query.edit_message_text(
                "🎉 *Annonce publiée dans le canal !* 🚀",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Publish error: {e}")
            try:
                await query.edit_message_text(f"❌ Erreur : {e}\n\nVérifiez que le bot est admin du canal.")
            except Exception:
                pass
    else:
        try:
            await query.edit_message_text("❌ Publication annulée.")
        except Exception:
            await query.edit_message_caption(caption="❌ Publication annulée.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={WAIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Bot Shein H24 démarré ! Envoyez un lien Shein au bot.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
