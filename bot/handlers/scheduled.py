"""Обработчик отложенных рассылок."""

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
from keyboards import scheduled_list_kb, scheduled_detail_kb, back_menu_kb
from services.scheduler import cancel_scheduled_job

router = Router()


@router.callback_query(F.data == "scheduled")
async def cb_scheduled(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_sub = await db.is_subscribed(user_id)

    if not is_sub:
        await callback.answer("🔒 Доступно только с подпиской!", show_alert=True)
        return

    mailings = await db.get_scheduled_mailings(user_id)
    if mailings:
        text = f"⏰ <b>Отложенные рассылки</b> ({len(mailings)})"
    else:
        text = "⏰ <b>Отложенные рассылки</b>\n\nНет запланированных рассылок."

    await callback.message.edit_text(text, reply_markup=scheduled_list_kb(mailings), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sched_") & ~F.data.startswith("sched_cancel_"))
async def cb_scheduled_detail(callback: CallbackQuery):
    sched_id = int(callback.data.split("_")[1])
    sched = await db.get_scheduled_mailing(sched_id)
    if not sched:
        await callback.answer("Не найдено", show_alert=True)
        return

    usernames = json.loads(sched["usernames"])
    text = (
        f"⏰ <b>Запланированная рассылка</b>\n\n"
        f"📅 Время: <b>{sched['scheduled_time'][:16]}</b>\n"
        f"👥 Получателей: <b>{len(usernames)}</b>\n"
        f"⏱ Задержка: <b>{sched['delay']} сек</b>\n"
        f"📝 Текст: <i>{sched['text'][:100]}</i>"
    )
    await callback.message.edit_text(text, reply_markup=scheduled_detail_kb(sched_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sched_cancel_"))
async def cb_cancel_scheduled(callback: CallbackQuery):
    sched_id = int(callback.data.split("_")[2])
    await db.cancel_scheduled_mailing(sched_id)
    cancel_scheduled_job(sched_id)
    await callback.answer("✅ Рассылка отменена", show_alert=True)

    user_id = callback.from_user.id
    mailings = await db.get_scheduled_mailings(user_id)
    text = f"⏰ <b>Отложенные рассылки</b> ({len(mailings)})"
    await callback.message.edit_text(text, reply_markup=scheduled_list_kb(mailings), parse_mode="HTML")
