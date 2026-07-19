import asyncio
import logging
from database import init_db, close_db, AsyncSessionLocal
from orchestrator import LotteryPipelineOrchestrator

# Inicialização centralizada de logs para todo o ecossistema do scraper
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("main_pipeline")

async def main():
    logger.info("Iniciando rotina mestre do ecossistema analítico...")
    
    # 1. Garante a integridade física e de dados do banco de dados
    await init_db()
    
    # 2. Abre a sessão (sem amarrar uma transação contínua que trave o banco)
    # ✅ CORRIGIDO: O 'async with session.begin()' foi removido para evitar Deadlocks de Timeout!
    async with AsyncSessionLocal() as session:
        orchestrator = LotteryPipelineOrchestrator(session)
        
        # Roda a esteira de captura de dados de rede
        await orchestrator.run_ingestao(dias_historico=320)
        
        # Roda o motor de predições acoplado à linhagem de MLOps
        await orchestrator.run_analytics()
            
    # 3. Libera os recursos de pooling no shutdown
    await close_db()
    logger.info("Pipeline encerrado com sucesso. Todos os recursos foram liberados.")

if __name__ == "__main__":
    asyncio.run(main())