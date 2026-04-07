from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN")

def telegram_request(method, data):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Telegram hiba: {e}")
        return None

def get_hubspot_contact(contact_id):
    # Fontos a crm/v3 API használata
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            return data.get("properties", {})
    except Exception as e:
        print(f"HubSpot API hiba (Contact ID: {contact_id}): {e}")
        return None

def handle_hubspot(body):
    try:
        events = json.loads(body)
        # Ha a HubSpot tesztet küld, az néha egy listát küld, néha egy objektumot
        if not isinstance(events, list):
            events = [events]

        for event in events:
            # Ha teszt üzenet érkezik, annak nincs subscriptionType-ja, engedjük át tesztelésre
            stype = event.get("subscriptionType", "")
            if stype and "contact.creation" not in stype:
                continue

            contact_id = event.get("objectId")
            if not contact_id:
                continue

            props = get_hubspot_contact(contact_id)
            if not props:
                # Ha nem sikerült lekérni a nevet, legalább az ID-t küldjük el
                name, email, phone = "Ismeretlen", "–", "–"
            else:
                first = props.get("firstname") or ""
                last = props.get("lastname") or ""
                name = f"{first} {last}".strip() or "Névtelen Lead"
                email = props.get("email") or "–"
                phone = props.get("phone") or "–"

            hubspot_url = f"https://app.hubspot.com/contacts/contact/{contact_id}"

            text = (
                f"🔥 <b>Új Lead érkezett!</b>\n\n"
                f"👤 <b>Név:</b> {name}\n"
                f"📧 <b>Email:</b> {email}\n"
                f"📞 <b>Telefon:</b> {phone}\n\n"
                f'🔗 <a href="{hubspot_url}">Megnyitás HubSpotban</a>'
            )

            reply_markup = {
                "inline_keyboard": [[
                    {"text": "✋ Kézbe veszem", "callback_data": f"claim:{contact_id}"}
                ]]
            }

            telegram_request("sendMessage", {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup
            })
    except Exception as e:
        print(f"Hiba a HubSpot feldolgozásakor: {e}")

def handle_telegram(body):
    try:
        data = json.loads(body)
        callback = data.get("callback_query")
        if not callback:
            return

        callback_data = callback.get("data", "")
        user = callback.get("from", {})
        username = user.get("username") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        message = callback.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")

        if not callback_data.startswith("claim:"):
            return

        # Csak a gombot módosítjuk, hogy ne vesszen el a formázás
        new_reply_markup = {
            "inline_keyboard": [[
                {"text": f"✅ {username} kezeli", "callback_data": "done"}
            ]]
        }

        telegram_request("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": new_reply_markup
        })

        telegram_request("answerCallbackQuery", {
            "callback_query_id": callback.get("id"),
            "text": "✅ Sikeresen hozzárendelve!"
        })
    except Exception as e:
        print(f"Hiba a Telegram gomb feldolgozásakor: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Lead Bot is running!")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        
        # Logoljuk a beérkező adatot a Vercel-be hibakereséshez
        print(f"Beérkező kérés: {body.decode('utf-8')}")

        if b"objectId" in body or b"subscriptionType" in body:
            handle_hubspot(body)
        elif b"callback_query" in body:
            handle_telegram(body)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass

app = handler
