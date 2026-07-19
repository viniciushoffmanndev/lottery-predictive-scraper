import asyncio
import logging
from sqlalchemy import text
from database import engine

# Configuração de observabilidade local para o script utilitário
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [reset_db] - %(message)s"
)
logger = logging.getLogger("reset_db")

async def resetar_dados_operacionais() -> None:
    """
    Limpa cirurgicamente os dados transacionais (Resultados, Predições, Execuções)
    preservando o schema do Alembic e as tabelas de domínio (Loterias, Bichos).
    """
    logger.warning("⚠️ ALERTA: INICIANDO TRUNCATE DOS DADOS OPERACIONAIS DO BANCO...")
    
    # ⚡ Comando SQL Nativo: Truncate é milhares de vezes mais rápido que o DELETE.
    # O RESTART IDENTITY zera os IDs (BigInteger).
    # O CASCADE garante que chaves estrangeiras dependentes sejam limpas junto.
    truncate_query = """
        TRUNCATE TABLE 
            predicoes_loteria, 
            resultados_loteria, 
            pipeline_execucoes 
        RESTART IDENTITY CASCADE;
    """
    
    try:
        # Abre uma transação atômica exclusiva para a limpeza
        async with engine.begin() as conn:
            logger.info("🗑️ Executando varredura rápida nas tabelas de Fatos e Logs de IA...")
            await conn.execute(text(truncate_query))
            
        logger.info("✅ Dados transacionais expurgados com sucesso! Schema e Domínios preservados.")
    except Exception:
        logger.exception("❌ Falha catastrófica ao tentar truncar o banco de dados.")
        raise
    finally:
        # Encerramento limpo do pool de conexões
        await engine.dispose()

if __name__ == "__main__":
    logger.warning("ATENÇÃO: Este script apagará todo o histórico de raspagem e predições.")
    confirmacao = input("Digite 'CONFIRMAR' para continuar: ")
    
    if confirmacao.strip() == "CONFIRMAR":
        asyncio.run(resetar_dados_operacionais())
    else:
        logger.info("Operação cancelada pelo usuário. O banco permanece intacto.")