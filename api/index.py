from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

# Környezeti változók lekérése
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN")

def telegram_request(method, data):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            res = r.read().decode('utf-8')
            print(f"Telegram válasz: {res}")
            return json.loads(res)
    except Exception as e:
        print(f"HIBA - Telegram küldés sikertelen: {e}")
        return None

def get_hubspot_contact(contact_id):
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode('utf-8'))
            return data.get("properties", {})
    except Exception as e:
        print(f"HIBA - HubSpot kontakt lekérés (ID: {contact_id}): {e}")
        return None

def handle_hubspot(body_str):
    try:
        events = json.loads(body_str)
        if not isinstance(events, list):
            events = [events]

        for event in events:
            #objectId keresése (teszt és éles üzenetben is benne van)
            contact_id = event.get("objectId")
            if not contact_id:
                print("INFO: Nincs objectId az eseményben, átugrás.")
                continue

            props = get_hubspot_contact(contact_id)
            
            if props:
                first = props.get("firstname") or ""
                last = props.get("lastname") or ""
                name = f"{first} {last}".strip() or "Névtelen Lead"
                email = props.get("email") or "–"
                phone = props.get("phone") or "–"
            else:
                name, email, phone = "Ismeretlen (Hiba az API-ban)", "–", "–"

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
        print(f"HIBA - HubSpot feldolgozás: {e}")

def handle_telegram(body_str):
    try:
        data = json.loads(body_str)
        callback = data.get("callback_query")
        if not callback: return

        callback_data = callback.get("data", "")
        user = callback.get("from", {})
        username = user.get("username") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        message = callback.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")

        if callback_data.startswith("claim:"):
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
            telegram_request("answerCallbackQuery", {"callback_query_id": callback.get("id"), "text": "✅ OK!"})
    except Exception as e:
        print(f"HIBA - Telegram callback: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Lead Bot is running!")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        print(f"DEBUG - Beérkező nyers adat: {body}")

        try:
            # Ha van benne objectId, akkor HubSpot küldte
            if "objectId" in body:
                handle_hubspot(body)
            # Ha callback_query, akkor Telegram gombnyomás
            elif "callback_query" in body:
                handle_telegram(body)
            else:
                print("INFO: Ismeretlen típusú POST kérés.")
        except Exception as e:
            print(f"HIBA - do_POST hiba: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return

app = handler
