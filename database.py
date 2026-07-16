import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base

# Carrega as variáveis do arquivo .env para a memória
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi encontrada no arquivo .env.")

# Criação do engine assíncrono
engine = create_async_engine(DATABASE_URL, echo=False)

# Fábrica de sessões assíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Verifica e cria as tabelas no banco de dados NeonDB apenas se elas não existirem."""
    print("Verificando a estrutura do banco de dados no NeonDB...")
    async with engine.begin() as conn:
        # Apenas cria as tabelas que estão faltando. NUNCA apaga dados existentes!
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados sincronizado com segurança!")