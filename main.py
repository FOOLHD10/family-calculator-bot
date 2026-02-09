import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
import asyncio
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Пропорции: вы 336, жена 164 из 500
HUSBAND_SHARE = 336 / 500  # 0.672 (67.2%)
WIFE_SHARE = 164 / 500     # 0.328 (32.8%)

# Получаем токен и список разрешённых пользователей
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "")
ALLOWED_USER_IDS = set(int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip())

# Создаём бота и диспетчер
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилище для отслеживания состояния пользователей
user_state = {}

# Кнопки
def get_start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Старт")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Общая сумма")],
            [KeyboardButton(text="Муж платит")],
            [KeyboardButton(text="Жена платит")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_restart_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Новый расчёт")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Функция расчёта
def calculate(amount, mode):
    if mode == "total":
        husband = round(amount * HUSBAND_SHARE)
        wife = round(amount * WIFE_SHARE)
        if husband + wife != amount:
            wife = amount - husband
        return {"husband": husband, "wife": wife, "total": amount}
    elif mode == "husband":
        total = round(amount / HUSBAND_SHARE)
        wife = total - amount
        return {"husband": amount, "wife": wife, "total": total}
    elif mode == "wife":
        total = round(amount / WIFE_SHARE)
        husband = total - amount
        return {"husband": husband, "wife": amount, "total": total}

# Проверка доступа
def is_user_allowed(user_id: int) -> bool:
    # Если список разрешённых пустой — разрешаем всем (для теста)
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS

# Обработчик всех сообщений — сначала проверяем доступ
@dp.message()
async def access_control(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без_имени"
    
    # Проверяем, разрешён ли пользователь
    if not is_user_allowed(user_id):
        logging.warning(f"❌ Доступ запрещён: user_id={user_id}, username=@{username}")
        await message.answer(
            "🔒 Доступ к этому боту ограничен.\n"
            "Обратитесь к владельцу бота для получения доступа."
        )
        return  # ВАЖНО: прерываем обработку
    
    # Если доступ разрешён — логируем и продолжаем обработку
    logging.info(f"✅ Доступ разрешён: user_id={user_id}, username=@{username}")
    # Ничего не делаем — сообщение автоматически передаётся другим обработчикам

# Старт (вызывается только для разрешённых пользователей)
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_user_allowed(message.from_user.id):
        return
    
    user_state[message.from_user.id] = "start"
    await message.answer(
        "👋 Привет! Я помогу рассчитать семейные расходы.\n\n"
        "Ваши пропорции:\n"
        "• Муж — 67.2% (336 ₽ из 500)\n"
        "• Жена — 32.8% (164 ₽ из 500)\n\n"
        "👇 Нажми кнопку, чтобы начать:",
        reply_markup=get_start_keyboard()
    )

# Кнопка Старт / Новый расчёт
@dp.message(F.text.in_({"Старт", "Новый расчёт"}))
async def start_calculation(message: Message):
    if not is_user_allowed(message.from_user.id):
        return
    
    user_state[message.from_user.id] = "choosing_type"
    await message.answer(
        "❓ Кто платит?",
        reply_markup=get_type_keyboard()
    )

# Выбор типа платежа
@dp.message(F.text.in_({"Общая сумма", "Муж платит", "Жена платит"}))
async def process_type(message: Message):
    if not is_user_allowed(message.from_user.id):
        return
    
    type_map = {
        "Общая сумма": "total",
        "Муж платит": "husband",
        "Жена платит": "wife"
    }
    user_state[message.from_user.id] = {
        "type": type_map[message.text]
    }
    
    hints = {
        "total": "Введите общую сумму покупки:",
        "husband": "Введите сумму, которую заплатил муж:",
        "wife": "Введите сумму, которую заплатила жена:"
    }
    await message.answer(hints[type_map[message.text]], reply_markup=get_restart_keyboard())

# Ввод суммы
@dp.message()
async def process_amount(message: Message):
    if not is_user_allowed(message.from_user.id):
        return
    
    user_id = message.from_user.id
    
    # Если пользователь ещё не выбрал тип — игнорируем
    if user_id not in user_state or user_state[user_id] is None:
        await message.answer(
            "👇 Нажмите кнопку «Старт», чтобы начать расчёт:",
            reply_markup=get_start_keyboard()
        )
        return
    
    # Если ожидаем выбор типа
    if user_state[user_id] == "choosing_type":
        await message.answer(
            "❓ Сначала выберите, кто платит:",
            reply_markup=get_type_keyboard()
        )
        return
    
    # Обрабатываем сумму
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!\nПопробуйте ещё раз:")
            return
        
        calc_type = user_state[user_id]["type"]
        result = calculate(amount, calc_type)
        
        response = f"✅ Расчёт готов:\n\n💰 Общая сумма: <b>{result['total']} ₽</b>\n👨 Муж: <b>{result['husband']} ₽</b>\n👩 Жена: <b>{result['wife']} ₽</b>"
        
        await message.answer(response, reply_markup=get_restart_keyboard())
        user_state[user_id] = "start"  # Возвращаем в стартовое состояние
        
    except (ValueError, AttributeError):
        if message.text in ["Новый расчёт", "Старт"]:
            user_state[user_id] = "choosing_type"
            await message.answer("❓ Кто платит?", reply_markup=get_type_keyboard())
        else:
            await message.answer("❌ Неверный формат суммы!\nВведите число (например: 1000 или 500.50):")

# Основная функция
async def main():
    logging.info(f"✅ Бот запускается...")
    logging.info(f"✅ Разрешённые пользователи: {ALLOWED_USER_IDS if ALLOWED_USER_IDS else 'ВСЕ (тестовый режим)'}")
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Запускаем long polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
