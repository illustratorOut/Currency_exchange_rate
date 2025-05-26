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
    parser.add_argument("--rub", type=float, default=0, help="Начальная сумма в RUB")
    parser.add_argument("--usd", type=float, default=0, help="Начальная сумма в USD")
    parser.add_argument("--eur", type=float, default=0, help="Начальная сумма в EUR")
    parser.add_argument("--period", type=int, default=10, help="Период обновления в минутах")
    parser.add_argument(
        "--debug",
        type=str,
        choices=["0", "1", "true", "false", "True", "False", "y", "n", "Y", "N"],
        default="false",
        help="Режим отладки"
    )
    return parser.parse_args()


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
    args = parse_args()
    debug = args.debug.lower() in ('1', 'true', 'y', 'yes', 'True')

    app_settings.initial_balances = {"RUB": args.rub, "USD": args.usd, "EUR": args.eur}
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
