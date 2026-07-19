import asyncio
import logging
from database import get_session_factory, close_db
from startup_checks import init_db
from orchestrator import LotteryPipelineOrchestrator

# Inicialização centralizada de logs para todo o ecossistema do scraper
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("main_pipeline")

async def main() -> None:
    logger.info("Iniciando rotina mestre do ecossistema analítico...")
    
    # 1. Pipeline de Startup (Garante a integridade física, warmup e dados de referência)
    await init_db()
    
    # 2. Abre a sessão utilizando a Factory Lazy-Loaded
    factory = get_session_factory()
    async with factory() as session:
        orchestrator = LotteryPipelineOrchestrator(session)
        
        # Roda a esteira de captura de dados de rede
        await orchestrator.run_ingestao(dias_historico=320)
        
        # Roda o motor de predições acoplado à linhagem de MLOps
        await orchestrator.run_analytics()
            
    # 3. Libera os recursos de pooling no shutdown prevenindo state leaks
    await close_db()
    logger.info("Pipeline encerrado com sucesso. Todos os recursos foram liberados.")

if __name__ == "__main__":
    asyncio.run(main())