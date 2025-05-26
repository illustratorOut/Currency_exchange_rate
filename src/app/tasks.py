import asyncio

from src.base.logger import logger


async def periodic_amount_log(service):
    last_data = None
    while True:
        await asyncio.sleep(60)
        current_data = await service.get_total_amounts()

        if last_data is None or current_data != last_data:
            logger.log_currency_data(current_data)
            last_data = current_data


def start_periodic_tasks(service):
    return asyncio.create_task(periodic_amount_log(service))
