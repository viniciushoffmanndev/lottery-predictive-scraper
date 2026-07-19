import logging
import itertools
from collections import Counter
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import ResultadoLoteria
from db.repository import DataRepository

logger = logging.getLogger(__name__)

class PredictionEngine:
    """Motor analítico empurrado para SQL Nativo (Push-Down Computation)."""
    
    # 🎯 Semântica para evitar IDs Mágicos na orquestração
    TIPO_PREDICAO_DUQUE = 1
    TIPO_PREDICAO_TERNO = 2

    def __init__(self, session: AsyncSession, repo: DataRepository):
        self.session = session
        self.repo = repo

    async def obter_janela_temporal_macro(self) -> tuple[datetime, datetime]:
        max_data = await self.session.scalar(select(func.max(ResultadoLoteria.data_hora)))
        if not max_data:
            return datetime.now(), datetime.now()
        return max_data, max_data - timedelta(days=15)

    async def processar_duques_de_grupo(self, id_loteria: int, max_data: datetime, data_macro: datetime) -> list[tuple[str, int, str]]:
        stmt_curto = (
            select(func.array_agg(ResultadoLoteria.grupo.distinct()))
            .where(ResultadoLoteria.id_loteria == id_loteria, ResultadoLoteria.data_hora >= max_data - timedelta(days=3))
            .group_by(ResultadoLoteria.data_hora)
        )
        res_curto = await self.session.scalars(stmt_curto)
        
        freq_casais = Counter()
        for grupos in res_curto:
            validos = [g for g in grupos if g is not None]
            if len(validos) >= 2:
                freq_casais.update(list(itertools.combinations(sorted(validos), 2)))
        top_casais = [c for c, _ in freq_casais.most_common(4)]

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
        
        jogos = [("Quente", i+1, f"{str(c[0]).zfill(2)} & {str(c[1]).zfill(2)}") for i, c in enumerate(top_casais[:4])]
        jogos += [("Morno", i+1, f"{str(grupo_rei).zfill(2)} & {str(g).zfill(2)}") for i, g in enumerate(mornos)]
        jogos += [("Frio", i+1, f"{str(c[0]).zfill(2)} & {str(c[1]).zfill(2)}") for i, c in enumerate(list(itertools.combinations(frios, 2))[:3])]
        return jogos

    async def processar_ternos_de_milhar(self, id_loteria: int, data_macro: datetime) -> list[tuple[str, int, str]]:
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

        mapa_bichos = await self.repo.buscar_mapeamento_bichos()

        def girar_centena(digito: str, grupo: int, offset: int) -> str:
            dezenas = mapa_bichos.get(grupo, ("00", "00", "00", "00"))
            m = [f"{digito}{str((offset + i) % 10)}{dezenas[i % len(dezenas)]}" for i in range(3)]
            return f"{m[0]} - {m[1]} - {m[2]}"

        jogos = [("Quente", i+1, girar_centena(freq_digitos[0], g, i)) for i, g in enumerate(freq_grupos[:4])]
        jogos += [("Morno", i+1, girar_centena(freq_digitos[1], g, i+4)) for i, g in enumerate(freq_grupos[4:7])]
        jogos += [("Frio", i+1, girar_centena(freq_digitos[-1], g, i+7)) for i, g in enumerate(freq_grupos[-3:])]
        return jogos