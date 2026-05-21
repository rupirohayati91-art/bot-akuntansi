#!/usr/bin/env python3
import os, json, logging, re
from datetime import datetime, date
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8849771737:AAH2xQJTg5lTAKcOaDtdcFwEpH7CbuV60qg")
DB_FILE = "data_akuntansi.json"

# ─── Database ─────────────────────────────────────────────────────────────────
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def get_user(uid):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {"saldo": 0, "transaksi": []}
        save_db(db)
    return db[uid]

def save_user(uid, data):
    db = load_db()
    db[str(uid)] = data
    save_db(db)

def rp(angka):
    return f"Rp {int(angka):,}".replace(",", ".")

def parse_nominal(teks):
    """Parse nominal: 50k, 50rb, 50ribu, 50000"""
    teks = teks.lower().strip()
    teks = teks.replace("ribu", "000").replace("rb", "000").replace("k", "000")
    teks = re.sub(r"[^0-9]", "", teks)
    return int(teks) if teks else 0

def waktu_sekarang():
    now = datetime.now()
    hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    return f"{hari[now.weekday()]}, {now.strftime('%d/%m/%Y %H:%M')}"

SET_MODAL, INPUT_KET, INPUT_JML, INPUT_FOTO, KONFIRM_RESET, KELUAR_FOTO = range(6)

# ─── Keyboard ─────────────────────────────────────────────────────────────────
def kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Saldo"), KeyboardButton("➕ Tambah Saldo")],
        [KeyboardButton("🛒 Catat Pengeluaran"), KeyboardButton("🖼️ Bukti Foto")],
        [KeyboardButton("📋 Transaksi Hari Ini"), KeyboardButton("📅 Bulanan")],
        [KeyboardButton("📊 Semua Transaksi"), KeyboardButton("🔄 Reset Data")],
    ], resize_keyboard=True)

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    nama = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Halo *{nama}*!\n\n"
        f"💰 *Saldo kamu: {rp(user['saldo'])}*\n\n"
        f"*Perintah tersedia:*\n"
        f"• `/addbal 50000` — tambah saldo\n"
        f"• `/keluar 20000 beli sayur` — catat pengeluaran\n"
        f"• `/saldo` — cek saldo\n"
        f"• `/hari` — transaksi hari ini\n"
        f"• `/bulanan` — laporan bulanan\n"
        f"• `/reset` — reset semua data\n\n"
        f"Atau gunakan tombol menu di bawah 👇",
        parse_mode="Markdown", reply_markup=kb()
    )

# ─── /addbal — Tambah Saldo ───────────────────────────────────────────────────
async def addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    args = context.args

    if not args:
        await update.message.reply_text(
            "💳 *Tambah Saldo*\n\nFormat: `/addbal 50000`\nAtau: `/addbal 50k`",
            parse_mode="Markdown"
        )
        return

    jumlah = parse_nominal(" ".join(args))
    if jumlah <= 0:
        await update.message.reply_text("❌ Nominal tidak valid! Contoh: `/addbal 50000`", parse_mode="Markdown")
        return

    saldo_lama = user["saldo"]
    user["saldo"] += jumlah
    user["transaksi"].append({
        "tipe": "masuk",
        "keterangan": "Tambah saldo",
        "jumlah": jumlah,
        "waktu": datetime.now().isoformat(),
        "foto_id": None
    })
    save_user(uid, user)

    await update.message.reply_text(
        f"✅ *Saldo Berhasil Ditambah!*\n\n"
        f"➕ Ditambah: *{rp(jumlah)}*\n"
        f"💰 Saldo lama: *{rp(saldo_lama)}*\n"
        f"💵 *Saldo sekarang: {rp(user['saldo'])}*\n\n"
        f"🕐 {waktu_sekarang()}",
        parse_mode="Markdown"
    )

# ─── Tambah Saldo via Menu ────────────────────────────────────────────────────
async def tambah_saldo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Tambah Saldo*\n\nKetik jumlah yang mau ditambah:\nContoh: `50000` atau `50k`",
        parse_mode="Markdown"
    )
    return SET_MODAL

async def proses_tambah_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    jumlah = parse_nominal(update.message.text)
    if jumlah <= 0:
        await update.message.reply_text("❌ Tidak valid! Contoh: `50000`", parse_mode="Markdown")
        return SET_MODAL
    saldo_lama = user["saldo"]
    user["saldo"] += jumlah
    user["transaksi"].append({"tipe": "masuk", "keterangan": "Tambah saldo", "jumlah": jumlah, "waktu": datetime.now().isoformat(), "foto_id": None})
    save_user(uid, user)
    await update.message.reply_text(
        f"✅ *Saldo Ditambah!*\n\n➕ {rp(jumlah)}\n💰 Lama: {rp(saldo_lama)}\n💵 *Sekarang: {rp(user['saldo'])}*\n🕐 {waktu_sekarang()}",
        parse_mode="Markdown", reply_markup=kb()
    )
    return ConversationHandler.END

# ─── /keluar — Catat Pengeluaran via Command (dengan opsi foto) ───────────────
async def keluar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    args = context.args

    if not args:
        await update.message.reply_text(
            "🛒 *Catat Pengeluaran*\n\nFormat: `/keluar 20000 beli sayur`\nAtau: `/keluar 20k beli sayur`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    jumlah = parse_nominal(args[0])
    keterangan = " ".join(args[1:]) if len(args) > 1 else "Pengeluaran"

    if jumlah <= 0:
        await update.message.reply_text("❌ Nominal tidak valid!", parse_mode="Markdown")
        return ConversationHandler.END

    if jumlah > user["saldo"]:
        await update.message.reply_text(
            f"❌ *Saldo tidak cukup!*\nSaldo: *{rp(user['saldo'])}*\nDibutuhkan: *{rp(jumlah)}*",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Simpan sementara ke user_data, tunggu keputusan foto
    context.user_data["ket"] = keterangan
    context.user_data["jml"] = jumlah

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Tambah Foto Bukti", callback_data="foto")],
        [InlineKeyboardButton("✅ Simpan Tanpa Foto", callback_data="nofoto")],
        [InlineKeyboardButton("❌ Batal", callback_data="batal")],
    ])
    await update.message.reply_text(
        f"🛒 *Ringkasan Pengeluaran*\n\n"
        f"📝 Keterangan: *{keterangan}*\n"
        f"💸 Jumlah: *{rp(jumlah)}*\n"
        f"💰 Saldo sekarang: *{rp(user['saldo'])}*\n\n"
        f"Mau tambah foto bukti?",
        parse_mode="Markdown", reply_markup=keyboard
    )
    return KELUAR_FOTO

async def keluar_terima_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima foto setelah user memilih 'Tambah Foto Bukti' dari /keluar"""
    uid = update.effective_user.id
    if update.message.photo:
        foto_id = update.message.photo[-1].file_id
        await simpan_keluar_msg(update.message, context, uid, foto_id)
        return ConversationHandler.END
    await update.message.reply_text("❌ Kirim foto dulu! Atau ketik /batal untuk membatalkan.")
    return KELUAR_FOTO

# ─── Catat Pengeluaran via Menu ───────────────────────────────────────────────
async def catat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    if user["saldo"] <= 0:
        await update.message.reply_text(f"❌ Saldo kosong! Tambah saldo dulu.\nSaldo: *{rp(user['saldo'])}*", parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text(
        f"🛒 *Catat Pengeluaran*\n\n💵 Saldo: *{rp(user['saldo'])}*\n\nKetik keterangan belanja:", parse_mode="Markdown"
    )
    return INPUT_KET

async def input_ket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ket"] = update.message.text.strip()
    await update.message.reply_text(f"📝 *{context.user_data['ket']}*\n\nKetik jumlah:", parse_mode="Markdown")
    return INPUT_JML

async def input_jml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    jumlah = parse_nominal(update.message.text)
    if jumlah <= 0:
        await update.message.reply_text("❌ Tidak valid! Contoh: `20000` atau `20k`", parse_mode="Markdown")
        return INPUT_JML
    if jumlah > user["saldo"]:
        await update.message.reply_text(f"❌ Melebihi saldo! Saldo: *{rp(user['saldo'])}*", parse_mode="Markdown")
        return INPUT_JML
    context.user_data["jml"] = jumlah
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Kirim Foto Bukti", callback_data="foto")],
        [InlineKeyboardButton("✅ Simpan Tanpa Foto", callback_data="nofoto")],
        [InlineKeyboardButton("❌ Batal", callback_data="batal")],
    ])
    await update.message.reply_text(
        f"💰 *Ringkasan:*\n📝 {context.user_data['ket']}\n💸 {rp(jumlah)}\n\nAda foto bukti?",
        parse_mode="Markdown", reply_markup=keyboard
    )
    return INPUT_FOTO

async def cb_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if query.data == "batal":
        await query.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END
    elif query.data == "nofoto":
        await simpan_keluar(query, context, uid, None)
        return ConversationHandler.END
    elif query.data == "foto":
        await query.edit_message_text("📷 Kirim foto bukti sekarang:")
        return INPUT_FOTO

async def terima_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.photo:
        foto_id = update.message.photo[-1].file_id
        await simpan_keluar_msg(update.message, context, uid, foto_id)
        return ConversationHandler.END
    await update.message.reply_text("❌ Kirim foto dulu!")
    return INPUT_FOTO

async def simpan_keluar(query, context, uid, foto_id):
    user = get_user(uid)
    ket = context.user_data.get("ket", "Pengeluaran")
    jml = context.user_data.get("jml", 0)
    saldo_lama = user["saldo"]
    user["saldo"] -= jml
    user["transaksi"].append({"tipe": "keluar", "keterangan": ket, "jumlah": jml, "waktu": datetime.now().isoformat(), "foto_id": foto_id})
    save_user(uid, user)
    await query.edit_message_text(
        f"✅ *Tersimpan!*\n\n📝 {ket}\n💸 -{rp(jml)}\n💰 Lama: {rp(saldo_lama)}\n💵 *Saldo: {rp(user['saldo'])}*\n{'📷 Foto: ✅' if foto_id else ''}\n\n🕐 {waktu_sekarang()}",
        parse_mode="Markdown"
    )

async def simpan_keluar_msg(message, context, uid, foto_id):
    user = get_user(uid)
    ket = context.user_data.get("ket", "Pengeluaran")
    jml = context.user_data.get("jml", 0)
    saldo_lama = user["saldo"]
    user["saldo"] -= jml
    user["transaksi"].append({"tipe": "keluar", "keterangan": ket, "jumlah": jml, "waktu": datetime.now().isoformat(), "foto_id": foto_id})
    save_user(uid, user)
    await message.reply_text(
        f"✅ *Tersimpan + Foto!*\n\n📝 {ket}\n💸 -{rp(jml)}\n💰 Lama: {rp(saldo_lama)}\n💵 *Saldo: {rp(user['saldo'])}*\n📷 Foto: ✅\n\n🕐 {waktu_sekarang()}",
        parse_mode="Markdown", reply_markup=kb()
    )

# ─── /help ───────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *DAFTAR PERINTAH BOT AKUNTANSI*\n\n"
        "💳 *SALDO*\n"
        "`/addbal 50000` — tambah saldo 50 ribu\n"
        "`/addbal 50k` — tambah saldo 50 ribu\n"
        "`/saldo` — cek saldo sekarang\n\n"
        "💸 *PENGELUARAN*\n"
        "`/keluar 20000 beli sayur` — catat pengeluaran\n"
        "`/keluar 20k beli sayur` — catat pengeluaran\n\n"
        "📊 *LAPORAN*\n"
        "`/hari` — transaksi hari ini\n"
        "`/bulanan` — laporan per bulan\n"
        "`/semua` — semua transaksi (20 terbaru)\n\n"
        "⚙️ *LAINNYA*\n"
        "`/reset` — reset semua data\n"
        "`/start` — tampilkan menu utama\n"
        "`/help` — tampilkan bantuan ini\n\n"
        "📱 *MENU TOMBOL*\n"
        "• 💰 Saldo\n"
        "• ➕ Tambah Saldo\n"
        "• 🛒 Catat Pengeluaran\n"
        "• 🖼️ Bukti Foto\n"
        "• 📋 Transaksi Hari Ini\n"
        "• 📅 Bulanan\n"
        "• 📊 Semua Transaksi\n"
        "• 🔄 Reset Data",
        parse_mode="Markdown"
    )

# ─── /saldo ───────────────────────────────────────────────────────────────────
async def cek_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    saldo = user["saldo"]
    total_masuk = sum(t["jumlah"] for t in user["transaksi"] if t["tipe"] == "masuk")
    total_keluar = sum(t["jumlah"] for t in user["transaksi"] if t["tipe"] == "keluar")
    hari_ini = date.today().isoformat()
    keluar_hari_ini = sum(t["jumlah"] for t in user["transaksi"] if t["tipe"] == "keluar" and t["waktu"].startswith(hari_ini))

    if total_masuk > 0:
        persen = max(0, saldo / total_masuk * 100)
        bar = "█" * int(persen / 10) + "░" * (10 - int(persen / 10))
        status = "🟢 Aman" if persen > 50 else "🟡 Perhatian" if persen > 20 else "🔴 Kritis"
    else:
        persen, bar, status = 0, "░░░░░░░░░░", "⚠️ Belum ada saldo"

    await update.message.reply_text(
        f"💰 *SALDO REAL-TIME*\n"
        f"🕐 {waktu_sekarang()}\n\n"
        f"💵 Total Masuk: *{rp(total_masuk)}*\n"
        f"💸 Total Keluar: *{rp(total_keluar)}*\n"
        f"📅 Keluar Hari Ini: *{rp(keluar_hari_ini)}*\n\n"
        f"━━━━━━━━━━\n"
        f"💰 *SALDO: {rp(saldo)}*\n"
        f"{status}\n"
        f"[{bar}] {persen:.1f}%",
        parse_mode="Markdown"
    )

# ─── /hari — Transaksi Hari Ini ──────────────────────────────────────────────
async def transaksi_hari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    hari_ini = date.today().isoformat()
    list_hari = [t for t in user["transaksi"] if t["waktu"].startswith(hari_ini)]

    if not list_hari:
        await update.message.reply_text(
            f"📋 *Transaksi Hari Ini*\n📅 {date.today().strftime('%d %B %Y')}\n\nBelum ada transaksi.",
            parse_mode="Markdown"
        )
        return

    total_masuk = sum(t["jumlah"] for t in list_hari if t["tipe"] == "masuk")
    total_keluar = sum(t["jumlah"] for t in list_hari if t["tipe"] == "keluar")
    jumlah_foto = sum(1 for t in list_hari if t.get("foto_id"))
    pesan = f"📋 *TRANSAKSI HARI INI*\n📅 {date.today().strftime('%d %B %Y')}\n\n"

    for i, t in enumerate(list_hari, 1):
        jam = datetime.fromisoformat(t["waktu"]).strftime("%H:%M")
        icon = "➕" if t["tipe"] == "masuk" else "💸"
        foto = " 📷" if t.get("foto_id") else ""
        pesan += f"{i}. {icon} *{t['keterangan']}*{foto}\n"
        pesan += f"    {rp(t['jumlah'])} | ⏰ {jam}\n\n"

    pesan += f"━━━━━━━━━━\n"
    pesan += f"➕ Masuk: *{rp(total_masuk)}*\n"
    pesan += f"💸 Keluar: *{rp(total_keluar)}*\n"
    pesan += f"💰 *Saldo: {rp(user['saldo'])}*"
    if jumlah_foto > 0:
        pesan += f"\n\n📷 Menampilkan *{jumlah_foto} foto bukti* di bawah..."
    await update.message.reply_text(pesan, parse_mode="Markdown")

    # Kirim foto bukti satu per satu dengan caption detail
    for i, t in enumerate(list_hari, 1):
        if not t.get("foto_id"):
            continue
        jam = datetime.fromisoformat(t["waktu"]).strftime("%H:%M")
        caption = (
            f"📷 *Bukti #{i} — {t['keterangan']}*\n"
            f"💸 {rp(t['jumlah'])}\n"
            f"⏰ {jam}"
        )
        try:
            await update.message.reply_photo(
                photo=t["foto_id"],
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Gagal kirim foto: {e}")

# ─── /bulanan — Laporan Bulanan ───────────────────────────────────────────────
async def bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if not user["transaksi"]:
        await update.message.reply_text("📅 Belum ada transaksi.", parse_mode="Markdown")
        return

    # Kelompokkan transaksi per bulan
    per_bulan = defaultdict(list)
    for t in user["transaksi"]:
        bulan = t["waktu"][:7]  # YYYY-MM
        per_bulan[bulan].append(t)

    for bulan in sorted(per_bulan.keys(), reverse=True):
        transaksi_bln = per_bulan[bulan]
        try:
            label = datetime.strptime(bulan, "%Y-%m").strftime("%B %Y")
        except:
            label = bulan

        total_masuk = sum(t["jumlah"] for t in transaksi_bln if t["tipe"] == "masuk")
        total_keluar = sum(t["jumlah"] for t in transaksi_bln if t["tipe"] == "keluar")
        jumlah_foto = sum(1 for t in transaksi_bln if t.get("foto_id"))

        # Teks ringkasan bulan
        pesan = f"📆 *LAPORAN {label.upper()}*\n\n"
        for i, t in enumerate(transaksi_bln, 1):
            dt = datetime.fromisoformat(t["waktu"])
            icon = "➕" if t["tipe"] == "masuk" else "💸"
            foto_tag = " 📷" if t.get("foto_id") else ""
            pesan += f"{i}. {icon} *{t['keterangan']}*{foto_tag}\n"
            pesan += f"    {rp(t['jumlah'])} | {dt.strftime('%d/%m %H:%M')}\n\n"

        pesan += f"━━━━━━━━━━\n"
        pesan += f"➕ Total Masuk: *{rp(total_masuk)}*\n"
        pesan += f"💸 Total Keluar: *{rp(total_keluar)}*\n"
        pesan += f"🔢 Transaksi: *{len(transaksi_bln)}x*"
        if jumlah_foto > 0:
            pesan += f"\n📷 *{jumlah_foto} foto bukti* di bawah"
        await update.message.reply_text(pesan, parse_mode="Markdown")

        # Kirim foto bukti bulan ini satu per satu
        for i, t in enumerate(transaksi_bln, 1):
            if not t.get("foto_id"):
                continue
            dt = datetime.fromisoformat(t["waktu"])
            caption = (
                f"📷 *Bukti — {t['keterangan']}*\n"
                f"💸 {rp(t['jumlah'])}\n"
                f"📅 {dt.strftime('%d %B %Y, %H:%M')}"
            )
            try:
                await update.message.reply_photo(
                    photo=t["foto_id"],
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Gagal kirim foto: {e}")

    # Ringkasan total akhir
    await update.message.reply_text(
        f"━━━━━━━━━━\n💰 *Saldo Sekarang: {rp(user['saldo'])}*",
        parse_mode="Markdown"
    )

# ─── /semua — Semua Transaksi ─────────────────────────────────────────────────
async def semua_transaksi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if not user["transaksi"]:
        await update.message.reply_text("📊 Belum ada transaksi.", parse_mode="Markdown")
        return

    pesan = f"📊 *SEMUA TRANSAKSI*\n💰 Saldo: *{rp(user['saldo'])}*\n\n"
    for t in reversed(user["transaksi"][-20:]):  # 20 terbaru
        dt = datetime.fromisoformat(t["waktu"])
        icon = "➕" if t["tipe"] == "masuk" else "💸"
        foto = "📷" if t.get("foto_id") else ""
        pesan += f"{icon} *{t['keterangan']}* {foto}\n"
        pesan += f"   {rp(t['jumlah'])} | {dt.strftime('%d/%m %H:%M')}\n\n"

    await update.message.reply_text(pesan, parse_mode="Markdown")

# ─── Bukti Foto ───────────────────────────────────────────────────────────────
async def bukti_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    dengan_foto = [t for t in user["transaksi"] if t.get("foto_id")]
    if not dengan_foto:
        await update.message.reply_text("🖼️ Belum ada bukti foto.", parse_mode="Markdown")
        return
    await update.message.reply_text(f"🖼️ *BUKTI FOTO* — {len(dengan_foto)} foto\nMenunjukkan 5 terbaru...", parse_mode="Markdown")
    for t in dengan_foto[-5:]:
        dt = datetime.fromisoformat(t["waktu"]).strftime("%d/%m/%Y %H:%M")
        try:
            await update.message.reply_photo(
                photo=t["foto_id"],
                caption=f"📝 *{t['keterangan']}*\n💸 {rp(t['jumlah'])}\n🕐 {dt}",
                parse_mode="Markdown"
            )
        except:
            pass

# ─── Reset Data ───────────────────────────────────────────────────────────────
async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ya, Reset Semua!", callback_data="reset_ya")],
        [InlineKeyboardButton("❌ Batal", callback_data="reset_batal")],
    ])
    await update.message.reply_text(
        "⚠️ *RESET DATA*\n\nSemua transaksi dan saldo akan dihapus!\nYakin mau reset?",
        parse_mode="Markdown", reply_markup=keyboard
    )

async def cb_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if query.data == "reset_ya":
        save_user(uid, {"saldo": 0, "transaksi": []})
        await query.edit_message_text("✅ *Data berhasil direset!*\nSaldo: *Rp 0*\n\nMulai dari awal 🚀", parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ Reset dibatalkan.")

# ─── Handle Text Menu ─────────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text
    if teks == "💰 Saldo": await cek_saldo(update, context)
    elif teks == "📋 Transaksi Hari Ini": await transaksi_hari(update, context)
    elif teks == "📅 Bulanan": await bulanan(update, context)
    elif teks == "🖼️ Bukti Foto": await bukti_foto(update, context)
    elif teks == "📊 Semua Transaksi": await semua_transaksi(update, context)
    elif teks == "🔄 Reset Data": await reset_start(update, context)
    else: await update.message.reply_text("Gunakan tombol menu atau ketik /start", reply_markup=kb())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Dibatalkan.", reply_markup=kb())
    return ConversationHandler.END

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("saldo", cek_saldo))
    app.add_handler(CommandHandler("addbal", addbal))
    app.add_handler(CommandHandler("hari", transaksi_hari))
    app.add_handler(CommandHandler("bulanan", bulanan))
    app.add_handler(CommandHandler("semua", semua_transaksi))
    app.add_handler(CommandHandler("reset", reset_start))
    app.add_handler(CallbackQueryHandler(cb_reset, pattern="^reset_"))

    # ConversationHandler untuk /keluar (dengan opsi foto)
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("keluar", keluar_cmd)],
        states={
            KELUAR_FOTO: [
                MessageHandler(filters.PHOTO, keluar_terima_foto),
                CallbackQueryHandler(cb_foto, pattern="^(foto|nofoto|batal)$"),
            ],
        },
        fallbacks=[CommandHandler("batal", cancel)],
        per_message=False,
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Tambah Saldo$"), tambah_saldo_menu)],
        states={SET_MODAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, proses_tambah_saldo)]},
        fallbacks=[CommandHandler("batal", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 Catat Pengeluaran$"), catat_menu)],
        states={
            INPUT_KET: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_ket)],
            INPUT_JML: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_jml)],
            INPUT_FOTO: [
                MessageHandler(filters.PHOTO, terima_foto),
                CallbackQueryHandler(cb_foto, pattern="^(foto|nofoto|batal)$"),
            ],
        },
        fallbacks=[CommandHandler("batal", cancel)],
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot Akuntansi v2 berjalan!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
