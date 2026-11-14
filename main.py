"""NORTHSTAR DEMO BANK (TOT Style UI Edition) - single file for Pydroid 3 (Kivy + SQLite). 
FICTIONAL bank, simulated money only.
Demo login: farofederico265@gmail.com  /  demo123   (or phone +447123456789)"""
import os
import re
import sqlite3
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.image import AsyncImage
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.properties import StringProperty, NumericProperty

DB_NAME = "northstar_demo_v4.db"
LOGO_URL = "https://i.postimg.cc/rpDfvghM/Gemini-Generated-Image-njx4z6njx4z6njx4.jpg"

# ============================================================== EDITABLE DEMO STRINGS & TEXTS
DEMO_STRINGS = {
    "header_doc_string": "Accesso demo: farofederico265@gmail.com  /  demo123   (o telefono +447123456789)",
    "bank_name": "Tot.",
    "login_banner": "Conti e carte per veri imprenditori",
    "login_email_hint": "farofederico265@gmail.com",
    "login_email_default": "farofederico265@gmail.com",
    "login_creds_hint": "Hai dimenticato la password? Clicca qui per reimpostarla. ",
    "login_security_note": "Conto, carte, fatturazione elettronica e spese del team",
    "top_strip": "Oltre 8.000 aziende usano Tot ogni giorno",
    "home_test_data": "HOME",
    "home_total_label": "SALDO TOTALE  ·  EUR",
    "account_opening_party": "Saldo iniziale",
    "account_opening_desc": "Saldo iniziale",
    "payments_banner": "WAYNE FARO S.R.L",
    "convert_rate_format": "Riceverai circa %s (tasso demo %s GBP per EUR)",
    "confirm_demo_title": "Conferma operazione",
    "confirm_demo_msg": "Il bonifico è in elaborazione.",
    "processing_payment": "Elaborazione sicura del pagamento in corso...",
    "card_merchants": ["Esselunga", "Kiko Milano", "Conad", "Autogrill", "Eataly"],
    "card_banner": "CARTA DI DEBITO VIRTUALE",
    "profile_screen_title": "Profilo e impostazioni",
    "lab_title": "Home",
    "reset_env_btn": "Reimposta ambiente demo",
    "reset_env_title": "Reimpostare tutto?",
    "reset_env_msg": "TUTTI i dati demo locali verranno cancellati definitivamente. Verrai disconnesso.",
    "lab_footer": "Northstar Banking  ·  Edizione Demo",
    "reset_prompt": "Reimpostazione demo completata. Accedi con farofederico265@gmail.com / demo123"
}

def validate_demo_strings():
    required = {
        "bank_name", "login_banner", "login_email_hint", "login_email_default",
        "login_creds_hint", "login_security_note", "top_strip", "home_test_data",
        "home_total_label", "account_opening_party", "account_opening_desc",
        "payments_banner", "convert_rate_format", "confirm_demo_title",
        "confirm_demo_msg", "processing_payment", "card_merchants", "card_banner",
        "profile_screen_title", "lab_title", "reset_env_btn", "reset_env_title",
        "reset_env_msg", "lab_footer", "reset_prompt",
    }
    missing = sorted(required - set(DEMO_STRINGS))
    if missing:
        raise ValueError("DEMO_STRINGS is missing key(s): " + ", ".join(missing))
    for key, value in DEMO_STRINGS.items():
        if key == "card_merchants":
            continue
        if not isinstance(value, str):
            raise TypeError("DEMO_STRINGS[%r] must be text." % key)
    merchants = DEMO_STRINGS["card_merchants"]
    if not isinstance(merchants, list) or not merchants or not all(
        isinstance(item, str) and item.strip() for item in merchants
    ):
        raise TypeError("DEMO_STRINGS['card_merchants'] must be a non-empty list of text.")
    try:
        DEMO_STRINGS["convert_rate_format"] % ("£1.00", "0.8500")
    except Exception as exc:
        raise ValueError(
            "DEMO_STRINGS['convert_rate_format'] must contain exactly two compatible %s placeholders."
        ) from exc


# ============================================================== TOT THEME & COLORS
# Northstar / Italian fintech light theme
# Palette supplied in the visual design specification.
BG = (0.961, 0.961, 0.949, 1)          # #F5F5F2 warm off-white
CARD = (1, 1, 1, 1)                    # #FFFFFF
FIELD = (0.973, 0.973, 0.961, 1)       # soft neutral input surface
GREEN = (0.141, 0.361, 0.278, 1)      # #245C47 deep green
BTN = GREEN
DARK = (1, 1, 1, 1)                    # primary button foreground
WHITE = (0.09, 0.09, 0.09, 1)          # charcoal primary typography
MUTED = (0.467, 0.467, 0.451, 1)      # #777773 secondary typography
RED = (0.722, 0.294, 0.263, 1)         # #B84B43
AMBER = (0.62, 0.43, 0.16, 1)          # restrained warm status accent
NAVBG = (1, 1, 1, 1)                    # white navigation surface
SOFT = (0.918, 0.949, 0.929, 1)        # #EAF2ED muted mint surface
BORDER_COLOR = (0.91, 0.91, 0.894, 1)  # #E8E8E4 subtle separators

STATUS_HEX = {"completed": "26734D", "pending": "A8792C", "failed": "B84B43", "reversed": "777773"}

# ============================================================== DATABASE ENGINE
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE, phone TEXT NOT NULL UNIQUE, pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
 pw_iter INTEGER NOT NULL, failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL, name TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency IN ('GBP','EUR')),
 balance_minor INTEGER NOT NULL DEFAULT 0 CHECK(balance_minor>=0), sort_code TEXT, account_number TEXT, iban TEXT);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE,
 idem_key TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL REFERENCES users(id), type TEXT NOT NULL,
 direction TEXT NOT NULL CHECK(direction IN ('IN','OUT','INT')), account_id INTEGER NOT NULL REFERENCES accounts(id),
 counter_account_id INTEGER, card_id INTEGER, amount_minor INTEGER NOT NULL CHECK(amount_minor>0), currency TEXT NOT NULL,
 converted_minor INTEGER, converted_currency TEXT, rate TEXT,
 status TEXT NOT NULL CHECK(status IN ('pending','completed','failed','reversed')),
 counterparty TEXT, detail TEXT, reference TEXT, description TEXT, category TEXT, fail_reason TEXT,
 settle_at TEXT, settle_outcome TEXT, reverses_id INTEGER, created_at TEXT NOT NULL, completed_at TEXT);
CREATE INDEX IF NOT EXISTS ix_tx_user ON transactions(user_id, id);
CREATE TABLE IF NOT EXISTS ledger_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, txn_id INTEGER NOT NULL REFERENCES transactions(id),
 account_id INTEGER NOT NULL REFERENCES accounts(id), direction TEXT NOT NULL CHECK(direction IN ('DEBIT','CREDIT')),
 amount_minor INTEGER NOT NULL CHECK(amount_minor>0), currency TEXT NOT NULL, entry_type TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_led_acc ON ledger_entries(account_id);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, message TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'info', is_read INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 account_id INTEGER NOT NULL REFERENCES accounts(id), holder TEXT NOT NULL, pan_masked TEXT NOT NULL, expiry TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active', online_enabled INTEGER NOT NULL DEFAULT 1, contactless_enabled INTEGER NOT NULL DEFAULT 1,
 limit_minor INTEGER NOT NULL DEFAULT 150000);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
DEFAULTS = {"sim_outcome": "success", "sepa_delay_s": "30", "instant_delay_s": "0", "fps_delay_s": "0",
            "gbp_per_eur": "0.8500", "limit_payment_minor": "10000000", "max_failed": "5", "lockout_s": "60",
            "session_min": "10", "hide_balances": "0"}
TYPE_LABEL = {"SEPA": "Bonifico SEPA", "SEPA_INSTANT": "Bonifico SEPA Istantaneo", "UK_FPS": "UK Faster Payment",
              "INTERNAL": "Giroconto tra i miei conti", "INCOMING": "Pagamento in entrata", "TOPUP": "Fondi demo",
              "CARD": "Pagamento con carta", "CONVERSION": "Conversione di valuta", "REVERSAL": "Storno", "OPENING": "Apertura"}
STATUS_LABEL = {"pending": "IN ATTESA", "completed": "COMPLETATO", "failed": "FALLITO", "reversed": "STORNATO"}
REVERSIBLE = {"SEPA", "SEPA_INSTANT", "UK_FPS", "INTERNAL", "INCOMING", "TOPUP", "CARD", "CONVERSION"}
RAILS = {"SEPA": ("EUR", "Bonifico SEPA", "sepa_delay_s"), "SEPA_INSTANT": ("EUR", "Bonifico SEPA Istantaneo", "instant_delay_s"),
         "UK_FPS": ("GBP", "UK Faster Payment", "fps_delay_s")}
SEPA_LEN = {"AT": 20, "BE": 16, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27,
            "GB": 22, "GR": 27, "IE": 22, "IT": 27, "LU": 20, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24}
SYMBOL = {"GBP": "£", "EUR": "€"}
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

conn = None
AFTER = []
SESSION = {"uid": None, "name": "", "last": 0.0}
HOOK = {"toast": None}

class BankErr(Exception):
    def __init__(self, msg, code="error"):
        super().__init__(msg)
        self.msg = msg
        self.code = code

try:
    from zoneinfo import ZoneInfo
    _ROME = ZoneInfo("Europe/Rome")
except Exception:
    _ROME = None

def rome_now():
    """Current wall-clock time in Italy (Europe/Rome), naive. Falls back to the EU summer-time rule if tzdata is missing."""
    if _ROME is not None:
        try:
            return datetime.now(_ROME).replace(tzinfo=None)
        except Exception:
            pass
    u = datetime.utcnow()
    def last_sunday(month):
        d = datetime(u.year, month, 31, 1)
        while d.weekday() != 6:
            d -= timedelta(days=1)
        return d
    return u + timedelta(hours=2 if last_sunday(3) <= u < last_sunday(10) else 1)

def now():
    return rome_now().strftime("%Y-%m-%d %H:%M:%S")

def today():
    return rome_now().strftime("%Y-%m-%d")

def dt_it(text, short=False):
    """Stored 'YYYY-MM-DD HH:MM:SS' -> Italian display 'GG/MM/AAAA HH:MM'."""
    try:
        d = datetime.strptime((text or "")[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return text or ""
    return d.strftime("%d/%m %H:%M" if short else "%d/%m/%Y %H:%M")

def q(sql, p=()):
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

def q1(sql, p=()):
    r = conn.execute(sql, p).fetchone()
    return dict(r) if r else None

@contextmanager
def tx():
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        del AFTER[:]
        raise
    todo = AFTER[:]
    del AFTER[:]
    for fn in todo:
        try:
            fn()
        except Exception:
            pass

def setting(k):
    r = q1("SELECT value FROM settings WHERE key=?", (k,))
    return r["value"] if r else DEFAULTS[k]

def set_setting(k, v):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))

def fmt(minor, ccy, code=False):
    num = "{:,.2f}".format(Decimal(abs(minor)) / Decimal(100)).replace(",", "X").replace(".", ",").replace("X", ".")
    s = "%s%s" % (SYMBOL[ccy], num)
    return ("-" if minor < 0 else "") + s + (" " + ccy if code else "")

AMT_FILTER = lambda sub, undo: re.sub(r"[^0-9.,]", "", sub)

def parse_amount(text):
    s = (text or "").strip().replace(" ", "")
    if not s:
        raise BankErr("Inserisci un importo.")
    if "," in s and "." in s:
        raise BankErr("Usa solo la virgola per i decimali, senza separatore delle migliaia (es. 125,50).")
    s = s.replace(",", ".")
    if re.fullmatch(r"\d+\.\d{3,}", s):
        raise BankErr("L'importo può avere al massimo 2 decimali.")
    if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", s):
        raise BankErr("L'importo non è un numero valido (esempio: 125,50).")
    m = int((Decimal(s) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if m <= 0:
        raise BankErr("L'importo deve essere maggiore di zero.")
    return m

def _mod97(s):
    return int("".join(str(int(ch, 36)) for ch in s)) % 97

def make_iban(country, bban):
    return "%s%02d%s" % (country, 98 - _mod97(bban + country + "00"), bban)

def check_iban(raw):
    iban = re.sub(r"\s+", "", raw or "").upper()
    if not iban:
        return False, "Inserisci l'IBAN del beneficiario.", iban
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False, "Il formato dell'IBAN non è valido.", iban
    want = SEPA_LEN.get(iban[:2])
    if want is None:
        return False, "Il paese %s non è supportato da questa demo." % iban[:2], iban
    if len(iban) != want:
        return False, "Un IBAN %s ha %d caratteri (ne hai digitati %d)." % (iban[:2], want, len(iban)), iban
    if _mod97(iban[4:] + iban[:4]) != 1:
        return False, "Controllo IBAN non superato: verifica eventuali errori di digitazione.", iban
    return True, "", iban

def mock_iban(sc, an):
    """Mock Italian IBAN (27 chars): IT + check digits + CIN + ABI + CAB + 12-char account number."""
    return make_iban("IT", "X0542811101" + sc.replace("-", "")[:4] + an)

def mask_iban(iban):
    """Show only the country/check digits and the last 4 characters, like banking apps do."""
    iban = re.sub(r"\s+", "", iban or "")
    if len(iban) <= 8:
        return iban
    return iban[:4] + " " + "•••• " * 5 + iban[-4:]

def pretty(iban):
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))

def new_txn(c, **f):
    f.setdefault("ref", "TOT-%s-%s" % (rome_now().strftime("%y%m%d"), "".join(secrets.choice(ALPHA) for _ in range(6))))
    f.setdefault("created_at", now())
    f["completed_at"] = f["created_at"] if f.get("status") == "completed" else None
    cols = list(f)
    cur = c.execute("INSERT INTO transactions(%s) VALUES(%s)" % (",".join(cols), ",".join("?" * len(cols))), [f[k] for k in cols])
    return cur.lastrowid

def post_leg(c, tid, acc_id, direction, amount, ccy, etype="POSTING", when=None):
    a = c.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if a is None:
        raise BankErr("Conto non trovato.")
    if a["currency"] != ccy:
        raise BankErr("Valute non corrispondenti.", "currency")
    nb = a["balance_minor"] + (amount if direction == "CREDIT" else -amount)
    if nb < 0:
        raise BankErr("Fondi insufficienti.", "insufficient")
    c.execute("UPDATE accounts SET balance_minor=? WHERE id=?", (nb, acc_id))
    c.execute("INSERT INTO ledger_entries(txn_id,account_id,direction,amount_minor,currency,entry_type,created_at) VALUES(?,?,?,?,?,?,?)",
              (tid, acc_id, direction, amount, ccy, etype, when or now()))
    return nb

def notify(uid, title, msg, sev="info"):
    conn.execute("INSERT INTO notifications(user_id,title,message,severity,is_read,created_at) VALUES(?,?,?,?,0,?)",
                 (uid, title, msg, sev, now()))
    def fire():
        if HOOK["toast"]:
            HOOK["toast"](title, msg, sev)
    if conn.in_transaction:
        AFTER.append(fire)
    else:
        fire()

def get_txn(tid):
    return q1("SELECT * FROM transactions WHERE id=?", (tid,))

def accounts(uid, ccy=None):
    if ccy:
        return q("SELECT * FROM accounts WHERE user_id=? AND currency=? ORDER BY id", (uid, ccy))
    return q("SELECT * FROM accounts WHERE user_id=? ORDER BY id", (uid,))

def dup_of(c, key):
    r = c.execute("SELECT * FROM transactions WHERE idem_key=?", (key,)).fetchone()
    return dict(r, duplicate=True) if r else None

def own_acc(c, aid, uid):
    a = c.execute("SELECT * FROM accounts WHERE id=? AND user_id=?", (aid, uid)).fetchone()
    if a is None:
        raise BankErr("Conto non trovato.")
    return a

def credit(uid, acc_id, amount, kind="TOPUP", sender="Laboratorio Demo", ref=""):
    with tx() as c:
        a = own_acc(c, acc_id, uid)
        tid = new_txn(c, idem_key="cr-" + secrets.token_hex(8), user_id=uid, type=kind, direction="IN", account_id=acc_id,
                      amount_minor=amount, currency=a["currency"], status="completed", counterparty=sender, reference=ref,
                      description=("Fondi demo aggiunti" if kind == "TOPUP" else "Pagamento in entrata da " + sender), category="Income")
        nb = post_leg(c, tid, acc_id, "CREDIT", amount, a["currency"])
        notify(uid, "Saldo del conto aggiornato" if kind == "TOPUP" else "Pagamento in entrata ricevuto",
               "%s +%s. Nuovo saldo %s." % (a["name"], fmt(amount, a["currency"]), fmt(nb, a["currency"])), "success")
    return get_txn(tid)

def pay_external(uid, kind, from_id, name, detail, amount, ref, idem):
    ccy, label, dkey = RAILS[kind]
    outcome, delay = setting("sim_outcome"), int(setting(dkey))
    with tx() as c:
        d = dup_of(c, idem)
        if d:
            return d
        a = own_acc(c, from_id, uid)
        if a["currency"] != ccy:
            raise BankErr("%s deve essere pagato da un conto in %s." % (label, ccy), "currency")
        if amount > int(setting("limit_payment_minor")):
            raise BankErr("L'importo supera il limite per pagamento di %s." % fmt(int(setting("limit_payment_minor")), ccy), "limit")
        base = dict(idem_key=idem, user_id=uid, type=kind, direction="OUT", account_id=from_id, amount_minor=amount,
                    currency=ccy, counterparty=name, detail=detail, reference=ref, category="Payments",
                    description="%s a %s" % (label, name))
        notify(uid, "Bonifico avviato", "%s a %s avviato (demo)." % (fmt(amount, ccy), name))
        if a["balance_minor"] < amount:
            tid = new_txn(c, status="failed", fail_reason="Fondi insufficienti", **base)
            notify(uid, "Fondi insufficienti", "%s non copre %s. Nessun addebito." % (a["name"], fmt(amount, ccy)), "warning")
        elif outcome == "fail":
            tid = new_txn(c, status="failed", fail_reason="Rifiutato dalla rete simulata", **base)
            notify(uid, "Pagamento fallito", "%s a %s non riuscito. Nessun addebito." % (fmt(amount, ccy), name), "error")
        else:
            if outcome == "success" and delay <= 0:
                tid = new_txn(c, status="completed", **base)
            else:
                if outcome == "pending_hold":
                    so, sa = None, None
                else:
                    so = "fail" if outcome == "fail_after_pending" else "complete"
                    sa = (rome_now() + timedelta(seconds=max(delay, 10) if so == "fail" else delay)).strftime("%Y-%m-%d %H:%M:%S")
                tid = new_txn(c, status="pending", settle_at=sa, settle_outcome=so, **base)
            post_leg(c, tid, from_id, "DEBIT", amount, ccy)
            if outcome == "success" and delay <= 0:
                notify(uid, "Bonifico completato", "%s a %s completato." % (fmt(amount, ccy), name), "success")
            else:
                notify(uid, "Bonifico in attesa", "%s a %s è in attesa di regolamento." % (fmt(amount, ccy), name))
    return get_txn(tid)

def internal_transfer(uid, src, dst, amount, idem, ref=""):
    if src == dst:
        raise BankErr("Scegli due conti diversi.")
    with tx() as c:
        d = dup_of(c, idem)
        if d:
            return d
        s, t = own_acc(c, src, uid), own_acc(c, dst, uid)
        if s["currency"] != t["currency"]:
            raise BankErr("Valute diverse: usa Converti valuta.", "currency")
        if s["balance_minor"] < amount:
            notify(uid, "Fondi insufficienti", "%s non copre %s." % (s["name"], fmt(amount, s["currency"])), "warning")
            raise BankErr("Fondi insufficienti in %s." % s["name"], "insufficient")
        tid = new_txn(c, idem_key=idem, user_id=uid, type="INTERNAL", direction="INT", account_id=src, counter_account_id=dst,
                      amount_minor=amount, currency=s["currency"], status="completed", counterparty=t["name"], reference=ref,
                      description="Giroconto da %s a %s" % (s["name"], t["name"]), category="Transfer")
        post_leg(c, tid, src, "DEBIT", amount, s["currency"])
        post_leg(c, tid, dst, "CREDIT", amount, s["currency"])
        notify(uid, "Bonifico completato", "%s spostati su %s." % (fmt(amount, s["currency"]), t["name"]), "success")
    return get_txn(tid)

def quote(src_ccy, amount):
    rate = Decimal(setting("gbp_per_eur"))
    out = Decimal(amount) * rate if src_ccy == "EUR" else Decimal(amount) / rate
    return int(out.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), ("GBP" if src_ccy == "EUR" else "EUR"), rate

def convert(uid, src, dst, amount, idem):
    with tx() as c:
        d = dup_of(c, idem)
        if d:
            return d
        s, t = own_acc(c, src, uid), own_acc(c, dst, uid)
        if s["currency"] == t["currency"]:
            raise BankErr("Scegli conti con valute diverse.")
        out, dc, rate = quote(s["currency"], amount)
        if out <= 0:
            raise BankErr("Importo troppo piccolo da convertire.")
        if s["balance_minor"] < amount:
            notify(uid, "Fondi insufficienti", "%s non copre %s." % (s["name"], fmt(amount, s["currency"])), "warning")
            raise BankErr("Fondi insufficienti in %s." % s["name"], "insufficient")
        tid = new_txn(c, idem_key=idem, user_id=uid, type="CONVERSION", direction="INT", account_id=src, counter_account_id=dst,
                      amount_minor=amount, currency=s["currency"], converted_minor=out, converted_currency=dc, rate=str(rate),
                      status="completed", counterparty=t["name"], reference="Cambio demo",
                      description="Conversione da %s a %s" % (s["currency"], dc), category="Transfer")
        post_leg(c, tid, src, "DEBIT", amount, s["currency"])
        post_leg(c, tid, dst, "CREDIT", out, dc)
        notify(uid, "Bonifico completato", "Convertiti %s in %s." % (fmt(amount, s["currency"]), fmt(out, dc)), "success")
    return get_txn(tid)

def settle(uid, tid, outcome):
    with tx() as c:
        t = c.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (tid, uid)).fetchone()
        if t is None or t["status"] != "pending":
            raise BankErr("Si possono regolare solo i pagamenti in attesa.")
        if outcome == "complete":
            c.execute("UPDATE transactions SET status='completed', completed_at=?, settle_at=NULL, settle_outcome=NULL WHERE id=?", (now(), tid))
            notify(uid, "Bonifico completato", "%s a %s è stato regolato." % (fmt(t["amount_minor"], t["currency"]), t["counterparty"]), "success")
        else:
            for e in c.execute("SELECT * FROM ledger_entries WHERE txn_id=? AND entry_type='POSTING' AND direction='DEBIT'", (tid,)).fetchall():
                post_leg(c, tid, e["account_id"], "CREDIT", e["amount_minor"], e["currency"], "HOLD_RELEASE")
            c.execute("UPDATE transactions SET status='failed', fail_reason=?, settle_at=NULL, settle_outcome=NULL WHERE id=?",
                      ("Rifiutato al regolamento (simulato).", tid))
            notify(uid, "Pagamento fallito", "%s a %s è stato rifiutato." % (fmt(t["amount_minor"], t["currency"]), t["counterparty"]), "error")

def settle_due(uid=None):
    n = 0
    for r in q("SELECT id,user_id,settle_outcome FROM transactions WHERE status='pending' AND settle_at IS NOT NULL AND settle_at<=? "
               "AND settle_outcome IS NOT NULL", (now(),)):
        if uid and r["user_id"] != uid:
            continue
        try:
            settle(r["user_id"], r["id"], r["settle_outcome"])
            n += 1
        except BankErr:
            pass
    return n

def reverse(uid, tid):
    with tx() as c:
        t = c.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (tid, uid)).fetchone()
        if t is None or t["status"] != "completed" or t["type"] not in REVERSIBLE:
            raise BankErr("Si possono stornare solo i pagamenti completati.")
        legs = c.execute("SELECT * FROM ledger_entries WHERE txn_id=? AND entry_type='POSTING'", (tid,)).fetchall()
        dr = {"OUT": "IN", "IN": "OUT", "INT": "INT"}[t["direction"]]
        try:
            rid = new_txn(c, idem_key="rev-%d" % tid, user_id=uid, type="REVERSAL", direction=dr, account_id=t["account_id"],
                          counter_account_id=t["counter_account_id"], amount_minor=t["amount_minor"], currency=t["currency"],
                          status="completed", counterparty=t["counterparty"], reference="Storno di " + t["ref"],
                          description="Storno: " + (t["description"] or t["ref"]), category="Reversal", reverses_id=tid)
        except sqlite3.IntegrityError:
            raise BankErr("Questa transazione è già stata stornata.")
        try:
            for e in legs:
                post_leg(c, rid, e["account_id"], "CREDIT" if e["direction"] == "DEBIT" else "DEBIT", e["amount_minor"], e["currency"], "REVERSAL")
        except BankErr:
            raise BankErr("Impossibile stornare: saldo del conto insufficiente.")
        c.execute("UPDATE transactions SET status='reversed' WHERE id=?", (tid,))
        notify(uid, "Pagamento stornato", "%s (%s) stornato." % (fmt(t["amount_minor"], t["currency"]), t["ref"]), "warning")

def card_pay(uid, card_id, amount, merchant, channel):
    with tx() as c:
        cd = c.execute("SELECT * FROM cards WHERE id=? AND user_id=?", (card_id, uid)).fetchone()
        a = c.execute("SELECT * FROM accounts WHERE id=?", (cd["account_id"],)).fetchone()
        spent = c.execute("SELECT COALESCE(SUM(amount_minor),0) s FROM transactions WHERE card_id=? AND type='CARD' AND status='completed' "
                          "AND created_at LIKE ?", (card_id, today()[:7] + "%")).fetchone()["s"]
        why = None
        if cd["status"] != "active":
            why = "Carta bloccata"
        elif channel == "online" and not cd["online_enabled"]:
            why = "Pagamenti online disattivati"
        elif channel == "contactless" and not cd["contactless_enabled"]:
            why = "Pagamenti contactless disattivati"
        elif spent + amount > cd["limit_minor"]:
            why = "Limite di spesa mensile superato"
        elif a["balance_minor"] < amount:
            why = "Fondi insufficienti"
        base = dict(idem_key="card-" + secrets.token_hex(8), user_id=uid, type="CARD", direction="OUT", account_id=a["id"], card_id=card_id,
                    amount_minor=amount, currency=a["currency"], counterparty=merchant, reference=channel, category="Shopping",
                    description="Pagamento con carta - %s (%s)" % (merchant, channel))
        if why:
            tid = new_txn(c, status="failed", fail_reason=why, **base)
            notify(uid, "Pagamento con carta rifiutato", "%s presso %s rifiutato: %s." % (fmt(amount, a["currency"]), merchant, why), "error")
        else:
            tid = new_txn(c, status="completed", **base)
            post_leg(c, tid, a["id"], "DEBIT", amount, a["currency"])
            notify(uid, "Pagamento con carta approvato", "%s presso %s approvato." % (fmt(amount, a["currency"]), merchant), "success")
    return get_txn(tid)

def reconcile(uid):
    rows = []
    for a in accounts(uid):
        s = q1("SELECT COALESCE(SUM(CASE direction WHEN 'CREDIT' THEN amount_minor ELSE -amount_minor END),0) s FROM ledger_entries WHERE account_id=?", (a["id"],))["s"]
        rows.append((a, s, s == a["balance_minor"]))
    return rows

def total_eur(uid):
    rate = Decimal(setting("gbp_per_eur"))
    t = sum(Decimal(a["balance_minor"]) / (rate if a["currency"] == "GBP" else 1) for a in accounts(uid))
    return int(t.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def total_gbp(uid):
    rate = Decimal(setting("gbp_per_eur"))
    t = sum(Decimal(a["balance_minor"]) * (rate if a["currency"] == "EUR" else 1) for a in accounts(uid))
    return int(t.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def hash_pw(pw, salt=None, it=120000):
    salt = salt or secrets.token_bytes(16)
    return salt.hex(), hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, it).hex(), it

def norm_ident(s):
    s = (s or "").strip()
    if "@" in s:
        return s.lower()
    s = re.sub(r"[\s\-().]", "", s)
    if s.startswith("00"):
        s = "+" + s[2:]
    if re.fullmatch(r"07\d{9}", s):
        s = "+44" + s[1:]
    return s

def ident_problem(s):
    n = norm_ident(s)
    if not n:
        return "Inserisci il tuo indirizzo email o numero di cellulare."
    if "@" in n:
        return None if re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", n) else "Questo indirizzo email non sembra corretto."
    return None if re.fullmatch(r"\+?\d{8,15}", n) else "Inserisci un numero di cellulare valido (es. +39 333 1234567)."

def login(ident, pw):
    p = ident_problem(ident)
    if p:
        raise BankErr(p)
    if not pw:
        raise BankErr("Inserisci la password.")
    n = norm_ident(ident)
    u = q1("SELECT * FROM users WHERE " + ("email=?" if "@" in n else "phone=?"), (n,))
    if not u:
        hash_pw(pw)
        raise BankErr("Email/numero di cellulare o password non corretti.")
    t = datetime.now().timestamp()
    if u["locked_until"] > t:
        raise BankErr("Troppi tentativi falliti. Riprova tra %d secondi." % int(u["locked_until"] - t + 1))
    _, h, _ = hash_pw(pw, bytes.fromhex(u["pw_salt"]), u["pw_iter"])
    if not hmac.compare_digest(h, u["pw_hash"]) and pw != pw.strip():
        _, h, _ = hash_pw(pw.strip(), bytes.fromhex(u["pw_salt"]), u["pw_iter"])
    if not hmac.compare_digest(h, u["pw_hash"]):
        att, lim = u["failed_attempts"] + 1, int(setting("max_failed"))
        if att >= lim:
            conn.execute("UPDATE users SET failed_attempts=0, locked_until=? WHERE id=?", (t + int(setting("lockout_s")), u["id"]))
            msg = "Troppi tentativi falliti. Accesso bloccato per %s secondi." % setting("lockout_s")
        else:
            conn.execute("UPDATE users SET failed_attempts=? WHERE id=?", (att, u["id"]))
            msg = "Credenziali non corrette. (%d tentativo/i rimasto/i)" % (lim - att)
        notify(u["id"], "Tentativo di accesso non riuscito", "Un tentativo di accesso è stato rifiutato alle %s." % dt_it(now()), "warning")
        raise BankErr(msg)
    conn.execute("UPDATE users SET failed_attempts=0, locked_until=0 WHERE id=?", (u["id"],))
    SESSION.update(uid=u["id"], name=u["full_name"], last=t)
    notify(u["id"], "Accesso riuscito", "Accesso effettuato alle %s." % dt_it(now()), "success")

def change_password(uid, cur, new, conf):
    u = q1("SELECT * FROM users WHERE id=?", (uid,))
    _, h, _ = hash_pw(cur or "", bytes.fromhex(u["pw_salt"]), u["pw_iter"])
    if not hmac.compare_digest(h, u["pw_hash"]):
        raise BankErr("La password attuale non è corretta.")
    if len(new) < 6:
        raise BankErr("La nuova password deve avere almeno 6 caratteri.")
    if new != conf:
        raise BankErr("Le nuove password non coincidono.")
    s, nh, it = hash_pw(new)
    conn.execute("UPDATE users SET pw_salt=?, pw_hash=?, pw_iter=? WHERE id=?", (s, nh, it, uid))
    notify(uid, "Password modificata", "La tua password demo è stata modificata.", "success")

def seed():
    with tx() as c:
        s, h, it = hash_pw("demo123")
        uid = c.execute("INSERT INTO users(full_name,email,phone,pw_salt,pw_hash,pw_iter,created_at) VALUES(?,?,?,?,?,?,?)",
                        ("Federico Faro", "farofederico265@gmail.com", "+447123456789", s, h, it, now())).lastrowid
        ids = {}
        for kind, name, ccy, opening, sc, an in [("CURRENT", "Conto Corrente EUR", "EUR", 10000000, "40-22-04", "82910382"),
                                                  ("SAVINGS", "Conto Risparmio EUR", "EUR", 10000000, "40-22-04", "82910399"),
                                                  ("WALLET", "Wayne S.R.L Main Account", "EUR", 10000000, "99-00-12", "55100382")]:
            iban = make_iban("GB", "TOTB" + sc.replace("-", "") + an) if ccy == "GBP" else mock_iban(sc, an)
            aid = c.execute("INSERT INTO accounts(user_id,kind,name,currency,balance_minor,sort_code,account_number,iban) VALUES(?,?,?,?,0,?,?,?)",
                            (uid, kind, name, ccy, sc, an, iban)).lastrowid
            ids[kind] = aid
            t = new_txn(c, idem_key="open-" + kind, user_id=uid, type="OPENING", direction="IN", account_id=aid, amount_minor=opening,
                        currency=ccy, status="completed", counterparty=DEMO_STRINGS["account_opening_party"], description=DEMO_STRINGS["account_opening_desc"],
                        category="Opening", created_at=(rome_now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S"))
            post_leg(c, t, aid, "CREDIT", opening, ccy, "OPENING")
        cid = c.execute("INSERT INTO cards(user_id,account_id,holder,pan_masked,expiry) VALUES(?,?,?,?,?)",
                        (uid, ids["CURRENT"], "ALEX MORGAN", "•••• •••• •••• 8821", "09/28")).lastrowid
        cur_ccy = c.execute("SELECT currency FROM accounts WHERE id=?", (ids["CURRENT"],)).fetchone()[0]
        hist = [("INCOMING", "IN", 125000, "Azienda Demo S.r.l.", "Stipendio (demo)", 6, None), ("CARD", "OUT", 6230, "Alimentari Demo", "chip", 5, cid),
                ("CARD", "OUT", 1840, "Trasporti Cittadini", "contactless", 4, cid), ("CARD", "OUT", 2480, "Bar dell'Angolo", "chip", 2, cid),
                ("CARD", "OUT", 9950, "Abbigliamento Demo", "online", 1, cid)]
        for i, (ty, di, amt, who, ref, ago, card) in enumerate(hist):
            when = (rome_now() - timedelta(days=ago)).replace(hour=10, minute=15, second=0).strftime("%Y-%m-%d %H:%M:%S")
            t = new_txn(c, idem_key="seed-%d" % i, user_id=uid, type=ty, direction=di, account_id=ids["CURRENT"], card_id=card,
                        amount_minor=amt, currency=cur_ccy, status="completed", counterparty=who, reference=ref, created_at=when,
                        description=("Pagamento in entrata da " + who) if ty == "INCOMING" else "Pagamento con carta - %s (%s)" % (who, ref), category="Seed")
            post_leg(c, t, ids["CURRENT"], "CREDIT" if di == "IN" else "DEBIT", amt, cur_ccy, "POSTING", when)
        notify(uid, "Benvenuto in Tot.", "Interfaccia bancaria digitale simulata.")

def ensure_demo_user():
    """Old database files keep the OLD demo user (old email/password) because seed() only runs on an empty DB.
    If the demo login is missing, repoint the first user to the current demo credentials and clear any lockout."""
    email, phone, name = "farofederico265@gmail.com", "+447123456789", "Federico Faro"
    if q1("SELECT id FROM users WHERE email=?", (email,)):
        conn.execute("UPDATE users SET failed_attempts=0, locked_until=0 WHERE email=?", (email,))
        return
    first = q1("SELECT id FROM users ORDER BY id LIMIT 1")
    if not first:
        return
    s, h, it = hash_pw("demo123")
    try:
        conn.execute("UPDATE users SET full_name=?, email=?, phone=?, pw_salt=?, pw_hash=?, pw_iter=?, failed_attempts=0, locked_until=0 WHERE id=?",
                     (name, email, phone, s, h, it, first["id"]))
    except sqlite3.IntegrityError:
        pass

def ensure_it_ibans():
    """Databases created earlier hold IE-style IBANs; convert the EUR accounts to the Italian mock format once."""
    for a in q("SELECT id, sort_code, account_number, iban, currency FROM accounts"):
        if a["currency"] == "EUR" and a["sort_code"] and a["account_number"] and not (a["iban"] or "").startswith("IT"):
            conn.execute("UPDATE accounts SET iban=? WHERE id=?", (mock_iban(a["sort_code"], a["account_number"]), a["id"]))

def open_db():
    global conn, DB_NAME
    try:
        app = App.get_running_app()
        if app is not None and hasattr(app, "user_data_dir"):
            os.makedirs(app.user_data_dir, exist_ok=True)
            DB_NAME = os.path.join(app.user_data_dir, "northstar_demo_v4.db")
    except Exception:
        pass
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    for k, v in DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    if not q1("SELECT id FROM users LIMIT 1"):
        seed()
    ensure_demo_user()
    ensure_it_ibans()

def reset_db():
    global conn
    conn.close()
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    open_db()


# ============================================================== UI HELPERS & TOT STYLING
def bgfill(w, rgba, radius=12, border_color=None):
    with w.canvas.before:
        Color(*rgba)
        r = RoundedRectangle(pos=w.pos, size=w.size, radius=[radius])
        if border_color:
            Color(*border_color)
            l = Line(rounded_rectangle=(w.x, w.y, w.width, w.height, radius), width=1.1)
    def _upd(*a):
        r.pos = w.pos
        r.size = w.size
        if border_color:
            l.rounded_rectangle = (w.x, w.y, w.width, w.height, radius)
    w.bind(pos=_upd, size=_upd)

def lab(text, size=14, color=WHITE, bold=False, h=None, halign="left", markup=False):
    l = Label(text=text, font_size=sp(size), color=color, bold=bold, halign=halign, valign="middle", markup=markup, size_hint_y=None)
    l.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
    if h:
        l.height = dp(h)
    else:
        l.bind(texture_size=lambda i, s: setattr(i, "height", s[1] + dp(6)))
    return l

def vbox(spacing=10, padding=0):
    b = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(spacing), padding=dp(padding))
    b.bind(minimum_height=b.setter("height"))
    return b

def card_box(padding=16, spacing=7, radius=16):
    b = vbox(spacing, padding)
    bgfill(b, CARD, dp(radius), BORDER_COLOR)
    return b

def btn(text, cb, bg=BTN, fg=DARK, h=48, radius=12):
    b = Button(text=text, background_normal="", background_color=(0,0,0,0), color=fg, bold=True, font_size=sp(14), size_hint_y=None, height=dp(h))
    bgfill(b, bg, dp(radius))
    b.bind(on_press=lambda *a: cb())
    return b

def inp(hint="", text="", password=False, filt=None, h=48):
    ti = TextInput(text=text, hint_text=hint, multiline=False, password=password, input_filter=filt, size_hint_y=None, height=dp(h),
                     background_normal="", background_active="", background_color=FIELD, foreground_color=(0.04, 0.24, 0.17, 1),
                     hint_text_color=(0.30, 0.42, 0.36, 1), cursor_color=GREEN, padding=[dp(14), dp(14), dp(14), dp(10)], font_size=sp(14))
    bgfill(ti, FIELD, dp(12), BORDER_COLOR)
    return ti

def spin(values, text=None):
    sp_ = Spinner(text=text or values[0], values=values, size_hint_y=None, height=dp(48), background_normal="",
                   background_color=(0,0,0,0), color=WHITE, font_size=sp(14))
    bgfill(sp_, FIELD, dp(12), BORDER_COLOR)
    return sp_

def popup(title, body_widget, size=(0.92, None), height=None):
    p = Popup(title=title, content=body_widget, size_hint=size, auto_dismiss=False,
              title_color=GREEN, separator_color=BORDER_COLOR, background_color=(1, 1, 1, 1))
    if height:
        p.height = dp(height)
    p.open()
    return p

def message(title, text, kind="info"):
    col = {"error": RED, "success": GREEN, "warning": AMBER}.get(kind, WHITE)
    body = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    sv = ScrollView()
    inner = vbox()
    inner.add_widget(lab(text, 14, col))
    sv.add_widget(inner)
    body.add_widget(sv)
    p = popup(title, body, (0.92, 0.6))
    body.add_widget(btn("OK", p.dismiss))
    return p

def ask(title, text, on_yes, yes="Conferma", danger=False):
    body = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    sv = ScrollView()
    inner = vbox()
    inner.add_widget(lab(text, 14))
    sv.add_widget(inner)
    body.add_widget(sv)
    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    p = popup(title, body, (0.92, 0.55))

    def go():
        p.dismiss()
        Clock.schedule_once(lambda dt: on_yes(), 0.05)
    row.add_widget(btn("Annulla", p.dismiss, SOFT, WHITE))
    row.add_widget(btn(yes, go, RED if danger else BTN, WHITE if danger else DARK))
    body.add_widget(row)
    return p

def processing(text, ms, work):
    body = BoxLayout(orientation="vertical", padding=dp(16))
    body.add_widget(lab(text, 15, GREEN, True, halign="center", h=60))
    p = Popup(title="Elaborazione", content=body, size_hint=(0.8, None), height=dp(150), auto_dismiss=False,
              title_color=GREEN, separator_color=BORDER_COLOR, background_color=(1, 1, 1, 1))
    p.open()
    app = App.get_running_app()
    app.busy = True

    def done(dt):
        p.dismiss()
        app.busy = False
        work()
    Clock.schedule_once(done, ms / 1000.0)

def txn_line(t):
    sign = {"IN": "+", "OUT": "-", "INT": ""}[t["direction"]]
    col = STATUS_HEX[t["status"]]
    return "[b]%s[/b]  [color=%s]%s%s[/color]\n[size=%d][color=8c9ba5]%s | %s | [/color][color=%s]%s[/color][/size]" % (
        (t["description"] or t["counterparty"] or t["ref"])[:34], "171717" if t["direction"] != "IN" else "26734D", sign,
        fmt(t["amount_minor"], t["currency"]), int(sp(11)), dt_it(t["created_at"], True), TYPE_LABEL.get(t["type"], t["type"]), col, STATUS_LABEL.get(t["status"], t["status"].upper()))

def tx_button(t, cb):
    b = Button(text=txn_line(t), markup=True, background_normal="", background_color=(0,0,0,0), halign="left", valign="middle",
               size_hint_y=None, height=dp(68), font_size=sp(13), color=WHITE)
    bgfill(b, CARD, dp(12), BORDER_COLOR)
    b.bind(size=lambda i, s: setattr(i, "text_size", (s[0] - dp(24), None)))
    b.bind(on_press=lambda *a: cb(t["id"]))
    return b

def show_txn(tid, after=None):
    app = App.get_running_app()
    t = get_txn(tid)
    if not t or t["user_id"] != SESSION["uid"]:
        return
    body = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    sv = ScrollView()
    box = vbox(4)
    st = t["status"]
    box.add_widget(lab(STATUS_LABEL.get(st, st.upper()), 18, {"completed": GREEN, "pending": AMBER, "failed": RED}.get(st, MUTED), True))
    sign = {"IN": "+", "OUT": "-", "INT": ""}[t["direction"]]
    box.add_widget(lab("%s%s" % (sign, fmt(t["amount_minor"], t["currency"], True)), 24, WHITE, True))
    if t["type"] == "CONVERSION":
        box.add_widget(lab("Ricevuti %s al tasso demo %s" % (fmt(t["converted_minor"], t["converted_currency"]), t["rate"]), 12, MUTED))
    acc = q1("SELECT name FROM accounts WHERE id=?", (t["account_id"],))
    rows = [("Riferimento", t["ref"]), ("Metodo", TYPE_LABEL.get(t["type"], t["type"])), ("Data", dt_it(t["created_at"])),
            ("Controparte", t["counterparty"]), ("Dettagli", t["detail"]), ("Causale", t["reference"]),
            ("Conto", acc["name"] if acc else ""), ("Motivo", t["fail_reason"]),
            ("Regolamento", dt_it(t["settle_at"]) if st == "pending" and t["settle_at"] else None)]
    for k, v in rows:
        if v:
            box.add_widget(lab("%s: %s" % (k, v), 13, MUTED))
    box.add_widget(lab("RICEVUTA WAYNE S.R.L", 11, AMBER))
    sv.add_widget(box)
    body.add_widget(sv)
    p = popup("Dettaglio transazione", body, (0.94, 0.8))

    def run(fn, *a):
        try:
            fn(*a)
        except BankErr as e:
            message("Operazione non possibile", e.msg, "error")
        p.dismiss()
        app.refresh_all()
        if after:
            after()
    if st == "pending":
        body.add_widget(btn("Autorizza", lambda: run(settle, SESSION["uid"], tid, "complete"), h=42))
        body.add_widget(btn("Presenta contestazione", lambda: run(settle, SESSION["uid"], tid, "fail"), SOFT, WHITE, 42))
    if st == "completed" and t["type"] in REVERSIBLE:
        body.add_widget(btn("Storna (demo)", lambda: ask("Stornare la transazione?", "Viene creato un movimento di storno e i saldi vengono ripristinati.",
                           lambda: run(reverse, SESSION["uid"], tid), "Storna", True), RED, WHITE, 42))
    body.add_widget(btn("Chiudi", p.dismiss, SOFT, WHITE, 42))


# ============================================================== SCREENS (TOT APP DESIGN)
class Page(Screen):
    title = ""

    def on_enter(self):
        self.refresh()

    def refresh(self):
        if not SESSION["uid"]:
            return
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=[dp(16), dp(4), dp(16), dp(12)], spacing=dp(12))
        bgfill(root, BG, 0)
        head = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        head.add_widget(lab(self.title, 23, WHITE, True, 52))
        self.extra_header(head)
        root.add_widget(head)
        sv = ScrollView()
        self.content = vbox(12)
        sv.add_widget(self.content)
        root.add_widget(sv)
        self.add_widget(root)
        self.build(self.content)

    def extra_header(self, head):
        pass

    def build(self, c):
        pass


class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.busy = False
        root = BoxLayout(orientation="vertical", padding=[dp(22), dp(4), dp(22), dp(20)])
        bgfill(root, BG, 0)
        sv = ScrollView()
        col = vbox(12, 4)
        col.add_widget(BoxLayout(size_hint_y=None, height=dp(10)))
        
        # User-supplied horse logo, styled as a restrained brand tile.
        logo_box = FloatLayout(size_hint=(None, None), size=(dp(112), dp(112)),
                               pos_hint={"center_x": 0.5})
        with logo_box.canvas.before:
            Color(*CARD)
            r_box = RoundedRectangle(pos=logo_box.pos, size=logo_box.size, radius=[dp(18)])
            Color(*BORDER_COLOR)
            l_box = Line(rounded_rectangle=(logo_box.x, logo_box.y, logo_box.width,
                                             logo_box.height, dp(18)), width=1)
        def _upd_logo(*a):
            r_box.pos = logo_box.pos
            r_box.size = logo_box.size
            l_box.rounded_rectangle = (logo_box.x, logo_box.y, logo_box.width,
                                       logo_box.height, dp(18))
        logo_box.bind(pos=_upd_logo, size=_upd_logo)

        logo_image = AsyncImage(source=LOGO_URL, size_hint=(None, None),
                                size=(dp(104), dp(104)), allow_stretch=True,
                                keep_ratio=True, pos_hint={"center_x": 0.5, "center_y": 0.5})
        logo_box.add_widget(logo_image)
        col.add_widget(logo_box)

        col.add_widget(lab(DEMO_STRINGS["bank_name"], 25, GREEN, True, 38, "center"))
        col.add_widget(lab(DEMO_STRINGS["login_banner"], 10, GREEN, True, 20, "center"))
        col.add_widget(lab("Bentornato", 26, WHITE, True, 38, "left"))
        col.add_widget(lab("Un modo più sereno di gestire il tuo denaro.", 13, MUTED, False, 22))
        col.add_widget(lab("Email o numero di cellulare", 12, MUTED, False, 20))
        
        self.f_id = inp(DEMO_STRINGS["login_email_hint"], DEMO_STRINGS["login_email_default"])
        col.add_widget(self.f_id)
        col.add_widget(lab("Password", 12, MUTED, False, 20))
        
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.f_pw = inp("Password", "", True)
        row.add_widget(self.f_pw)
        self.eye = Button(text="Mostra", size_hint=(None, 1), width=dp(76), background_normal="", background_color=(0,0,0,0), color=WHITE)
        bgfill(self.eye, SOFT, dp(12), BORDER_COLOR)
        self.eye.bind(on_press=self.toggle_pw)
        row.add_widget(self.eye)
        col.add_widget(row)
        
        self.err = lab("", 12, RED, False, None, "left")
        col.add_widget(self.err)
        self.go_btn = btn("Accedi", self.do_login, h=52, radius=14)
        col.add_widget(self.go_btn)
        col.add_widget(lab(DEMO_STRINGS["login_creds_hint"], 11, MUTED, False, 24, "center"))
        col.add_widget(lab(DEMO_STRINGS["login_security_note"], 10, MUTED, False, 24, "center"))
        
        sv.add_widget(col)
        root.add_widget(sv)
        self.add_widget(root)

    def on_pre_enter(self):
        self.f_pw.text = ""
        self.f_pw.password = True
        self.eye.text = "Mostra"
        self.busy = False
        self.go_btn.disabled = False
        self.go_btn.text = "Accedi"

    def toggle_pw(self, *a):
        self.f_pw.password = not self.f_pw.password
        self.eye.text = "Mostra" if self.f_pw.password else "Nascondi"

    def do_login(self):
        if self.busy:
            return
        p = ident_problem(self.f_id.text)
        if p:
            self.err.text = p
            return
        if not self.f_pw.text:
            self.err.text = "Inserisci la password."
            return
        self.err.text = ""
        self.busy = True
        self.go_btn.disabled = True
        self.go_btn.text = "Accesso in corso..."
        ident, pw = self.f_id.text, self.f_pw.text
        Clock.schedule_once(lambda dt: self.finish(ident, pw), 0.5)

    def finish(self, ident, pw):
        try:
            login(ident, pw)
        except BankErr as e:
            self.err.text = e.msg
            self.f_pw.text = ""
            self.busy = False
            self.go_btn.disabled = False
            self.go_btn.text = "Accedi"
            return
        self.f_pw.text = ""
        App.get_running_app().after_login()


class HomeScreen(Page):
    title = "Panoramica"

    def extra_header(self, head):
        n = q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (SESSION["uid"],))["c"]
        b = Button(text="Avvisi (%d)" % n if n else "Avvisi", size_hint=(None, None), size=(dp(96), dp(38)), background_normal="",
                   background_color=(0,0,0,0), color=WHITE, font_size=sp(12))
        bgfill(b, SOFT, dp(10), BORDER_COLOR)
        b.bind(on_press=lambda *a: App.get_running_app().open_notifications())
        head.add_widget(b)

    def build(self, c):
        uid, hide = SESSION["uid"], setting("hide_balances") == "1"
        
        # User Header Row with Logo
        user_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        logo_mini = AsyncImage(source=LOGO_URL, size_hint=(None, None),
                               size=(dp(40), dp(40)), allow_stretch=True,
                               keep_ratio=True)
        user_row.add_widget(logo_mini)
        user_row.add_widget(lab("Ciao, %s" % SESSION["name"], 18, WHITE, True))
        c.add_widget(user_row)
        
        # Main Net Worth Card
        tot = card_box(16, 6)
        tot.add_widget(lab(DEMO_STRINGS["home_total_label"], 12, MUTED))
        tot.add_widget(lab("€ ••••••" if hide else fmt(total_eur(uid), "EUR", True), 28, GREEN, True))
        tot.add_widget(btn("Mostra saldi" if hide else "Nascondi saldi", self.toggle, SOFT, WHITE, 36))
        c.add_widget(tot)

        # Lightweight cashflow summary derived from the existing ledger.
        month_prefix = today()[:7] + "%"
        incoming = q1("SELECT COALESCE(SUM(amount_minor),0) AS total FROM transactions WHERE user_id=? AND direction='IN' AND status='completed' AND created_at LIKE ?", (uid, month_prefix))["total"]
        outgoing = q1("SELECT COALESCE(SUM(amount_minor),0) AS total FROM transactions WHERE user_id=? AND direction='OUT' AND status='completed' AND created_at LIKE ?", (uid, month_prefix))["total"]
        flow = GridLayout(cols=2, size_hint_y=None, height=dp(104), spacing=dp(10))
        inc = card_box(13, 4, 14)
        inc.add_widget(lab("ENTRATE  ·  QUESTO MESE", 10, MUTED, True))
        inc.add_widget(lab("••••••" if hide else fmt(incoming, "EUR"), 20, GREEN, True))
        exp = card_box(13, 4, 14)
        exp.add_widget(lab("USCITE  ·  QUESTO MESE", 10, MUTED, True))
        exp.add_widget(lab("••••••" if hide else fmt(outgoing, "EUR"), 20, RED, True))
        flow.add_widget(inc)
        flow.add_widget(exp)
        c.add_widget(flow)
        
        # Accounts
        for a in accounts(uid):
            cb = card_box(14, 4)
            cb.add_widget(lab("%s" % a["name"], 14, WHITE, True))
            cb.add_widget(lab("••••••" if hide else fmt(a["balance_minor"], a["currency"], True), 22, GREEN, True))
            cb.add_widget(lab(("Sort Code %s  Conto %s" % (a["sort_code"], a["account_number"])) if a["currency"] == "GBP" else "IBAN " + mask_iban(a["iban"]), 11, MUTED))
            c.add_widget(cb)
            
        grid = GridLayout(cols=2, size_hint_y=None, height=dp(104), spacing=dp(10))
        app = App.get_running_app()
        grid.add_widget(btn("Invia denaro", lambda: app.switch_tab("payments")))
        grid.add_widget(btn("Carte", lambda: app.switch_tab("cards"), SOFT, WHITE))
        grid.add_widget(btn("Attività", lambda: app.switch_tab("activity"), SOFT, WHITE))
        grid.add_widget(btn("Impostazioni", lambda: app.switch_tab("profile"), SOFT, AMBER))
        c.add_widget(grid)
        
        c.add_widget(lab("Attività recente", 17, WHITE, True))
        rows = q("SELECT * FROM transactions WHERE user_id=? AND type!='OPENING' ORDER BY id DESC LIMIT 5", (uid,))
        if not rows:
            c.add_widget(lab("Nessuna transazione.", 13, MUTED))
        for t in rows:
            c.add_widget(tx_button(t, lambda i: show_txn(i)))

    def toggle(self):
        set_setting("hide_balances", "0" if setting("hide_balances") == "1" else "1")
        self.refresh()


KINDS = [("Bonifico SEPA", "SEPA"), ("Bonifico SEPA Istantaneo", "SEPA_INSTANT"), ("UK Faster Payment", "UK_FPS"),
         ("Tra i miei conti", "INTERNAL"), ("Converti valuta", "CONVERT")]


class PaymentsScreen(Page):
    title = "Pagamenti e bonifici"
    kind = "SEPA"

    def build(self, c):
        self.sp_kind = spin([k for k, _ in KINDS], dict((v, k) for k, v in KINDS)[self.kind])
        self.sp_kind.bind(text=self.on_kind)
        c.add_widget(self.sp_kind)
        self.form = vbox(10)
        c.add_widget(self.form)
        self.build_form()

    def on_kind(self, sp_, text):
        self.kind = dict(KINDS)[text]
        self.build_form()

    def acc_spinner(self, ccy=None):
        accs = accounts(SESSION["uid"], ccy)
        labels = ["%s  %s" % (a["name"], fmt(a["balance_minor"], a["currency"])) for a in accs]
        if not labels:
            # Keep the screen usable if an account is missing instead of
            # crashing while Spinner tries to read values[0].
            labels = ["Nessun conto idoneo"]
        m = dict(zip(labels, [a["id"] for a in accs]))
        return spin(labels), m

    def build_form(self):
        f, k = self.form, self.kind
        f.clear_widgets()
        self.idem = "pay-" + secrets.token_hex(10)
        self.f = {}
        f.add_widget(lab(DEMO_STRINGS["payments_banner"], 11, AMBER))
        if k in RAILS:
            ccy = RAILS[k][0]
            f.add_widget(lab("Paga da (conto %s)" % ccy, 12, MUTED, False, 20))
            self.sp_from, self.map_from = self.acc_spinner(ccy)
            f.add_widget(self.sp_from)
            self.f["name"] = inp("Nome del beneficiario")
            f.add_widget(self.f["name"])
            if k == "UK_FPS":
                self.f["sort"] = inp("Sort Code (es. 11-22-33)")
                self.f["acct"] = inp("Numero di conto (8 cifre)", filt="int")
                f.add_widget(self.f["sort"])
                f.add_widget(self.f["acct"])
            else:
                self.f["iban"] = inp("IBAN (es. IT60 X054 2811 1010 0000 0123 456)")
                f.add_widget(self.f["iban"])
            self.f["amount"] = inp("Importo (%s)" % ccy, filt=AMT_FILTER)
            self.f["ref"] = inp("Causale")
            f.add_widget(self.f["amount"])
            f.add_widget(self.f["ref"])
        else:
            f.add_widget(lab("Da", 12, MUTED, False, 20))
            self.sp_from, self.map_from = self.acc_spinner()
            f.add_widget(self.sp_from)
            f.add_widget(lab("A", 12, MUTED, False, 20))
            self.sp_to, self.map_to = self.acc_spinner()
            if len(self.sp_to.values) > 1:
                self.sp_to.text = self.sp_to.values[1]
            f.add_widget(self.sp_to)
            self.f["amount"] = inp("Importo (valuta di origine)", filt=AMT_FILTER)
            f.add_widget(self.f["amount"])
            if k == "CONVERT":
                self.quote = lab("", 13, GREEN, True)
                f.add_widget(self.quote)
                self.f["amount"].bind(text=lambda *a: self.update_quote())
        self.msg = lab("", 12, RED)
        f.add_widget(self.msg)
        f.add_widget(btn("Rivedi bonifico", self.review, h=50))

    def update_quote(self):
        try:
            a = q1("SELECT * FROM accounts WHERE id=?", (self.map_from[self.sp_from.text],))
            o, dc, _ = quote(a["currency"], parse_amount(self.f["amount"].text))
            self.quote.text = DEMO_STRINGS["convert_rate_format"] % (fmt(o, dc), setting("gbp_per_eur").replace(".", ","))
        except Exception:
            self.quote.text = ""

    def review(self):
        app, k = App.get_running_app(), self.kind
        if app.busy:
            return
        try:
            amount = parse_amount(self.f["amount"].text)
            src = self.map_from[self.sp_from.text]
            sa = q1("SELECT * FROM accounts WHERE id=?", (src,))
            if k in RAILS:
                name = self.f["name"].text.strip()
                if len(name) < 2:
                    raise BankErr("Inserisci il nome del beneficiario.")
                ref = self.f["ref"].text.strip()
                if not ref:
                    raise BankErr("Inserisci la causale del pagamento.")
                if k == "UK_FPS":
                    sc = re.sub(r"\D", "", self.f["sort"].text)
                    ac = re.sub(r"\D", "", self.f["acct"].text)
                    if len(sc) != 6:
                        raise BankErr("Lo sort code deve avere 6 cifre.")
                    if len(ac) != 8:
                        raise BankErr("Il numero di conto deve avere 8 cifre.")
                    detail = "%s-%s-%s / %s" % (sc[:2], sc[2:4], sc[4:], ac)
                    if len(ref) > 18:
                        raise BankErr("La causale UK può avere al massimo 18 caratteri.")
                else:
                    ok, why, iban = check_iban(self.f["iban"].text)
                    if not ok:
                        raise BankErr(why)
                    detail = iban
                if sa["currency"] != RAILS[k][0]:
                    raise BankErr("Scegli un conto in %s." % RAILS[k][0])
                summary = "Metodo: %s\nDa: %s\nA: %s\nDettagli: %s\nCausale: %s\nImporto: %s" % (
                    RAILS[k][1], sa["name"], name, pretty(detail) if k != "UK_FPS" else detail, ref, fmt(amount, sa["currency"], True))
                work = lambda: pay_external(SESSION["uid"], k, src, name, detail, amount, ref, self.idem)
                ms = 600 if k == "SEPA_INSTANT" else 1500
            else:
                dst = self.map_to[self.sp_to.text]
                da = q1("SELECT * FROM accounts WHERE id=?", (dst,))
                if src == dst:
                    raise BankErr("Scegli due conti diversi.")
                if k == "INTERNAL":
                    if sa["currency"] != da["currency"]:
                        raise BankErr("Valute diverse: usa 'Converti valuta'.")
                    summary = "Sposta %s\nDa: %s\nA: %s" % (fmt(amount, sa["currency"], True), sa["name"], da["name"])
                    work = lambda: internal_transfer(SESSION["uid"], src, dst, amount, self.idem)
                else:
                    if sa["currency"] == da["currency"]:
                        raise BankErr("Scegli conti con valute diverse.")
                    o, dc, _ = quote(sa["currency"], amount)
                    summary = "Converti %s\nDa: %s\nIn: %s (circa %s)" % (fmt(amount, sa["currency"], True), sa["name"], da["name"], fmt(o, dc))
                    work = lambda: convert(SESSION["uid"], src, dst, amount, self.idem)
                ms = 800
        except (BankErr, KeyError) as e:
            self.msg.text = e.msg if isinstance(e, BankErr) else "Scegli un conto."
            if isinstance(e, BankErr):
                notify(SESSION["uid"], "Dati di pagamento non validi", e.msg, "warning")
            return
        self.msg.text = ""
        ask(DEMO_STRINGS["confirm_demo_title"], summary + "\n\n" + DEMO_STRINGS["confirm_demo_msg"],
            lambda: processing(DEMO_STRINGS["processing_payment"], ms, lambda: self.finish(work)), "Conferma e invia")

    def finish(self, work):
        try:
            t = work()
        except BankErr as e:
            message("Non completato", e.msg, "error")
            self.idem = "pay-" + secrets.token_hex(10)
            return
        App.get_running_app().refresh_all()
        self.build_form()
        show_txn(t["id"])


class CardsScreen(Page):
    title = "Cards"
    CHAN = ["online", "contactless", "chip"]

    def build(self, c):
        uid = SESSION["uid"]
        cd = q1("SELECT * FROM cards WHERE user_id=?", (uid,))
        if not cd:
            c.add_widget(lab("Nessuna carta disponibile.", 14, MUTED))
            return
        self.cd = cd
        
        # Virtual TOT Card Visual
        box = card_box(18, 6, radius=18)
        bgfill(box, (0.918, 0.949, 0.929, 1), dp(18), BORDER_COLOR)
        box.add_widget(lab("NORTHSTAR  /  DEBITO", 14, GREEN, True))
        box.add_widget(lab(cd["pan_masked"], 22, WHITE, True))
        box.add_widget(lab("SCAD. %s     %s" % (cd["expiry"], cd["holder"]), 12, WHITE))
        box.add_widget(lab(DEMO_STRINGS["card_banner"], 10, AMBER, True))
        c.add_widget(box)
        
        spent = q1("SELECT COALESCE(SUM(amount_minor),0) s FROM transactions WHERE card_id=? AND type='CARD' AND status='completed' AND created_at LIKE ?",
                   (cd["id"], today()[:7] + "%"))["s"]
        frozen = cd["status"] == "frozen"
        c.add_widget(lab("Stato: BLOCCATA" if frozen else "Stato: ATTIVA", 16, RED if frozen else GREEN, True))
        c.add_widget(btn("Sblocca carta" if frozen else "Blocca carta", lambda: self.set("status", "active" if frozen else "frozen"),
                         BTN if frozen else RED, DARK if frozen else WHITE))
        for col, name in (("online_enabled", "Pagamenti online"), ("contactless_enabled", "Pagamenti contactless")):
            on = bool(cd[col])
            c.add_widget(btn("%s: %s" % (name, "ATTIVI" if on else "DISATTIVATI"), lambda col=col, on=on: self.set(col, 0 if on else 1), SOFT, WHITE))
        c.add_widget(lab("Limite mensile %s (utilizzato %s)" % (fmt(cd["limit_minor"], "EUR"), fmt(spent, "EUR")), 13, MUTED))
        self.f_lim = inp("Nuovo limite mensile (EUR)", filt=AMT_FILTER)
        c.add_widget(self.f_lim)
        c.add_widget(btn("Salva limite", self.save_limit, SOFT, WHITE))
        
        c.add_widget(lab("Simulatore pagamenti con carta", 16, WHITE, True))
        self.s_m = spin(DEMO_STRINGS["card_merchants"])
        self.s_c = spin(self.CHAN)
        self.f_amt = inp("Importo (EUR)", "12,50", filt=AMT_FILTER)
        for w in (self.s_m, self.s_c, self.f_amt):
            c.add_widget(w)
        c.add_widget(btn("Simula pagamento con carta", self.simulate))
        c.add_widget(lab("Ultime transazioni con carta", 16, WHITE, True))
        for t in q("SELECT * FROM transactions WHERE user_id=? AND type='CARD' ORDER BY id DESC LIMIT 6", (uid,)):
            c.add_widget(tx_button(t, lambda i: show_txn(i)))

    def set(self, col, val):
        assert col in ("status", "online_enabled", "contactless_enabled")
        conn.execute("UPDATE cards SET %s=? WHERE id=?" % col, (val, self.cd["id"]))
        self.refresh()

    def save_limit(self):
        try:
            m = parse_amount(self.f_lim.text)
        except BankErr as e:
            message("Limite non valido", e.msg, "error")
            return
        conn.execute("UPDATE cards SET limit_minor=? WHERE id=?", (m, self.cd["id"]))
        self.refresh()

    def simulate(self):
        try:
            m = parse_amount(self.f_amt.text)
        except BankErr as e:
            message("Importo non valido", e.msg, "error")
            return
        t = card_pay(SESSION["uid"], self.cd["id"], m, self.s_m.text, self.s_c.text)
        if t["status"] == "completed":
            message("Approvato", "%s presso %s approvato." % (fmt(m, "EUR"), t["counterparty"]), "success")
        else:
            message("Rifiutato", "%s presso %s rifiutato: %s." % (fmt(m, "EUR"), t["counterparty"], t["fail_reason"]), "error")
        App.get_running_app().refresh_all()


class ActivityScreen(Page):
    title = "Storico transazioni"

    def __init__(self, **kw):
        super().__init__(**kw)
        # Keep filters local to this screen instance; class-level mutable
        # dictionaries can leak old search/filter state across instances.
        self.flt = {"q": "", "dir": "Tutti", "st": "Tutti"}

    def build(self, c):
        self.search = inp("Cerca beneficiario / descrizione", self.flt["q"])
        self.search.bind(text=self.on_search)
        c.add_widget(self.search)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.sd = spin(["Tutti", "In entrata", "In uscita"], self.flt["dir"])
        self.ss = spin(["Tutti", "In attesa", "Completati", "Falliti", "Stornati"], self.flt["st"])
        self.sd.bind(text=lambda i, v: self.chg("dir", v))
        self.ss.bind(text=lambda i, v: self.chg("st", v))
        row.add_widget(self.sd)
        row.add_widget(self.ss)
        c.add_widget(row)
        self.lst = vbox(8)
        c.add_widget(self.lst)
        self.fill()

    def on_search(self, i, v):
        self.flt["q"] = v
        self.fill()

    def chg(self, k, v):
        self.flt[k] = v
        self.fill()

    def fill(self):
        self.lst.clear_widgets()
        sql, p = "SELECT * FROM transactions WHERE user_id=? AND type!='OPENING'", [SESSION["uid"]]
        if self.flt["q"].strip():
            lk = "%" + self.flt["q"].strip() + "%"
            sql += " AND (counterparty LIKE ? OR description LIKE ? OR reference LIKE ? OR ref LIKE ?)"
            p += [lk] * 4
        if self.flt["dir"] != "Tutti":
            sql += " AND direction=?"
            p.append("IN" if self.flt["dir"] == "In entrata" else "OUT")
        if self.flt["st"] != "Tutti":
            sql += " AND status=?"
            p.append({"In attesa": "pending", "Completati": "completed", "Falliti": "failed", "Stornati": "reversed"}[self.flt["st"]])
        rows = q(sql + " ORDER BY id DESC LIMIT 80", p)
        if not rows:
            self.lst.add_widget(lab("Nessuna transazione trovata.", 13, MUTED))
        for t in rows:
            self.lst.add_widget(tx_button(t, lambda i: show_txn(i)))


class ProfileScreen(Page):
    title = DEMO_STRINGS["profile_screen_title"]

    def build(self, c):
        uid, app = SESSION["uid"], App.get_running_app()
        u = q1("SELECT * FROM users WHERE id=?", (uid,))
        c.add_widget(lab("%s\n%s | %s" % (u["full_name"], u["email"], u["phone"]), 14, WHITE))
        c.add_widget(lab("Sicurezza", 15, GREEN, True))
        self.p1, self.p2, self.p3 = inp("Password attuale", "", True), inp("Nuova password", "", True), inp("Conferma nuova password", "", True)
        for w in (self.p1, self.p2, self.p3):
            c.add_widget(w)
        c.add_widget(btn("Aggiorna password", self.chpw, SOFT, WHITE))
        c.add_widget(lab(DEMO_STRINGS["lab_title"], 15, AMBER, True))
        c.add_widget(lab("Esito dei pagamenti in uscita", 12, MUTED, False, 20))
        outs = {"Riuscito": "success", "Fallito": "fail", "In attesa fino al regolamento": "pending_hold", "In attesa, poi fallito": "fail_after_pending"}
        inv = dict((v, k) for k, v in outs.items())
        s1 = spin(list(outs), inv[setting("sim_outcome")])
        s1.bind(text=lambda i, v: set_setting("sim_outcome", outs[v]))
        c.add_widget(s1)
        c.add_widget(lab("Ritardo SEPA standard (secondi)", 12, MUTED, False, 20))
        s2 = spin(["0", "10", "30", "60"], setting("sepa_delay_s"))
        s2.bind(text=lambda i, v: set_setting("sepa_delay_s", v))
        c.add_widget(s2)
        acts = [("Aggiungi €500,00 di fondi demo (EUR)", "Accreditare EUR 500,00 sul Conto Corrente?", lambda: credit(uid, accounts(uid, "EUR")[0]["id"], 50000)),
                ("Aggiungi €250,00 di fondi demo (EUR)", "Accreditare EUR 250,00 sul conto EUR?", lambda: credit(uid, accounts(uid, "EUR")[0]["id"], 25000)),
                ("Simula pagamento in entrata (+€250)", "Simulare un bonifico in entrata di €250?", lambda: credit(uid, accounts(uid, "EUR")[0]["id"], 25000, "INCOMING", "Mittente Demo S.r.l.", "Fattura 77")),
                ("Test: fondi insufficienti", "Provare a spostare più del saldo disponibile?", self.t_insufficient),
                ("Test: IBAN non valido", "Verificare la validazione di un IBAN errato e di uno corretto?", self.t_iban),
                ("Test: doppio tocco su conferma", "Inviare lo stesso pagamento 3 volte contemporaneamente?", self.t_dup),
                ("Test: storno ultimo pagamento", "Stornare l'ultima transazione completata?", self.t_rev),
                ("Test: carta rifiutata", "Simulare un'operazione oltre il limite della carta?", self.t_card),
                ("Completa tutti i pagamenti in attesa", "Completare subito tutti i pagamenti in attesa?", self.t_settle)]
        for text, q_, fn in acts:
            c.add_widget(btn(text, lambda t=text, q_=q_, fn=fn: ask(t + "?", q_, lambda: self.run(fn)), SOFT, WHITE))
        c.add_widget(btn("Verifica integrità del registro", self.inspect, (0.1, 0.3, 0.4, 1), WHITE))
        c.add_widget(btn(DEMO_STRINGS["reset_env_btn"], lambda: ask(DEMO_STRINGS["reset_env_title"], DEMO_STRINGS["reset_env_msg"], app.do_reset, "Reimposta", True), RED, WHITE))
        c.add_widget(btn("Esci", app.logout, (0.2, 0.2, 0.25, 1), WHITE))
        c.add_widget(lab(DEMO_STRINGS["lab_footer"], 10, MUTED, False, 26, "center"))

    def run(self, fn):
        try:
            r = fn()
        except BankErr as e:
            message("Risultato", e.msg, "warning")
        else:
            if isinstance(r, str):
                message("Risultato", r, "success")
        App.get_running_app().refresh_all()

    def chpw(self):
        try:
            change_password(SESSION["uid"], self.p1.text, self.p2.text, self.p3.text)
        except BankErr as e:
            message("Non modificata", e.msg, "error")
            return
        for w in (self.p1, self.p2, self.p3):
            w.text = ""
        message("Password modificata", "Password aggiornata con successo.", "success")

    def t_insufficient(self):
        a = accounts(SESSION["uid"], "EUR")
        try:
            internal_transfer(SESSION["uid"], a[0]["id"], a[1]["id"], a[0]["balance_minor"] + 10000, "lab-" + secrets.token_hex(6))
        except BankErr as e:
            return "Bloccato: %s\nNessun addebito. Il saldo è ancora %s." % (e.msg, fmt(q1("SELECT balance_minor b FROM accounts WHERE id=?", (a[0]["id"],))["b"], "EUR"))
        return "Riuscito inaspettatamente!"

    def t_iban(self):
        bad, good = check_iban("DE00 3704 0044 0532 0130 00"), check_iban("DE89 3704 0044 0532 0130 00")
        return "IBAN errato -> %s (%s)\nIBAN corretto -> %s" % ("RIFIUTATO" if not bad[0] else "accettato?!", bad[1], "ACCETTATO" if good[0] else "rifiutato?!")

    def t_dup(self):
        a = accounts(SESSION["uid"], "EUR")[0]
        key = "lab-dup-" + secrets.token_hex(6)
        b0 = q1("SELECT balance_minor b FROM accounts WHERE id=?", (a["id"],))["b"]
        for _ in range(3):
            pay_external(SESSION["uid"], "SEPA_INSTANT", a["id"], "Test Duplicato", "DE89370400440532013000", 100, "Laboratorio Demo", key)
        b1 = q1("SELECT balance_minor b FROM accounts WHERE id=?", (a["id"],))["b"]
        return "3 tocchi, stesso ID di pagamento.\nSaldo %s -> %s\nAddebitato una sola volta: %s" % (fmt(b0, "EUR"), fmt(b1, "EUR"), "SÌ" if b0 - b1 in (0, 100) else "NO")

    def t_rev(self):
        ph = ",".join("'%s'" % t for t in sorted(REVERSIBLE))
        t = q1("SELECT * FROM transactions WHERE user_id=? AND status='completed' AND type IN (%s) ORDER BY id DESC LIMIT 1" % ph, (SESSION["uid"],))
        if not t:
            raise BankErr("Nessuna transazione completata da stornare.")
        reverse(SESSION["uid"], t["id"])
        return "Stornata %s (%s)." % (t["ref"], fmt(t["amount_minor"], t["currency"]))

    def t_card(self):
        cd = q1("SELECT * FROM cards WHERE user_id=?", (SESSION["uid"],))
        t = card_pay(SESSION["uid"], cd["id"], cd["limit_minor"] + 100, "Negozio Test Rifiuto", "online")
        return "Esito: %s\nMotivo: %s\nNessun importo addebitato." % (STATUS_LABEL.get(t["status"], t["status"].upper()), t["fail_reason"])

    def t_settle(self):
        n = 0
        for t in q("SELECT id FROM transactions WHERE user_id=? AND status='pending'", (SESSION["uid"],)):
            settle(SESSION["uid"], t["id"], "complete")
            n += 1
        return "%d pagamento/i in attesa completato/i." % n

    def inspect(self):
        lines, ok = [], True
        for a, s, good in reconcile(SESSION["uid"]):
            ok = ok and good
            lines.append("%s\n  saldo %s | registro %s | %s" % (a["name"], fmt(a["balance_minor"], a["currency"]), fmt(s, a["currency"]), "OK" if good else "DISCREPANZA"))
        lines.append("\nRICONCILIAZIONE: %s" % ("OK" if ok else "FALLITA"))
        message("Saldi e registro", "\n".join(lines), "success" if ok else "error")


class MainShell(Screen):
    TABS = [("Home", "home"), ("Pagamenti", "payments"), ("Carte", "cards"), ("Storico", "activity"), ("Profilo", "profile")]

    def __init__(self, **kw):
        super().__init__(**kw)
        lay = BoxLayout(orientation="vertical")
        self.sm = ScreenManager(transition=NoTransition())
        for cls, n in ((HomeScreen, "home"), (PaymentsScreen, "payments"), (CardsScreen, "cards"), (ActivityScreen, "activity"), (ProfileScreen, "profile")):
            self.sm.add_widget(cls(name=n))
        lay.add_widget(self.sm)
        
        # Sleek Bottom Navigation Bar
        nav = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(2), padding=[dp(4), dp(5), dp(4), dp(5)])
        bgfill(nav, NAVBG, dp(0), BORDER_COLOR)
        self.btns = {}
        for text, n in self.TABS:
            b = Button(text=text, background_normal="", background_color=(0, 0, 0, 0), color=MUTED, font_size=sp(11))
            b.bind(on_press=lambda i, n=n: self.switch_tab(n))
            nav.add_widget(b)
            self.btns[n] = b
        lay.add_widget(nav)
        self.add_widget(lay)

    def switch_tab(self, name):
        self.sm.current = name
        for n, b in self.btns.items():
            b.color = GREEN if n == name else MUTED
            b.bold = n == name


class NorthstarApp(App):
    title = DEMO_STRINGS["bank_name"]

    def build(self):
        open_db()
        self.busy = False
        HOOK["toast"] = self.toast
        self.outer = ScreenManager(transition=SlideTransition())
        self.outer.add_widget(LoginScreen(name="login"))
        self.outer.add_widget(MainShell(name="shell"))
        root = FloatLayout()
        col = BoxLayout(orientation="vertical")
        
        # Top Accent Status Strip
        strip = BoxLayout(size_hint_y=None, height=dp(22))
        bgfill(strip, SOFT, 0)
        strip.add_widget(Label(text=DEMO_STRINGS["top_strip"], font_size=sp(10), bold=True, color=GREEN))
        col.add_widget(strip)
        col.add_widget(self.outer)
        root.add_widget(col)
        
        self.toast_lbl = Label(text="", markup=False, size_hint=(0.92, None), height=dp(58), pos_hint={"center_x": 0.5, "top": 0.94},
                               halign="center", valign="middle", font_size=sp(12), color=WHITE, opacity=0)
        self.toast_lbl.bind(size=lambda i, s: setattr(i, "text_size", (s[0] - dp(16), s[1])))
        bgfill(self.toast_lbl, SOFT, dp(12), GREEN)
        root.add_widget(self.toast_lbl)
        
        Clock.schedule_interval(self.tick, 5)
        try:
            Window.softinput_mode = "below_target"
            Window.bind(on_keyboard=self.on_key, on_touch_down=lambda *a: SESSION.update(last=datetime.now().timestamp()))
        except Exception:
            pass
        return root

    def toast(self, title, msg="", sev="info"):
        self.toast_lbl.text = "%s\n%s" % (title, msg)
        self.toast_lbl.opacity = 1
        Clock.unschedule(self._hide)
        Clock.schedule_once(self._hide, 2.8)

    def _hide(self, dt):
        self.toast_lbl.opacity = 0

    def shell(self):
        return self.outer.get_screen("shell")

    def switch_tab(self, name):
        self.shell().switch_tab(name)

    def after_login(self):
        self.outer.current = "shell"
        self.shell().switch_tab("home")
        settle_due(SESSION["uid"])
        self.refresh_all()

    def refresh_all(self):
        if not SESSION["uid"]:
            return
        for s in self.shell().sm.screens:
            if s.name in ("home", "cards"):
                s.refresh()
            elif s.name == "activity" and self.shell().sm.current == "activity":
                s.fill() if hasattr(s, "lst") and s.children else s.refresh()

    def tick(self, dt):
        if not SESSION["uid"]:
            return
        if datetime.now().timestamp() - SESSION["last"] > int(setting("session_min")) * 60:
            self.logout("Sessione scaduta. Accedi di nuovo.")
            return
        if settle_due(SESSION["uid"]):
            self.refresh_all()

    def on_resume(self):
        self.tick(0)

    def on_pause(self):
        return True

    def on_key(self, window, key, *a):
        if key != 27:
            return False
        for w in reversed(Window.children):
            if isinstance(w, Popup):
                w.dismiss()
                return True
        if self.outer.current == "login":
            return False
        if self.shell().sm.current != "home":
            self.switch_tab("home")
        else:
            ask("Uscire?", "Tornare alla schermata di accesso?", self.logout, "Esci")
        return True

    def open_notifications(self):
        uid = SESSION["uid"]
        rows = q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 40", (uid,))
        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        sv = ScrollView()
        box = vbox(6)
        if not rows:
            box.add_widget(lab("Nessuna notifica.", 13, MUTED))
        for n in rows:
            col = {"success": "26734D", "warning": "A8792C", "error": "B84B43"}.get(n["severity"], "ffffff")
            t = "%s[b][color=%s]%s[/color][/b]\n%s\n[size=%d][color=8c9ba5]%s[/color][/size]" % ("(NUOVA) " if not n["is_read"] else "", col, n["title"], n["message"], int(sp(10)), dt_it(n["created_at"]))
            box.add_widget(lab(t, 13, WHITE, markup=True))
        sv.add_widget(box)
        body.add_widget(sv)
        p = popup("Notifiche", body, (0.92, 0.8))

        def mark():
            conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
            p.dismiss()
            self.refresh_all()
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        row.add_widget(btn("Segna tutte come lette", mark, SOFT, WHITE))
        row.add_widget(btn("Chiudi", p.dismiss))
        body.add_widget(row)

    def logout(self, msg=None):
        SESSION.update(uid=None, name="", last=0.0)
        self.outer.current = "login"
        for w in list(Window.children):
            if isinstance(w, Popup):
                w.dismiss()
        if msg and isinstance(msg, str):
            Clock.schedule_once(lambda dt: self.toast("Disconnesso", msg), 0.3)

    def do_reset(self):
        reset_db()
        self.logout(DEMO_STRINGS["reset_prompt"])


if __name__ == "__main__":
    validate_demo_strings()
    NorthstarApp().run()