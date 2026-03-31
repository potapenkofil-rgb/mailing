"""Все клавиатуры бота."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_sub: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="mailing_start")],
        [InlineKeyboardButton(text="📋 Мои аккаунты", callback_data="accounts")],
        [InlineKeyboardButton(text="🗂 Шаблоны сообщений", callback_data="templates")],
        [InlineKeyboardButton(text="📄 Списки получателей", callback_data="recipients")],
    ]
    if is_sub:
        buttons.append([InlineKeyboardButton(text="⏰ Отложенные рассылки", callback_data="scheduled")])
    buttons += [
        [InlineKeyboardButton(text="📈 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="💳 Подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def resend_code_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Запросить новый код", callback_data="acc_resend_code")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


# ==================== ACCOUNTS ====================

def accounts_kb(accounts: list[dict], can_add: bool) -> InlineKeyboardMarkup:
    buttons = []
    for acc in accounts:
        phone = acc["phone"]
        masked = phone[:4] + "***" + phone[-2:] if len(phone) > 6 else phone
        buttons.append([InlineKeyboardButton(text=f"📱 {masked}", callback_data=f"acc_{acc['id']}")])
    if can_add:
        buttons.append([InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="acc_add")])
    else:
        buttons.append([InlineKeyboardButton(text="🔓 Купить ячейку", callback_data="buy_slot")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def account_detail_kb(acc_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"acc_del_{acc_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="accounts")]
    ])


# ==================== TEMPLATES ====================

def templates_kb(templates: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for t in templates:
        buttons.append([InlineKeyboardButton(text=f"📝 {t['name']}", callback_data=f"tpl_{t['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать шаблон", callback_data="tpl_add")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def template_detail_kb(tpl_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"tpl_del_{tpl_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="templates")]
    ])


# ==================== RECIPIENT LISTS ====================

def recipient_lists_kb(lists: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for rl in lists:
        cnt = len(rl.get("usernames", "[]"))
        buttons.append([InlineKeyboardButton(text=f"📋 {rl['name']}", callback_data=f"rl_{rl['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать список", callback_data="rl_add")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def recipient_list_detail_kb(rl_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"rl_del_{rl_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="recipients")]
    ])


# ==================== MAILING ====================

def choose_account_kb(accounts: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for acc in accounts:
        phone = acc["phone"]
        masked = phone[:4] + "***" + phone[-2:] if len(phone) > 6 else phone
        buttons.append([InlineKeyboardButton(text=f"📱 {masked}", callback_data=f"mail_acc_{acc['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def message_source_kb(has_templates: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="✏️ Ввести текст", callback_data="mail_text_manual")]]
    if has_templates:
        buttons.append([InlineKeyboardButton(text="🗂 Из шаблона", callback_data="mail_text_template")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def choose_template_kb(templates: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for t in templates:
        buttons.append([InlineKeyboardButton(text=f"📝 {t['name']}", callback_data=f"mail_tpl_{t['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def recipients_source_kb(has_lists: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="✏️ Ввести юзернеймы", callback_data="mail_rcpt_manual")]]
    if has_lists:
        buttons.append([InlineKeyboardButton(text="📋 Из списка", callback_data="mail_rcpt_list")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def choose_recipient_list_kb(lists: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for rl in lists:
        buttons.append([InlineKeyboardButton(text=f"📋 {rl['name']}", callback_data=f"mail_rl_{rl['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def break_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, настроить", callback_data="mail_break_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="mail_break_no")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def schedule_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="mail_schedule")],
        [InlineKeyboardButton(text="🚀 Запустить сейчас", callback_data="mail_now")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def test_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Тест", callback_data="mail_test")],
        [InlineKeyboardButton(text="▶️ Пропустить тест", callback_data="mail_skip_test")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def confirm_mailing_kb(is_sub: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="✅ Запустить", callback_data="mail_confirm")]]
    if is_sub:
        buttons.append([InlineKeyboardButton(text="⏰ Запланировать", callback_data="mail_schedule")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stop_mailing_kb(mailing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Остановить рассылку", callback_data=f"mail_stop_{mailing_id}")]
    ])


# ==================== SUBSCRIPTION ====================

def subscription_kb(is_sub: bool) -> InlineKeyboardMarkup:
    buttons = []
    if not is_sub:
        buttons.append([InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_sub")])
    else:
        buttons.append([InlineKeyboardButton(text="💎 Продлить подписку", callback_data="buy_sub")])
    buttons.append([InlineKeyboardButton(text="🔓 Купить доп. ячейку", callback_data="buy_slot")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== SCHEDULED ====================

def scheduled_list_kb(mailings: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for m in mailings:
        buttons.append([InlineKeyboardButton(
            text=f"⏰ {m['scheduled_time'][:16]}",
            callback_data=f"sched_{m['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def scheduled_detail_kb(sched_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"sched_cancel_{sched_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="scheduled")]
    ])


# ==================== ADMIN ====================

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика подписок", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm_search")],
        [InlineKeyboardButton(text="🚫 Бан пользователя", callback_data="adm_ban")],
        [InlineKeyboardButton(text="✅ Разбан пользователя", callback_data="adm_unban")],
        [InlineKeyboardButton(text="💎 Управление подпиской", callback_data="adm_sub")],
        [InlineKeyboardButton(text="💰 Изменить цены", callback_data="adm_prices")],
        [InlineKeyboardButton(text="📢 Рассылка по боту", callback_data="adm_broadcast")],
    ])


def admin_user_card_kb(is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ Разбанить", callback_data="adm_card_unban")
        if is_banned
        else InlineKeyboardButton(text="🚫 Забанить", callback_data="adm_card_ban")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [InlineKeyboardButton(text="💎 Управление подпиской", callback_data="adm_card_sub")],
        [InlineKeyboardButton(text="🔍 Найти другого", callback_data="adm_search")],
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin")],
    ])


def admin_prices_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Цена подписки", callback_data="adm_price_sub")],
        [InlineKeyboardButton(text="🔓 Цена доп. ячейки", callback_data="adm_price_slot")],
        [InlineKeyboardButton(text="🎁 Бонус реферала (дни)", callback_data="adm_price_ref")],
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin")]
    ])
