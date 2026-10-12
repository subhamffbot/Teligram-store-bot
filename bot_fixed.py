import os, sqlite3, secrets, logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlparse
import qrcode
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)
UPI_ID = os.getenv("UPI_ID", "45deb45@fam")
MERCHANT = os.getenv("MERCHANT_NAME", "MAT MAX STORE")
ADMIN_URL = os.getenv("ADMIN_CONTACT_URL", "https://t.me/MADSUBHAM")
FREE_PANEL_URL = os.getenv("FREE_PANEL_URL", "https://t.me/subhamrrpnale")
REFERRAL_BONUS = max(0, int(os.getenv("REFERRAL_BONUS", "0") or 0))
DB_PATH = os.getenv("DATABASE_PATH", "mat_max_store.sqlite3")
if not BOT_TOKEN or not OWNER_ID:
    raise SystemExit("Set BOT_TOKEN and OWNER_TELEGRAM_ID environment variables first.")

SERVICES = {
 "unban": ("Free Fire ID Unban",50), "guild_two":("Two Guild Glory Bot",20),
 "guild_four":("Four Guild Glory Bot",None), "guild_eight":("Eight Guild Glory Bot",None),
 "proxy_vip":("VIP Proxy Server",50), "proxy_normal":("Normal Proxy Server",30),
 "diamond":("Free Fire Diamond Hack",40),
 "vala_1h":("Vala Mod — 1 Hour",15), "vala_7d":("Vala Mod — 7 Days",200),
 "vala_1m":("Vala Mod — 1 Month",240), "p20_7d":("P20 — 7 Days",150),
 "p20_15d":("P20 — 15 Days",300), "p20_1m":("P20 — 1 Month",450),
 "balamod_7d":("Balamod — 7 Days",100), "balamod_15d":("Balamod — 15 Days",200),
 "balamod_1m":("Balamod — 1 Month",300)
}
def now(): return datetime.now(timezone.utc).isoformat()
def db():
 c=sqlite3.connect(DB_PATH, timeout=20); c.row_factory=sqlite3.Row; return c
def init_db():
 with db() as c:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, name TEXT, balance INTEGER NOT NULL DEFAULT 0, referrer INTEGER, created TEXT, last_share TEXT, referrals INTEGER NOT NULL DEFAULT 0, earnings INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS codes(code TEXT PRIMARY KEY, amount INTEGER NOT NULL, created_by INTEGER, created TEXT, used_by INTEGER, used TEXT);
  CREATE TABLE IF NOT EXISTS tx(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, amount INTEGER, kind TEXT, note TEXT, created TEXT);
  CREATE TABLE IF NOT EXISTS orders(ref TEXT PRIMARY KEY, uid INTEGER, service TEXT, amount INTEGER, status TEXT, created TEXT, photo_id TEXT);
  CREATE TABLE IF NOT EXISTS rewards(referred INTEGER PRIMARY KEY, referrer INTEGER, amount INTEGER, created TEXT);
  """)
def money(n): return f"₹{int(n)}"
def record_tx(c, uid, amount, kind, note):
 c.execute("INSERT INTO tx(uid,amount,kind,note,created) VALUES(?,?,?,?,?)",(uid,amount,kind,note,now()))
def user_exists(c, uid): return c.execute("SELECT 1 FROM users WHERE id=?",(uid,)).fetchone() is not None
def register(tg, payload=None):
 with db() as c:
  if user_exists(c,tg.id):
   c.execute("UPDATE users SET username=?,name=? WHERE id=?",(tg.username or "",tg.first_name or "",tg.id)); return False
  ref=None
  if payload and payload.startswith("ref_"):
   try:
    candidate=int(payload[4:])
    if candidate != tg.id and user_exists(c,candidate): ref=candidate
   except ValueError: pass
  c.execute("INSERT INTO users(id,username,name,referrer,created) VALUES(?,?,?,?,?)",(tg.id,tg.username or "",tg.first_name or "",ref,now()))
  if ref:
   c.execute("UPDATE users SET referrals=referrals+1 WHERE id=?",(ref,))
   if REFERRAL_BONUS:
    c.execute("UPDATE users SET balance=balance+?,earnings=earnings+? WHERE id=?",(REFERRAL_BONUS,REFERRAL_BONUS,ref))
    c.execute("INSERT INTO rewards VALUES(?,?,?,?)",(tg.id,ref,REFERRAL_BONUS,now()))
    record_tx(c,ref,REFERRAL_BONUS,"REFERRAL",f"Referral bonus for user {tg.id}")
  return True
def balance(uid):
 with db() as c:
  r=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()
  return int(r["balance"]) if r else 0
def kb(rows): return Markup([[Btn(t,callback_data=d) if d else Btn(t,url=u)] for t,d,u in rows])
def main_kb(uid=None):
 rows=[[Btn("🛍️ Services",callback_data="services"),Btn("💰 My Wallet",callback_data="wallet")],
       [Btn("➕ Add Money",callback_data="addmoney"),Btn("🎟️ Redeem Code",callback_data="redeem")],
       [Btn("🧾 Transaction History",callback_data="history")],
       [Btn("👥 Refer & Earn",callback_data="referral"),Btn("📩 Message Admin",url=admin_contact_url("Hi, I need help with my order/payment."))]]
 if uid == OWNER_ID:
  rows.append([Btn("🔑 Create Redeem Code",callback_data="create")])
 return Markup(rows)
def services_kb(): return Markup([[Btn("🔓 Free Fire ID Unban — ₹50",callback_data="svc:unban")],
 [Btn("🤖 Guild Glory Bot",callback_data="guild")],[Btn("🌐 Proxy Server",callback_data="proxy")],
 [Btn("💎 Free Fire Diamond Hack — ₹40",callback_data="svc:diamond")],
 [Btn("🛠️ Free Fire Panel",callback_data="panel")],[Btn("⬅️ Main Menu",callback_data="home")]])
def admin_contact_url(message=""):
 # This must point to a personal Telegram username/chat, not a channel invite/link.
 base = ADMIN_URL.strip()
 if message and base.startswith("https://t.me/") and "?" not in base:
  return base + "?" + urlencode({"text": message})
 return base

def qr_file(amount, ref):
 uri=f"upi://pay?pa={quote(UPI_ID, safe='')}&pn={quote(MERCHANT, safe='')}&am={int(amount)}&cu=INR&tn={quote(ref, safe='')}"
 path=f"/tmp/{ref}.png"; qrcode.make(uri).save(path); return path
async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
 payload=context.args[0] if context.args else None
 new=register(update.effective_user,payload)
 await update.effective_message.reply_text(f"🛍️ Welcome to {MERCHANT}!\nChoose an option below.",reply_markup=main_kb(update.effective_user.id if update.effective_user else None))
async def help_cmd(update,context):
 await update.effective_message.reply_text("Use the menu below.",reply_markup=main_kb(update.effective_user.id if update.effective_user else None))
async def cb(update:Update,context:ContextTypes.DEFAULT_TYPE):
 q=update.callback_query; await q.answer(); uid=q.from_user.id; register(q.from_user)
 d=q.data
 if d=="home": await q.edit_message_text(f"🛍️ {MERCHANT}",reply_markup=main_kb(uid))
 elif d=="services": await q.edit_message_text("🛍️ Choose a service:",reply_markup=services_kb())
 elif d=="guild": await q.edit_message_text("🤖 Guild Glory Bot",reply_markup=Markup([[Btn("Two Guild Glory Bot — ₹20",callback_data="svc:guild_two")],[Btn("Four Guild Glory Bot — price not set",callback_data="svc:guild_four")],[Btn("Eight Guild Glory Bot — price not set",callback_data="svc:guild_eight")],[Btn("⬅️ Services",callback_data="services")]]))
 elif d=="proxy": await q.edit_message_text("🌐 Proxy Server",reply_markup=Markup([[Btn("VIP Proxy Server — ₹50",callback_data="svc:proxy_vip")],[Btn("Normal Proxy Server — ₹30",callback_data="svc:proxy_normal")],[Btn("⬅️ Services",callback_data="services")]]))
 elif d=="panel": await q.edit_message_text("🛠️ Free Fire Panel",reply_markup=Markup([[Btn("Vala Mod",callback_data="p:vala")],[Btn("P20",callback_data="p:p20")],[Btn("Balamod",callback_data="p:balamod")],[Btn("🆓 Free Panel",url=FREE_PANEL_URL)],[Btn("⬅️ Services",callback_data="services")]]))
 elif d.startswith("p:"):
  group=d[2:]
  choices={"vala":[("1 Hour — ₹15","vala_1h"),("7 Days — ₹200","vala_7d"),("1 Month — ₹240","vala_1m")],"p20":[("7 Days — ₹150","p20_7d"),("15 Days — ₹300","p20_15d"),("1 Month — ₹450","p20_1m")],"balamod":[("7 Days — ₹100","balamod_7d"),("15 Days — ₹200","balamod_15d"),("1 Month — ₹300","balamod_1m")]}
  await q.edit_message_text("Choose duration:",reply_markup=Markup([[Btn(label,callback_data="svc:"+key)] for label,key in choices[group]]+[[Btn("⬅️ Panel Menu",callback_data="panel")]]))
 elif d.startswith("svc:"):
  key=d[4:]
  if key not in SERVICES: await q.edit_message_text("Unknown service.",reply_markup=services_kb()); return
  name,price=SERVICES[key]
  if price is None: await q.edit_message_text(f"{name}: price has not been set. Contact admin.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url("Hi, I need help with my order/payment."))],[Btn("⬅️ Services",callback_data="services")]])); return
  context.user_data["service"]=key
  await q.edit_message_text(f"{name}\nPrice: {money(price)}\nChoose payment:",reply_markup=Markup([[Btn("💰 Wallet",callback_data="buy:"+key)],[Btn("⚡ UPI Payment",callback_data="upi:"+key)],[Btn("⬅️ Services",callback_data="services")]]))
 elif d.startswith("buy:"):
  key=d[4:]
  if key not in SERVICES: await q.edit_message_text("Unknown service.",reply_markup=services_kb()); return
  name,price=SERVICES[key]
  if price is None:
   await q.edit_message_text(f"{name}: price has not been set. Contact admin.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url())],[Btn("⬅️ Services",callback_data="services")]])); return
  with db() as c:
   r=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone(); bal=int(r["balance"])
   if bal<price:
    await q.edit_message_text(f"❌ Insufficient balance.\nCurrent: {money(bal)}\nRequired: {money(price)}",reply_markup=Markup([[Btn("➕ Add Money",callback_data="addmoney")],[Btn("⬅️ Services",callback_data="services")]])); return
   c.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",(price,uid,price))
   ref="MMX-"+secrets.token_hex(4).upper()
   c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)",(ref,uid,name,price,"PAID_WALLET",now(),None)); record_tx(c,uid,-price,"SERVICE",name)
   bal-=price
  await q.edit_message_text(f"✅ Payment successful\nOrder: {ref}\n{name}\nPaid: {money(price)}\nRemaining: {money(bal)}\nContact admin for fulfillment.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url("Hi, I need help with my order/payment."))],[Btn("🏠 Main Menu",callback_data="home")]]))
  await context.bot.send_message(OWNER_ID,f"Wallet order: {ref}\nUser: {uid}\n{name}\nAmount: {money(price)}")
 elif d.startswith("upi:"):
  key=d[4:]
  if key not in SERVICES: await q.edit_message_text("Unknown service.",reply_markup=services_kb()); return
  name,price=SERVICES[key]
  if price is None: await q.edit_message_text("Price has not been set. Contact admin.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url("Hi, I need help with my order/payment."))],[Btn("⬅️ Services",callback_data="services")]])); return
  ref="MMX-"+secrets.token_hex(4).upper()
  with db() as c: c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)",(ref,uid,name,price,"AWAITING_PAYMENT",now(),None))
  context.user_data["screenshot_order"]=ref
  path=qr_file(price,ref)
  with open(path,"rb") as f: await context.bot.send_photo(uid,f,caption=f"UPI Payment\n{name}\nAmount: {money(price)}\nReference: {ref}\nAfter paying, send the screenshot as a photo.")
  try: os.remove(path)
  except OSError: pass
  await q.edit_message_text("QR sent to your chat. Upload payment screenshot as a photo to submit for manual verification.")
 elif d=="wallet":
  await q.edit_message_text(f"💰 My Wallet\nBalance: {money(balance(uid))}",reply_markup=Markup([[Btn("➕ Add Money",callback_data="addmoney")],[Btn("🎟️ Redeem Code",callback_data="redeem")],[Btn("🧾 History",callback_data="history")],[Btn("⬅️ Main Menu",callback_data="home")]]))
 elif d=="addmoney":
  context.user_data.pop("add_amount_input", None)
  context.user_data.pop("pending_add_amount", None)
  await q.edit_message_text("➕ Add Balance\nChoose an amount below, or tap Custom Amount to enter your own amount. Then tap Generate UPI to create a dynamic QR code.",reply_markup=Markup([[Btn("₹10",callback_data="addamt:10"),Btn("₹20",callback_data="addamt:20")],[Btn("₹50",callback_data="addamt:50"),Btn("₹100",callback_data="addamt:100")],[Btn("✏️ Custom Amount",callback_data="addcustom")],[Btn("⬅️ Main Menu",callback_data="home")]]))
 elif d.startswith("addamt:"):
  try: amount=int(d.split(":",1)[1])
  except (ValueError,IndexError): await q.edit_message_text("Invalid amount.",reply_markup=Markup([[Btn("➕ Add Money",callback_data="addmoney")]])); return
  if not 1 <= amount <= 100000: await q.edit_message_text("Amount must be between ₹1 and ₹100000.",reply_markup=Markup([[Btn("➕ Add Money",callback_data="addmoney")]])); return
  context.user_data.pop("add_amount_input", None)
  context.user_data["pending_add_amount"]=amount
  await q.edit_message_text(f"Selected amount: {money(amount)}\nTap Generate UPI to create your dynamic QR code.",reply_markup=Markup([[Btn("⚡ Generate UPI",callback_data="generate_add_qr")],[Btn("↩️ Change Amount",callback_data="addmoney")],[Btn("Cancel",callback_data="home")]]))
 elif d=="addcustom":
  context.user_data.pop("pending_add_amount", None)
  context.user_data["add_amount_input"]=True
  await q.edit_message_text("✏️ Custom Amount\nSend any whole-rupee amount from ₹1 to ₹100000. For example, send 1 to generate a ₹1 UPI QR code.",reply_markup=Markup([[Btn("Cancel",callback_data="home")]]))
 elif d=="generate_add_qr":
  amount=context.user_data.get("pending_add_amount")
  if not amount:
   await q.edit_message_text("Please choose Add Money and enter an amount first.",reply_markup=Markup([[Btn("➕ Add Money",callback_data="addmoney")],[Btn("⬅️ Main Menu",callback_data="home")]])); return
  context.user_data.pop("pending_add_amount",None)
  ref="ADD-"+secrets.token_hex(4).upper()
  with db() as c: c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)",(ref,uid,"Wallet Add Money",amount,"AWAITING_PAYMENT",now(),None))
  context.user_data["screenshot_order"]=ref
  path=qr_file(amount,ref)
  try:
   with open(path,"rb") as f:
    await context.bot.send_photo(uid,f,caption=f"➕ Add Balance via UPI\nAmount: {money(amount)}\nReference: {ref}\n\n1. Pay by scanning this dynamic UPI QR.\n2. Tap Message Admin below and send your payment screenshot.\n3. After manual verification, the admin will create a redeem code for you. Redeem it in this bot to add coins to your wallet. Payment is not automatically verified.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url(f"Hi, I paid {money(amount)} for wallet balance. Reference: {ref}. I will send my payment screenshot here."))],[Btn("🎟️ Redeem Code",callback_data="redeem")],[Btn("🏠 Main Menu",callback_data="home")]]))
  finally:
   try: os.remove(path)
   except OSError: pass
  await q.edit_message_text("Your UPI QR has been sent in the bot chat. After payment, use Message Admin and send the screenshot. Once verified, redeem the code the admin gives you.",reply_markup=Markup([[Btn("📩 Message Admin",url=admin_contact_url("Hi, I need help verifying my wallet top-up payment."))],[Btn("🏠 Main Menu",callback_data="home")]]))
 elif d=="redeem":
  context.user_data["redeem_input"]=True; await q.edit_message_text("Send your redeem code in a message.",reply_markup=Markup([[Btn("Cancel",callback_data="home")]]))
 elif d=="create":
  if uid!=OWNER_ID: await q.edit_message_text("⛔ Owner only."); return
  context.user_data["create_amount"]=True; await q.edit_message_text("Owner verified by Telegram ID. Send redeem amount in whole rupees.")
 elif d=="history":
  with db() as c: rows=c.execute("SELECT amount,note,created FROM tx WHERE uid=? ORDER BY id DESC LIMIT 10",(uid,)).fetchall()
  lines=["🧾 Recent transactions:"]+[f"{'+' if r['amount']>0 else ''}{money(r['amount'])} — {r['note']} ({r['created'][:16]})" for r in rows]
  await q.edit_message_text("\n".join(lines),reply_markup=Markup([[Btn("⬅️ Main Menu",callback_data="home")]]))
 elif d=="referral":
  me=await context.bot.get_me(); link=f"https://t.me/{me.username}?start=ref_{uid}"
  with db() as c: r=c.execute("SELECT referrals,earnings,last_share FROM users WHERE id=?",(uid,)).fetchone()
  last=datetime.fromisoformat(r["last_share"]) if r["last_share"] else None
  ready=not last or datetime.now(timezone.utc)>=last+timedelta(hours=24)
  rem=max(0,int(((last+timedelta(hours=24))-datetime.now(timezone.utc)).total_seconds())) if last else 0
  msg=f"👥 Refer & Earn\nYour link:\n{link}\nReferrals: {r['referrals']}\nEarnings: {money(r['earnings'])}\n"
  msg+= "You can share now." if ready else f"Next share in {rem//3600}h {(rem%3600)//60}m."
  rows=[[Btn("📤 Share Referral Link",callback_data="share")] ] if ready else []
  rows += [[Btn("🔗 Open Referral Link",url=link)],[Btn("⬅️ Main Menu",callback_data="home")]]
  await q.edit_message_text(msg,reply_markup=Markup(rows))
 elif d=="share":
  with db() as c:
   r=c.execute("SELECT last_share FROM users WHERE id=?",(uid,)).fetchone()
   last=datetime.fromisoformat(r["last_share"]) if r["last_share"] else None
   if last and datetime.now(timezone.utc)<last+timedelta(hours=24):
    rem=int(((last+timedelta(hours=24))-datetime.now(timezone.utc)).total_seconds()); await q.edit_message_text(f"Cooldown: {rem//3600}h {(rem%3600)//60}m remaining.",reply_markup=Markup([[Btn("Back",callback_data="referral")]])); return
   c.execute("UPDATE users SET last_share=? WHERE id=?",(now(),uid))
  me=await context.bot.get_me(); link=f"https://t.me/{me.username}?start=ref_{uid}"
  await context.bot.send_message(uid,f"🎁 Join {MERCHANT} using my referral link:\n{link}")
  await q.edit_message_text("Share message prepared. Your 24-hour cooldown has started.",reply_markup=Markup([[Btn("⬅️ Main Menu",callback_data="home")]]))
 elif d.startswith("shot:"):
  context.user_data["screenshot_order"]=d[5:]; await q.message.reply_text("Send the payment screenshot as a photo.")
 elif d.startswith("review:"):
  if uid!=OWNER_ID: await q.answer("Owner only",show_alert=True); return
  _,decision,ref=d.split(":",2); status="VERIFIED_MANUAL" if decision=="yes" else "REJECTED_MANUAL"
  with db() as c: row=c.execute("SELECT uid,service,amount FROM orders WHERE ref=?",(ref,)).fetchone(); c.execute("UPDATE orders SET status=? WHERE ref=?",(status,ref))
  if row: await context.bot.send_message(row["uid"],f"{'Payment verified' if decision=='yes' else 'Payment rejected'} for {ref}. Contact admin for next steps.")
  await q.edit_message_caption(caption=(q.message.caption or "")+f"\nStatus: {status}")

async def messages(update:Update,context:ContextTypes.DEFAULT_TYPE):
 m=update.effective_message; u=update.effective_user
 if not m or not u: return
 register(u)
 if context.user_data.get("screenshot_order") and m.photo:
  ref=context.user_data.pop("screenshot_order")
  with db() as c:
   r=c.execute("SELECT service,amount,status FROM orders WHERE ref=? AND uid=?",(ref,u.id)).fetchone()
   if r: c.execute("UPDATE orders SET status='AWAITING_SCREENSHOT',photo_id=? WHERE ref=?",(m.photo[-1].file_id,ref))
  if not r: await m.reply_text("Order not found."); return
  await context.bot.send_photo(OWNER_ID,m.photo[-1].file_id,caption=f"Payment screenshot for manual review\nOrder: {ref}\nUser ID: {u.id}\nService: {r['service']}\nAmount: {money(r['amount'])}",reply_markup=Markup([[Btn("✅ Mark Verified",callback_data=f"review:yes:{ref}"),Btn("❌ Reject",callback_data=f"review:no:{ref}")]]))
  await m.reply_text("Screenshot sent to admin. Payment is not confirmed until reviewed."); return
 text=(m.text or "").strip()
 if context.user_data.get("add_amount_input"):
  if not text.isdigit() or not 1<=int(text)<=100000:
   await m.reply_text("Enter a whole amount from ₹1 to ₹100000."); return
  amount=int(text)
  context.user_data.pop("add_amount_input",None)
  context.user_data["pending_add_amount"]=amount
  await m.reply_text(f"Amount selected: {money(amount)}\nTap Generate UPI to create your dynamic QR code.",reply_markup=Markup([[Btn("⚡ Generate UPI",callback_data="generate_add_qr")],[Btn("Cancel",callback_data="home")]]))
  return
 if context.user_data.get("redeem_input"):
  context.user_data.pop("redeem_input",None); code=text.upper().replace(" ","")
  amount=0
  with db() as c:
   c.execute("BEGIN IMMEDIATE"); r=c.execute("SELECT amount,used_by FROM codes WHERE code=?",(code,)).fetchone()
   if not r: result="invalid"
   elif r["used_by"] is not None: result="used"
   else:
    amount=r["amount"]; cur=c.execute("UPDATE codes SET used_by=?,used=? WHERE code=? AND used_by IS NULL",(u.id,now(),code))
    if cur.rowcount!=1: result="used"
    else: c.execute("UPDATE users SET balance=balance+? WHERE id=?",(amount,u.id)); record_tx(c,u.id,amount,"REDEEM",f"Redeem code {code}"); result="ok"
  await m.reply_text(f"✅ Redeemed {money(amount)}. New balance: {money(balance(u.id))}" if result=="ok" else ("❌ Code already used." if result=="used" else "❌ Invalid code.")); return
 if context.user_data.get("create_amount"):
  if u.id!=OWNER_ID: context.user_data.pop("create_amount",None); return
  if not text.isdigit() or not 1<=int(text)<=100000: await m.reply_text("Enter a whole amount from ₹1 to ₹100000."); return
  amount=int(text); context.user_data.pop("create_amount",None); code="MMX-"+secrets.token_hex(5).upper()
  with db() as c: c.execute("INSERT INTO codes(code,amount,created_by,created) VALUES(?,?,?,?)",(code,amount,OWNER_ID,now()))
  await m.reply_text(f"✅ REDEEM CODE CREATED\nCode: {code}\nAmount: {money(amount)}\nStatus: UNUSED\nSend it privately to the user.")
  return
 await m.reply_text("Use /start to open the menu.",reply_markup=main_kb(u.id))

async def cancel(update,context):
 context.user_data.clear(); await update.effective_message.reply_text("Cancelled.",reply_markup=main_kb(update.effective_user.id if update.effective_user else None))
async def error(update,context): logging.exception("Bot error",exc_info=context.error)
def main():
 init_db(); app=Application.builder().token(BOT_TOKEN).build()
 app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("help",help_cmd)); app.add_handler(CommandHandler("cancel",cancel))
 app.add_handler(CallbackQueryHandler(cb)); app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,messages)); app.add_error_handler(error)
 print("MAT MAX STORE bot running..."); app.run_polling()
if __name__=="__main__": main()
