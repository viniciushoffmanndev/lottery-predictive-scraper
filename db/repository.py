import logging
from typing import Any, Dict, Final, Sequence, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from models import ResultadoLoteria, PredicaoLoteria, BichoGrupoDezena, TipoResultado, Loteria

logger = logging.getLogger(__name__)

LOTE_MAXIMO_GRAVACAO: Final[int] = 100

class DataRepository:
    """Repositório isolado para abstração transacional e de mapeamento ORM."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        # Cache local em memória (Resolvido no Startup) para não onerar queries de Ingestão
        self._cache_tipos_resultado: Dict[str, int] = {}
        self._cache_loterias: Dict[str, int] = {}

    async def _carregar_caches_dominio(self) -> None:
        """Preenche o dicionário interno para resolução de Enum -> ID em O(1)."""
        if not self._cache_tipos_resultado:
            res = await self.session.execute(select(TipoResultado.nome, TipoResultado.id))
            self._cache_tipos_resultado = {row.nome: row.id for row in res}
            
        if not self._cache_loterias:
            res = await self.session.execute(select(Loteria.nome, Loteria.id))
            self._cache_loterias = {row.nome: row.id for row in res}

    async def resolver_id_tipo_resultado(self, nome_enum: str) -> Optional[int]:
        await self._carregar_caches_dominio()
        return self._cache_tipos_resultado.get(nome_enum)
        
    async def resolver_id_loteria(self, nome_enum: str) -> Optional[int]:
        await self._carregar_caches_dominio()
        return self._cache_loterias.get(nome_enum)

    async def salvar_resultados_bulk(self, dados: Sequence[Dict[str, Any]]) -> None:
        """Insere resultados ignorando colisões garantindo idempotência absoluta."""
        if not dados: 
            return

        for i in range(0, len(dados), LOTE_MAXIMO_GRAVACAO):
            chunk = dados[i:i + LOTE_MAXIMO_GRAVACAO]
            try:
                stmt = insert(ResultadoLoteria).values(chunk)
                stmt = stmt.on_conflict_do_nothing(index_elements=['id_loteria', 'data_hora', 'premio'])
                await self.session.execute(stmt)
            except SQLAlchemyError:
                logger.exception("Falha transacional ao injetar lote histórico.")
                raise

    async def salvar_predicoes_bulk(self, predicoes: Sequence[Dict[str, Any]]) -> None:
        """Upsert de inteligência com substituição de versão analítica."""
        if not predicoes: 
            return

        try:
            stmt = insert(PredicaoLoteria).values(predicoes)
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'id_loteria', 'tipo_predicao_id', 'temperatura', 'ranking'],
                set_={'palpite': stmt.excluded.palpite, 'pipeline_execucao_id': stmt.excluded.pipeline_execucao_id}
            )
            await self.session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("Falha transacional ao persistir score preditivo.")
            raise

    async def buscar_mapeamento_bichos(self) -> Dict[int, Sequence[str]]:
        stmt = select(BichoGrupoDezena.grupo, BichoGrupoDezena.dezenas)
        result = await self.session.execute(stmt)
        return {row.grupo: row.dezenas for row in result}