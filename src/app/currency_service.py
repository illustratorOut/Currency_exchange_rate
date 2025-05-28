import asyncio
import time
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
        self._last_error = None
        self._initial_rates_loaded = False

    def _safe_divide(self, a: float, b: float) -> float:
        """Безопасное деление на ноль"""
        try:
            return round(a / b, 1) if b != 0 else 0.0
        except Exception as e:
            logger.warning(f"Ошибка деления {a}/{b}: {str(e)}")
            return 0.0

    async def get_exchange_rates(self) -> Dict[str, float]:
        try:
            if self._last_error and time.time() - self._last_error[0] < 60:
                return {}

            response = await self.client.get(settings.api_url)
            data = response.json()

            rates = {"RUB": 1.0}

            for currency in settings.supported_currencies:
                if currency != "RUB":
                    if currency in data["Valute"]:
                        rates[currency] = data["Valute"][currency]["Value"]
                    else:
                        logger.warning(f"Курс для валюты {currency} не найден в API, используется 0")
                        rates[currency] = 0.0

            return rates
        except Exception as e:
            if str(e) != getattr(self._last_error, '1', ''):
                logger.error(f"Не удалось получить курсы обмена валют: {e}")
                self._last_error = (time.time(), str(e))
            return {curr: 0.0 for curr in settings.supported_currencies}

    async def update_balances(self, silent: bool = False):
        new_rates = await self.get_exchange_rates()
        if new_rates:
            self.exchange_rates = new_rates
            for currency in self.balances.values():
                currency.update_rate(self.exchange_rates)
            if not silent:
                logger.log_currency_update(new_rates)

    async def set_amounts(self, amounts: dict):
        """Устанавливает суммы валют с проверкой на инициализацию валюты"""
        logger.debug(f"Попытка установки балансов: {amounts}")

        if not amounts:
            logger.warning("Получен пустой запрос на установку балансов")
            raise ValueError("Не указаны суммы для установки")

        invalid_currencies = []

        for currency, amount in amounts.items():
            currency = currency.upper()

            if currency not in settings.supported_currencies:
                invalid_currencies.append(currency)
                continue

            if amount < 0:
                logger.warning(
                    f"Попытка установки отрицательного баланса для {currency}. "
                    f"Запрошенное значение: {amount}"
                )
                raise ValueError(f"Баланс для {currency} не может быть отрицательным")

            self.balances[currency].amount = amount
            logger.debug(f"Баланс {currency} успешно установлен на {amount}")

        if invalid_currencies:
            raise ValueError(f"Неподдерживаемые валюты: {', '.join(invalid_currencies)}")

    async def modify_amounts(self, amounts: dict):
        """Изменяет суммы валют с проверкой на отрицательный баланс"""
        invalid_currencies = []
        errors = []

        for currency, delta in amounts.items():
            currency = currency.upper()

            if currency not in settings.supported_currencies:
                invalid_currencies.append(currency)
                continue

            new_balance = self.balances[currency].amount + delta
            if new_balance < 0:
                errors.append(
                    f"Баланс для {currency} не может быть отрицательным. "
                    f"Текущий баланс: {self.balances[currency].amount}, "
                    f"попытка изменить на: {delta}"
                )
                continue

            self.balances[currency].amount = new_balance

        if invalid_currencies:
            errors.append(f"Неподдерживаемые валюты: {', '.join(invalid_currencies)}")

        if errors:
            raise ValueError("\n".join(errors))

    async def get_total_amounts(self) -> dict:
        """Возвращает текущие балансы с проверкой на валидность"""
        try:
            if not self._initial_rates_loaded:
                await self.update_balances(silent=True)
                self._initial_rates_loaded = True

            rates = {}
            currencies = settings.supported_currencies
            base_currency = "RUB"

            base_rates = {curr: self.exchange_rates.get(curr, 1.0)
                          for curr in currencies if curr != base_currency}
            base_rates[base_currency] = 1.0

            for i, currency_from in enumerate(currencies):
                for currency_to in currencies[i + 1:]:
                    if currency_from == base_currency:
                        rate = base_rates[currency_to]
                    elif currency_to == base_currency:
                        rate = self._safe_divide(1, base_rates[currency_from])
                    else:
                        rate = self._safe_divide(base_rates[currency_to], base_rates[currency_from])

                    rates[f"{currency_from.lower()}_{currency_to.lower()}"] = rate

            return {
                "currencies": {curr: self.balances[curr].amount for curr in currencies},
                "rates": rates,
                "totals": self._calculate_totals()
            }
        except Exception as e:
            logger.error(f"Ошибка при получении балансов: {str(e)}")
            raise

    def _calculate_totals(self) -> dict:
        """Вычисляет общие суммы с проверкой на отрицательные балансы"""
        base_currency = "RUB"

        for currency, balance in self.balances.items():
            if balance.amount < 0:
                logger.error(f"Обнаружен отрицательный баланс для {currency}: {balance.amount}")
                raise ValueError(f"Обнаружен отрицательный баланс для {currency}")

        totals = {}
        known_rates = set(self.exchange_rates.keys()) | {base_currency}

        for target_currency in settings.supported_currencies:
            if target_currency not in known_rates:
                logger.warning(f"Невозможно рассчитать сумму для {target_currency} - неизвестен курс")
                totals[target_currency] = None
                continue

            total = 0.0
            for currency, balance in self.balances.items():
                if currency == target_currency:
                    total += balance.amount
                else:
                    if currency == base_currency:
                        rate = self._safe_divide(1, self.exchange_rates.get(target_currency, 0.0))
                    elif target_currency == base_currency:
                        rate = self.exchange_rates.get(currency, 0.0)
                    else:
                        rate_to_base = self.exchange_rates.get(currency, 0.0)
                        rate_from_base = self._safe_divide(1, self.exchange_rates.get(target_currency, 0.0))
                        rate = rate_to_base * rate_from_base

                    total += balance.amount * rate
            totals[target_currency] = round(total, 2)
        return totals

    async def start(self):
        self.exchange_rates = await self.get_exchange_rates()
        if not any(v > 0 for v in self.exchange_rates.values()):
            raise RuntimeError("Не удалось загрузить начальные курсы валют")
        self._initial_rates_loaded = True
        self._update_task = asyncio.create_task(self._periodic_update())

    async def get_formatted_amounts(self) -> str:
        """Возвращает данные в текстовом формате для API"""
        data = await self.get_total_amounts()
        lines = []

        lines.append("\n".join(f"{curr.lower()}: {amount}" for curr, amount in data['currencies'].items()))
        lines.append("\n".join(f"{rate.replace('_', '-')}: {value}" for rate, value in data['rates'].items()))
        sums = " / ".join(f"{total:.2f} {curr.lower()}" for curr, total in data['totals'].items())

        lines.append(f"\nsum: {sums}")
        return "\n".join(lines)

    async def _periodic_update(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(settings.update_period * 60)
            await self.update_balances()

    async def stop(self):
        self._stop_event.set()
        await self.client.aclose()
