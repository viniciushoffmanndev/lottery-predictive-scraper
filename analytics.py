import logging
import itertools
from collections import Counter
from datetime import datetime, date, timedelta
# ✅ OTIMIZADO: Tipagens obsoletas (List, Dict, Tuple) removidas. Usaremos as built-ins nativas.
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import ResultadoLoteria
from repository import DataRepository

logger = logging.getLogger(__name__)

class PredictionEngine:
    """Motor analítico de alta performance. Executa cruzamentos estatísticos direto no hardware do Postgres."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def obter_janela_temporal_macro(self) -> tuple[datetime, datetime]:
        """Obtém os marcos cronológicos delimitadores com base no registro mais recente do banco."""
        max_data = await self.session.scalar(select(func.max(ResultadoLoteria.data_hora)))
        if not max_data:
            return datetime.now(), datetime.now()
        return max_data, max_data - timedelta(days=15)

    async def processar_duques_de_grupo(self, id_loteria: int, max_data: datetime, data_macro: datetime) -> list[tuple[str, int, str]]:
        """Calcula a frequência de grupos no Postgres e monta a matriz de 10 jogos."""
        # ⚡ OTIMIZAÇÃO MAX: Curto prazo processado de forma compacta (apenas arrays agrupados de 3 dias)
        stmt_curto = (
            select(func.array_agg(ResultadoLoteria.grupo.distinct()))
            .where(ResultadoLoteria.id_loteria == id_loteria, ResultadoLoteria.data_hora >= max_data - timedelta(days=3))
            .group_by(ResultadoLoteria.data_hora)
        )
        res_curto = await self.session.scalars(stmt_curto)
        
        freq_casais = Counter()
        # ✅ OTIMIZADO: Itera diretamente no cursor sem alocar uma lista `.all()` na memória
        for grupos in res_curto:
            validos = [g for g in grupos if g is not None]
            if len(validos) >= 2:
                freq_casais.update(list(itertools.combinations(sorted(validos), 2)))
        top_casais = [c for c, _ in freq_casais.most_common(4)]

        # ⚡ OTIMIZAÇÃO MAX: Frequência macro agregada 100% no banco. Retorna no máximo 25 linhas na rede!
        stmt_macro = (
            select(ResultadoLoteria.grupo)
            .where(ResultadoLoteria.id_loteria == id_loteria, ResultadoLoteria.data_hora >= data_macro)
            .group_by(ResultadoLoteria.grupo)
            .order_by(func.count(ResultadoLoteria.id).desc())
        )
        freq_grupos = (await self.session.scalars(stmt_macro)).all()
        if len(freq_grupos) < 15:
            return []

        grupo_rei = freq_grupos[0]
        mornos, frios = freq_grupos[5:8], freq_grupos[-3:]
        
        # Estruturação matricial dos 10 jogos
        jogos = [("Quente", i+1, f"{str(c[0]).zfill(2)} & {str(c[1]).zfill(2)}") for i, c in enumerate(top_casais[:4])]
        jogos += [("Morno", i+1, f"{str(grupo_rei).zfill(2)} & {str(g).zfill(2)}") for i, g in enumerate(mornos)]
        jogos += [("Frio", i+1, f"{str(c[0]).zfill(2)} & {str(c[1]).zfill(2)}") for i, c in enumerate(list(itertools.combinations(frios, 2))[:3])]
        return jogos

    async def processar_ternos_de_milhar(self, id_loteria: int, data_macro: datetime) -> list[tuple[str, int, str]]:
        """Gera matrizes analíticas de rotação de milhares avaliando tendências de dígitos em disco."""
        
        # Agregação nativa de dígitos iniciais mais frequentes
        stmt_digitos = (
            select(ResultadoLoteria.milhar_inicio)
            .where(ResultadoLoteria.id_loteria == id_loteria, ResultadoLoteria.data_hora >= data_macro)
            .group_by(ResultadoLoteria.milhar_inicio)
            .order_by(func.count(ResultadoLoteria.id).desc())
        )
        freq_digitos = (await self.session.scalars(stmt_digitos)).all()

        stmt_grupos = (
            select(ResultadoLoteria.grupo)
            .where(ResultadoLoteria.id_loteria == id_loteria, ResultadoLoteria.data_hora >= data_macro)
            .group_by(ResultadoLoteria.grupo)
            .order_by(func.count(ResultadoLoteria.id).desc())
        )
        freq_grupos = (await self.session.scalars(stmt_grupos)).all()
        
        if len(freq_digitos) < 3 or len(freq_grupos) < 10:
            return []

        mapa_bichos = await DataRepository.buscar_mapeamento_bichos(self.session)

        def girar_centena(digito: str, grupo: int, offset: int) -> str:
            dezenas = mapa_bichos.get(grupo, ("00", "00", "00", "00"))
            m = [f"{digito}{str((offset + i) % 10)}{dezenas[i % len(dezenas)]}" for i in range(3)]
            return f"{m[0]} - {m[1]} - {m[2]}"

        jogos = [("Quente", i+1, girar_centena(freq_digitos[0], g, i)) for i, g in enumerate(freq_grupos[:4])]
        jogos += [("Morno", i+1, girar_centena(freq_digitos[1], g, i+4)) for i, g in enumerate(freq_grupos[4:7])]
        jogos += [("Frio", i+1, girar_centena(freq_digitos[-1], g, i+7)) for i, g in enumerate(freq_grupos[-3:])]
        
        return jogos