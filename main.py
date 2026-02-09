import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F
import asyncio
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Пропорции: вы 336, жена 164 из 500
HUSBAND_SHARE = 336 / 500  # 0.672 (67.2%)
WIFE_SHARE = 164 / 500     # 0.328 (32.8%)

# Получаем токен из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 8080))

# Создаём бота и диспетчер
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Функция расчёта
def calculate(amount, mode):
    if mode == "total":
        husband = round(amount * HUSBAND_SHARE)
        wife = round(amount * WIFE_SHARE)
        # Корректируем, чтобы сумма была точной
        if husband + wife != amount:
            wife = amount - husband
        return {
            "husband": husband,
            "wife": wife,
            "total": amount
        }
    elif mode == "husband":
        total = round(amount / HUSBAND_SHARE)
        wife = total - amount
        return {
            "husband": amount,
            "wife": wife,
            "total": total
        }
    elif mode == "wife":
        total = round(amount / WIFE_SHARE)
        husband = total - amount
        return {
            "husband": husband,
            "wife": amount,
            "total": total
        }

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 Привет! Я бот для расчёта семейных расходов.\n\n"
        "Ваши пропорции: Ты — 67.2%, Жена — 32.8%\n\n"
        "📝 Как пользоваться:\n"
        "• Общая сумма: <code>/total 1000</code>\n"
        "• Ты заплатил: <code>/me 500</code>\n"
        "• Жена заплатила: <code>/wife 300</code>"
    )
    await message.answer(text, parse_mode="HTML")

# Команда /total — вводим общую сумму
@dp.message(Command("total"))
async def cmd_total(message: Message):
    try:
        amount = float(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        
        result = calculate(amount, "total")
        
        response = (
            f"💰 Общая сумма: <b>{result['total']} ₽</b>\n\n"
            f"👨 Тебе платить: <b>{result['husband']} ₽</b>\n"
            f"👩 Жене платить: <b>{result['wife']} ₽</b>"
        )
        await message.answer(response, parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("❌ Неправильный формат!\nПример: <code>/total 1000</code>", parse_mode="HTML")

# Команда /me — вводим сколько заплатил ты
@dp.message(Command("me"))
async def cmd_me(message: Message):
    try:
        amount = float(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        
        result = calculate(amount, "husband")
        
        response = (
            f"👨 Ты заплатил: <b>{result['husband']} ₽</b>\n\n"
            f"💰 Общая сумма: <b>{result['total']} ₽</b>\n"
            f"👩 Жене платить: <b>{result['wife']} ₽</b>"
        )
        await message.answer(response, parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("❌ Неправильный формат!\nПример: <code>/me 500</code>", parse_mode="HTML")

# Команда /wife — вводим сколько заплатила жена
@dp.message(Command("wife"))
async def cmd_wife(message: Message):
    try:
        amount = float(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        
        result = calculate(amount, "wife")
        
        response = (
            f"👩 Жена заплатила: <b>{result['wife']} ₽</b>\n\n"
            f"💰 Общая сумма: <b>{result['total']} ₽</b>\n"
            f"👨 Тебе платить: <b>{result['husband']} ₽</b>"
        )
        await message.answer(response, parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("❌ Неправильный формат!\nПример: <code>/wife 300</code>", parse_mode="HTML")

# Обработчик всех остальных сообщений
@dp.message(F.text)
async def echo(message: Message):
    await message.answer(
        "🤔 Не понял команду!\n\n"
        "📝 Используй:\n"
        "• <code>/total 1000</code> — общая сумма\n"
        "• <code>/me 500</code> — ты заплатил\n"
        "• <code>/wife 300</code> — жена заплатила",
        parse_mode="HTML"
    )

# Webhook handler
async def on_startup(bot: Bot):
    # Получаем домен из переменной Railway
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://your-app.up.railway.app")
    webhook_url = f"{domain}{WEBHOOK_PATH}"
    
    # Удаляем старый вебхук и устанавливаем новый
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    logging.info(f"✅ Webhook установлен на: {webhook_url}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
