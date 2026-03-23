"""Точка входа — запуск Telegram-бота."""

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import init_db
from middlewares import BanMiddleware
from services.scheduler import start_scheduler

from handlers import (
    start,
    accounts,
    mailing,
    templates,
    recipients,
    subscription,
    referral,
    scheduled,
    stats,
    admin,
    instruction,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def send_expiry_notifications(bot: Bot):
    """Фоновая задача: уведомления об истечении подписки."""
    from database import get_all_user_ids, get_user
    while True:
        try:
            user_ids = await get_all_user_ids()
            now = datetime.utcnow()
            for uid in user_ids:
                user = await get_user(uid)
                if not user or user.get("subscription_end") == "forever":
                    continue
                try:
                    end = datetime.fromisoformat(user["subscription_end"])
                except (TypeError, ValueError):
                    continue

                days_left = (end - now).days
                # Напоминание за 3 дня
                if days_left == 3:
                    try:
                        await bot.send_message(
                            uid,
                            "⚠️ Ваша подписка истекает через <b>3 дня</b>!\n"
                            "Продлите в меню «💳 Подписка».",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                # Уведомление об истечении
                elif days_left == 0:
                    try:
                        await bot.send_message(
                            uid,
                            "❌ Ваша подписка <b>истекла</b>.\n"
                            "Возобновите в меню «💳 Подписка».",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Notification task error: {e}")

        # Проверяем раз в 6 часов
        await asyncio.sleep(6 * 3600)


async def main():
    """Главная функция."""
    # Инициализация БД
    await init_db()
    logger.info("Database initialized")

    # Создание бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Мидлвари
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(BanMiddleware())

    # Регистрация роутеров (порядок важен — admin и cancel первыми)
    dp.include_router(admin.router)
    dp.include_router(accounts.router)  # содержит cancel handler
    dp.include_router(mailing.router)
    dp.include_router(templates.router)
    dp.include_router(recipients.router)
    dp.include_router(subscription.router)
    dp.include_router(referral.router)
    dp.include_router(scheduled.router)
    dp.include_router(stats.router)
    dp.include_router(instruction.router)
    dp.include_router(start.router)  # start/main_menu последним

    # Запуск планировщика
    start_scheduler()
    logger.info("Scheduler started")

    # Фоновые задачи
    asyncio.create_task(send_expiry_notifications(bot))

    # Запуск поллинга
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
