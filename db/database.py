"""
Infraestrutura de acesso ao PostgreSQL.

Responsabilidades:
- Engine configuration (Síncrono, Thread-Safe)
- Session Factory (async_sessionmaker)
- Dependency Injection Provider (get_session)
- Shutdown handling (Pool disposal)
"""

import logging
import threading
from typing import AsyncGenerator, Optional, TypeAlias
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings

logger = logging.getLogger(__name__)

class DatabaseInitializationError(RuntimeError):
    """Lançada quando ocorre uma falha catastrófica na inicialização/handshake do banco[cite: 6]."""
    pass

# ==============================================================================
# 🚨 1. ALIASES E ESTADO GLOBAL
# ==============================================================================
AsyncEngineSingleton: TypeAlias = Optional[AsyncEngine]
AsyncSessionFactory: TypeAlias = Optional[async_sessionmaker[AsyncSession]]

_engine: AsyncEngineSingleton = None
_session_factory: AsyncSessionFactory = None
_engine_lock = threading.Lock()
_factory_lock = threading.Lock()

# ==============================================================================
# 🚀 2. MOTOR ASYNC E FÁBRICA DE SESSÕES (SÍNCRONOS & THREAD-SAFE)
# ==============================================================================

def get_engine() -> AsyncEngine:
    """Retorna o AsyncEngine Singleton. Inicialização síncrona sob Lock simples[cite: 6]."""
    global _engine
    
    with _engine_lock:
        if _engine is None:  # Check simples, sem Double-Checked herdado do Java[cite: 6]
            safe_url = make_url(settings.db.url).render_as_string(hide_password=True)
            
            logger.info(
                f"🔌 Inicializando DB Engine [{safe_url}] | Pool: {settings.db.pool_size} "
                f"| Overflow: {settings.db.max_overflow} | Timeout: {settings.db.pool_timeout}s"
            )
            
            connect_args = {
                "command_timeout": settings.db.command_timeout,
                "server_settings": {"application_name": settings.db.application_name}
            }
            
            _engine = create_async_engine(
                settings.db.url,
                echo=settings.db.echo,
                pool_size=settings.db.pool_size,          
                max_overflow=settings.db.max_overflow,       
                pool_timeout=settings.db.pool_timeout,       
                pool_recycle=settings.db.pool_recycle,     
                pool_pre_ping=settings.db.pool_pre_ping,    
                pool_use_lifo=settings.db.pool_use_lifo,    
                connect_args=connect_args
            )
    return _engine

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retorna a fábrica de sessões Singleton."""
    global _session_factory
    
    with _factory_lock:
        if _session_factory is None:
            _session_factory = async_sessionmaker(
                bind=get_engine(),
                class_=AsyncSession,
                expire_on_commit=False
            )
    return _session_factory

# ==============================================================================
# 💉 3. PROVEDOR DE SESSÃO (DEPENDENCY INJECTION)
# ==============================================================================

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provedor assíncrono de contexto de sessão com controle de ciclo de vida explícito[cite: 6]."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        await session.close()

# ==============================================================================
# 🛑 4. DESALOCAÇÃO DE RECURSOS
# ==============================================================================

async def close_db() -> None:
    """Desaloca recursos e destrói conexões ativas prevenindo state leaks[cite: 6]."""
    global _engine, _session_factory
    
    if _engine is not None:
        logger.info("Iniciando encerramento controlado e descarte do pool de conexões...")
        try:
            await _engine.dispose()
            _engine = None            
            _session_factory = None   
            logger.info("Pool de conexões do PostgreSQL encerrado com sucesso.")
            logger.debug("Singleton limpo.")  # Rastreio de liberação de memória em nível de Debug[cite: 6]
        except (SQLAlchemyError, OSError) as err:
            logger.exception("Erro ocorrido durante a desalocação do pool de conexões assíncronas.")
            raise DatabaseInitializationError("Falha ao encerrar os recursos do banco de dados.") from err