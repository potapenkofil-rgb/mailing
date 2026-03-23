"""Админ-панель бота."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

import database as db
from config import ADMIN_ID
from keyboards import admin_kb, admin_prices_kb, back_menu_kb

router = Router()


class AdminStates(StatesGroup):
    ban_user = State()
    unban_user = State()
    sub_user_id = State()
    sub_action = State()
    sub_days = State()
    price_sub = State()
    price_slot = State()
    price_ref = State()
    broadcast_text = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🔧 <b>Админ-панель</b>", reply_markup=admin_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin")
async def cb_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("🔧 <b>Админ-панель</b>", reply_markup=admin_kb(), parse_mode="HTML")
    await callback.answer()


# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    today = await db.get_payments_stats(days=1)
    yesterday = await db.get_payments_stats(days=2)  # приблизительно
    week = await db.get_payments_stats(days=7)
    month = await db.get_payments_stats(days=30)
    total = await db.get_payments_stats()

    # Общее количество пользователей
    all_users = await db.get_all_user_ids()

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{len(all_users)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Продажи подписок:</b>\n\n"
        f"📅 Сегодня: <b>{today['count']}</b> шт. — <b>${today['total']:.2f}</b>\n"
        f"📅 За неделю: <b>{week['count']}</b> шт. — <b>${week['total']:.2f}</b>\n"
        f"📅 За месяц: <b>{month['count']}</b> шт. — <b>${month['total']:.2f}</b>\n"
        f"📅 Всего: <b>{total['count']}</b> шт. — <b>${total['total']:.2f}</b>"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==================== БАН ====================

@router.callback_query(F.data == "adm_ban")
async def cb_adm_ban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "🚫 Введите <b>user_id</b> пользователя для бана:",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.ban_user)
    await callback.answer()


@router.message(AdminStates.ban_user)
async def process_ban(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID:")
        return

    user = await db.get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=back_menu_kb())
        await state.clear()
        return

    await db.update_user(uid, is_banned=1)
    await message.answer(
        f"✅ Пользователь <b>{uid}</b> забанен.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    await state.clear()


# ==================== РАЗБАН ====================

@router.callback_query(F.data == "adm_unban")
async def cb_adm_unban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "✅ Введите <b>user_id</b> пользователя для разбана:",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.unban_user)
    await callback.answer()


@router.message(AdminStates.unban_user)
async def process_unban(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID:")
        return

    user = await db.get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=back_menu_kb())
        await state.clear()
        return

    await db.update_user(uid, is_banned=0)
    await message.answer(
        f"✅ Пользователь <b>{uid}</b> разбанен.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    await state.clear()


# ==================== УПРАВЛЕНИЕ ПОДПИСКОЙ ====================

@router.callback_query(F.data == "adm_sub")
async def cb_adm_sub(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "💎 Введите <b>user_id</b> пользователя:",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.sub_user_id)
    await callback.answer()


@router.message(AdminStates.sub_user_id)
async def process_sub_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID:")
        return

    user = await db.get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=back_menu_kb())
        await state.clear()
        return

    await state.update_data(target_uid=uid)

    sub_end = user.get("subscription_end", "нет")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить дни", callback_data="adm_sub_add")],
        [InlineKeyboardButton(text="➖ Убрать дни", callback_data="adm_sub_remove")],
        [InlineKeyboardButton(text="♾ Навсегда", callback_data="adm_sub_forever")],
        [InlineKeyboardButton(text="❌ Забрать подписку", callback_data="adm_sub_revoke")],
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin")]
    ])

    await message.answer(
        f"💎 Пользователь: <b>{uid}</b>\n"
        f"Подписка: <code>{sub_end[:16] if sub_end != 'forever' else '♾ Навсегда'}</code>\n\n"
        f"Выберите действие:",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(AdminStates.sub_action)


@router.callback_query(F.data == "adm_sub_forever", AdminStates.sub_action)
async def cb_sub_forever(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    uid = data["target_uid"]
    await db.update_user(uid, subscription_end="forever")
    await callback.message.edit_text(
        f"✅ Пользователю <b>{uid}</b> выдана подписка навсегда.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "adm_sub_revoke", AdminStates.sub_action)
async def cb_sub_revoke(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    uid = data["target_uid"]
    from datetime import datetime
    await db.update_user(uid, subscription_end=datetime(2000, 1, 1).isoformat())
    await callback.message.edit_text(
        f"✅ У пользователя <b>{uid}</b> подписка забрана.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "adm_sub_add", AdminStates.sub_action)
async def cb_sub_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(sub_mode="add")
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "Сколько дней <b>добавить</b>?",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.sub_days)
    await callback.answer()


@router.callback_query(F.data == "adm_sub_remove", AdminStates.sub_action)
async def cb_sub_remove(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(sub_mode="remove")
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "Сколько дней <b>убрать</b>?",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.sub_days)
    await callback.answer()


@router.message(AdminStates.sub_days)
async def process_sub_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число:")
        return

    data = await state.get_data()
    uid = data["target_uid"]
    mode = data.get("sub_mode", "add")
    user = await db.get_user(uid)

    from datetime import datetime, timedelta

    current_end = user.get("subscription_end", "")
    if current_end == "forever":
        await message.answer("Подписка навсегда, изменение дней невозможно.", reply_markup=admin_kb())
        await state.clear()
        return

    try:
        end = datetime.fromisoformat(current_end)
        if end < datetime.utcnow():
            end = datetime.utcnow()
    except (TypeError, ValueError):
        end = datetime.utcnow()

    if mode == "add":
        new_end = end + timedelta(days=days)
        await db.update_user(uid, subscription_end=new_end.isoformat())
        await message.answer(
            f"✅ Пользователю <b>{uid}</b> добавлено <b>{days}</b> дней.\n"
            f"Подписка до: {new_end.strftime('%d.%m.%Y')}",
            reply_markup=admin_kb(), parse_mode="HTML"
        )
    else:
        new_end = end - timedelta(days=days)
        await db.update_user(uid, subscription_end=new_end.isoformat())
        await message.answer(
            f"✅ У пользователя <b>{uid}</b> убрано <b>{days}</b> дней.\n"
            f"Подписка до: {new_end.strftime('%d.%m.%Y')}",
            reply_markup=admin_kb(), parse_mode="HTML"
        )
    await state.clear()


# ==================== ЦЕНЫ ====================

@router.callback_query(F.data == "adm_prices")
async def cb_adm_prices(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    sub_price = await db.get_subscription_price()
    slot_price = await db.get_extra_account_price()
    ref_bonus = await db.get_referral_bonus_days()

    text = (
        f"💰 <b>Текущие цены</b>\n\n"
        f"💎 Подписка: <b>${sub_price}</b>/мес\n"
        f"🔓 Доп. ячейка: <b>${slot_price}</b>\n"
        f"🎁 Бонус реферала: <b>{ref_bonus}</b> дней"
    )
    await callback.message.edit_text(text, reply_markup=admin_prices_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm_price_sub")
async def cb_price_sub(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text("Введите новую цену подписки ($):", reply_markup=cancel_kb())
    await state.set_state(AdminStates.price_sub)
    await callback.answer()


@router.message(AdminStates.price_sub)
async def process_price_sub(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число:")
        return
    await db.set_setting("subscription_price", str(price))
    await message.answer(f"✅ Цена подписки: <b>${price}</b>", reply_markup=admin_kb(), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "adm_price_slot")
async def cb_price_slot(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text("Введите новую цену доп. ячейки ($):", reply_markup=cancel_kb())
    await state.set_state(AdminStates.price_slot)
    await callback.answer()


@router.message(AdminStates.price_slot)
async def process_price_slot(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число:")
        return
    await db.set_setting("extra_account_price", str(price))
    await message.answer(f"✅ Цена ячейки: <b>${price}</b>", reply_markup=admin_kb(), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "adm_price_ref")
async def cb_price_ref(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text("Введите новое кол-во бонусных дней за реферала:", reply_markup=cancel_kb())
    await state.set_state(AdminStates.price_ref)
    await callback.answer()


@router.message(AdminStates.price_ref)
async def process_price_ref(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите неотрицательное целое число:")
        return
    await db.set_setting("referral_bonus_days", str(days))
    await message.answer(f"✅ Бонус реферала: <b>{days} дней</b>", reply_markup=admin_kb(), parse_mode="HTML")
    await state.clear()


# ==================== РАССЫЛКА ПО БОТУ ====================

@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    from keyboards import cancel_kb
    await callback.message.edit_text(
        "📢 Введите текст рассылки для всех пользователей бота:",
        reply_markup=cancel_kb()
    )
    await state.set_state(AdminStates.broadcast_text)
    await callback.answer()


@router.message(AdminStates.broadcast_text)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = message.text
    if not text:
        await message.answer("❌ Текст не может быть пустым.")
        return

    user_ids = await db.get_all_user_ids()
    sent = 0
    failed = 0

    status_msg = await message.answer(f"📢 Рассылка: 0/{len(user_ids)}...")

    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        if (sent + failed) % 20 == 0:
            try:
                await status_msg.edit_text(f"📢 Рассылка: {sent + failed}/{len(user_ids)}...")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не отправлено: {failed}\n"
        f"📊 Всего: {len(user_ids)}",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    await state.clear()
