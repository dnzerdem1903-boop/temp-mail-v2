from fastapi import FastAPI, Request
import uvicorn
import sqlite3
import random
import string
from datetime import datetime
import telebot
import re
import requests
import asyncio

# --- AYARLAR ---
BOT_TOKEN = "8383211881:AAF5Vi78HrS29DwMQz4RIME2e2jgYp9Xg6w"
DOMAIN = "tekotpmail.xyz"
RENDER_URL = "https://temp-mail-v2-dpwj.onrender.com"
# DİKKAT: Bu API Key kesinlikle 'Full Access' yetkisiyle oluşturulmuş olmalı!
RESEND_API_KEY = "re_7q2MifzS_CGJtifF2utB2nJQioiZPYPke"

app = FastAPI()
bot = telebot.TeleBot(BOT_TOKEN)

def veritabani_kur():
    conn = sqlite3.connect("tekmail.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mailler (id INTEGER PRIMARY KEY AUTOINCREMENT, kime TEXT, kimden TEXT, konu TEXT, icerik TEXT, tarih TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (chat_id TEXT, mail_adresi TEXT)''')
    conn.commit()
    conn.close()

veritabani_kur()

def rastgele_mail_uret(uzunluk=8):
    karakterler = string.ascii_lowercase + string.digits
    rastgele_isim = ''.join(random.choice(karakterler) for _ in range(uzunluk))
    return f"{rastgele_isim}@{DOMAIN}"

@bot.message_handler(commands=['start'])
def start_mesaji(message):
    bot.reply_to(message, "Hoş geldin! Yeni bir geçici mail adresi almak için /yeni yazabilirsin.")

@bot.message_handler(commands=['yeni'])
def yeni_mail_ver(message):
    chat_id = str(message.chat.id)
    yeni_adres = rastgele_mail_uret()
    
    conn = sqlite3.connect("tekmail.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kullanicilar WHERE chat_id=?", (chat_id,))
    cursor.execute("INSERT INTO kullanicilar (chat_id, mail_adresi) VALUES (?, ?)", (chat_id, yeni_adres))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Yeni mail adresiniz oluşturuldu:\n\n`{yeni_adres}`\n\nBu adrese mail geldiğinde size anında bildireceğim!", parse_mode="Markdown")

@app.on_event("startup")
def startup_event():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/telegram-kanca")
    print("[+] Telegram Webhook başarıyla ayarlandı!")

@app.post("/telegram-kanca")
async def telegram_webhook(request: Request):
    json_str = await request.body()
    update = telebot.types.Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return {"status": "ok"}

@app.post("/gelen-mail")
async def resend_webhook(request: Request):
    veri = await request.json()

    if veri.get("type") == "email.received":
        mail_detay = veri.get("data", {})
        email_id = mail_detay.get("email_id")
        
        kime_ham = mail_detay.get("to")
        kime_str = str(kime_ham[0] if isinstance(kime_ham, list) else kime_ham).lower()
        kime_match = re.search(r'[\w\.-]+@[\w\.-]+', kime_str)
        kime = kime_match.group(0) if kime_match else kime_str

        kimden_ham = mail_detay.get("from")
        kimden_str = str(kimden_ham[0] if isinstance(kimden_ham, list) else kimden_ham)
        kimden_match = re.search(r'[\w\.-]+@[\w\.-]+', kimden_str)
        kimden = kimden_match.group(0) if kimden_match else kimden_str
        
        konu = mail_detay.get("subject", "Konu Yok")
        icerik = mail_detay.get("text") or mail_detay.get("html")
        
        if (not icerik or icerik == "Mail içeriği boş.") and email_id and RESEND_API_KEY:
            await asyncio.sleep(2) # Resend'in maili işlemesi için 2 saniye bekle
            try:
                headers = {"Authorization": f"Bearer {RESEND_API_KEY}"}
                r = requests.get(f"https://api.resend.com/emails/{email_id}", headers=headers, timeout=10)
                if r.status_code == 200:
                    email_verisi = r.json()
                    icerik = email_verisi.get("text") or email_verisi.get("html")
                else:
                    print(f"[-] API Hatası: {r.status_code} - {r.text}")
            except Exception as e:
                print(f"[-] Resend API Bağlantı Hatası: {e}")

        # 2026 TUZAĞI BURADA BOZULDU: Artık JSON verisini string'e çevirip kaydetmiyoruz.
        if not icerik:
            icerik = "HATA: Mail godesi cekilemedi. Resend API Key 'Full Access' yetkisine sahip mi kontrol et."

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect("tekmail.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mailler (kime, kimden, konu, icerik, tarih) VALUES (?, ?, ?, ?, ?)", 
                       (kime, kimden, konu, str(icerik), tarih))
        
        cursor.execute("SELECT chat_id FROM kullanicilar WHERE mail_adresi=?", (kime,))
        kullanici = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if kullanici:
            chat_id = kullanici[0]
            mesaj_metni = (
                f"📬 *YENİ MAİL GELDİ!*\n\n"
                f"👤 *Kimden:* `{kimden}`\n"
                f"🎯 *Kime:* `{kime}`\n"
                f"📌 *Konu:* {konu}\n\n"
                f"📝 *İçerik:*\n{str(icerik)[:1000]}"
            )
            try:
                bot.send_message(chat_id, mesaj_metni, parse_mode="Markdown")
            except Exception as e:
                pass
            
    return {"durum": "basarili"}

@app.get("/api/yeni-mail")
def api_yeni_mail():
    return {"mail_adresi": rastgele_mail_uret()}

@app.get("/api/oku/{mail_adresi}")
def api_mail_oku(mail_adresi: str):
    conn = sqlite3.connect("tekmail.db")
    cursor = conn.cursor()
    cursor.execute("SELECT kimden, konu, icerik, tarih FROM mailler WHERE kime=? ORDER BY id DESC", (mail_adresi.lower(),))
    mailler = cursor.fetchall()
    conn.close()
    
    sonuclar = [{"kimden": m[0], "konu": m[1], "icerik": m[2], "tarih": m[3]} for m in mailler]
    return {"durum": "basarili", "gelen_kutusu": sonuclar}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)