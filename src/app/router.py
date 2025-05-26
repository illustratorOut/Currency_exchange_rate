from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from src.app.schemas import CurrencyResponse, ModifyRequest, SetAmountRequest
from src.app.currency_service import CurrencyService
from src.base.logger import logger
from src.config.config import settings

service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    service = CurrencyService()
    await service.start()
    yield
    await service.stop()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Регистрируем каждый запрос и ответ"""
    response = await call_next(request)
    logger.log_http_request(request, response)
    return response


@app.on_event("startup")
async def startup():
    await service.start()


@app.on_event("shutdown")
async def shutdown():
    await service.stop()


@app.get("/amount/get")
async def get_amount():
    """Получает общую сумму баланса"""
    try:
        if settings.debug:
            data = await service.get_total_amounts()
            logger.debug(f"Returning JSON data: {data}")
            return data
        else:
            text_data = await service.get_formatted_amounts()
            logger.info(f"Returning text data:\n{text_data}")
            return PlainTextResponse(content=text_data, media_type="text/plain")
    except Exception as e:
        logger.error(f"Error in /amount/get: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/{currency}/get", response_model=CurrencyResponse)
async def get_currency(currency: str):
    """Позволяет получать детали конкретной валюты"""
    currency = currency.upper()
    if currency not in settings.supported_currencies:
        raise HTTPException(status_code=404, detail="Валюта не поддерживается")
    return {"name": currency, "value": service.balances[currency].amount}


@app.post("/amount/set")
async def set_amount(request: SetAmountRequest):
    """ Устанавливает новые суммы валют"""
    amounts = request.model_dump(exclude_unset=True)
    await service.set_amounts(amounts)
    return {"status": "success"}


@app.post("/modify")
async def modify_amount(request: ModifyRequest):
    """Позволяет изменять существующие остатки валют путем добавления или вычитания указанных величин"""
    amounts = request.model_dump(exclude_unset=True)
    await service.modify_amounts(amounts)
    return {"status": "success"}
