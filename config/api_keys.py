from typing import Optional
import os

try:
    from pydantic_settings import BaseSettings

    class AlpacaCredentials(BaseSettings):
        api_key: str = ""
        secret_key: str = ""
        base_url: str = "https://paper-api.alpaca.markets"
        data_url: str = "https://data.alpaca.markets"

        class Config:
            env_prefix = "ALPACA_"
            env_file = ".env"

except ImportError:
    class AlpacaCredentials:
        def __init__(self):
            self.api_key = os.getenv("ALPACA_API_KEY", "")
            self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
            self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
            self.data_url = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

class APICredentials:
    def __init__(self):
        self.alpaca: Optional[AlpacaCredentials] = None

    def load_alpaca_credentials(self) -> AlpacaCredentials:
        if self.alpaca is None:
            self.alpaca = AlpacaCredentials()
        return self.alpaca

    def validate_credentials(self) -> bool:
        try:
            creds = self.load_alpaca_credentials()
            return bool(creds.api_key and creds.secret_key)
        except Exception:
            return False

credentials = APICredentials()
