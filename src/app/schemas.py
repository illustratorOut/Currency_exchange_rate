from pydantic import BaseModel, Field
from typing import Optional


class CurrencyResponse(BaseModel):
    name: str
    value: float


class ModifyRequest(BaseModel):
    rub: Optional[float] = None
    usd: Optional[float] = None
    eur: Optional[float] = None


class SetAmountRequest(BaseModel):
    rub: Optional[float] = None
    usd: Optional[float] = None
    eur: Optional[float] = None


class ExchangeRatesResponse(BaseModel):
    rub_usd: float
    rub_eur: float
    usd_eur: float


class ErrorResponse(BaseModel):
    detail: str = Field(examples=["Валюта не поддерживается!!!!"])
