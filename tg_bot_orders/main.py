from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import re
import json
import os

# 🔑 ТВОЙ ТОКЕН ОТ BotFather
API_TOKEN = "8323635812:AAHJldl1LxNt86BMxPbMxStAHur_gecnKeI"

# 📌 ID канала (начинается с -100...)
CHANNEL_ID = -1002945674765

# Инициализация бота
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# 📂 база товаров: {название -> file_id}
PRODUCTS_FILE = "products.json"
PRODUCTS = {}

# Память для галерей пользователей
USER_GALLERIES = {}


# ======================
# Загрузка / сохранение базы
# ======================
def save_products():
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(PRODUCTS, f, ensure_ascii=False, indent=2)


def load_products():
    global PRODUCTS
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            PRODUCTS = json.load(f)
    print(f"Загружено {len(PRODUCTS)} товаров из базы")


# ======================
# Автообновление при новых фото в канале
# ======================
@dp.channel_post(F.photo & F.caption)
async def update_products(message: types.Message):
    caption = message.caption.strip()
    file_id = message.photo[-1].file_id
    PRODUCTS[caption] = file_id
    save_products()
    print(f"Добавлен/обновлён товар: {caption}")


# ======================
# Парсинг заказа
# ======================
def parse_order(text: str):
    pattern = r"\d+\)\s(.+?)\sx\s(\d+)\s-\s([\d.]+)\sEUR"
    return re.findall(pattern, text)


# ======================
# Клавиатура-листалка
# ======================
def get_kb(index: int, total: int):
    kb = []
    row = []

    if index > 0:
        row.append(InlineKeyboardButton(text="⏮", callback_data=f"first:{index}"))
        row.append(InlineKeyboardButton(text="⬅", callback_data=f"prev:{index}"))

    if index < total - 1:
        row.append(InlineKeyboardButton(text="➡", callback_data=f"next:{index}"))
        row.append(InlineKeyboardButton(text="⏭", callback_data=f"last:{index}"))

    if row:
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None


# ======================
# Обработка заказа
# ======================
@dp.message()
async def handle_order(message: types.Message):
    items = parse_order(message.text)
    if not items:
        await message.answer("❌ Не смог распознать заказ")
        return

    gallery = []
    for name, qty, price in items:
        file_id = PRODUCTS.get(name)
        if file_id:
            caption = f"<b>{name}</b>\nКол-во: {qty}\nЦена: {price} EUR"
            gallery.append((file_id, caption))
        else:
            # ✅ используем fallback "Товар не найден"
            fallback_id = PRODUCTS.get("Товар не найден")
            caption = f"❌ Товар не найден: {name}\nКол-во: {qty}\nЦена: {price} EUR"
            if fallback_id:
                gallery.append((fallback_id, caption))
            else:
                gallery.append((None, caption))

    if not gallery:
        await message.answer("❌ Нет фото товаров в базе")
        return

    # отправляем первый товар
    file_id, caption = gallery[0]
    if file_id:
        msg = await message.answer_photo(
            photo=file_id,
            caption=caption,
            reply_markup=get_kb(0, len(gallery))
        )
    else:
        msg = await message.answer(
            caption,
            reply_markup=get_kb(0, len(gallery))
        )

    # ✅ сохраняем галерею отдельно для каждого пользователя
    USER_GALLERIES[message.from_user.id] = {
        "gallery": gallery,
        "msg_id": msg.message_id,
        "chat_id": msg.chat.id
    }


# ======================
# Перелистывание
# ======================
@dp.callback_query(F.data.startswith(("prev", "next", "first", "last")))
async def paginate(query: CallbackQuery):
    user_id = query.from_user.id
    user_gallery = USER_GALLERIES.get(user_id)

    if not user_gallery:
        await query.answer("❌ Галерея не найдена")
        return

    gallery = user_gallery["gallery"]
    msg_id = user_gallery["msg_id"]
    chat_id = user_gallery["chat_id"]

    action, index = query.data.split(":")
    index = int(index)

    if action == "prev":
        index -= 1
    elif action == "next":
        index += 1
    elif action == "first":
        index = 0
    elif action == "last":
        index = len(gallery) - 1

    file_id, caption = gallery[index]

    if file_id:  # ✅ есть фото
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=msg_id,
            media=types.InputMediaPhoto(media=file_id, caption=caption),
            reply_markup=get_kb(index, len(gallery))
        )
    else:  # ❌ только текст
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=msg_id,
            caption=caption,
            reply_markup=get_kb(index, len(gallery))
        )

    await query.answer()


# ======================
# Запуск
# ======================
async def main():
    load_products()   # при старте подгружаем базу
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
