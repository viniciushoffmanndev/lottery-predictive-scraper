import logging
from typing import Any, Dict, Final, Optional, Sequence  # ✅ CORRIGIDO: Remoção de não utilizados, adição de Optional e uso de Sequence
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from models import ResultadoLoteria, PredicaoLoteria, BichoGrupoDezena, TipoResultado  # ✅ CORRIGIDO: Removido TipoPredicao por falta de uso

logger = logging.getLogger(__name__)

LOTE_MAXIMO_GRAVACAO: Final[int] = 100

class DataRepository:
    """Repositório encapsulado para transações atômicas e bulk operations nativas."""

    @staticmethod
    async def salvar_resultados_bulk(session: AsyncSession, dados: Sequence[Dict[str, Any]]) -> None:  # ✅ OTIMIZADO: Uso de Sequence para flexibilidade polimórfica
        """Executa a inserção em lotes (Bulk Insert) de novos resultados ignorando duplicidades."""
        if not dados:
            return

        for i in range(0, len(dados), LOTE_MAXIMO_GRAVACAO):
            chunk = dados[i:i + LOTE_MAXIMO_GRAVACAO]
            try:
                stmt = insert(ResultadoLoteria).values(chunk)
                stmt = stmt.on_conflict_do_nothing(index_elements=['id_loteria', 'data_hora', 'premio'])
                await session.execute(stmt)
            except SQLAlchemyError:
                logger.exception("Falha crítica ao executar inserção em lote de resultados históricos.")
                raise

    @staticmethod
    async def salvar_predicoes_bulk(session: AsyncSession, predicoes: Sequence[Dict[str, Any]]) -> None:  # ✅ OTIMIZADO: Uso de Sequence
        """Executa bulk upsert de predições analíticas atualizando palpites em caso de colisão."""
        if not predicoes:
            return

        try:
            stmt = insert(PredicaoLoteria).values(predicoes)
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'id_loteria', 'tipo_predicao_id', 'temperatura', 'ranking'],
                set_={'palpite': stmt.excluded.palpite, 'pipeline_execucao_id': stmt.excluded.pipeline_execucao_id}
            )
            await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("Falha crítica ao persistir lote de predições analíticas.")
            raise

    @staticmethod
    async def buscar_mapeamento_bichos(session: AsyncSession) -> Dict[int, Sequence[str]]:
        """Busca o mapa estático de dezenas por grupo diretamente da Single Source of Truth do banco."""
        stmt = select(BichoGrupoDezena.grupo, BichoGrupoDezena.dezenas)
        result = await session.execute(stmt)
        # ✅ OTIMIZADO: Iteração sobre o cursor nativo do result elimina a criação de listas temporárias em memória de result.all()
        return {row.grupo: row.dezenas for row in result}

    @staticmethod
    async def buscar_id_tipo_resultado(session: AsyncSession, nome_tipo: str) -> Optional[int]:  # ✅ CORRIGIDO: NameError evitado com o import de Optional
        """Resolve dinamicamente o ID de um tipo de resultado com base no nome."""
        stmt = select(TipoResultado.id).where(TipoResultado.nome == nome_tipo)
        return await session.scalar(stmt)