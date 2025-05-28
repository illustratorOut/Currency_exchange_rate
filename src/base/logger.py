import logging

from typing import Optional, Dict, Union
from fastapi import Request, Response
from httpx import Request as HttpxRequest, Response as HttpxResponse

from src.config.config import settings


class AppLogger:
    def __init__(self):
        self.logger = logging.getLogger("currency_service")
        self._configure_logger()
        self._last_currency_data = None

    def _configure_logger(self) -> None:
        """Настройка логгера только с консольным выводом"""
        self.logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
        self.logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def log_http_request(self, request: Union[Request, HttpxRequest],
                         response: Optional[Union[Response, HttpxResponse]] = None) -> None:
        """Логирование HTTP запросов/ответов (только в debug-режиме)"""
        if not settings.debug:
            return

        try:
            log_msg = f"{request.method} {request.url.path}"
            if request.query_params:
                log_msg += f"?{request.query_params}"

            self.debug(log_msg)

            if response:
                self.debug(f"Response {response.status_code}")
                if response.status_code >= 400:
                    self.debug(f"Error response: {response.body}")
        except Exception as e:
            self.error(f"HTTP log error: {e}")

    def log_currency_data(self, data: Dict) -> None:
        if not data:
            self.warning("Получены пустые данные о валюте")
            return

        try:
            if not all(key in data for key in ['currencies', 'rates', 'totals']):
                raise ValueError("Недопустимая структура данных")

            output = [
                "Текущие балансы:",
                *[f"{k.lower()}: {v}" for k, v in data['currencies'].items()],
                "\nКурсы обмена:",
                *[f"{rate.replace('_', '-'):<10}: {value}" for rate, value in data['rates'].items()],
                "\nОбщие суммы:",
                f"sum: {' / '.join(f'{v:.2f} {k.lower()}' for k, v in data['totals'].items())}"
            ]

            self.info("\n".join(output))
        except Exception as e:
            self.error(f"Ошибка при регистрации валютных данных: {str(e)}")
            raise

    def log_currency_update(rates):
        if not rates:
            logger.warning("Нет данных о курсах валют")
            return

        rates_str = "\n".join(
            f"{pair}: {rate if rate != 0 else 'N/A'}"
            for pair, rate in sorted(rates.items())
        )

        logger.info(f"Обновленные курсы:\n{rates_str}")

    def debug(self, msg: str, *args, **kwargs) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        self.logger.exception(msg, *args, **kwargs)


logger = AppLogger()
