"""Обработчик настройки и запуска рассылок."""

import asyncio
import json
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import (
    choose_account_kb, message_source_kb, choose_template_kb,
    recipients_source_kb, choose_recipient_list_kb, break_kb,
    confirm_mailing_kb, stop_mailing_kb, cancel_kb, back_menu_kb,
    test_kb
)
from services.mailing_service import run_mailing, send_test_message, active_mailings
from config import FREE_DELAY, FREE_DAILY_LIMIT

router = Router()


class MailingStates(StatesGroup):
    choose_account = State()
    choose_text_source = State()
    enter_text = State()
    choose_recipients_source = State()
    enter_recipients = State()
    enter_delay = State()
    break_choice = State()
    enter_break_after = State()
    enter_break_duration = State()
    test_or_confirm = State()
    schedule_time = State()
    confirm = State()


@router.callback_query(F.data == "mailing_start")
async def cb_mailing_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    accounts = await db.get_accounts(user_id)

    if not accounts:
        await callback.message.edit_text(
            "❌ У вас нет привязанных аккаунтов.\nСначала добавьте аккаунт.",
            reply_markup=back_menu_kb()
        )
        await callback.answer()
        return

    if user_id in active_mailings:
        await callback.answer("⚠️ У вас уже идёт рассылка!", show_alert=True)
        return

    if len(accounts) == 1:
        await state.update_data(account_id=accounts[0]["id"])
        # Переход к выбору текста
        templates = await db.get_templates(user_id)
        is_sub = await db.is_subscribed(user_id)
        await callback.message.edit_text(
            "📝 <b>Шаг 2/5: Текст сообщения</b>\n\n"
            "Выберите источник текста:\n\n"
            "💡 Поддерживаются переменные:\n"
            "<code>{username}</code> — юзернейм получателя\n"
            "<code>{first_name}</code> — имя получателя",
            reply_markup=message_source_kb(bool(templates) and is_sub),
            parse_mode="HTML"
        )
        await state.set_state(MailingStates.choose_text_source)
    else:
        await callback.message.edit_text(
            "📱 <b>Шаг 1/5: Выбор аккаунта</b>\n\nС какого аккаунта делать рассылку?",
            reply_markup=choose_account_kb(accounts),
            parse_mode="HTML"
        )
        await state.set_state(MailingStates.choose_account)

    await callback.answer()


@router.callback_query(F.data.startswith("mail_acc_"), MailingStates.choose_account)
async def cb_choose_account(callback: CallbackQuery, state: FSMContext):
    acc_id = int(callback.data.split("_")[2])
    await state.update_data(account_id=acc_id)

    user_id = callback.from_user.id
    templates = await db.get_templates(user_id)
    is_sub = await db.is_subscribed(user_id)

    await callback.message.edit_text(
        "📝 <b>Шаг 2/5: Текст сообщения</b>\n\n"
        "Выберите источник текста:\n\n"
        "💡 Поддерживаются переменные:\n"
        "<code>{username}</code> — юзернейм получателя\n"
        "<code>{first_name}</code> — имя получателя",
        reply_markup=message_source_kb(bool(templates) and is_sub),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.choose_text_source)
    await callback.answer()


@router.callback_query(F.data == "mail_text_manual", MailingStates.choose_text_source)
async def cb_text_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ Введите текст сообщения для рассылки:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.enter_text)
    await callback.answer()


@router.callback_query(F.data == "mail_text_template", MailingStates.choose_text_source)
async def cb_text_template(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    templates = await db.get_templates(user_id)
    await callback.message.edit_text(
        "🗂 Выберите шаблон:",
        reply_markup=choose_template_kb(templates),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mail_tpl_"))
async def cb_choose_template(callback: CallbackQuery, state: FSMContext):
    tpl_id = int(callback.data.split("_")[2])
    tpl = await db.get_template(tpl_id)
    if not tpl:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await state.update_data(text=tpl["text"])
    user_id = callback.from_user.id
    lists = await db.get_recipient_lists(user_id)
    is_sub = await db.is_subscribed(user_id)

    await callback.message.edit_text(
        "📋 <b>Шаг 3/5: Получатели</b>\n\nВыберите источник списка получателей:",
        reply_markup=recipients_source_kb(bool(lists) and is_sub),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.choose_recipients_source)
    await callback.answer()


@router.message(MailingStates.enter_text)
async def process_text(message: Message, state: FSMContext):
    text = message.text
    if not text or len(text.strip()) == 0:
        await message.answer("❌ Текст не может быть пустым. Введите текст:", reply_markup=cancel_kb())
        return

    await state.update_data(text=text)
    user_id = message.from_user.id
    lists = await db.get_recipient_lists(user_id)
    is_sub = await db.is_subscribed(user_id)

    await message.answer(
        "📋 <b>Шаг 3/5: Получатели</b>\n\nВыберите источник списка получателей:",
        reply_markup=recipients_source_kb(bool(lists) and is_sub),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.choose_recipients_source)


@router.callback_query(F.data == "mail_rcpt_manual", MailingStates.choose_recipients_source)
async def cb_rcpt_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ Введите юзернеймы получателей.\n\n"
        "Формат: через запятую, пробел или каждый с новой строки.\n"
        "Пример: <code>@user1, @user2, @user3</code>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.enter_recipients)
    await callback.answer()


@router.callback_query(F.data == "mail_rcpt_list", MailingStates.choose_recipients_source)
async def cb_rcpt_list(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lists = await db.get_recipient_lists(user_id)
    await callback.message.edit_text(
        "📋 Выберите список получателей:",
        reply_markup=choose_recipient_list_kb(lists),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mail_rl_"))
async def cb_choose_list(callback: CallbackQuery, state: FSMContext):
    rl_id = int(callback.data.split("_")[2])
    rl = await db.get_recipient_list(rl_id)
    if not rl:
        await callback.answer("Список не найден", show_alert=True)
        return

    usernames = json.loads(rl["usernames"])
    await state.update_data(usernames=usernames)

    user_id = callback.from_user.id
    is_sub = await db.is_subscribed(user_id)

    if is_sub:
        await callback.message.edit_text(
            f"⏱ <b>Шаг 4/5: Задержка</b>\n\n"
            f"Получателей: {len(usernames)}\n\n"
            f"Введите задержку между сообщениями (в секундах):",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        await state.set_state(MailingStates.enter_delay)
    else:
        await state.update_data(delay=FREE_DELAY, break_after=0, break_duration=0)
        await _show_confirm(callback.message, state, callback.from_user.id, edit=True)

    await callback.answer()


@router.message(MailingStates.enter_recipients)
async def process_recipients(message: Message, state: FSMContext):
    raw = message.text.replace(",", " ").replace("\n", " ").replace(";", " ")
    usernames = [u.strip().lstrip("@") for u in raw.split() if u.strip().lstrip("@")]

    if not usernames:
        await message.answer("❌ Не найдено ни одного юзернейма. Попробуйте снова:", reply_markup=cancel_kb())
        return

    await state.update_data(usernames=usernames)
    user_id = message.from_user.id
    is_sub = await db.is_subscribed(user_id)

    if is_sub:
        await message.answer(
            f"⏱ <b>Шаг 4/5: Задержка</b>\n\n"
            f"Получателей: {len(usernames)}\n\n"
            f"Введите задержку между сообщениями (в секундах):",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        await state.set_state(MailingStates.enter_delay)
    else:
        # Free — ограничения
        today_sent = await db.get_today_sent(user_id)
        remaining = max(0, FREE_DAILY_LIMIT - today_sent)
        if remaining == 0:
            await message.answer(
                "❌ Лимит сообщений на сегодня исчерпан (10/10).\n"
                "Купите подписку для безлимита!",
                reply_markup=back_menu_kb()
            )
            await state.clear()
            return

        if len(usernames) > remaining:
            usernames = usernames[:remaining]
            await state.update_data(usernames=usernames)

        await state.update_data(delay=FREE_DELAY, break_after=0, break_duration=0)
        await _show_confirm(message, state, user_id, edit=False)


@router.message(MailingStates.enter_delay)
async def process_delay(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Введите число больше 0:", reply_markup=cancel_kb())
        return

    await state.update_data(delay=int(text))
    await message.answer(
        "⏸ <b>Шаг 5/5: Перерывы</b>\n\nНастроить перерывы в рассылке?\n"
        "(например, пауза 60 сек каждые 10 сообщений)",
        reply_markup=break_kb(),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.break_choice)


@router.callback_query(F.data == "mail_break_no", MailingStates.break_choice)
async def cb_break_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(break_after=0, break_duration=0)
    await _show_confirm(callback.message, state, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "mail_break_yes", MailingStates.break_choice)
async def cb_break_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Через сколько сообщений делать перерыв?",
        reply_markup=cancel_kb()
    )
    await state.set_state(MailingStates.enter_break_after)
    await callback.answer()


@router.message(MailingStates.enter_break_after)
async def process_break_after(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Введите число больше 0:", reply_markup=cancel_kb())
        return
    await state.update_data(break_after=int(text))
    await message.answer("Длительность перерыва (в секундах):", reply_markup=cancel_kb())
    await state.set_state(MailingStates.enter_break_duration)


@router.message(MailingStates.enter_break_duration)
async def process_break_duration(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Введите число больше 0:", reply_markup=cancel_kb())
        return
    await state.update_data(break_duration=int(text))
    await _show_confirm(message, state, message.from_user.id, edit=False)


async def _show_confirm(message_or_cb, state: FSMContext, user_id: int, edit: bool = False):
    """Показать итоговое подтверждение."""
    data = await state.get_data()
    is_sub = await db.is_subscribed(user_id)

    acc = await db.get_account(data["account_id"])
    phone = acc["phone"] if acc else "?"
    masked = phone[:4] + "***" + phone[-2:] if len(phone) > 6 else phone

    usernames = data.get("usernames", [])
    delay = data.get("delay", FREE_DELAY)
    break_after = data.get("break_after", 0)
    break_duration = data.get("break_duration", 0)
    text_preview = data.get("text", "")[:100]
    if len(data.get("text", "")) > 100:
        text_preview += "..."

    summary = (
        f"📋 <b>Подтверждение рассылки</b>\n\n"
        f"📱 Аккаунт: <code>{masked}</code>\n"
        f"📝 Текст: <i>{text_preview}</i>\n"
        f"👥 Получателей: <b>{len(usernames)}</b>\n"
        f"⏱ Задержка: <b>{delay} сек</b>\n"
    )

    if break_after > 0:
        summary += f"⏸ Перерыв: <b>{break_duration} сек</b> каждые <b>{break_after}</b> сообщ.\n"

    if not is_sub:
        today_sent = await db.get_today_sent(user_id)
        summary += f"\n⚠️ Free: осталось {max(0, FREE_DAILY_LIMIT - today_sent)} сообщ. сегодня"

    kb = confirm_mailing_kb(is_sub)

    if is_sub:
        # Предложить тест
        from keyboards import test_kb as get_test_kb
        summary += "\n\n🧪 Хотите отправить тестовое сообщение себе?"
        kb = get_test_kb()

    await state.set_state(MailingStates.confirm)

    if edit:
        await message_or_cb.edit_text(summary, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_cb.answer(summary, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "mail_test", MailingStates.confirm)
async def cb_test(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    acc = await db.get_account(data["account_id"])
    if not acc:
        await callback.answer("Аккаунт не найден!", show_alert=True)
        return

    await callback.answer("Отправляю тест...")
    success = await send_test_message(acc, data.get("text", "test"))

    if success:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ Тестовое сообщение отправлено в Saved Messages!",
            reply_markup=confirm_mailing_kb(True),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Не удалось отправить тест. Проверьте аккаунт.",
            reply_markup=confirm_mailing_kb(True),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "mail_skip_test", MailingStates.confirm)
async def cb_skip_test(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_sub = await db.is_subscribed(callback.from_user.id)

    acc = await db.get_account(data["account_id"])
    phone = acc["phone"] if acc else "?"
    masked = phone[:4] + "***" + phone[-2:] if len(phone) > 6 else phone
    usernames = data.get("usernames", [])
    delay = data.get("delay", FREE_DELAY)
    text_preview = data.get("text", "")[:100]

    summary = (
        f"📋 <b>Подтверждение рассылки</b>\n\n"
        f"📱 Аккаунт: <code>{masked}</code>\n"
        f"📝 Текст: <i>{text_preview}</i>\n"
        f"👥 Получателей: <b>{len(usernames)}</b>\n"
        f"⏱ Задержка: <b>{delay} сек</b>\n"
    )

    await callback.message.edit_text(summary, reply_markup=confirm_mailing_kb(is_sub), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "mail_schedule", MailingStates.confirm)
async def cb_schedule(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏰ Введите дату и время запуска:\n\n"
        "Формат: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "Пример: <code>25.04.2026 14:00</code>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(MailingStates.schedule_time)
    await callback.answer()


@router.message(MailingStates.schedule_time)
async def process_schedule_time(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        if dt <= datetime.utcnow():
            await message.answer("❌ Время должно быть в будущем!", reply_markup=cancel_kb())
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте: ДД.ММ.ГГГГ ЧЧ:ММ", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    user_id = message.from_user.id

    sched_id = await db.add_scheduled_mailing(
        user_id=user_id,
        account_id=data["account_id"],
        text=data.get("text", ""),
        usernames=data.get("usernames", []),
        delay=data.get("delay", 5),
        break_after=data.get("break_after", 0),
        break_duration=data.get("break_duration", 0),
        scheduled_time=dt.isoformat()
    )

    from services.scheduler import schedule_mailing
    schedule_mailing(message.bot, sched_id, dt)

    await message.answer(
        f"✅ <b>Рассылка запланирована!</b>\n\n"
        f"⏰ Время: {dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 Получателей: {len(data.get('usernames', []))}",
        reply_markup=back_menu_kb(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "mail_confirm", MailingStates.confirm)
async def cb_confirm_mailing(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    bot = callback.bot

    acc = await db.get_account(data["account_id"])
    if not acc:
        await callback.message.edit_text("❌ Аккаунт не найден.", reply_markup=back_menu_kb())
        await state.clear()
        return

    usernames = data.get("usernames", [])
    total = len(usernames)
    is_sub = await db.is_subscribed(user_id)

    mailing_id = await db.create_mailing(user_id, acc["id"], acc["phone"], data.get("text", ""), total)

    from services.mailing_service import make_progress_text
    progress_text = make_progress_text(0, 0, total)
    progress_msg = await callback.message.edit_text(
        progress_text, reply_markup=stop_mailing_kb(mailing_id), parse_mode="HTML"
    )

    await state.clear()
    await callback.answer("🚀 Рассылка запущена!")

    # Запуск в фоне
    asyncio.create_task(run_mailing(
        bot=bot,
        user_id=user_id,
        mailing_id=mailing_id,
        account=acc,
        text=data.get("text", ""),
        usernames=usernames,
        delay=data.get("delay", FREE_DELAY),
        break_after=data.get("break_after", 0),
        break_duration=data.get("break_duration", 0),
        progress_msg_id=progress_msg.message_id,
        chat_id=user_id,
        is_subscribed=is_sub
    ))


@router.callback_query(F.data.startswith("mail_stop_"))
async def cb_stop_mailing(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in active_mailings:
        active_mailings[user_id]["stop"] = True
        await callback.answer("🛑 Останавливаю рассылку...", show_alert=True)
    else:
        await callback.answer("Рассылка уже завершена.", show_alert=True)
