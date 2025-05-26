from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, List


class Settings(BaseSettings):
    initial_balances: Dict[str, float] = Field(default={"RUB": 0, "USD": 0, "EUR": 0})
    update_period: int = Field(default=10)
    debug: bool = Field(default=False)
    supported_currencies: List[str] = Field(default=["RUB", "USD", "EUR"])
    api_url: str = Field(default="https://www.cbr-xml-daily.ru/daily_json.js")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()
