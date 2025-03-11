import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler
import yt_dlp
import os
import time
from flask import Flask, request
import threading

# Durumlar
CHOOSE_QUALITY, GET_TRIM, BULK_MODE = range(3)

# Bot token'ı
TOKEN = "7922647331:AAFTXWyzVRL4pqjVsbUbRDDFrUD-vq8xVuU"
WEBHOOK_URL = "https://videokap.onrender.com/webhook"  # Deploy sonrası Render URL’ni buraya yaz

# Flask app
app = Flask(__name__)

# Bot ve Dispatcher
bot = telegram.Bot(TOKEN)
dispatcher = None

# Video indirme fonksiyonu
def download_video(update, url, quality=None, trim=None):
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
            if percent >= 50 and not update.message.chat.bot_data.get('50_reported'):
                update.message.reply_text("%50 bitti... Sabret biraz.")
                update.message.chat.bot_data['50_reported'] = True
            elif percent >= 80 and not update.message.chat.bot_data.get('80_reported'):
                update.message.reply_text("%80 oldu... Az kaldı la.")
                update.message.chat.bot_data['80_reported'] = True

    update.message.chat.bot_data['50_reported'] = False
    update.message.chat.bot_data['80_reported'] = False

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best' if not quality else quality,
        'outtmpl': f'video_{int(time.time())}.%(ext)s',
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
    }
    if trim:
        start, end = trim.split('-')
        start_sec = sum(x * int(t) for x, t in zip([3600, 60, 1], start.split(':')))
        end_sec = sum(x * int(t) for x, t in zip([3600, 60, 1], end.split(':')))
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractSubclip',
            'start_time': start_sec,
            'end_time': end_sec,
        }]
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return next(f for f in os.listdir('.') if f.startswith('video_') and f.endswith('.mp4'))
    except Exception as e:
        update.message.reply_text(f"La bi’ hata oldu: {str(e)}. Linki kontrol et!")
        return None

# Komutlar ve İşleyiciler
def start(update, context):
    update.message.reply_text(
        "Selam la, VideoKap burda!\n"
        "Bi’ sosyal medya linki at, videoyu kapıp geleyim.\n"
        "Ne yapacan bilmiyosan /yardim yaz, anlatırım.\n"
        "Hadi la, boş durma!"
    )

def help_command(update, context):
    update.message.reply_text(
        "Ne yapacan bilmiyosan buraya bak la:\n"
        "/basla - VideoKap’ı uyandırırım, iş başlar.\n"
        "/toplu - Bi’ sürü link at, hepsini kapayım.\n"
        "/kes - Videoyu doğrarım, nerden nereye istiyon söyle.\n"
        "Link atarsan direk başlarım:\n"
        "- YouTube’da kalite sorarım,\n"
        "- Diğerlerinde maksimum kaliteyi çakarım.\n"
        "Hala anlamadıysan bi’ daha sor la, üşenmem!"
    )

def handle_link(update, context):
    url = update.message.text
    if context.user_data.get('bulk'):
        context.user_data['urls'].append(url)
        update.message.reply_text(f"{len(context.user_data['urls'])}. linki aldım la, devam mı? /bitir yazarsan başlarım.")
        return BULK_MODE
    if "youtube.com" in url or "youtu.be" in url:
        update.message.reply_text(
            "Bu YouTube la, kaliteyi sen seç:\n"
            "1. 720p - idare eder\n"
            "2. 1080p - mis gibi net\n"
            "3. MP3 - sadece ses alırım\n"
            "Hangisi olacak la, bi’ numara yaz!"
        )
        context.user_data['url'] = url
        return CHOOSE_QUALITY
    else:
        update.message.reply_text("Bu YouTube değil la, maksimum kaliteyle indiriyorum.")
        filename = download_video(update, url)
        if filename:
            with open(filename, 'rb') as video:
                update.message.reply_video(video, caption="Buyur la, VideoKap kaptı getirdi. 🎥")
            os.remove(filename)
        return ConversationHandler.END

def choose_quality(update, context):
    choice = update.message.text
    url = context.user_data['url']
    trim = context.user_data.get('trim')
    quality_map = {'1': 'best[height<=720]', '2': 'best[height<=1080]', '3': 'bestaudio/best'}
    if choice not in quality_map:
        update.message.reply_text("La oğlum, 1-2-3 var, ne yazdın sen? Düzgün bi’ şey yaz!")
        return CHOOSE_QUALITY
    update.message.reply_text("Tamam la, indiriyorum.")
    filename = download_video(update, url, quality_map[choice], trim)
    if filename:
        with open(filename, 'rb') as video:
            update.message.reply_video(video, caption="Al la, VideoKap işini gördü. 🎥")
        os.remove(filename)
    context.user_data.clear()
    return ConversationHandler.END

def bulk_download(update, context):
    update.message.reply_text(
        "Hooop, toplu iş mi istiyon la?\n"
        "Linkleri peş peşe at, VideoKap sırayla kapar.\n"
        "10 tane yeter, /bitir yazarsan indiririm."
    )
    context.user_data['bulk'] = True
    context.user_data['urls'] = []

def bulk_finish(update, context):
    if not context.user_data.get('bulk') or not context.user_data['urls']:
        update.message.reply_text("La önce /toplu de, link at, neyi bitireyim?")
        return ConversationHandler.END
    update.message.reply_text(f"{len(context.user_data['urls'])} link aldım la, başlıyorum:")
    for i, url in enumerate(context.user_data['urls'], 1):
        update.message.reply_text(f"{i}. link işleniyor la...")
        if "youtube.com" in url or "youtu.be" in url:
            update.message.reply_text(
                "Bu YouTube la, kaliteyi sen seç:\n"
                "1. 720p - idare eder\n"
                "2. 1080p - mis gibi net\n"
                "3. MP3 - sadece ses alırım\n"
                "Hangisi olacak la, bi’ numara yaz!"
            )
            context.user_data['url'] = url
            context.user_data['bulk_index'] = i
            return CHOOSE_QUALITY
        else:
            filename = download_video(update, url)
            if filename:
                with open(filename, 'rb') as video:
                    update.message.reply_video(video, caption=f"{i}. video tamam la! 🎥")
                os.remove(filename)
    context.user_data.clear()
    update.message.reply_text("Hepsini hallettik la, başka işin var mı?")
    return ConversationHandler.END

def trim_video(update, context):
    update.message.reply_text(
        "Videoyu kesecem la, neyi istiyon?\n"
        "Önce nerden nereye keseyim söyle, mesela '0:10-0:30' gibi yaz.\n"
        "Sonra linki at, VideoKap halleder."
    )
    return GET_TRIM

def get_trim(update, context):
    text = update.message.text
    if '-' in text and not context.user_data.get('trim'):
        context.user_data['trim'] = text
        update.message.reply_text("Tamam la, şimdi linki at!")
        return GET_TRIM
    else:
        context.user_data['url'] = text
        if "youtube.com" in text or "youtu.be" in text:
            update.message.reply_text(
                "YouTube mu la? Kaliteyi seç:\n"
                "1. 720p - idare eder\n"
                "2. 1080p - mis gibi net"
            )
            return CHOOSE_QUALITY
        else:
            update.message.reply_text("Bu YouTube değil la, maksimum kaliteyle kesip indiriyorum.")
            filename = download_video(update, text, trim=context.user_data['trim'])
            if filename:
                with open(filename, 'rb') as video:
                    update.message.reply_video(video, caption="Al la, VideoKap tam istediğin gibi yaptı. 🎥")
                os.remove(filename)
            context.user_data.clear()
            return ConversationHandler.END

def unknown(update, context):
    update.message.reply_text("Selamla işim yok la, video linki at! VideoKap boş muhabbet çevirmez.")

# Webhook işleme
@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'OK'

# Botu başlatma
def setup_bot():
    global dispatcher
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, handle_link),
                      CommandHandler('kes', trim_video),
                      CommandHandler('toplu', bulk_download)],
        states={
            CHOOSE_QUALITY: [MessageHandler(Filters.text & ~Filters.command, choose_quality)],
            GET_TRIM: [MessageHandler(Filters.text & ~Filters.command, get_trim)],
            BULK_MODE: [CommandHandler('bitir', bulk_finish),
                        MessageHandler(Filters.text & ~Filters.command, handle_link)],
        },
        fallbacks=[MessageHandler(Filters.text & ~Filters.command, unknown)]
    )

    dispatcher.add_handler(CommandHandler("basla", start))
    dispatcher.add_handler(CommandHandler("yardim", help_command))
    dispatcher.add_handler(conv_handler)

    bot.set_webhook(WEBHOOK_URL)

# Flask server’ı başlatma
if __name__ == "__main__":
    setup_bot()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) 
