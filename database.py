import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base

# Carrega as variáveis do arquivo .env para a memória
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi encontrada no arquivo .env.")

# Criação do engine assíncrono (echo=False para não poluir o terminal com SQL, mude para True se quiser debugar)
engine = create_async_engine(DATABASE_URL, echo=False)

# Fábrica de sessões assíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Cria as tabelas no banco de dados NeonDB."""
    print("Sincronizando tabelas com o NeonDB...")
    async with engine.begin() as conn:
        # ATENÇÃO: Apaga a tabela atual para recriá-la com a nova regra de unicidade
        await conn.run_sync(Base.metadata.drop_all) 
        
        # Cria a tabela novamente
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados formatado e pronto!")