"""Обработчик реферальной системы."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
from keyboards import back_menu_kb

router = Router()


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # Подсчёт рефералов
    async with __import__("aiosqlite").connect(db.DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
        )
        total_refs = (await cursor.fetchone())[0]

        cursor = await conn.execute(
            """SELECT COUNT(DISTINCT u.user_id) FROM users u 
            JOIN payments p ON u.user_id = p.user_id 
            WHERE u.referrer_id = ? AND p.status = 'paid' AND p.type = 'subscription'""",
            (user_id,)
        )
        paid_refs = (await cursor.fetchone())[0]

    bonus_days = await db.get_referral_bonus_days()

    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: <b>{total_refs}</b>\n"
        f"• Купили подписку: <b>{paid_refs}</b>\n"
        f"• Бонусных дней получено: <b>{paid_refs * bonus_days}</b>\n\n"
        f"💡 За каждого друга, купившего подписку, вы получаете <b>+{bonus_days} дней</b>!"
    )
    await callback.message.edit_text(text, reply_markup=back_menu_kb(), parse_mode="HTML")
    await callback.answer()
