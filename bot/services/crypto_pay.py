"""Сервис работы с CryptoPay API (@CryptoBot)."""

import aiohttp
from config import CRYPTO_PAY_TOKEN

BASE_URL = "https://pay.crypt.bot/api"

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
    "Content-Type": "application/json"
}


async def create_invoice(amount: float, description: str, payload: str = "") -> dict | None:
    """Создать инвойс для оплаты."""
    async with aiohttp.ClientSession() as session:
        data = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": str(amount),
            "description": description,
            "payload": payload,
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/bot"
        }
        try:
            async with session.post(f"{BASE_URL}/createInvoice", headers=HEADERS, json=data) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return result["result"]
                return None
        except Exception as e:
            print(f"CryptoPay error: {e}")
            return None


async def get_invoices(invoice_ids: str = None, status: str = None) -> list[dict]:
    """Получить список инвойсов."""
    async with aiohttp.ClientSession() as session:
        params = {}
        if invoice_ids:
            params["invoice_ids"] = invoice_ids
        if status:
            params["status"] = status
        try:
            async with session.get(f"{BASE_URL}/getInvoices", headers=HEADERS, params=params) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return result["result"].get("items", [])
                return []
        except Exception as e:
            print(f"CryptoPay error: {e}")
            return []


async def check_invoice(invoice_id: int) -> dict | None:
    """Проверить статус инвойса."""
    invoices = await get_invoices(invoice_ids=str(invoice_id))
    return invoices[0] if invoices else None
