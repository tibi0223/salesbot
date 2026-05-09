import json
import os
import urllib.request
import urllib.error

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
        if isinstance(e, urllib.error.HTTPError):
            try:
                error_body = e.read().decode('utf-8')
            except:
                error_body = str(e)
            print(f"HIBA - HubSpot módosítás (Contact ID: {contact_id}): {error_body}")
            return error_body
        else:
            print(f"HIBA - HubSpot módosítás (Contact ID: {contact_id}): {e}")
            return str(e)

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

def create_hubspot_deal(contact_id, deal_name, deal_properties=None):
    """Létrehoz egy új Deal-t a HubSpotban és összeköti a kontakttal. Visszaadja a Deal ID-t."""
    if not contact_id: return None
    url = "https://api.hubapi.com/crm/v3/objects/deals"
    props = {"dealname": f"{deal_name} - Új Érdeklődő", "dealstage": DEALSTAGE_ERDEKLODO}
    if deal_properties:
        props.update({k: v for k, v in deal_properties.items() if v})
    payload = {
        "properties": props,
        "associations": [{
            "to": {"id": str(contact_id)},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
        }]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode('utf-8')).get("id")
    except Exception as e:
        print(f"HIBA - Deal letrehozas: {e}")
        return None

def get_hubspot_deal(deal_id):
    """Lekéri egy Deal adatait."""
    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=szolgaltatas_tipusa,epulet_tipusa,felmeres_idopontja"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode('utf-8')).get("properties", {})
    except:
        return None

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

def create_hubspot_note(contact_id, text, deal_id=None):
    """Létrehoz egy beépített Jegyzetet (Note) a kontakthoz és opcionálisan a dealhez."""
    if not text: return False
    url = "https://api.hubapi.com/crm/v3/objects/notes"
    associations = []
    if contact_id:
        associations.append({"to": {"id": str(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
    if deal_id:
        associations.append({"to": {"id": str(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]})
    payload = {"properties": {"hs_note_body": text, "hs_timestamp": str(int(__import__('time').time() * 1000))}, "associations": associations}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True
    except Exception as e:
        print(f"HIBA - Note letrehozas: {e}")
        return False

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
        
        # 1. Kontakt létrehozása HubSpotban (csak személyes alapmezők)
        hs_props = {
            "firstname": data.get("Keresztnév", ""),
            "lastname": data.get("Vezetéknév", ""),
            "email": email,
            "phone": phone
        }
        # Kiszedjük az üres mezőket, hogy a HubSpot ne dobjon hibát
        hs_props = {k: v for k, v in hs_props.items() if v}
        
        contact_id = create_hubspot_contact(hs_props)
        
        # Ha nem sikerült létrehozni (pl. mert már létezik), megpróbáljuk megkeresni email alapján
        if not contact_id and email:
            contact_id = search_hubspot_contact_by_email(email)

        deal_id = None
        if contact_id:
            # Deal létrehozása a szolgáltatással
            deal_props = {"szolgaltatas_tipusa": data.get("Szolgáltatás", "")}
            deal_id = create_hubspot_deal(contact_id, name, deal_props)
            # Hozzáadjuk a megjegyzést külön Note-ként (Contact-hoz és Deal-hez is)
            sheet_note = data.get("Üzenet", "").strip()
            if sheet_note:
                create_hubspot_note(contact_id, f"Üzenet az űrlapról:\n{sheet_note}", deal_id)
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
            web_data["source"] = "webapp"
            web_data["user_id"] = user_id
            handle_webapp_submission(web_data)
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

            chat_id = msg.get("chat", {}).get("id")
            message_id = msg.get("message_id")
            
            if chat_id and message_id:
                # CSOPORTBAN: Gomb lecserélése státuszra (azonnali visszajelzés a csoportnak)
                new_markup = {"inline_keyboard": [[{"text": f"✅ {t_name} kezeli", "callback_data": "done"}]]}
                telegram_request("editMessageReplyMarkup", {
                    "chat_id": chat_id, 
                    "message_id": message_id, 
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
            res = telegram_request("sendMessage", {
                "chat_id": user_id,
                "text": private_text,
                "parse_mode": "HTML",
                "reply_markup": private_markup
            })
            
            if not res and chat_id and message_id:
                # Ha nem sikerült elküldeni a privát üzenetet (pl. blokkolva van a bot)
                telegram_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": f"⚠️ <b>{t_name}</b>, nem tudtam elküldeni neked a privát űrlapot (valószínűleg blokkoltad a botot). Kérlek, keress rá a botra és nyomj egy /start -ot!",
                    "parse_mode": "HTML"
                })
                # Visszaállítjuk a gombot, hogy más is elvihesse
                reset_markup = {"inline_keyboard": [[{"text": "✋ Kézbe veszem", "callback_data": f"claim:{contact_id}"}]]}
                telegram_request("editMessageReplyMarkup", {
                    "chat_id": chat_id, 
                    "message_id": message_id, 
                    "reply_markup": reset_markup
                })

    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"HIBA - Telegram feldolgozás:\n{err_msg}")
        try:
            telegram_request("sendMessage", {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"Kritikus hiba a Telegram feldolgozásakor:\n<pre>{str(e)}</pre>",
                "parse_mode": "HTML"
            })
        except:
            pass

def handle_webapp_submission(data):
    """A Web App űrlap közvetlen beküldésének feldolgozása."""
    try:
        contact_id = data.get("contact_id")
        user_id = data.get("user_id")
        
        # --- CÍM a Contact-ra megy ---
        contact_props = {}
        if data.get("post_code"): contact_props["zip"] = data["post_code"]
        if data.get("street_address"): contact_props["address"] = data["street_address"]
        if contact_props:
            update_hubspot(contact_id, contact_props)
        
        # --- PROJEKT adatok: Mindig új Deal jön létre ---
        deal_props = {}
        if data.get("epulet_tipusa"): deal_props["epulet_tipusa"] = data["epulet_tipusa"]
        if data.get("szolgaltatas_tipusa"): deal_props["szolgaltatas_tipusa"] = data["szolgaltatas_tipusa"]
        if data.get("felmeres_idopontja"): deal_props["felmeres_idopontja"] = data["felmeres_idopontja"]
        
        contact_data = get_hubspot_contact(contact_id) or {}
        c_name = f"{contact_data.get('firstname','')} {contact_data.get('lastname','')}".strip() or "Névtelen"
        deal_id = create_hubspot_deal(contact_id, c_name, deal_props)
        update_result = deal_id is not None
        
        # Megjegyzés Note-ként (Contact-hoz ÉS Deal-hez csatolva, címmel együtt)
        note_parts = []
        if data.get("post_code") or data.get("street_address"):
            note_parts.append(f"Cím: {data.get('post_code', '')} {data.get('street_address', '')}")
        if data.get("note", "").strip():
            note_parts.append(f"Megjegyzés: {data['note'].strip()}")
        if note_parts:
            create_hubspot_note(contact_id, "Salesbot űrlap:\n" + "\n".join(note_parts), deal_id)
        
        # Deal stage frissítés felmérés időpontja esetén
        if data.get("felmeres_idopontja") and DEALSTAGE_FELMERES:
            update_deal(deal_id, {"dealstage": DEALSTAGE_FELMERES})
        
        if update_result:
            if user_id:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "✅ Az adatokat sikeresen rögzítettem a HubSpotban!"})
        else:
            if user_id:
                telegram_request("sendMessage", {"chat_id": user_id, "text": "❌ Hiba történt a HubSpot mentésnél."})
    except Exception as e:
        print(f"HIBA - Web App submission feldolgozás: {e}")

from http.server import BaseHTTPRequestHandler

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
