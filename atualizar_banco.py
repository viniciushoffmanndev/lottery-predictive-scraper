"""
Script utilitário para MANUTENÇÃO CIRÚRGICA DE DADOS (DML) em ambiente de produção.

🚨 ALERTA DE ARQUITETURA 🚨
É ESTRITAMENTE PROIBIDO executar comandos DDL (ALTER TABLE, CREATE, DROP) neste arquivo.
Alterações estruturais (adicionar colunas, mudar constraints) devem ser feitas 
EXCLUSIVAMENTE através das migrações do Alembic.

Uso permitido: Correção em massa de registros, backfills de dados ou expurgo pontual.
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from database import AsyncSessionLocal, engine

# Configuração isolada de log para intervenções operacionais
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [HOTFIX] - %(message)s"
)
logger = logging.getLogger("atualizar_banco")

async def aplicar_hotfix_de_dados() -> None:
    """
    Executa correções atômicas de dados (UPDATE/DELETE/INSERT) de forma segura,
    garantindo o rollback imediato em caso de pane lógica ou de rede.
    """
    logger.warning("Iniciando intervenção cirúrgica nos dados do banco...")
    
    # Exemplo de uso legítimo (Correção de dados retroativos):
    # query_correcao = text("UPDATE predicoes_loteria SET ranking = 1 WHERE ranking IS NULL;")
    
    async with AsyncSessionLocal() as session:
        # Abre transação atômica manual para controle estrito
        async with session.begin():
            try:
                # =========================================================
                # INSIRA SUA LÓGICA DE ATUALIZAÇÃO DE DADOS (DML) AQUI
                # =========================================================
                
                # await session.execute(query_correcao)
                
                logger.info("Nenhuma rotina de correção de dados foi definida no momento.")
                
            except SQLAlchemyError:
                # O rollback já é garantido pelo context manager 'session.begin()'
                logger.exception("Falha catastrófica durante a intervenção de dados. Rollback efetuado!")
                raise
            
    logger.info("Intervenção concluída com segurança.")

async def main():
    try:
        await aplicar_hotfix_de_dados()
    finally:
        # Garantir o descarte limpo das conexões para não deixar sessões presas no servidor
        await engine.dispose()

if __name__ == "__main__":
    logger.warning("ATENÇÃO: Operação direta no banco de dados.")
    confirmacao = input("Digite 'CONFIRMAR' para executar o hotfix: ")
    
    if confirmacao.strip() == "CONFIRMAR":
        asyncio.run(main())
    else:
        logger.info("Operação cancelada. Nenhuma alteração foi realizada.")