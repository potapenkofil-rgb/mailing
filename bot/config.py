"""Конфигурация бота."""

BOT_TOKEN = "8747829473:AAEQJ9B0kMhVN1r88-FN736fcZLjZ5OGdQQ"
CRYPTO_PAY_TOKEN = "484266:AAtvpozUB5U5ABnaIEGRqdUBpeLZx2izqrj"

ADMIN_ID = 7835543351

DB_PATH = "bot_data.db"

# Дефолтные цены (могут быть изменены админом)
DEFAULT_SUBSCRIPTION_PRICE = 2.0  # $/мес
DEFAULT_EXTRA_ACCOUNT_PRICE = 3.0  # $ единоразово
DEFAULT_REFERRAL_BONUS_DAYS = 7

# Ограничения бесплатной версии
FREE_DELAY = 300  # 5 минут между сообщениями
FREE_DAILY_LIMIT = 20

# Триал
TRIAL_DAYS = 7
