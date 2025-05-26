import asyncio
import httpx

from abc import ABC, abstractmethod
from typing import Dict

from src.base.logger import logger
from src.config.config import settings
from src.app.models import CurrencyBalance


class BaseCurrencyService(ABC):
    @abstractmethod
    async def get_exchange_rates(self) -> Dict[str, float]:
        pass

    @abstractmethod
    async def update_balances(self):
        pass


class CurrencyService(BaseCurrencyService):
    def __init__(self):
        self.balances = {
            currency: CurrencyBalance(amount=settings.initial_balances.get(currency, 0))
            for currency in settings.supported_currencies
        }
        self.exchange_rates = {}
        self.client = httpx.AsyncClient()
        self._stop_event = asyncio.Event()
        self._update_task = None

    async def get_exchange_rates(self) -> Dict[str, float]:
        try:
            response = await self.client.get(settings.api_url)
            data = response.json()
            rates = {"USD": data["Valute"]["USD"]["Value"], "EUR": data["Valute"]["EUR"]["Value"]}
            rates["RUB"] = 1.0
            return rates
        except Exception as e:
            logger.error(f"Не удалось получить курсы обмена валют: {e}")
            return {}

    async def update_balances(self, silent: bool = False):
        new_rates = await self.get_exchange_rates()
        if new_rates:
            self.exchange_rates = new_rates
            for currency in self.balances.values():
                currency.update_rate(self.exchange_rates)
            if not silent:
                logger.log_currency_update(new_rates)

    async def set_amounts(self, amounts: dict):
        for currency, amount in amounts.items():
            if currency.upper() in self.balances:
                self.balances[currency.upper()].amount = amount

    async def modify_amounts(self, amounts: dict):
        for currency, delta in amounts.items():
            if currency.upper() in self.balances:
                self.balances[currency.upper()].amount += delta

    async def get_total_amounts(self) -> dict:
        if not self.exchange_rates:
            await self.update_balances(silent=True)

        for currency in settings.supported_currencies:
            if currency not in self.balances:
                raise ValueError(f"Currency {currency} not initialized")

        return {
            "currencies": {curr: self.balances[curr].amount for curr in settings.supported_currencies},
            "rates": {
                "rub_usd": self.exchange_rates["USD"],
                "rub_eur": self.exchange_rates["EUR"],
                "usd_eur": self.exchange_rates["EUR"] / self.exchange_rates["USD"]
            },
            "totals": self._calculate_totals()
        }

    async def get_formatted_amounts(self) -> str:
        """Возвращает данные в текстовом формате для API"""
        data = await self.get_total_amounts()
        lines = []

        lines.append("\n".join(f"{curr.lower()}: {amount}" for curr, amount in data['currencies'].items()))
        lines.append("\n".join(f"{rate.replace('_', '-')}: {value}" for rate, value in data['rates'].items()))
        sums = " / ".join(f"{total:.2f} {curr.lower()}" for curr, total in data['totals'].items())

        lines.append(f"\nsum: {sums}")
        return "\n".join(lines)

    def _calculate_totals(self) -> dict:
        rub_amount = self.balances["RUB"].amount
        usd_amount = self.balances["USD"].amount
        eur_amount = self.balances["EUR"].amount

        rub_total = rub_amount + usd_amount * self.exchange_rates["USD"] + eur_amount * self.exchange_rates["EUR"]
        usd_total = rub_amount / self.exchange_rates["USD"] + usd_amount + eur_amount * (
                self.exchange_rates["EUR"] / self.exchange_rates["USD"])
        eur_total = rub_amount / self.exchange_rates["EUR"] + usd_amount / (
                self.exchange_rates["EUR"] / self.exchange_rates["USD"]) + eur_amount

        return {"RUB": rub_total, "USD": usd_total, "EUR": eur_total}

    async def start(self):
        self._update_task = asyncio.create_task(self._periodic_update())

    async def _periodic_update(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(settings.update_period * 60)
            await self.update_balances()

    async def stop(self):
        self._stop_event.set()
        await self.client.aclose()
