"""Обработчик шаблонов сообщений."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import templates_kb, template_detail_kb, cancel_kb, back_menu_kb

router = Router()


class TemplateStates(StatesGroup):
    name = State()
    text = State()


@router.callback_query(F.data == "templates")
async def cb_templates(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    is_sub = await db.is_subscribed(user_id)

    if not is_sub:
        await callback.answer("🔒 Шаблоны доступны только с подпиской!", show_alert=True)
        return

    templates = await db.get_templates(user_id)
    if templates:
        text = f"🗂 <b>Мои шаблоны</b> ({len(templates)})"
    else:
        text = "🗂 <b>Мои шаблоны</b>\n\nУ вас пока нет шаблонов."
    await callback.message.edit_text(text, reply_markup=templates_kb(templates), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("tpl_") & ~F.data.startswith("tpl_add") & ~F.data.startswith("tpl_del_"))
async def cb_template_detail(callback: CallbackQuery):
    tpl_id = int(callback.data.split("_")[1])
    tpl = await db.get_template(tpl_id)
    if not tpl:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    text = (
        f"📝 <b>{tpl['name']}</b>\n\n"
        f"{tpl['text']}\n\n"
        f"📅 Создан: {tpl['created_at'][:10]}"
    )
    await callback.message.edit_text(text, reply_markup=template_detail_kb(tpl_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("tpl_del_"))
async def cb_delete_template(callback: CallbackQuery):
    tpl_id = int(callback.data.split("_")[2])
    await db.delete_template(tpl_id)
    await callback.answer("✅ Шаблон удалён", show_alert=True)

    user_id = callback.from_user.id
    templates = await db.get_templates(user_id)
    text = f"🗂 <b>Мои шаблоны</b> ({len(templates)})"
    await callback.message.edit_text(text, reply_markup=templates_kb(templates), parse_mode="HTML")


@router.callback_query(F.data == "tpl_add")
async def cb_add_template(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите <b>название</b> шаблона:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(TemplateStates.name)
    await callback.answer()


@router.message(TemplateStates.name)
async def process_template_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым:", reply_markup=cancel_kb())
        return
    await state.update_data(name=name)
    await message.answer(
        "✏️ Теперь введите <b>текст</b> шаблона:\n\n"
        "💡 Переменные: <code>{username}</code>, <code>{first_name}</code>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(TemplateStates.text)


@router.message(TemplateStates.text)
async def process_template_text(message: Message, state: FSMContext):
    text = message.text
    if not text:
        await message.answer("❌ Текст не может быть пустым:", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    await db.add_template(message.from_user.id, data["name"], text)
    await message.answer(f"✅ Шаблон «{data['name']}» сохранён!", reply_markup=back_menu_kb())
    await state.clear()
