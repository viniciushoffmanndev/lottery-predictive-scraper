import logging
import time
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session_factory

logger = logging.getLogger("maintenance.hotfix")

class BaseHotfix(ABC):
    """Interface padrão para scripts de intervenção de dados em produção."""
    version: str
    description: str

    @abstractmethod
    async def execute(self, session: AsyncSession, dry_run: bool) -> int:
        """Deve retornar a quantidade de linhas afetadas."""
        pass

# ==============================================================================
# 🗃️ REGISTRO DE HOTFIXES (Versionados)
# ==============================================================================
class Hotfix202607RankingNull(BaseHotfix):
    version = "2026_07_fix_ranking"
    description = "Corrige predições antigas que ficaram com ranking NULL."
    
    async def execute(self, session: AsyncSession, dry_run: bool) -> int:
        if dry_run:
            logger.info(f"[DRY-RUN] Simulação: {self.description}")
            return 0
            
        # Lógica de correção DML aqui (ex: await session.execute(...))
        logger.info(f"Aplicando: {self.description}")
        return 150  # Simulando 150 linhas afetadas

HOTFIX_REGISTRY = {
    "fix_ranking": Hotfix202607RankingNull()
}

async def run_hotfix(name: str, dry_run: bool) -> None:
    hotfix = HOTFIX_REGISTRY.get(name)
    if not hotfix:
        logger.error(f"Hotfix '{name}' não encontrado no registro. Opções: {list(HOTFIX_REGISTRY.keys())}")
        return

    start_time = time.perf_counter()
    factory = get_session_factory()
    
    async with factory() as session:
        async with session.begin():
            try:
                linhas = await hotfix.execute(session, dry_run)
                
                if not dry_run:
                    elapsed = time.perf_counter() - start_time
                    logger.info(
                        "hotfix_applied",
                        extra={
                            "version": hotfix.version,
                            "affected_rows": linhas,
                            "duration_seconds": round(elapsed, 4)
                        }
                    )
                    logger.info(f"✅ Hotfix '{hotfix.version}' aplicado com sucesso ({linhas} linhas em {elapsed:.4f}s).")
            # ✅ CORRIGIDO: Remoção do 'as err' não utilizado
            except Exception:
                logger.exception(f"Falha ao aplicar hotfix '{hotfix.version}'. Rollback automático efetuado.")
                raise