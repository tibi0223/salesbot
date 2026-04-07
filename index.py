from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN")

def telegram_request(method, data):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def get_hubspot_contact(contact_id):
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()).get("properties", {})
    except:
        return None

def handle_hubspot(body):
    events = json.loads(body)
    for event in events:
        if "contact.creation" not in event.get("subscriptionType", ""):
            continue
        contact_id = event.get("objectId")
        if not contact_id:
            continue

        props = get_hubspot_contact(contact_id)
        if not props:
            continue

        first = props.get("firstname") or ""
        last = props.get("lastname") or ""
        name = f"{first} {last}".strip() or "Ismeretlen"
        email = props.get("email") or "–"
        phone = props.get("phone") or "–"
        hubspot_url = f"https://app.hubspot.com/contacts/contact/{contact_id}"

        text = (
            f"🔥 <b>Új Lead érkezett!</b>\n\n"
            f"👤 <b>Név:</b> {name}\n"
            f"📧 <b>Email:</b> {email}\n"
            f"📞 <b>Telefon:</b> {phone}\n\n"
            f'<a href="{hubspot_url}">👁 Megnyitás HubSpotban</a>'
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

def handle_telegram(body):
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
    original_text = message.get("text", "")

    if not callback_data.startswith("claim:"):
        return

    new_text = original_text + f"\n\n✅ <b>{username} kezeli</b>"

    telegram_request("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "HTML"
    })

    telegram_request("answerCallbackQuery", {
        "callback_query_id": callback.get("id"),
        "text": "✅ Kézbe vetted!"
    })

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Lead Bot is running!")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            if "/api/hubspot" in self.path:
                handle_hubspot(body)
            elif "/api/telegram" in self.path:
                handle_telegram(body)
        except Exception as e:
            print(f"Error: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass
