"""Обработчик /start и главного меню."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from datetime import datetime

import database as db
from keyboards import main_menu_kb

router = Router()


async def get_menu_text(user_id: int) -> str:
    user = await db.get_user(user_id)
    if not user:
        return "Добро пожаловать!"

    first_name = user.get("first_name", "")
    is_sub = await db.is_subscribed(user_id)
    accounts = await db.get_accounts(user_id)
    today_sent = await db.get_today_sent(user_id)

    if user.get("subscription_end") == "forever":
        sub_text = "💎 Подписка: ♾ Навсегда"
    elif is_sub:
        try:
            end = datetime.fromisoformat(user["subscription_end"])
            sub_text = f"💎 Подписка до: {end.strftime('%d.%m.%Y')}"
        except (TypeError, ValueError):
            sub_text = "❌ Нет подписки"
    else:
        sub_text = "❌ Нет подписки"

    max_acc = user.get("max_accounts", 1)

    return (
        f"👋 Привет, <b>{first_name}</b>!\n\n"
        f"📊 Сегодня отправлено: <b>{today_sent}</b> | "
        f"Аккаунтов: <b>{len(accounts)}/{max_acc}</b>\n"
        f"{sub_text}\n\n"
        f"Выберите действие:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    # Обработка реферальной ссылки
    referrer_id = None
    if message.text and "ref_" in message.text:
        try:
            referrer_id = int(message.text.split("ref_")[1])
            if referrer_id == user_id:
                referrer_id = None
        except (ValueError, IndexError):
            pass

    if not user:
        await db.create_user(
            user_id=user_id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            referrer_id=referrer_id
        )
    else:
        await db.update_user(user_id,
                              username=message.from_user.username or "",
                              first_name=message.from_user.first_name or "")

    is_sub = await db.is_subscribed(user_id)
    text = await get_menu_text(user_id)
    await message.answer(text, reply_markup=main_menu_kb(is_sub), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(
            user_id=user_id,
            username=callback.from_user.username or "",
            first_name=callback.from_user.first_name or ""
        )

    is_sub = await db.is_subscribed(user_id)
    text = await get_menu_text(user_id)
    try:
        await callback.message.edit_text(text, reply_markup=main_menu_kb(is_sub), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=main_menu_kb(is_sub), parse_mode="HTML")
    await callback.answer()
