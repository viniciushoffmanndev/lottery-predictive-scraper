"""
Orquestrador de Prontidão (Readiness Pipeline).
Arquitetura Plug-and-Play orientada a Protocolos para microsserviços.
"""

import logging
import asyncio
from typing import Protocol, Sequence, Any
from sqlalchemy import text, Select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_session_factory
from exceptions import DatabaseInitializationError, MissingReferenceDataError, MissingReference

logger = logging.getLogger(__name__)

# ==============================================================================
# 🧩 REGISTRY PATTERN (Inversão de Dependência)
# ==============================================================================
_REFERENCE_REGISTRY: list[tuple[str, Select[Any]]] = []

def register_reference_check(name: str, stmt: Select[Any]) -> None:
    """Permite que os domínios (models) registrem seus próprios checks, isolando a infra."""
    _REFERENCE_REGISTRY.append((name, stmt))

# ==============================================================================
# 🔄 STARTUP PIPELINE (Protocolo de Plataforma)
# ==============================================================================
class StartupStep(Protocol):
    async def run(self) -> None:
        """Executa a rotina de validação e aquecimento do componente."""
        ...

class DatabaseStartupStep:
    """Etapa de inicialização exclusiva do ecossistema PostgreSQL."""
    
    async def _check_connection(self, session: AsyncSession) -> None:
        """Validação crua de L4/L7 (Readiness Probe Kubernetes-friendly)."""
        async with asyncio.timeout(5.0):
            await session.execute(text("SELECT 1"))

    async def _collect_telemetry(self, session: AsyncSession) -> None:
        """Coleta de metadados focada em Logging Estruturado (JSON/Extra)."""
        res = await session.execute(text("SELECT current_database(), current_setting('server_version');"))
        db_name, version = res.fetchone()  # type: ignore
        engine = session.bind
        
        logger.info(
            "database_readiness_success",
            extra={
                "db_name": db_name,
                "db_version": version,
                "driver": f"{engine.dialect.name}+{engine.dialect.driver}",
                "pool_size": settings.db.pool_size,
                "app_name": settings.db.application_name
            }
        )

    async def _validate_references(self, session: AsyncSession) -> None:
        """Valida dinamicamente os domínios registrados no Registry."""
        missing = []
        for name, stmt in _REFERENCE_REGISTRY:
            async with asyncio.timeout(5.0):
                exists = await session.scalar(stmt)
                
            if exists is None:
                missing.append(MissingReference(name=name, expected=1, found=0))
                
        if missing:
            raise MissingReferenceDataError(missing)

    async def run(self) -> None:
        factory = get_session_factory()
        try:
            async with factory() as session:
                await self._check_connection(session)
                await self._collect_telemetry(session)
                await self._validate_references(session)
        except TimeoutError as err:
            logger.exception("Timeout esgotado ao tentar estabelecer conexão física (DNS/Rede).")
            raise DatabaseInitializationError("Timeout na comunicação com o PostgreSQL.") from err
        except SQLAlchemyError as err:
            logger.exception("Falha física no handshake de conectividade.")
            raise DatabaseInitializationError("Falha de autenticação/conexão com a base.") from err

# ==============================================================================
# 🚂 ORQUESTRADOR CENTRAL
# ==============================================================================
async def run_startup_pipeline(steps: Sequence[StartupStep]) -> None:
    """Motor de execução sequencial de dependências da aplicação."""
    logger.info("Iniciando pipeline de prontidão da plataforma...")
    for step in steps:
        await step.run()
    logger.info("Todos os componentes foram validados com sucesso.")