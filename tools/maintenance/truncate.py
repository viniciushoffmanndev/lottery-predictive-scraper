import logging
import time
from sqlalchemy import text
from database import get_engine
from models import PipelineExecucao, PredicaoLoteria, ResultadoLoteria

logger = logging.getLogger("maintenance.truncate")

# 🔒 SINGLE SOURCE OF TRUTH (Evita quebras se o Alembic renomear tabelas)
TABLES_TO_RESET = (
    PredicaoLoteria.__tablename__,
    ResultadoLoteria.__tablename__,
    PipelineExecucao.__tablename__,
)

async def run_truncate(dry_run: bool) -> None:
    """Expurga dados operacionais utilizando Truncate com Restart Identity."""
    tabelas_str = ", ".join(TABLES_TO_RESET)
    query = f"TRUNCATE TABLE {tabelas_str} RESTART IDENTITY CASCADE;"
    
    logger.info(f"Alvo do Truncate: {tabelas_str}")
    
    if dry_run:
        logger.warning("[DRY-RUN] Nenhuma alteração será feita.")
        logger.info(f"[DRY-RUN] Query que seria executada:\n{query}")
        return

    start_time = time.perf_counter()
    engine = get_engine()
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text(query))
            
        elapsed = time.perf_counter() - start_time
        logger.info(
            "truncate_success",
            extra={
                "action": "truncate",
                "tables_affected": len(TABLES_TO_RESET),
                "duration_seconds": round(elapsed, 4)
            }
        )
        logger.info(f"✅ Tabelas expurgadas com sucesso em {elapsed:.4f}s.")
    except Exception as err:
        logger.exception("Falha catastrófica ao executar TRUNCATE.")
        raise RuntimeError("Intervenção de banco falhou.") from err