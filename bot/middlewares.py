"""Мидлвари бота."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

import database as db


class BanMiddleware(BaseMiddleware):
    """Проверка бана пользователя."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            user = await db.get_user(user_id)
            if user and user.get("is_banned"):
                if isinstance(event, Message):
                    await event.answer("🚫 Вы заблокированы. Обратитесь к администратору.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Вы заблокированы.", show_alert=True)
                return

        return await handler(event, data)
