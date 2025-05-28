import argparse
import asyncio
import uvicorn

from src.app.currency_service import CurrencyService
from src.app.router import app
from src.app.tasks import start_periodic_tasks
from src.base.logger import logger
from src.config.config import settings as app_settings


def parse_args():
    parser = argparse.ArgumentParser(description="Отслеживание валютных курсов")
    parser.add_argument("--period", type=int, default=10, help="Период обновления в минутах")
    parser.add_argument(
        "--debug",
        type=str,
        choices=["0", "1", "true", "false", "True", "False", "y", "n", "Y", "N"],
        default="false",
        help="Режим отладки"
    )

    for currency in app_settings.supported_currencies:
        parser.add_argument(
            f"--{currency.lower()}",
            type=float,
            nargs='?',
            const=0.0,
            default=None,
            help=f"Начальная сумма в {currency} (по умолчанию 0)"
        )

    args, unknown = parser.parse_known_args()

    extra_currencies = {}
    i = 0
    while i < len(unknown):
        if unknown[i].startswith('--'):
            currency_name = unknown[i][2:].upper()
            if i + 1 >= len(unknown) or unknown[i + 1].startswith('--'):
                extra_currencies[currency_name] = 0.0
                app_settings.supported_currencies.append(currency_name)
                i += 1
            else:
                try:
                    value = float(unknown[i + 1])
                    extra_currencies[currency_name] = value
                    app_settings.supported_currencies.append(currency_name)
                    i += 2
                except ValueError:
                    extra_currencies[currency_name] = 0.0
                    app_settings.supported_currencies.append(currency_name)
                    i += 1
        else:
            i += 1
    return args, extra_currencies


async def cleanup(periodic_task, currency_service):
    """Метод очистки ресурсов"""
    periodic_task.cancel()
    try:
        await periodic_task
    except asyncio.CancelledError:
        pass

    await currency_service.stop()
    logger.info("Работа успешно завершена.")


async def run_app():
    """Запуск приложения"""
    args, extra_currencies = parse_args()
    debug = args.debug.lower() in ('1', 'true', 'y', 'yes', 'True')

    initial_balances = {}

    for currency in app_settings.supported_currencies:
        arg_value = getattr(args, currency.lower(), None)
        if arg_value is not None:
            initial_balances[currency] = arg_value if arg_value is not None else 0.0

    initial_balances.update(extra_currencies)

    app_settings.initial_balances = initial_balances
    app_settings.update_period = args.period
    app_settings.debug = debug

    global currency_service
    currency_service = CurrencyService()
    await currency_service.start()

    periodic_task = start_periodic_tasks(currency_service)

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level=debug if debug else "info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        await cleanup(periodic_task, currency_service)


currency_service = None

if __name__ == "__main__":
    asyncio.run(run_app())
