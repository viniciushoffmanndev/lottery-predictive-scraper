import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings
from db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

async def init_models():
    engine = create_async_engine(settings.db.url, echo=True)
    logger.info("🛠️  Iniciando reconstrução do esquema do banco de dados...")
    
    async with engine.begin() as conn:
        logger.info("Sincronizando novas tabelas no banco da nuvem...")
        # create_all verifica o que não existe e cria, sem apagar o que já tem!
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("✅ Esquema criado e atualizado com sucesso!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_models())