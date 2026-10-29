from fastapi import FastAPI, Request
import uvicorn
import sqlite3
import random
import string
from datetime import datetime
import telebot
import re  # <--- METİN AYIKLAMAK İÇİN YENİ EKLENDİ

# --- AYARLAR ---
BOT_TOKEN = "BURAYA_BOTFATHERDAN_ALDIĞIN_TOKENI_YAPIŞTIR"
DOMAIN = "tekmail.xyz"
RENDER_URL = "https://temp-mail-v2-dpwj.onrender.com" 

app = FastAPI()
bot = telebot.TeleBot(BOT_TOKEN)

# 1. VERİTABANI KURULUMU
def veritabani_kur():
    conn = sqlite3.connect("tekmail.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mailler (id INTEGER PRIMARY KEY AUTOINCREMENT, kime TEXT, kimden TEXT, konu TEXT, icerik TEXT, tarih TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (chat_id TEXT, mail_adresi TEXT)''')
    conn.commit()
    conn.close()

veritabani_kur()

# 2. RASTGELE MAİL ÜRETİCİ
def rastgele_mail_uret(uzunluk=8):
    karakterler = string.ascii_lowercase + string.digits
    rastgele_isim = ''.join(random.choice(karakterler) for _ in range(uzunluk))
    return f"{rastgele_isim}@{DOMAIN}"

# 3. TELEGRAM MESAJ CEVAPLARI
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

# 4. SİSTEM BAŞLARKEN TELEGRAM'A KANCAYI AT
@app.on_event("startup")
def startup_event():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/telegram-kanca")
    print("[+] Telegram Webhook başarıyla ayarlandı!")

# 5. TELEGRAM'DAN GELEN KOMUTLARI BURADA YAKALIYORUZ
@app.post("/telegram-kanca")
async def telegram_webhook(request: Request):
    json_str = await request.body()
    update = telebot.types.Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return {"status": "ok"}

# 6. RESEND'DEN GELEN MAİLLERİ BURADA YAKALIYORUZ
@app.post("/gelen-mail")
async def resend_webhook(request: Request):
    veri = await request.json()

    if veri.get("type") == "email.received":
        mail_detay = veri.get("data", {})
        
        # KİME KISMINI TEMİZLEME (Regex ile sadece saf e-posta adresini alıyoruz)
        kime_ham = mail_detay.get("to")
        kime_str = str(kime_ham[0] if isinstance(kime_ham, list) else kime_ham).lower()
        kime_match = re.search(r'[\w\.-]+@[\w\.-]+', kime_str)
        kime = kime_match.group(0) if kime_match else kime_str

        # KİMDEN KISMINI TEMİZLEME
        kimden_ham = mail_detay.get("from")
        kimden_str = str(kimden_ham[0] if isinstance(kimden_ham, list) else kimden_ham)
        kimden_match = re.search(r'[\w\.-]+@[\w\.-]+', kimden_str)
        kimden = kimden_match.group(0) if kimden_match else kimden_str
        
        konu = mail_detay.get("subject", "Konu Yok")
        
        icerik_ham = mail_detay.get("text") or mail_detay.get("html") or "Mail içeriği boş."
        icerik = str(icerik_ham)
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n[+] Mail İşleniyor... Hedef: {kime}")
        
        conn = sqlite3.connect("tekmail.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mailler (kime, kimden, konu, icerik, tarih) VALUES (?, ?, ?, ?, ?)", 
                       (kime, kimden, konu, icerik, tarih))
        
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
                f"📝 *İçerik:*\n{icerik[:1000]}"
            )
            try:
                bot.send_message(chat_id, mesaj_metni, parse_mode="Markdown")
                print("[+] Telegram mesajı başarıyla gönderildi!")
            except Exception as e:
                print(f"[-] Telegram gönderim hatası: {e}")
        else:
            print(f"[-] DİKKAT: Veritabanında '{kime}' adresi için kayıtlı kullanıcı bulunamadı!")
            
    return {"durum": "basarili"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)