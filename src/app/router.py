from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.responses import PlainTextResponse

from src.app.schemas import CurrencyResponse, ModifyRequest, SetAmountRequest
from src.app.currency_service import CurrencyService
from src.base.logger import logger
from src.config.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекст жизненного цикла приложения с внедрением зависимости сервиса"""
    service = CurrencyService()
    await service.start()
    yield {"service": service}
    await service.stop()


app = FastAPI(lifespan=lifespan)


async def get_currency_service(request: Request) -> CurrencyService:
    """Зависимость для получения сервиса работы с валютами"""
    return request.state.service


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование всех входящих запросов и ответов"""
    response = await call_next(request)
    logger.log_http_request(request, response)
    return response


@app.get("/amount/get", response_model=None)
async def get_amount(
        service: CurrencyService = Depends(get_currency_service),
) -> Dict[str, Any] | PlainTextResponse:
    """Получение общего баланса по всем валютам"""
    try:
        if settings.debug:
            data = await service.get_total_amounts()
            logger.debug(f"Возвращаемые JSON данные: {data}")
            return data
        text_data = await service.get_formatted_amounts()
        logger.info(f"Возвращаемые текстовые данные:\n{text_data}")
        return PlainTextResponse(content=text_data, media_type="text/plain")
    except Exception as e:
        logger.error(f"Ошибка в /amount/get: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.get("/{currency}/get", response_model=CurrencyResponse)
async def get_currency(
        currency: str,
        service: CurrencyService = Depends(get_currency_service),
) -> Dict[str, str | float]:
    """Получение информации по конкретной валюте"""
    currency = currency.upper()
    if currency not in settings.supported_currencies:
        raise HTTPException(status_code=404, detail="Валюта не поддерживается")
    return {"name": currency, "value": service.balances[currency].amount}


@app.post("/modify")
async def modify_amount(
        request_data: Dict[str, Any] = Body(...),
        service: CurrencyService = Depends(get_currency_service),
) -> Dict[str, str]:
    """Изменение текущих балансов валют"""
    try:
        validated = ModifyRequest(**request_data)
        amounts = validated.model_dump(exclude_unset=True)

        valid_currencies = {}
        invalid_currencies = []

        for k, v in amounts.items():
            currency_upper = k.upper()
            if currency_upper in settings.supported_currencies:
                valid_currencies[currency_upper] = v
            else:
                invalid_currencies.append(k)

        if not valid_currencies:
            raise HTTPException(
                status_code=400,
                detail="Не указаны суммы для изменения или все валюты не поддерживаются"
            )

        logger.info(f"Запрос на изменение балансов: {valid_currencies}")
        await service.modify_amounts(valid_currencies)

        if invalid_currencies:
            return {
                "status": "success",
                "message": "Балансы успешно обновлены",
                "warning": f"Следующие валюты не поддерживаются: {', '.join(invalid_currencies)}"
            }

        return {"status": "success", "message": "Балансы успешно обновлены"}

    except ValueError as e:
        logger.warning(f"Ошибка изменения баланса: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при изменении баланса: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.post("/amount/set")
async def set_amount(
        request_data: Dict[str, Any] = Body(...),
        service: CurrencyService = Depends(get_currency_service),
) -> Dict[str, str]:
    """Установка новых значений балансов валют"""
    try:
        validated = SetAmountRequest(**request_data)
        amounts = validated.model_dump(exclude_unset=True)

        valid_currencies = {}
        invalid_currencies = []

        for k, v in amounts.items():
            currency_upper = k.upper()
            if currency_upper in settings.supported_currencies:
                valid_currencies[currency_upper] = v
            else:
                invalid_currencies.append(k)

        if not valid_currencies:
            raise HTTPException(
                status_code=400,
                detail="Не указаны суммы для установки или все валюты не поддерживаются"
            )

        logger.info(f"Запрос на установку балансов: {valid_currencies}")
        await service.set_amounts(valid_currencies)

        if invalid_currencies:
            return {
                "status": "success",
                "warning": f"Следующие валюты не поддерживаются: {', '.join(invalid_currencies)}"
            }

        return {"status": "success"}

    except ValueError as e:
        logger.warning(f"Ошибка установки баланса: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при установке баланса: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
