"""Обработчик подписки и оплаты."""

import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from keyboards import subscription_kb, back_menu_kb
from services.crypto_pay import create_invoice, check_invoice

router = Router()


@router.callback_query(F.data == "subscription")
async def cb_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    is_sub = await db.is_subscribed(user_id)
    sub_price = await db.get_subscription_price()
    slot_price = await db.get_extra_account_price()

    if user.get("subscription_end") == "forever":
        sub_info = "💎 Подписка: <b>♾ Навсегда</b>"
    elif is_sub:
        try:
            end = datetime.fromisoformat(user["subscription_end"])
            days_left = (end - datetime.utcnow()).days
            sub_info = f"💎 Подписка до: <b>{end.strftime('%d.%m.%Y')}</b> ({days_left} дн.)"
        except (TypeError, ValueError):
            sub_info = "❌ Нет активной подписки"
    else:
        sub_info = "❌ Нет активной подписки"

    max_acc = user.get("max_accounts", 1) if user else 1

    text = (
        f"💳 <b>Подписка</b>\n\n"
        f"{sub_info}\n"
        f"📱 Ячеек аккаунтов: <b>{max_acc}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 Pro-подписка — <b>${sub_price}/мес</b>\n"
        f"• Безлимит сообщений\n"
        f"• Настройка задержек\n"
        f"• Шаблоны и списки\n"
        f"• Отложенные рассылки\n"
        f"• До 5 аккаунтов\n\n"
        f"🔓 Доп. ячейка — <b>${slot_price}</b> (навсегда)"
    )
    await callback.message.edit_text(text, reply_markup=subscription_kb(is_sub), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "buy_sub")
async def cb_buy_sub(callback: CallbackQuery):
    user_id = callback.from_user.id
    price = await db.get_subscription_price()

    invoice = await create_invoice(
        amount=price,
        description=f"Pro-подписка на 30 дней",
        payload=f"sub_{user_id}"
    )

    if not invoice:
        await callback.answer("❌ Ошибка создания инвойса", show_alert=True)
        return

    invoice_id = str(invoice["invoice_id"])
    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url", "")
    await db.create_payment(user_id, "subscription", price, invoice_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить в CryptoBot", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_pay_{invoice_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="subscription")]
    ])

    await callback.message.edit_text(
        f"💎 <b>Оплата подписки</b>\n\n"
        f"Сумма: <b>${price}</b>\n"
        f"Период: 30 дней\n\n"
        f"Нажмите кнопку ниже для оплаты через @CryptoBot:",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "buy_slot")
async def cb_buy_slot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    max_acc = user.get("max_accounts", 1) if user else 1

    if max_acc >= 5:
        await callback.answer("У вас уже максимум ячеек (5)!", show_alert=True)
        return

    price = await db.get_extra_account_price()

    invoice = await create_invoice(
        amount=price,
        description=f"Дополнительная ячейка аккаунта",
        payload=f"slot_{user_id}"
    )

    if not invoice:
        await callback.answer("❌ Ошибка создания инвойса", show_alert=True)
        return

    invoice_id = str(invoice["invoice_id"])
    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url", "")
    await db.create_payment(user_id, "extra_account", price, invoice_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить в CryptoBot", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_pay_{invoice_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="subscription")]
    ])

    await callback.message.edit_text(
        f"🔓 <b>Покупка доп. ячейки</b>\n\n"
        f"Сумма: <b>${price}</b>\n"
        f"Текущих ячеек: {max_acc}\n\n"
        f"Нажмите кнопку ниже для оплаты через @CryptoBot:",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_pay_"))
async def cb_check_payment(callback: CallbackQuery):
    invoice_id = callback.data.replace("check_pay_", "")
    user_id = callback.from_user.id

    payment = await db.get_payment_by_invoice(invoice_id)
    if not payment:
        await callback.answer("Платёж не найден", show_alert=True)
        return

    if payment["status"] == "paid":
        await callback.answer("✅ Этот платёж уже обработан!", show_alert=True)
        return

    # Проверка через CryptoPay API
    invoice_data = await check_invoice(int(invoice_id))
    if not invoice_data or invoice_data.get("status") != "paid":
        await callback.answer("⏳ Оплата ещё не получена. Попробуйте позже.", show_alert=True)
        return

    # Обработка оплаты
    await db.update_payment_status(invoice_id, "paid")

    if payment["type"] == "subscription":
        user = await db.get_user(user_id)
        current_end = user.get("subscription_end", "")
        try:
            end = datetime.fromisoformat(current_end)
            if end < datetime.utcnow():
                end = datetime.utcnow()
        except (TypeError, ValueError):
            end = datetime.utcnow()

        if current_end != "forever":
            new_end = end + timedelta(days=30)
            await db.update_user(user_id, subscription_end=new_end.isoformat())

        # Реферальный бонус
        if user.get("referrer_id"):
            bonus_days = await db.get_referral_bonus_days()
            referrer = await db.get_user(user["referrer_id"])
            if referrer:
                ref_end = referrer.get("subscription_end", "")
                if ref_end != "forever":
                    try:
                        rend = datetime.fromisoformat(ref_end)
                        if rend < datetime.utcnow():
                            rend = datetime.utcnow()
                    except (TypeError, ValueError):
                        rend = datetime.utcnow()
                    new_rend = rend + timedelta(days=bonus_days)
                    await db.update_user(user["referrer_id"], subscription_end=new_rend.isoformat())
                    try:
                        await callback.bot.send_message(
                            user["referrer_id"],
                            f"🎁 Ваш реферал купил подписку! Вам начислено <b>+{bonus_days} дней</b>!",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

        await callback.message.edit_text(
            "✅ <b>Оплата получена!</b>\n\n"
            f"Подписка активирована на 30 дней.",
            reply_markup=back_menu_kb(), parse_mode="HTML"
        )

    elif payment["type"] == "extra_account":
        user = await db.get_user(user_id)
        new_max = min((user.get("max_accounts", 1) + 1), 5)
        await db.update_user(user_id, max_accounts=new_max)
        await callback.message.edit_text(
            f"✅ <b>Оплата получена!</b>\n\n"
            f"Ячеек аккаунтов: {new_max}",
            reply_markup=back_menu_kb(), parse_mode="HTML"
        )

    await callback.answer("✅ Оплата подтверждена!")
