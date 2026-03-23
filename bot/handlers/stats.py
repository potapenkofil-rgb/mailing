"""Обработчик статистики пользователя."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
from keyboards import back_menu_kb

router = Router()


@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    mailings = await db.get_user_mailings(user_id, limit=20)

    total_sent = sum(m.get("sent", 0) for m in mailings)
    total_failed = sum(m.get("failed", 0) for m in mailings)
    total_mailings = len(mailings)

    text = (
        f"📈 <b>Ваша статистика</b>\n\n"
        f"📬 Всего рассылок: <b>{total_mailings}</b>\n"
        f"✅ Успешно отправлено: <b>{total_sent}</b>\n"
        f"❌ Не отправлено: <b>{total_failed}</b>\n"
    )

    if mailings:
        text += "\n━━━━━━━━━━━━━━━━━━\n"
        text += "📋 <b>Последние рассылки:</b>\n\n"
        for m in mailings[:5]:
            status_icon = {"completed": "✅", "aborted": "⚠️", "spam_block": "🚫", "running": "🔄"}.get(m["status"], "❓")
            date = m.get("started_at", "")[:10]
            text += f"{status_icon} {date} — {m.get('sent', 0)}/{m.get('total', 0)} отправлено\n"

    await callback.message.edit_text(text, reply_markup=back_menu_kb(), parse_mode="HTML")
    await callback.answer()
