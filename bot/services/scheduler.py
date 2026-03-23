"""Сервис планировщика отложенных рассылок."""

import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from services.mailing_service import run_mailing

scheduler = AsyncIOScheduler()


async def execute_scheduled_mailing(bot, sched_id: int):
    """Выполнить запланированную рассылку."""
    sched = await db.get_scheduled_mailing(sched_id)
    if not sched or sched["status"] != "pending":
        return

    await db.update_scheduled_status(sched_id, "running")

    user_id = sched["user_id"]
    account = await db.get_account(sched["account_id"])
    if not account:
        await db.update_scheduled_status(sched_id, "failed")
        try:
            await bot.send_message(user_id, "❌ Отложенная рассылка не выполнена: аккаунт не найден.")
        except Exception:
            pass
        return

    usernames = json.loads(sched["usernames"])
    total = len(usernames)

    # Уведомление о начале
    try:
        msg = await bot.send_message(user_id, "⏰ Запланированная рассылка запускается...", parse_mode="HTML")
    except Exception:
        msg = None

    mailing_id = await db.create_mailing(user_id, account["id"], account["phone"], sched["text"], total)
    is_sub = await db.is_subscribed(user_id)

    await run_mailing(
        bot=bot,
        user_id=user_id,
        mailing_id=mailing_id,
        account=account,
        text=sched["text"],
        usernames=usernames,
        delay=sched["delay"],
        break_after=sched["break_after"] or 0,
        break_duration=sched["break_duration"] or 0,
        progress_msg_id=msg.message_id if msg else None,
        chat_id=user_id,
        is_subscribed=is_sub
    )

    await db.update_scheduled_status(sched_id, "completed")


def schedule_mailing(bot, sched_id: int, run_time: datetime):
    """Запланировать рассылку на определённое время."""
    scheduler.add_job(
        execute_scheduled_mailing,
        trigger="date",
        run_date=run_time,
        args=[bot, sched_id],
        id=f"sched_{sched_id}",
        replace_existing=True
    )


def cancel_scheduled_job(sched_id: int):
    """Отменить запланированную задачу."""
    job_id = f"sched_{sched_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass


def start_scheduler():
    """Запустить планировщик."""
    if not scheduler.running:
        scheduler.start()
