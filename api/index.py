from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

# --- BEÁLLÍTÁSOK ---
# A környezeti változókat a Vercel felületén kell beállítani
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
WEB_APP_URL = "https://salesbot1.vercel.app/form.html"

# Felhasználó párosítás a HubSpot 'Lead szerző' mezőhöz
USER_MAPPING = {
    "Tibor Kaplonyi": "Kaplonyi Tibor",
    "István Varró": "Varró István",
    "Selim Cilingir": "Cilingir Selim"
}

def telegram_request(method, data):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"HIBA - Telegram kérés ({method}): {e}")
        return None

def update_hubspot(contact_id, properties):
    """Frissíti a HubSpot kontaktot a megadott tulajdonságokkal."""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    req = urllib.request.Request(url, data=json.dumps({"properties": properties}).encode("utf-8"), method="PATCH",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True
    except Exception as e:
        print(f"HIBA - HubSpot módosítás (Contact ID: {contact_id}): {e}")
        return False

def get_hubspot_contact(contact_id):
    """Lekéri a kontakt alapadatait a Telegram értesítéshez."""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode('utf-8')).get("properties", {})
    except:
        return None

def handle_hubspot(body_str):
    """HubSpot Webhook feldolgozása (új lead érkezése)."""
    try:
        data = json.loads(body_str)
        events = data if isinstance(data, list) else [data]
        for event in events:
            contact_id = event.get("objectId") or event.get("entityId")
            if not contact_id: continue
            
            props = get_hubspot_contact(contact_id)
            if not props: continue

            name = f"{props.get('firstname','')} {props.get('lastname','')}".strip() or "Névtelen Lead"
            text = (
                f"🔥 <b>Új Lead érkezett!</b>\n\n"
                f"👤 <b>Név:</b> {name}\n"
                f"📧 <b>Email:</b> {props.get('email','–')}\n"
                f"📞 <b>Telefon:</b> {props.get('phone','–')}\n\n"
                f'🔗 <a href="https://app.hubspot.com/contacts/contact/{contact_id}">Megnyitás HubSpotban</a>'
            )
            
            markup = {"inline_keyboard": [[{"text": "✋ Kézbe veszem", "callback_data": f"claim:{contact_id}"}]]}
            telegram_request("sendMessage", {
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": text, 
                "parse_mode": "HTML", 
                "reply_markup": markup
            })
    except Exception as e:
        print(f"HIBA - HubSpot bejövő feldolgozás: {e}")

def handle_telegram(body_str):
    """Telegram üzenetek és Web App válaszok feldolgozása."""
    try:
        data = json.loads(body_str)
        
        # 1. Web App adat érkezése (Privát chatben kitöltött űrlap)
        if "message" in data and "web_app_data" in data["message"]:
            user_id = data["message"]["from"]["id"]
            web_data = json.loads(data["message"]["web_app_data"]["data"])
            contact_id = web_data.get("contact_id")
            
            # A HubSpot belső nevei a képernyőfotók alapján
            props = {
                "szolgaltatas_tipusa": web_data.get("service"),
                "lead_megjegyzes": web_data.get("note")
            }
            if update_hubspot(contact_id, props):
                telegram_request("sendMessage", {"chat_id": user_id, "text": "✅ Az adatokat sikeresen rögzítettem a HubSpotban!"})
            else:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "❌ Hiba történt a HubSpot mentésnél. Ellenőrizd a mezőértékeket!"})
            return

        # 2. Gombnyomás kezelése (Kézbe veszem)
        callback = data.get("callback_query")
        if not callback: return
        
        cb_id = callback.get("id")
        cb_data = callback.get("data", "")
        user = callback.get("from", {})
        user_id = user.get("id")
        # Felhasználó teljes neve a Telegramból
        t_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        msg = callback.get("message", {})

        if cb_data.startswith("claim:"):
            contact_id = cb_data.split(":")[1]
            
            # Ellenőrizzük az aktuális üzenet gombját
            current_reply_markup = msg.get("reply_markup", {})
            inline_keyboard = current_reply_markup.get("inline_keyboard", [[]])
            button_text = inline_keyboard[0][0].get("text", "") if inline_keyboard and inline_keyboard[0] else ""
            
            # Ha már valaki kezelte (a gomb szövege tartalmazza a pipát), akkor ne engedjük újra
            if "✅" in button_text:
                telegram_request("answerCallbackQuery", {
                    "callback_query_id": cb_id, 
                    "text": "Ezt a leadet már valaki elvitte!",
                    "show_alert": True
                })
                return

            telegram_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Küldöm az űrlapot privátban!"})

            # Lead szerző frissítése a mapping alapján
            hub_val = USER_MAPPING.get(t_name)
            if hub_val:
                update_hubspot(contact_id, {"lead_szerzo": hub_val})

            # CSOPORTBAN: Gomb lecserélése státuszra (azonnali visszajelzés a csoportnak)
            new_markup = {"inline_keyboard": [[{"text": f"✅ {t_name} kezeli", "callback_data": "done"}]]}
            telegram_request("editMessageReplyMarkup", {
                "chat_id": msg["chat"]["id"], 
                "message_id": msg["message_id"], 
                "reply_markup": new_markup
            })

            # PRIVÁTBAN: Az űrlap kiküldése a Contact ID-val az URL-ben
            private_text = f"📋 <b>Adatlap kitöltése</b>\nLead ID: {contact_id}\n\nKérlek, add meg a részleteket az alábbi gombbal:"
            private_markup = {"inline_keyboard": [[
                {"text": "📋 Űrlap megnyitása", "web_app": {"url": f"{WEB_APP_URL}?id={contact_id}"}}
            ]]}
            telegram_request("sendMessage", {
                "chat_id": user_id,
                "text": private_text,
                "parse_mode": "HTML",
                "reply_markup": private_markup
            })

    except Exception as e:
        print(f"HIBA - Telegram feldolgozás: {e}")

def handle_webapp_submission(data):
    """A Web App űrlap közvetlen beküldésének feldolgozása."""
    try:
        contact_id = data.get("contact_id")
        user_id = data.get("user_id")
        
        props = {
            "szolgaltatas_tipusa": data.get("service"),
            "telepules": data.get("telepules"),
            "irsz": data.get("irsz"),
            "cim": data.get("cim"),
            "lead_megjegyzes": data.get("note")
        }
        
        if update_hubspot(contact_id, props):
            if user_id:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "✅ Az adatokat sikeresen rögzítettem a HubSpotban!"})
        else:
            if user_id:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "❌ Hiba történt a HubSpot mentésnél. Ellenőrizd a mezőértékeket!"})
    except Exception as e:
        print(f"HIBA - Web App submission feldolgozás: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body_str = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body_str)
        except:
            data = {}

        # Eldönti, hogy HubSpot webhook, Web App submission vagy Telegram üzenet érkezett-e
        if isinstance(data, list) or "objectId" in data or "subscriptionType" in data:
            handle_hubspot(body_str)
        elif data.get("source") == "webapp":
            handle_webapp_submission(data)
        else:
            handle_telegram(body_str)
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

app = handler
