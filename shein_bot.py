import os, logging, re, json, base64
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "METS_TON_TOKEN_ICI")
CANAL      = os.environ.get("CANAL", "@Bonsplanshein")
CODE_AFFIL = os.environ.get("CODE_AFFIL", "TU87V")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")
REMISE     = "60%"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
WAIT_PRICE = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── Résolution lien court ────────────────────────────────────────────────────

def resolve_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        return r.url
    except Exception as e:
        logging.warning(f"Redirect error: {e}")
        return url

# ─── Extraction via Claude AI ─────────────────────────────────────────────────

def extract_with_claude(url: str, html_snippet: str) -> dict:
    if not CLAUDE_KEY:
        return {}
    try:
        prompt = f"""Voici le HTML d'une page produit Shein (URL: {url}).

Extrait ces informations en JSON uniquement, sans backticks :
{{
  "name": "nom complet du produit en français",
  "price": "prix en chiffres uniquement ex: 12.99",
  "image": "URL de l'image principale du produit"
}}

Si une info est introuvable, mets null.

HTML (tronqué) :
{html_snippet[:6000]}"""

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        text = resp.json()["content"][0]["text"].strip()
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception as e:
        logging.warning(f"Claude extraction error: {e}")
        return {}

# ─── Scraping Shein ───────────────────────────────────────────────────────────

def extract_name_from_url(url: str) -> str:
    m = re.search(r'shein\.com/(?:[a-z]{2}/)?(.+?)-p-\d+', url)
    if m:
        return m.group(1).replace("-", " ").title()
    return "Produit Shein"

def scrape_shein(url: str):
    name, price, img = None, None, None
    html_text = ""

    try:
        session = requests.Session()
        session.get("https://fr.shein.com/", headers=HEADERS, timeout=8)
        r = session.get(url, headers=HEADERS, timeout=15)
        html_text = r.text

        if r.status_code == 200 and len(html_text) > 500:
            soup = BeautifulSoup(html_text, "lxml")

            og = lambda p: (soup.find("meta", property=p) or {}).get("content")
            name  = og("og:title")
            img   = og("og:image")
            price = og("product:price:amount")

            if not price:
                for s in soup.find_all("script", type="application/ld+json"):
                    try:
                        d = json.loads(s.string or "")
                        if isinstance(d, dict) and "offers" in d:
                            price = str(d["offers"].get("price", ""))
                            if not img:
                                img = d.get("image", [None])[0] if isinstance(d.get("image"), list) else d.get("image")
                            break
                    except Exception:
                        pass

            if not price:
                m_data = re.search(r'"salePrice"[:\s]*\{[^}]*"amount"[:\s]*"?([\d.]+)"?', html_text)
                if m_data:
                    price = m_data.group(1)

            if not price:
                m_data = re.search(r'"price"[:\s]*"?([\d]{1,3}[.,]\d{2})"?', html_text)
                if m_data:
                    price = m_data.group(1)

    except Exception as e:
        logging.warning(f"Scraping error: {e}")

    if (not name or not price) and html_text and CLAUDE_KEY:
        logging.info("Fallback vers Claude pour extraction...")
        extracted = extract_with_claude(url, html_text)
        if not name:
            name = extracted.get("name")
        if not price:
            price = extracted.get("price")
        if not img:
            img = extracted.get("image")

    if not name:
        name = extract_name_from_url(url)

    if price:
        price = re.sub(r'[^\d.,]', '', str(price)).replace(",", ".").strip(".")
        if price in ("", "."):
            price = None

    return name or "Produit Shein", price, img

# ─── Formatage message canal (style capture) ─────────────────────────────────

def build_caption(name: str, price, url: str) -> str:
    # Format exact comme la capture :
    # NOM DU PRODUIT 😍
    # Prix : 12.99€
    # -60% coupon : TU87V 🏷️
    #
    # 👉 https://...
    lines = [f"{name.upper()} 😍"]
    if price:
        lines.append(f"Prix : {price}€")
    lines.append(f"-{REMISE} coupon : {CODE_AFFIL} 🏷️")
    lines.append("")
    lines.append(f"👉 {url}")
    return "\n".join(lines)

# ─── Aperçu utilisateur ───────────────────────────────────────────────────────

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url     = context.user_data["url"]
    name    = context.user_data["name"]
    price   = context.user_data.get("price")
    img     = context.user_data.get("img")
    caption = build_caption(name, price, url)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Publier dans le canal", callback_data="publish"),
        InlineKeyboardButton("❌ Annuler", callback_data="cancel"),
    ]])

    await update.message.reply_text("📋 Aperçu du message :")

    if img:
        try:
            await update.message.reply_photo(
                photo=img,
                caption=caption,
                reply_markup=keyboard
            )
            return
        except Exception as e:
            logging.warning(f"Photo preview failed: {e}")

    await update.message.reply_text(
        caption,
        reply_markup=keyboard,
        disable_web_page_preview=False
    )

# ─── Handler message entrant ──────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Accepte shein.com ET onelink.shein.com
    url_match = re.search(r'https?://[^\s]*(shein\.com|onelink\.shein\.com)[^\s]*', text)

    if not url_match:
        await update.message.reply_text(
            "👋 Envoie-moi un lien Shein !\n\n"
            "✅ Formats acceptés :\n"
            "• https://fr.shein.com/...\n"
            "• https://onelink.shein.com/...\n\n"
            "💡 Tu peux ajouter le prix directement :\n"
            "https://fr.shein.com/... 12.99"
        )
        return ConversationHandler.END

    raw_url = url_match.group(0)

    # Prix dans le message ?
    clean_text = text.replace(raw_url, "").strip()
    price_match = re.search(r'\b(\d+[.,]\d{1,2})\b', clean_text)
    manual_price = price_match.group(1).replace(",", ".") if price_match else None

    await update.message.reply_text("⏳ Je récupère les infos du produit...")

    # Résoudre lien court onelink → lien Shein réel
    if "onelink.shein.com" in raw_url:
        resolved = resolve_url(raw_url)
        url = resolved if "shein.com" in resolved and "onelink" not in resolved else raw_url
    else:
        url = raw_url

    name, scraped_price, img = scrape_shein(url)
    price = manual_price or scraped_price

    context.user_data.update({"url": raw_url, "name": name, "price": price, "img": img})
    # On garde le lien original (court) pour le message final

    if price:
        await send_preview(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            f"✅ Produit : {name}\n\n"
            f"💬 Prix non détecté automatiquement.\n"
            f"Quel est le prix ? (ex: 12.99)\n"
            f"Tape 0 pour ne pas afficher de prix."
        )
        return WAIT_PRICE

# ─── Handler prix manuel ──────────────────────────────────────────────────────

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "0":
        context.user_data["price"] = None
    else:
        m = re.search(r'(\d+[.,]\d{1,2})', text)
        if m:
            context.user_data["price"] = m.group(1).replace(",", ".")
        else:
            await update.message.reply_text("❌ Envoie un nombre comme 12.99 ou 0.")
            return WAIT_PRICE
    await send_preview(update, context)
    return ConversationHandler.END

# ─── Handler bouton Publier / Annuler ─────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data != "publish":
        try:
            await query.edit_message_caption(caption="❌ Annulé.")
        except Exception:
            await query.edit_message_text("❌ Annulé.")
        return

    url     = context.user_data.get("url")
    name    = context.user_data.get("name")
    price   = context.user_data.get("price")
    img     = context.user_data.get("img")
    caption = build_caption(name, price, url)

    published = False

    # Tentative 1 : avec image
    if img:
        try:
            await context.bot.send_photo(
                chat_id=CANAL,
                photo=img,
                caption=caption,
            )
            published = True
        except Exception as e:
            logging.warning(f"send_photo au canal échoué: {e}")

    # Tentative 2 : texte seul (avec preview lien)
    if not published:
        try:
            await context.bot.send_message(
                chat_id=CANAL,
                text=caption,
                disable_web_page_preview=False
            )
            published = True
        except Exception as e:
            logging.error(f"send_message au canal échoué: {e}")
            try:
                await query.edit_message_text(
                    f"❌ Erreur publication canal :\n{e}\n\n"
                    f"Vérifie que le bot est bien admin de {CANAL} avec le droit Publier des messages."
                )
            except Exception:
                pass
            return

    if published:
        try:
            await query.edit_message_caption(caption="🎉 Publié dans le canal ! 🚀")
        except Exception:
            try:
                await query.edit_message_text("🎉 Publié dans le canal ! 🚀")
            except Exception:
                pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={WAIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Bot Shein démarré !")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
