from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

# Resend'in gelen mailleri fırlatacağı uç nokta
@app.post("/gelen-mail")
async def resend_webhook(request: Request):
    # Resend'den gelen paketi açıyoruz
    veri = await request.json()
    
    # Gelen paketin türü "yeni mail" ise işleme alıyoruz
    if veri.get("type") == "email.received":
        mail_detay = veri.get("data", {})
        
        kimden = mail_detay.get("from")
        kime = mail_detay.get("to") # Bu senin ürettiğin geçici adres olacak
        konu = mail_detay.get("subject")
        icerik = mail_detay.get("text") or mail_detay.get("html")
        
        print(f"\n[+] YENİ MAİL YAKALANDI!")
        print(f" -> Kime Geldi: {kime}")
        print(f" -> Kimden: {kimden}")
        print(f" -> Konu: {konu}")
        print(f" -> İçerik: {icerik[:200]}...") # Ekrana çok taşmasın diye ilk 200 karakter
        
        # İleride burada bu verileri alıp SQLite veritabanına kaydedeceğiz
        
    return {"durum": "basarili", "mesaj": "Resend paketi alindi"}

if __name__ == "__main__":
    # VPS'in IP adresi üzerinden 8000 portunu dış dünyaya açıyoruz
    uvicorn.run(app, host="0.0.0.0", port=8000)