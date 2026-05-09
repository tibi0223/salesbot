from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

# --- BEÁLLÍTÁSOK ---
# A környezeti változókat a Vercel felületén kell beállítani
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
DEALSTAGE_ERDEKLODO = "5143666925"
DEALSTAGE_FELMERES = "5143666926"
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

def create_hubspot_contact(properties):
    """Létrehoz egy új HubSpot kontaktot (Google Sheet trigger esetén)."""
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    req = urllib.request.Request(url, data=json.dumps({"properties": properties}).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode('utf-8')).get("id")
    except Exception as e:
        print(f"HIBA - HubSpot letrehozás: {e}")
        return None

def search_hubspot_contact_by_email(email):
    """Megkeresi a kontaktot email alapján, ha már létezik."""
    if not email:
        return None
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            results = data.get("results", [])
            if results:
                return str(results[0].get("id"))
    except Exception as e:
        print(f"HIBA - Kontakt keresés: {e}")
    return None

def create_hubspot_deal(contact_id, deal_name):
    """Létrehoz egy új Deal-t a HubSpotban és összeköti a kontakttal."""
    if not contact_id: return False
    url = "https://api.hubapi.com/crm/v3/objects/deals"
    payload = {
        "properties": {
            "dealname": f"{deal_name} - Új Érdeklődő",
            "dealstage": DEALSTAGE_ERDEKLODO
        },
        "associations": [
            {
                "to": {"id": str(contact_id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}] # Deal to Contact
            }
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True
    except Exception as e:
        print(f"HIBA - Deal letrehozas: {e}")
        return False

def get_associated_deals(contact_id):
    """Lekéri egy kontakthoz tartozó Deal-ek ID-ját."""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/deals"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode('utf-8'))
            return [res['id'] for res in data.get('results', [])]
    except Exception as e:
        print(f"HIBA - Dealek lekerese: {e}")
        return []

def update_deal(deal_id, properties):
    """Frissíti a Deal állapotát (pl. pipeline stage)."""
    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}"
    req = urllib.request.Request(url, data=json.dumps({"properties": properties}).encode("utf-8"), method="PATCH",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True
    except Exception as e:
        print(f"HIBA - Deal frissites: {e}")
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

def handle_google_sheet(data):
    """Google Sheet webhook feldolgozása (új lead érkezése)."""
    try:
        name = data.get("Teljes név", "") or f'{data.get("Vezetéknév", "")} {data.get("Keresztnév", "")}'.strip() or "Névtelen Lead"
        email = data.get("Email", "")
        phone = data.get("Telefonszám", "")
        
        # --- DIAGNOSZTIKA: Azonnal szólunk a Telegramon ---
        telegram_request("sendMessage", {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": f"🔄 <b>Feldolgozás elindult...</b>\nEmail: {email or 'Nincs'}\nKérlek, várj pár másodpercet!",
            "parse_mode": "HTML"
        })
        
        # 1. Kontakt létrehozása HubSpotban (csak biztonságos alapmezők)
        hs_props = {
            "firstname": data.get("Keresztnév", ""),
            "lastname": data.get("Vezetéknév", ""),
            "email": email,
            "phone": phone,
            "lead_megjegyzes": f"Szolgáltatás: {data.get('Szolgáltatás', '')} | Üzenet: {data.get('Üzenet', '')}"
        }
        # Kiszedjük az üres mezőket, hogy a HubSpot ne dobjon hibát
        hs_props = {k: v for k, v in hs_props.items() if v}
        
        contact_id = create_hubspot_contact(hs_props)
        
        # Ha nem sikerült létrehozni (pl. mert már létezik), megpróbáljuk megkeresni email alapján
        if not contact_id and email:
            contact_id = search_hubspot_contact_by_email(email)
            # Direkt KIVETTÜK az update_hubspot hívást a gyorsítás és stabilitás miatt!

        if contact_id:
            # Létrehozzuk a Dealt (Érdeklődő szakaszba kerül alapból) a régi vagy új kontakthoz
            create_hubspot_deal(contact_id, name)
        else:
            print("Nem sikerült létrehozni/megtalálni a kontaktot a HubSpotban, de a Telegram üzenet kimegy!")

        # 2. Telegram értesítés
        text = (
            f"🔥 <b>Új Lead érkezett (Google Sheetből)!</b>\n\n"
            f"👤 <b>Név:</b> {name}\n"
            f"📧 <b>Email:</b> {email or '–'}\n"
            f"📞 <b>Telefon:</b> {phone or '–'}\n"
            f"🔧 <b>Szolgáltatás:</b> {data.get('Szolgáltatás', '–')}\n"
            f"💬 <b>Üzenet:</b> {data.get('Üzenet', '–')}\n\n"
            f'🔗 <a href="https://app.hubspot.com/contacts/contact/{contact_id}">Megnyitás HubSpotban</a>'
        )
        
        
        if contact_id:
            markup = {"inline_keyboard": [[{"text": "✋ Kézbe veszem", "callback_data": f"claim:{contact_id}"}]]}
        else:
            markup = {"inline_keyboard": [[{"text": "⚠️ Hiba a HubSpotnál (Nincs ID)", "callback_data": "error"}]]}
            
        telegram_request("sendMessage", {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": text, 
            "parse_mode": "HTML", 
            "reply_markup": markup
        })
    except Exception as e:
        print(f"HIBA - Google Sheet feldolgozás: {e}")

def handle_telegram(body_str):
    """Telegram üzenetek és Web App válaszok feldolgozása."""
    try:
        data = json.loads(body_str)
        
        # 1. Web App adat érkezése (Privát chatben kitöltött űrlap)
        if "message" in data and "web_app_data" in data["message"]:
            user_id = data["message"]["from"]["id"]
            web_data = json.loads(data["message"]["web_app_data"]["data"])
            contact_id = web_data.get("contact_id")
            
            # A HubSpot belső nevei
            props = {
                "epulet_tipusa": web_data.get("epulet_tipusa"),
                "szolgaltatas_tipusa": web_data.get("szolgaltatas_tipusa"),
                "zip": web_data.get("post_code"),
                "address": web_data.get("street_address"),
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

            # Lekérjük az ügyfél adatait a privát üzenethez
            props = get_hubspot_contact(contact_id) or {}
            c_name = f"{props.get('firstname','')} {props.get('lastname','')}".strip() or "Névtelen Lead"
            c_email = props.get('email', '–')
            c_phone = props.get('phone', '–')

            # PRIVÁTBAN: Az űrlap kiküldése az adatokkal
            private_text = (
                f"📋 <b>Adatlap kitöltése</b>\n\n"
                f"👤 <b>Név:</b> {c_name}\n"
                f"📧 <b>Email:</b> {c_email}\n"
                f"📞 <b>Telefon:</b> {c_phone}\n\n"
                f"Kérlek, add meg a részleteket az alábbi gombbal:"
            )
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
            "epulet_tipusa": data.get("epulet_tipusa"),
            "szolgaltatas_tipusa": data.get("szolgaltatas_tipusa"),
            "zip": data.get("post_code"),
            "address": data.get("street_address"),
            "lead_megjegyzes": data.get("note"),
            "felmeres_idopontja": data.get("felmeres_idopontja")
        }

        # Csak a kitöltött mezőket küldjük
        props = {k: v for k, v in props.items() if v}
        
        if update_hubspot(contact_id, props):
            if user_id:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "✅ Az adatokat sikeresen rögzítettem a HubSpotban!"})
                
            # Ha van felmérés időpontja, frissítjük a hozzá tartozó Deal állapotát is
            if felmeres and DEALSTAGE_FELMERES:
                deals = get_associated_deals(contact_id)
                for deal_id in deals:
                    update_deal(deal_id, {"dealstage": DEALSTAGE_FELMERES})
                    
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

        # Eldönti, hogy HubSpot webhook, Web App submission, Google Sheet vagy Telegram üzenet érkezett-e
        if isinstance(data, list) or "objectId" in data or "subscriptionType" in data:
            handle_hubspot(body_str)
        elif data.get("source") == "webapp":
            handle_webapp_submission(data)
        elif data.get("source") == "google_sheet" or "Teljes név" in data or "Beküldés ideje" in data:
            handle_google_sheet(data)
        else:
            handle_telegram(body_str)
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

app = handler
