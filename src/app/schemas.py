from pydantic import BaseModel, field_validator, ConfigDict
from typing import Any


class CurrencyResponse(BaseModel):
    name: str
    value: float


class CurrencyOperationBase(BaseModel):
    model_config = ConfigDict(extra='allow')

    @field_validator('*', mode='before')
    @classmethod
    def validate_currency_values(cls, v: Any, info):
        if not isinstance(v, (int, float)):
            raise ValueError(f"Некорректное значение для {info.field_name}")
        return float(v)


def create_currency_model():
    class DynamicCurrencyModel(CurrencyOperationBase):
        pass

    return DynamicCurrencyModel


ModifyRequest = create_currency_model()
SetAmountRequest = create_currency_model()
