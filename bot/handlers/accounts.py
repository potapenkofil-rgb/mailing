"""Обработчик привязки аккаунтов Telegram."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PasswordHashInvalidError, PhoneNumberInvalidError,
    ApiIdInvalidError
)

import database as db
from keyboards import accounts_kb, account_detail_kb, cancel_kb, back_menu_kb

router = Router()


class AddAccountStates(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code = State()
    password = State()


# Временное хранилище клиентов для авторизации
_pending_clients: dict[int, TelegramClient] = {}


@router.callback_query(F.data == "accounts")
async def cb_accounts(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    accounts = await db.get_accounts(user_id)
    max_acc = user.get("max_accounts", 1) if user else 1
    can_add = len(accounts) < max_acc
    is_sub = await db.is_subscribed(user_id)

    if not accounts:
        text = "📋 <b>Мои аккаунты</b>\n\nУ вас пока нет привязанных аккаунтов."
    else:
        text = f"📋 <b>Мои аккаунты</b> ({len(accounts)}/{max_acc})\n\nВыберите аккаунт или добавьте новый:"

    await callback.message.edit_text(text, reply_markup=accounts_kb(accounts, can_add), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc_") & ~F.data.startswith("acc_add") & ~F.data.startswith("acc_del_"))
async def cb_account_detail(callback: CallbackQuery):
    acc_id = int(callback.data.split("_")[1])
    acc = await db.get_account(acc_id)
    if not acc:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    phone = acc["phone"]
    masked = phone[:4] + " ***-**-" + phone[-2:] if len(phone) > 6 else phone
    text = (
        f"📱 <b>Аккаунт</b>\n\n"
        f"Телефон: <code>{masked}</code>\n"
        f"Добавлен: {acc['added_at'][:10]}"
    )
    await callback.message.edit_text(text, reply_markup=account_detail_kb(acc_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acc_del_"))
async def cb_delete_account(callback: CallbackQuery):
    acc_id = int(callback.data.split("_")[2])
    await db.delete_account(acc_id)
    await callback.answer("✅ Аккаунт удалён", show_alert=True)

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    accounts = await db.get_accounts(user_id)
    max_acc = user.get("max_accounts", 1) if user else 1
    can_add = len(accounts) < max_acc
    text = f"📋 <b>Мои аккаунты</b> ({len(accounts)}/{max_acc})"
    await callback.message.edit_text(text, reply_markup=accounts_kb(accounts, can_add), parse_mode="HTML")


@router.callback_query(F.data == "acc_add")
async def cb_add_account(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    accounts = await db.get_accounts(user_id)
    max_acc = user.get("max_accounts", 1) if user else 1

    if len(accounts) >= max_acc:
        await callback.answer("Лимит аккаунтов исчерпан! Купите доп. ячейку.", show_alert=True)
        return

    await callback.message.edit_text(
        "🔑 <b>Добавление аккаунта</b>\n\n"
        "Введите ваш <b>API ID</b>.\n\n"
        "💡 Получить его можно на <a href='https://my.telegram.org'>my.telegram.org</a>:\n"
        "1. Войдите по номеру телефона\n"
        "2. Перейдите в API Development Tools\n"
        "3. Скопируйте App api_id",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await state.set_state(AddAccountStates.api_id)
    await callback.answer()


@router.message(AddAccountStates.api_id)
async def process_api_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ API ID должен быть числом. Попробуйте снова:", reply_markup=cancel_kb())
        return
    await state.update_data(api_id=text)
    await message.answer("Теперь введите ваш <b>API Hash</b>:", reply_markup=cancel_kb(), parse_mode="HTML")
    await state.set_state(AddAccountStates.api_hash)


@router.message(AddAccountStates.api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("❌ API Hash слишком короткий. Попробуйте снова:", reply_markup=cancel_kb())
        return
    await state.update_data(api_hash=text)
    await message.answer(
        "📱 Введите <b>номер телефона</b> аккаунта\n(в международном формате, например +79991234567):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(AddAccountStates.phone)


@router.message(AddAccountStates.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer("❌ Неверный формат. Введите номер с +:", reply_markup=cancel_kb())
        return

    await state.update_data(phone=phone)
    data = await state.get_data()

    wait_msg = await message.answer("⏳ Подключаюсь и отправляю код...")

    try:
        client = TelegramClient(
            StringSession(),
            int(data["api_id"]),
            data["api_hash"]
        )
        await client.connect()
        result = await client.send_code_request(phone)
        await state.update_data(phone_code_hash=result.phone_code_hash)
        _pending_clients[message.from_user.id] = client

        await wait_msg.edit_text(
            "📨 Код отправлен! Введите <b>код подтверждения</b> из Telegram:\n\n"
            "⚠️ Введите код через пробелы или дефисы (например: 1-2-3-4-5), "
            "чтобы Telegram не заблокировал его.",
            parse_mode="HTML"
        )
        await state.set_state(AddAccountStates.code)

    except PhoneNumberInvalidError:
        await wait_msg.edit_text("❌ Неверный номер телефона.", reply_markup=cancel_kb())
        await state.clear()
    except ApiIdInvalidError:
        await wait_msg.edit_text("❌ Неверный API ID или API Hash.", reply_markup=cancel_kb())
        await state.clear()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}", reply_markup=cancel_kb())
        await state.clear()


@router.message(AddAccountStates.code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "").replace("-", "")
    data = await state.get_data()
    user_id = message.from_user.id

    client = _pending_clients.get(user_id)
    if not client:
        await message.answer("❌ Сессия истекла. Начните заново.", reply_markup=cancel_kb())
        await state.clear()
        return

    try:
        await client.sign_in(data["phone"], code, phone_code_hash=data.get("phone_code_hash"))

        # Успешная авторизация
        session_str = client.session.save()
        await db.add_account(user_id, data["phone"], data["api_id"], data["api_hash"], session_str)
        await client.disconnect()
        _pending_clients.pop(user_id, None)

        await message.answer(
            f"✅ <b>Аккаунт {data['phone']} привязан!</b>",
            reply_markup=back_menu_kb(), parse_mode="HTML"
        )
        await state.clear()

    except SessionPasswordNeededError:
        await message.answer(
            "🔐 На аккаунте включена двухфакторная аутентификация.\n"
            "Введите <b>пароль 2FA</b>:",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )
        await state.set_state(AddAccountStates.password)

    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:", reply_markup=cancel_kb())

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=cancel_kb())
        await state.clear()
        if client:
            await client.disconnect()
        _pending_clients.pop(user_id, None)


@router.message(AddAccountStates.password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id

    client = _pending_clients.get(user_id)
    if not client:
        await message.answer("❌ Сессия истекла. Начните заново.", reply_markup=cancel_kb())
        await state.clear()
        return

    try:
        await client.sign_in(password=password)

        session_str = client.session.save()
        await db.add_account(user_id, data["phone"], data["api_id"], data["api_hash"], session_str)
        await client.disconnect()
        _pending_clients.pop(user_id, None)

        await message.answer(
            f"✅ <b>Аккаунт {data['phone']} привязан!</b>",
            reply_markup=back_menu_kb(), parse_mode="HTML"
        )
        await state.clear()

    except PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль. Попробуйте ещё раз:", reply_markup=cancel_kb())

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=cancel_kb())
        await state.clear()
        if client:
            await client.disconnect()
        _pending_clients.pop(user_id, None)


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    client = _pending_clients.pop(user_id, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.", reply_markup=back_menu_kb())
    await callback.answer()
