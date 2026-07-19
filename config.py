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

class Settings(BaseSettings):
    """
    Objeto raiz de configuração. 
    O único ponto do sistema que interage com o ambiente e o arquivo .env.
    """
    db: DatabaseSettings = DatabaseSettings()
    
    # model_config dita o comportamento apenas para a injeção do objeto raiz
    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        env_nested_delimiter="__"  # Permite injeção de nested models (ex: DB__URL)
    )

settings = Settings()