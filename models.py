import uuid
from datetime import datetime
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