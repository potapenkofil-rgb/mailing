"""Обработчик списков получателей."""

import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import recipient_lists_kb, recipient_list_detail_kb, cancel_kb, back_menu_kb

router = Router()


class RecipientListStates(StatesGroup):
    name = State()
    usernames = State()


@router.callback_query(F.data == "recipients")
async def cb_recipients(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    is_sub = await db.is_subscribed(user_id)

    if not is_sub:
        await callback.answer("🔒 Списки доступны только с подпиской!", show_alert=True)
        return

    lists = await db.get_recipient_lists(user_id)
    if lists:
        text = f"📄 <b>Мои списки получателей</b> ({len(lists)})"
    else:
        text = "📄 <b>Мои списки</b>\n\nУ вас пока нет сохранённых списков."
    await callback.message.edit_text(text, reply_markup=recipient_lists_kb(lists), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("rl_") & ~F.data.startswith("rl_add") & ~F.data.startswith("rl_del_"))
async def cb_list_detail(callback: CallbackQuery):
    rl_id = int(callback.data.split("_")[1])
    rl = await db.get_recipient_list(rl_id)
    if not rl:
        await callback.answer("Список не найден", show_alert=True)
        return

    usernames = json.loads(rl["usernames"])
    preview = ", ".join(f"@{u}" for u in usernames[:10])
    if len(usernames) > 10:
        preview += f"\n... и ещё {len(usernames) - 10}"

    text = (
        f"📋 <b>{rl['name']}</b>\n\n"
        f"👥 Получателей: {len(usernames)}\n"
        f"{preview}\n\n"
        f"📅 Создан: {rl['created_at'][:10]}"
    )
    await callback.message.edit_text(text, reply_markup=recipient_list_detail_kb(rl_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("rl_del_"))
async def cb_delete_list(callback: CallbackQuery):
    rl_id = int(callback.data.split("_")[2])
    await db.delete_recipient_list(rl_id)
    await callback.answer("✅ Список удалён", show_alert=True)

    user_id = callback.from_user.id
    lists = await db.get_recipient_lists(user_id)
    text = f"📄 <b>Мои списки</b> ({len(lists)})"
    await callback.message.edit_text(text, reply_markup=recipient_lists_kb(lists), parse_mode="HTML")


@router.callback_query(F.data == "rl_add")
async def cb_add_list(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📋 Введите <b>название</b> списка:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(RecipientListStates.name)
    await callback.answer()


@router.message(RecipientListStates.name)
async def process_list_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым:", reply_markup=cancel_kb())
        return
    await state.update_data(name=name)
    await message.answer(
        "✏️ Введите юзернеймы (через запятую, пробел или с новой строки):\n"
        "Пример: <code>@user1, @user2, @user3</code>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(RecipientListStates.usernames)


@router.message(RecipientListStates.usernames)
async def process_list_usernames(message: Message, state: FSMContext):
    raw = message.text.replace(",", " ").replace("\n", " ").replace(";", " ")
    usernames = [u.strip().lstrip("@") for u in raw.split() if u.strip().lstrip("@")]

    if not usernames:
        await message.answer("❌ Не найдено юзернеймов. Попробуйте снова:", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    await db.add_recipient_list(message.from_user.id, data["name"], usernames)
    await message.answer(
        f"✅ Список «{data['name']}» сохранён!\n"
        f"👥 Получателей: {len(usernames)}",
        reply_markup=back_menu_kb()
    )
    await state.clear()
