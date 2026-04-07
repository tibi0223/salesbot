from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

# Környezeti változók lekérése és tisztítása
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()

# --- BEÁLLÍTÁS: Itt párosítjuk a Telegram neveket a HubSpot dropdown értékekkel ---
USER_MAPPING = {
    "Tibor Kaplonyi": "Kaplonyi Tibor",
    "István Varró": "Varró István",
    "Selim Cilingir": "Cilingir Selim",
    # Ha valakinek van @felhasználóneve, azt is ideírhatod:
    # "tibor_admin_vagyok": "Kaplonyi Tibor"
}

def telegram_request(method, data):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"HIBA - Telegram: {e}")
        return None

def update_hubspot_owner(contact_id, telegram_name):
    # Megnézzük, szerepel-e a név a fenti listában
    hubspot_value = USER_MAPPING.get(telegram_name)
    
    if not hubspot_value:
        print(f"DEBUG: Nincs párosítás a névhez: {telegram_name}")
        return False

    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    # FONTOS: A 'lead_szerzo' helyett a HubSpot mező BELSŐ NEVÉT használd!
    data = {
        "properties": {
            "lead_szerzo": hubspot_value 
        }
    }
    
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="PATCH",
        headers={
            "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"HubSpot frissítve: {hubspot_value} hozzárendelve.")
            return True
    except Exception as e:
        print(f"HIBA - HubSpot frissítés: {e}")
        return False

def get_hubspot_contact(contact_id):
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode('utf-8'))
            return data.get("properties", {})
    except:
        return None

def handle_hubspot(body_str):
    try:
        data = json.loads(body_str)
        events = data if isinstance(data, list) else [data]
        for event in events:
            contact_id = event.get("objectId") or event.get("entityId")
            if not contact_id: continue

            props = get_hubspot_contact(contact_id)
            name = f"{props.get('firstname','')} {props.get('lastname','')}".strip() or "Névtelen Lead"
            
            text = (
                f"🔥 <b>Új Lead érkezett!</b>\n\n"
                f"👤 <b>Név:</b> {name}\n"
                f"📧 <b>Email:</b> {props.get('email','–')}\n"
                f"📞 <b>Telefon:</b> {props.get('phone','–')}\n\n"
                f'🔗 <a href="https://app.hubspot.com/contacts/contact/{contact_id}">Megnyitás</a>'
            )

            reply_markup = {"inline_keyboard": [[{"text": "✋ Kézbe veszem", "callback_data": f"claim:{contact_id}"}]]}
            telegram_request("sendMessage", {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup})
    except Exception as e:
        print(f"HubSpot hiba: {e}")

def handle_telegram(body_str):
    try:
        data = json.loads(body_str)
        callback = data.get("callback_query")
        if not callback: return

        callback_data = callback.get("data", "")
        # Lekérjük a gombot megnyomó user nevét
        user = callback.get("from", {})
        telegram_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        
        message = callback.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")

        if callback_data.startswith("claim:"):
            contact_id = callback_data.split(":")[1]
            
            # 1. Frissítjük a HubSpotot
            success = update_hubspot_owner(contact_id, telegram_name)
            
            # 2. Módosítjuk az üzenetet a Telegramban
            status_text = f"✅ {telegram_name} kezeli" if success else f"⚠️ {telegram_name} vinné, de hiba történt"
            
            new_reply_markup = {"inline_keyboard": [[{"text": status_text, "callback_data": "done"}]]}
            telegram_request("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": new_reply_markup})
            telegram_request("answerCallbackQuery", {"callback_query_id": callback.get("id"), "text": "Kész!"})
    except Exception as e:
        print(f"Telegram hiba: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        if "objectId" in body or "subscriptionType" in body:
            handle_hubspot(body)
        elif "callback_query" in body:
            handle_telegram(body)
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

app = handler
