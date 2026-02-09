import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Пропорции: вы 336, жена 164 из 500
HUSBAND_SHARE = 336 / 500  # 0.672 (67.2%)
WIFE_SHARE = 164 / 500     # 0.328 (32.8%)

# Получаем токен из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создаём бота и диспетчер с хранилищем состояний
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# Состояния для конечного автомата
class CalcState(StatesGroup):
    waiting_for_type = State()  # Ожидаем выбор: общая/муж/жена
    waiting_for_amount = State()  # Ожидаем ввод суммы

# Главное меню с кнопкой Старт
def get_start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Старт")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Кнопки выбора типа платежа
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

# Кнопки для нового расчёта
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

# Обработчик команды /start и кнопки Старт
@dp.message(CommandStart())
@dp.message(F.text.in_({"Старт", "Новый расчёт"}))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я помогу рассчитать семейные расходы.\n\n"
        "Ваши пропорции:\n"
        "• Муж — 67.2% (336 ₽ из 500)\n"
        "• Жена — 32.8% (164 ₽ из 500)\n\n"
        "👇 Нажми кнопку, чтобы начать:",
        reply_markup=get_start_keyboard()
    )

# Обработчик нажатия на кнопку Старт (после приветствия)
@dp.message(F.text == "Старт")
async def start_calculation(message: Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_type)
    await message.answer(
        "❓ Кто платит?",
        reply_markup=get_type_keyboard()
    )

# Обработчик выбора типа платежа
@dp.message(CalcState.waiting_for_type, F.text.in_({"Общая сумма", "Муж платит", "Жена платит"}))
async def process_type(message: Message, state: FSMContext):
    type_map = {
        "Общая сумма": "total",
        "Муж платит": "husband",
        "Жена платит": "wife"
    }
    calc_type = type_map[message.text]
    await state.update_data(calc_type=calc_type)
    await state.set_state(CalcState.waiting_for_amount)
    
    # Формируем подсказку в зависимости от выбора
