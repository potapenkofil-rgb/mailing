"""Сервис рассылки сообщений через Telethon."""

import asyncio
import json
import time
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PeerFloodError, FloodWaitError, UserPrivacyRestrictedError,
    UserNotMutualContactError, ChatWriteForbiddenError,
    UserBannedInChannelError, InputUserDeactivatedError,
    UserBlockedError
)

import database as db

# Активные рассылки: {user_id: {"stop": False}}
active_mailings: dict[int, dict] = {}


def make_progress_text(sent: int, failed: int, total: int) -> str:
    """Генерация текста прогресса."""
    remaining = total - sent - failed
    pct = int((sent + failed) / total * 100) if total > 0 else 0
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "━" * filled + "░" * (bar_len - filled)

    return (
        f"📬 <b>Рассылка в процессе...</b>\n\n"
        f"✅ Отправлено: <b>{sent}</b>\n"
        f"⏭ Пропущено: <b>{failed}</b>\n"
        f"📭 Осталось: <b>{remaining}</b>\n\n"
        f"{bar} <b>{pct}%</b>"
    )


def make_report(phone: str, sent: int, failed: int, total: int,
                failed_usernames: list[str], elapsed: float, status: str) -> str:
    """Генерация финального отчёта."""
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    time_str = f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"

    now = datetime.utcnow().strftime("%d.%m.%Y, %H:%M")
    masked_phone = phone[:4] + " ***-**-" + phone[-2:] if len(phone) > 6 else phone

    status_map = {
        "completed": "✅ Завершена",
        "aborted": "⚠️ Прервана пользователем",
        "spam_block": "🚫 Остановлена (спам-блок)"
    }
    status_text = status_map.get(status, status)

    failed_text = ""
    if failed_usernames:
        failed_list = ", ".join(f"@{u}" for u in failed_usernames[:50])
        if len(failed_usernames) > 50:
            failed_list += f"\n... и ещё {len(failed_usernames) - 50}"
        failed_text = f"\n\n❌ <b>Не удалось отправить:</b>\n<code>{failed_list}</code>"

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>ОТЧЁТ О РАССЫЛКЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Аккаунт: <code>{masked_phone}</code>\n"
        f"⏱ Время: {time_str}\n"
        f"📅 {now}\n\n"
        f"✅ Успешно: <b>{sent}</b>\n"
        f"❌ Не отправлено: <b>{failed}</b>\n"
        f"📊 Всего: <b>{total}</b>"
        f"{failed_text}\n\n"
        f"🏁 Статус: <b>{status_text}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


async def send_test_message(account: dict, text: str) -> bool:
    """Отправить тестовое сообщение в Saved Messages."""
    try:
        client = TelegramClient(
            StringSession(account["session_string"]),
            int(account["api_id"]),
            account["api_hash"]
        )
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False
        await client.send_message("me", text)
        await client.disconnect()
        return True
    except Exception as e:
        print(f"Test message error: {e}")
        return False


async def run_mailing(
    bot,
    user_id: int,
    mailing_id: int,
    account: dict,
    text: str,
    usernames: list[str],
    delay: int,
    break_after: int = 0,
    break_duration: int = 0,
    progress_msg_id: int = None,
    chat_id: int = None,
    is_subscribed: bool = True
):
    """
    Основная функция рассылки.
    """
    active_mailings[user_id] = {"stop": False}

    client = TelegramClient(
        StringSession(account["session_string"]),
        int(account["api_id"]),
        account["api_hash"]
    )

    sent = 0
    failed = 0
    failed_usernames_list = []
    status = "completed"
    start_time = time.time()
    total = len(usernames)
    last_update = 0

    try:
        await client.connect()
        if not await client.is_user_authorized():
            status = "aborted"
            return

        for i, username in enumerate(usernames):
            # Проверка остановки
            if active_mailings.get(user_id, {}).get("stop"):
                status = "aborted"
                break

            # Проверка лимита для бесплатных
            if not is_subscribed:
                today_sent = await db.get_today_sent(user_id)
                if today_sent >= 10:
                    status = "completed"
                    break

            uname = username.strip().lstrip("@")
            if not uname:
                continue

            # Персонализация
            try:
                entity = await client.get_entity(uname)
                first_name = getattr(entity, "first_name", uname) or uname
                personal_text = text.replace("{username}", f"@{uname}").replace("{first_name}", first_name)
            except Exception:
                first_name = uname
                personal_text = text.replace("{username}", f"@{uname}").replace("{first_name}", first_name)

            # Попытка отправки
            spam_blocked = False
            try:
                await client.send_message(uname, personal_text)
                sent += 1
                await db.increment_today_sent(user_id)
            except PeerFloodError:
                # Спам-блок — пробуем через @SpamBot
                try:
                    spambot = await client.get_entity("SpamBot")
                    await client.send_message(spambot, "/start")
                    await asyncio.sleep(5)
                    # Повторная попытка
                    try:
                        await client.send_message(uname, personal_text)
                        sent += 1
                        await db.increment_today_sent(user_id)
                    except PeerFloodError:
                        spam_blocked = True
                    except Exception:
                        failed += 1
                        failed_usernames_list.append(uname)
                except Exception:
                    spam_blocked = True

                if spam_blocked:
                    status = "spam_block"
                    break

            except FloodWaitError as e:
                await asyncio.sleep(min(e.seconds, 60))
                try:
                    await client.send_message(uname, personal_text)
                    sent += 1
                    await db.increment_today_sent(user_id)
                except Exception:
                    failed += 1
                    failed_usernames_list.append(uname)

            except (UserPrivacyRestrictedError, UserNotMutualContactError,
                    ChatWriteForbiddenError, UserBannedInChannelError,
                    InputUserDeactivatedError, UserBlockedError):
                failed += 1
                failed_usernames_list.append(uname)
            except Exception as e:
                print(f"Send error to @{uname}: {e}")
                failed += 1
                failed_usernames_list.append(uname)

            # Обновление прогресса (каждые 5 сообщений или 30 сек)
            now = time.time()
            if progress_msg_id and chat_id and ((sent + failed) % 5 == 0 or now - last_update > 30):
                last_update = now
                try:
                    from keyboards import stop_mailing_kb
                    await bot.edit_message_text(
                        text=make_progress_text(sent, failed, total),
                        chat_id=chat_id,
                        message_id=progress_msg_id,
                        reply_markup=stop_mailing_kb(mailing_id),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            # Обновление БД
            await db.update_mailing(mailing_id, sent=sent, failed=failed,
                                     failed_usernames=json.dumps(failed_usernames_list))

            # Задержка
            if i < len(usernames) - 1:
                # Перерыв
                if break_after > 0 and break_duration > 0 and (sent + failed) % break_after == 0 and (sent + failed) > 0:
                    for _ in range(break_duration):
                        if active_mailings.get(user_id, {}).get("stop"):
                            break
                        await asyncio.sleep(1)
                else:
                    for _ in range(delay):
                        if active_mailings.get(user_id, {}).get("stop"):
                            break
                        await asyncio.sleep(1)

    except Exception as e:
        print(f"Mailing error: {e}")
        status = "aborted"
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

        if active_mailings.get(user_id, {}).get("stop") and status != "spam_block":
            status = "aborted"

        elapsed = time.time() - start_time

        # Финализация в БД
        await db.update_mailing(
            mailing_id,
            sent=sent,
            failed=failed,
            failed_usernames=json.dumps(failed_usernames_list),
            finished_at=datetime.utcnow().isoformat(),
            status=status
        )

        # Отправка отчёта
        report = make_report(
            account["phone"], sent, failed, total,
            failed_usernames_list, elapsed, status
        )

        if chat_id:
            try:
                from keyboards import back_menu_kb
                await bot.send_message(chat_id, report, parse_mode="HTML", reply_markup=back_menu_kb())
            except Exception:
                pass

        # Удаление прогресс-сообщения
        if progress_msg_id and chat_id:
            try:
                await bot.delete_message(chat_id, progress_msg_id)
            except Exception:
                pass

        active_mailings.pop(user_id, None)
