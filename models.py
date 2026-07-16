import uuid
from datetime import datetime, date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import UniqueConstraint

class Base(DeclarativeBase):
    pass

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
    criado_em: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Adicionando a regra: A combinação dessas 3 colunas não pode se repetir!
    __table_args__ = (
        UniqueConstraint('id_loteria', 'data_hora', 'premio', name='uix_loteria_data_premio'),
    )

# --- NOSSA NOVA TABELA DE INTELIGÊNCIA ---
class PredicaoLoteria(Base):
    __tablename__ = 'predicoes_loterias'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_referencia: Mapped[date]                 # Para qual dia o palpite foi gerado
    no_loteria: Mapped[str]                       # 'Nacional' ou '26 da Sorte'
    tipo_predicao: Mapped[str]                    # Ex: 'Duque de Grupo'
    ranking: Mapped[int]                          # Ex: 1 (Top 1), 2 (Top 2)
    palpite: Mapped[str]                          # Ex: 'AVESTRUZ & BURRO'
    criado_em: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Regra de ouro para evitar duplicidade: não gravar o mesmo palpite duas vezes para o mesmo dia e loteria
    __table_args__ = (
        UniqueConstraint('data_referencia', 'no_loteria', 'tipo_predicao', 'ranking', name='uix_predicao_unica'),
    )