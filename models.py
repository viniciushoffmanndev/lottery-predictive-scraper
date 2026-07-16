import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import UniqueConstraint, ForeignKey, ARRAY, String, Integer

class Base(DeclarativeBase):
    pass

# =========================================================
# 🐾 TABELA DE REFERÊNCIA ESTÁTICA: BICHOS, GRUPOS E DEZENAS
# =========================================================
class BichoGrupoDezena(Base):
    __tablename__ = 'tabela_bicho_grupo_dezenas'

    grupo: Mapped[int] = mapped_column(Integer, primary_key=True)
    bicho: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dezenas: Mapped[List[str]] = mapped_column(ARRAY(String(2)), nullable=False) # Armazena como ['01', '02', '03', '04']

    # Amarração: Uma linha de bicho pode estar vinculada a muitos resultados de loteria
    resultados: Mapped[List["ResultadoLoteria"]] = relationship("ResultadoLoteria", back_populates="grupo_ref")


class ResultadoLoteria(Base):
    __tablename__ = 'resultados_loteria'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_hora: Mapped[datetime]
    dt_horario_sorteio: Mapped[datetime]
    horario: Mapped[str]
    dt_sorteio: Mapped[str]
    resultado: Mapped[str]
    premio: Mapped[int]
    tipo_resultado: Mapped[str]
    id_concurso: Mapped[int]
    no_loteria: Mapped[str]
    no_apelido: Mapped[str]
    id_loteria: Mapped[int]
    tempo_restante_segundos: Mapped[int]
    
    # 🔗 AMARRAÇÃO (Chave Estrangeira para o Grupo)
    # Definido como nullable=True para garantir compatibilidade com dados legados
    grupo: Mapped[Optional[int]] = mapped_column(ForeignKey('tabela_bicho_grupo_dezenas.grupo'), nullable=True)
    
    criado_em: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # 🔗 RELACIONAMENTO ORM: Permite fazer `resultado.grupo_ref.bicho` diretamente no Python!
    grupo_ref: Mapped[Optional[BichoGrupoDezena]] = relationship("BichoGrupoDezena", back_populates="resultados")

    __table_args__ = (
        UniqueConstraint('id_loteria', 'data_hora', 'premio', name='uix_loteria_data_premio'),
    )


class PredicaoLoteria(Base):
    __tablename__ = 'predicoes_loterias'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_referencia: Mapped[date]
    no_loteria: Mapped[str]
    tipo_predicao: Mapped[str]
    ranking: Mapped[int]
    palpite: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('data_referencia', 'no_loteria', 'tipo_predicao', 'ranking', name='uix_predicao_unica'),
    )