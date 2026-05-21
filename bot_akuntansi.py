#!/usr/bin/env python3
import os, json, logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DB_FILE = "data_akuntansi.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {"modal": 0, "transaksi": []}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def hitung_saldo(data):
    return data["modal"] - sum(t["jumlah"] for t in data["transaksi"])

def rp(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

def tgl(iso_str):
    try:
        return datetime.fromisoformat(iso_str).strftime("%d/%m/%Y %H:%M")
    except:
        return iso_str

SET_MODAL, INPUT_KETERANGAN, INPUT_JUMLAH, INPUT_FOTO = range(4)

def kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Saldo"), KeyboardButton("📊 Pengeluaran")],
        [KeyboardButton("➕ Catat Pengeluaran"), KeyboardButton("🖼️ Bukti Foto")],
        [KeyboardButton("📋 Transaksi Hari Ini"), KeyboardButton("⚙️ Atur Modal")],
    ], resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    saldo = hitung_saldo(data)
    if data["modal"] == 0:
        ket = "⚠️ *Modal belum diatur!*\nKetuk tombol *⚙️ Atur Modal* di bawah."
    else:
        ket = f"💼 Modal: *{rp(data['modal'])}*\n💵 Saldo: *{rp(saldo)}*"
    await update.message.reply_text(
        f"👋 *Selamat datang di Bot Akuntansi Harian!*\n\n{ket}",
        parse_mode="Markdown", reply_markup=kb()
    )

async def atur_modal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    modal_skrg = rp(data["modal"]) if data["modal"] > 0 else "Belum diatur"
    await update.message.reply_text(
        f"⚙️ *Atur Modal*\n\nModal saat ini: *{modal_skrg}*\n\nKetik jumlah modal (angka saja):\nContoh: `200000`",
        parse_mode="Markdown"
    )
    return SET_MODAL

async def set_modal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        jumlah = int(float(teks))
        if jumlah <= 0: raise ValueError()
        data = load_data()
        data["modal"] = jumlah
        save_data(data)
        await update.message.reply_text(
            f"✅ *Modal berhasil diatur!*\n\n💼 Modal: *{rp(jumlah)}*\n💵 Saldo: *{rp(hitung_saldo(data))}*",
            parse_mode="Markdown", reply_markup=kb()
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Angka tidak valid! Contoh: `200000`", parse_mode="Markdown")
        return SET_MODAL

async def catat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if data["modal"] == 0:
        await update.message.reply_text("⚠️ Atur modal dulu! Ketuk *⚙️ Atur Modal*", parse_mode="Markdown")
        return ConversationHandler.END
    saldo = hitung_saldo(data)
    if saldo <= 0:
        await update.message.reply_text(f"❌ Saldo habis! Saldo: *{rp(saldo)}*", parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text(
        f"➕ *Catat Pengeluaran*\n\n💵 Saldo tersedia: *{rp(saldo)}*\n\nKetik *keterangan* pengeluaran:\nContoh: `Beli sayur`",
        parse_mode="Markdown"
    )
    return INPUT_KETERANGAN

async def input_keterangan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["keterangan"] = update.message.text.strip()
    await update.message.reply_text(
        f"📝 Keterangan: *{context.user_data['keterangan']}*\n\nKetik *jumlah* pengeluaran:\nContoh: `50000`",
        parse_mode="Markdown"
    )
    return INPUT_JUMLAH

async def input_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        jumlah = int(float(teks))
        if jumlah <= 0: raise ValueError()
        data = load_data()
        saldo = hitung_saldo(data)
        if jumlah > saldo:
            await update.message.reply_text(f"❌ Melebihi saldo! Saldo: *{rp(saldo)}*\nMasukkan jumlah lain:", parse_mode="Markdown")
            return INPUT_JUMLAH
        context.user_data["jumlah"] = jumlah
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📷 Kirim Foto Bukti", callback_data="dengan_foto")],
            [InlineKeyboardButton("✅ Simpan Tanpa Foto", callback_data="tanpa_foto")],
            [InlineKeyboardButton("❌ Batal", callback_data="batal")],
        ])
        await update.message.reply_text(
            f"💰 *Ringkasan:*\n\n📝 {context.user_data['keterangan']}\n💵 {rp(jumlah)}\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nAda bukti foto?",
            parse_mode="Markdown", reply_markup=keyboard
        )
        return INPUT_FOTO
    except:
        await update.message.reply_text("❌ Angka tidak valid! Contoh: `50000`", parse_mode="Markdown")
        return INPUT_JUMLAH

async def callback_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "batal":
        await query.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END
    elif query.data == "tanpa_foto":
        await simpan(query, context, None)
        return ConversationHandler.END
    elif query.data == "dengan_foto":
        await query.edit_message_text("📷 *Kirim foto bukti sekarang:*", parse_mode="Markdown")
        return INPUT_FOTO

async def input_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await simpan_msg(update.message, context, update.message.photo[-1].file_id)
        return ConversationHandler.END
    await update.message.reply_text("❌ Kirim file foto. Coba lagi:")
    return INPUT_FOTO

async def simpan(query, context, foto_id):
    data = load_data()
    t = {"id": len(data["transaksi"])+1, "keterangan": context.user_data.get("keterangan","-"),
         "jumlah": context.user_data.get("jumlah",0), "waktu": datetime.now().isoformat(), "foto_id": foto_id}
    data["transaksi"].append(t)
    save_data(data)
    saldo = hitung_saldo(data)
    total = sum(x["jumlah"] for x in data["transaksi"])
    await query.edit_message_text(
        f"✅ *Tersimpan!*\n\n📝 {t['keterangan']}\n💵 {rp(t['jumlah'])}\n{'📷 Foto: ✅' if foto_id else '📷 Foto: ❌'}\n\n━━━━━━━━━━\n💼 Modal: *{rp(data['modal'])}*\n📉 Pengeluaran: *{rp(total)}*\n💰 *Saldo: {rp(saldo)}*",
        parse_mode="Markdown"
    )

async def simpan_msg(message, context, foto_id):
    data = load_data()
    t = {"id": len(data["transaksi"])+1, "keterangan": context.user_data.get("keterangan","-"),
         "jumlah": context.user_data.get("jumlah",0), "waktu": datetime.now().isoformat(), "foto_id": foto_id}
    data["transaksi"].append(t)
    save_data(data)
    saldo = hitung_saldo(data)
    total = sum(x["jumlah"] for x in data["transaksi"])
    await message.reply_text(
        f"✅ *Tersimpan + Foto!*\n\n📝 {t['keterangan']}\n💵 {rp(t['jumlah'])}\n📷 Foto: ✅\n\n━━━━━━━━━━\n💼 Modal: *{rp(data['modal'])}*\n📉 Pengeluaran: *{rp(total)}*\n💰 *Saldo: {rp(saldo)}*",
        parse_mode="Markdown", reply_markup=kb()
    )

async def menu_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    saldo = hitung_saldo(data)
    total = sum(t["jumlah"] for t in data["transaksi"])
    hari_ini = date.today().isoformat()
    hari_ini_total = sum(t["jumlah"] for t in data["transaksi"] if t["waktu"].startswith(hari_ini))
    if data["modal"] > 0:
        persen = saldo / data["modal"] * 100
        status = "🟢 Aman" if persen > 50 else "🟡 Perhatian" if persen > 20 else "🔴 Kritis"
        bar = "█" * int(persen/10) + "░" * (10 - int(persen/10))
    else:
        persen, status, bar = 0, "⚠️ Modal belum diatur", "░░░░░░░░░░"
    await update.message.reply_text(
        f"💰 *SALDO REAL-TIME*\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"💼 Modal: *{rp(data['modal'])}*\n📉 Total Pengeluaran: *{rp(total)}*\n📅 Hari Ini: *{rp(hari_ini_total)}*\n\n━━━━━━━━━━\n"
        f"💵 *SALDO: {rp(saldo)}*\n{status}\n[{bar}] {persen:.1f}%",
        parse_mode="Markdown"
    )

async def menu_pengeluaran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["transaksi"]:
        await update.message.reply_text("📊 Belum ada transaksi.", parse_mode="Markdown")
        return
    total = sum(t["jumlah"] for t in data["transaksi"])
    per_hari = {}
    for t in data["transaksi"]:
        tgl_key = t["waktu"][:10]
        per_hari[tgl_key] = per_hari.get(tgl_key, 0) + t["jumlah"]
    pesan = f"📊 *LAPORAN PENGELUARAN*\n\n💼 Modal: *{rp(data['modal'])}*\n💰 Saldo: *{rp(hitung_saldo(data))}*\n📉 Total: *{rp(total)}*\n🔢 Transaksi: *{len(data['transaksi'])}x*\n\n━━━━━━━━━━\n📅 *Per Hari:*\n"
    for k in sorted(per_hari.keys(), reverse=True)[:7]:
        label = datetime.strptime(k, "%Y-%m-%d").strftime("%d %b %Y")
        pesan += f"• {label}: *{rp(per_hari[k])}*\n"
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def menu_transaksi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    hari_ini = date.today().isoformat()
    list_hari = [t for t in data["transaksi"] if t["waktu"].startswith(hari_ini)]
    if not list_hari:
        await update.message.reply_text(f"📋 *Transaksi Hari Ini*\n📅 {date.today().strftime('%d %B %Y')}\n\nBelum ada transaksi.", parse_mode="Markdown")
        return
    total = sum(t["jumlah"] for t in list_hari)
    pesan = f"📋 *TRANSAKSI HARI INI*\n📅 {date.today().strftime('%d %B %Y')}\n\n"
    for i, t in enumerate(list_hari, 1):
        waktu = datetime.fromisoformat(t["waktu"]).strftime("%H:%M")
        foto = "📷" if t.get("foto_id") else "  "
        pesan += f"{i}. {foto} *{t['keterangan']}*\n    💵 {rp(t['jumlah'])} | ⏰ {waktu}\n\n"
    pesan += f"━━━━━━━━━━\n📉 Total: *{rp(total)}*\n💰 Saldo: *{rp(hitung_saldo(data))}*"
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def menu_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    dengan_foto = [t for t in data["transaksi"] if t.get("foto_id")]
    if not dengan_foto:
        await update.message.reply_text("🖼️ Belum ada bukti foto.", parse_mode="Markdown")
        return
    await update.message.reply_text(f"🖼️ *BUKTI FOTO* — {len(dengan_foto)} foto\nMenunjukkan 5 terbaru...", parse_mode="Markdown")
    for t in dengan_foto[-5:]:
        try:
            await update.message.reply_photo(
                photo=t["foto_id"],
                caption=f"📝 *{t['keterangan']}*\n💵 {rp(t['jumlah'])}\n📅 {tgl(t['waktu'])}",
                parse_mode="Markdown"
            )
        except:
            pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Dibatalkan.", reply_markup=kb())
    return ConversationHandler.END

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text
    if teks == "💰 Saldo": await menu_saldo(update, context)
    elif teks == "📊 Pengeluaran": await menu_pengeluaran(update, context)
    elif teks == "📋 Transaksi Hari Ini": await menu_transaksi(update, context)
    elif teks == "🖼️ Bukti Foto": await menu_foto(update, context)
    else: await update.message.reply_text("Gunakan tombol menu di bawah atau ketik /start", reply_markup=kb())

def main():
    TOKEN = "8849771737:AAH2xQJTg5lTAKcOaDtdcFwEpH7CbuV60qg"
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚙️ Atur Modal$"), atur_modal_start), CommandHandler("modal", atur_modal_start)],
        states={SET_MODAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_modal)]},
        fallbacks=[CommandHandler("batal", cancel)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Catat Pengeluaran$"), catat_start), CommandHandler("catat", catat_start)],
        states={
            INPUT_KETERANGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_keterangan)],
            INPUT_JUMLAH: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_jumlah)],
            INPUT_FOTO: [CallbackQueryHandler(callback_foto, pattern="^(dengan_foto|tanpa_foto|batal)$"), MessageHandler(filters.PHOTO, input_foto)],
        },
        fallbacks=[CommandHandler("batal", cancel)],
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot Akuntansi berjalan! Tekan Ctrl+C untuk berhenti.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
