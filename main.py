import asyncio
import logging
import sys

# ==============================================================================
# IMPORTS DA NOVA ARQUITETURA DE DOMÍNIOS
# ==============================================================================
from db.database import get_session_factory, close_db
from core.startup import run_startup_pipeline, DatabaseStartupStep
from scraper.client import ResultadoNacionalClient
from db.repository import DataRepository
from engine.analytics import PredictionEngine
from engine.orchestrator import LotteryPipelineOrchestrator

# Inicialização centralizada de logs para todo o ecossistema do scraper
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("main_pipeline")

async def main() -> None:
    # RESOLUÇÃO DINÂMICA DA VOLUMETRIA (Fim do código engessado)
    # Se você passar um número no terminal, ele assume; caso contrário, mantém 320 dias como fallback seguro.
    dias_historico = int(sys.argv[1]) if len(sys.argv) > 1 else 320
    
    logger.info(f"Iniciando rotina mestre do ecossistema analítico para {dias_historico} dias...")
    
    # 1. Pipeline de Startup (Health Check, Telemetria e Validação de Domínio)
    await run_startup_pipeline([DatabaseStartupStep()])
    
    # 2. Abre a sessão utilizando a Factory Lazy-Loaded
    factory = get_session_factory()
    async with factory() as session:
        
        # ======================================================================
        # INJEÇÃO DE DEPENDÊNCIAS (IoC - Inversion of Control)
        # ======================================================================
        client = ResultadoNacionalClient()
        repo = DataRepository(session)
        analytics = PredictionEngine(session, repo)
        
        orchestrator = LotteryPipelineOrchestrator(
            session=session,
            client=client,
            repo=repo,
            analytics=analytics
        )
        
        # ======================================================================
        # EXECUÇÃO DA ESTEIRA (PIPELINE)
        # ======================================================================
        # Roda a esteira de captura de dados de rede em Lotes de Streaming (Batching)
        metricas = await orchestrator.run_ingestao(dias_historico=dias_historico)
        logger.info(f"Ingestão finalizada. Resumo Operacional: {metricas}")
        
        # Roda o motor de predições acoplado à linhagem idempotente de MLOps
        await orchestrator.run_analytics()
            
    # 3. Libera os recursos de pooling no shutdown prevenindo vazamento de conexões
    await close_db()
    logger.info("Pipeline encerrado com sucesso. Todos os recursos foram liberados.")

if __name__ == "__main__":
    asyncio.run(main())