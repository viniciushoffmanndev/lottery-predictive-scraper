"""
Infraestrutura de acesso ao PostgreSQL.

Responsabilidades:
- Engine configuration (AsyncEngine otimizado para NeonDB)
- Session Factory (async_sessionmaker)
- Dependency Injection Provider (get_session)
- Startup readiness validation (Health check & Reference data validation)
- Shutdown handling (Pool disposal)

Não executa migrations.
Não cria schema.
Não popula dados.

Todas as alterações estruturais e dados de sementes são de responsabilidade exclusiva do Alembic.
"""

import os
import logging
from typing import AsyncGenerator, Sequence, Tuple, Final  # ✅ CORRIGIDO: Final adicionado aos imports
from sqlalchemy import select, text                     
from sqlalchemy.sql import Select                       
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Loteria, TipoResultado, TipoPredicao, BichoGrupoDezena

# ==============================================================================
# 🛰️ 1. OBSERVABILIDADE E EXCEÇÕES DE DOMÍNIO CUSTOMIZADAS
# ==============================================================================
logger = logging.getLogger(__name__)

class DatabaseInitializationError(RuntimeError):
    """Lançada quando ocorre uma falha catastrófica na inicialização/handshake do banco."""
    pass


class MissingReferenceDataError(RuntimeError):
    """Lançada quando dados essenciais de semente/referência não são localizados."""
    pass

# ==============================================================================
# 🚨 2. CONFIGURAÇÕES GLOBAIS, CONSTANTES E MOTOR ASYNC (POOLING ENTERPRISE)
# ==============================================================================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("A variável de ambiente DATABASE_URL não foi encontrada no ambiente de execução.")

# Constante estática fora das funções para evitar recriação na memória.
REFERENCE_CHECKS: Final[Sequence[Tuple[str, Select]]] = (
    ("Loterias", select(Loteria.id).limit(1)),
    ("Tipos de Resultado", select(TipoResultado.id).limit(1)),
    ("Tipos de Predição", select(TipoPredicao.id).limit(1)),
    ("Bichos/Grupos de Domínio", select(BichoGrupoDezena.grupo).limit(1)),
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,          
    max_overflow=10,       
    pool_timeout=30,       
    pool_recycle=1800,     
    pool_pre_ping=True,    
    pool_use_lifo=True,    
    connect_args={
        "command_timeout": 45  
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# ==============================================================================
# 💉 3. PROVEDOR DE SESSÃO (FASTAPI DEPENDENCY INJECTION / CONTEXT MANAGER)
# ==============================================================================

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provedor assíncrono de contexto de sessão (Dependency Injection).
    Garante o isolamento transacional e o descarte correto da conexão após o uso.
    """
    async with AsyncSessionLocal() as session:
        yield session

# ==============================================================================
# 🛡️ 4. GUARDIÕES DE PRONTIDÃO (VALIDAÇÃO DE INFRAESTRUTURA E DADOS DE SEED)
# ==============================================================================

async def health_check() -> None:
    """
    Executa um handshake de baixo nível ignorando o compilador do ORM (text SQL)
    para atestar a vivacidade da comunicação física com o cluster PostgreSQL.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Falha crítica no handshake de conectividade com o banco de dados.")
        raise DatabaseInitializationError("Não foi possível estabelecer conexão física com a base de dados.")


async def validate_reference_data() -> None:  
    """
    Varre os dados de referência estáticos e de domínio usando estratégias de varredura
    de custo mínimo (scalar LIMIT 1). Garante que o ecossistema foi provisionado via Alembic[cite: 3].
    """
    async with AsyncSessionLocal() as session:
        try:
            for name, stmt in REFERENCE_CHECKS:
                exists = await session.scalar(stmt)
                if exists is None:
                    raise MissingReferenceDataError(
                        f"A tabela de referência/domínio '{name}' está vazia! "
                        "Certifique-se de aplicar as migrações e cargas do Alembic antes de inicializar o app[cite: 3]."
                    )
        except SQLAlchemyError:
            logger.exception("Erro de persistência ao validar integridade estrutural dos dados de semente[cite: 3].")
            raise


async def init_db() -> None:
    """
    Orquestrador assíncrono de inicialização e prontidão da camada de dados.
    Separa a checagem de infraestrutura física da validação lógica dos dados[cite: 3].
    """
    logger.info("Iniciando validação de prontidão da infraestrutura de dados...")
    await health_check()
    await validate_reference_data()
    logger.info("Infraestrutura de dados validada e pronta para operação[cite: 3].")


async def close_db() -> None:
    """
    Desaloca os recursos e encerra de forma limpa o pool de conexões do Engine assíncrono[cite: 3].
    Protege o encerramento do processo contra exceções latentes de rede no fechamento de sockets.
    """
    logger.info("Iniciando encerramento controlado e descarte do pool de conexões com o banco de dados...[cite: 3]")
    try:
        await engine.dispose()
    except Exception:
        logger.exception("Erro inesperado ocorrido durante a desalocação do pool de conexões assíncronas[cite: 3].")
        raise