from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseModel):
    """Configurações exclusivas do domínio de persistência (Apenas Modelo)."""
    url: str = Field(alias="DATABASE_URL")
    
    # Tuning de Infraestrutura
    pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
    
    # Resiliência e Comportamento
    pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")
    pool_use_lifo: bool = Field(default=True, alias="DB_POOL_USE_LIFO")
    command_timeout: int = Field(default=45, alias="DB_COMMAND_TIMEOUT")
    echo: bool = Field(default=False, alias="DB_ECHO")
    
    # Observabilidade de SGBD
    application_name: str = Field(default="lottery_scraper_worker", alias="APP_NAME")

class ScraperSettings(BaseModel):
    """Configurações exclusivas do domínio de ingestão HTTP."""
    base_url: str = Field(default="https://resultadonacional.com", alias="SCRAPER_BASE_URL")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        alias="SCRAPER_USER_AGENT"
    )
    
    # Resiliência (Circuit Breaking & Backoff)
    max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")
    
    # Timeouts Granulares
    timeout_connect: float = Field(default=5.0, alias="SCRAPER_TIMEOUT_CONNECT")
    timeout_read: float = Field(default=20.0, alias="SCRAPER_TIMEOUT_READ")
    timeout_write: float = Field(default=10.0, alias="SCRAPER_TIMEOUT_WRITE")
    timeout_pool: float = Field(default=5.0, alias="SCRAPER_TIMEOUT_POOL")

class Settings(BaseSettings):
    """
    Objeto raiz de configuração. 
    O único ponto do sistema que interage com o ambiente e o arquivo .env.
    """
    db: DatabaseSettings = DatabaseSettings()
    scraper: ScraperSettings = ScraperSettings()  # NOVO DOMÍNIO ADICIONADO
    
    # model_config dita o comportamento apenas para a injeção do objeto raiz
    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        env_nested_delimiter="__"  # Permite injeção de nested models (ex: DB__URL)
    )

settings = Settings()