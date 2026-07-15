import uuid
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class ResultadoLoteria(Base):
    __tablename__ = 'resultados_loteria'

    # Nossa chave primária usando UUID para performance em sistemas distribuídos
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Datas que converteremos para formato DateTime real
    data_hora: Mapped[datetime]
    dt_horario_sorteio: Mapped[datetime]
    
    # Strings e outros dados
    horario: Mapped[str]
    dt_sorteio: Mapped[str]
    resultado: Mapped[str]  # Mantido como string para não perder os zeros à esquerda!
    premio: Mapped[int]
    tipo_resultado: Mapped[str]
    id_concurso: Mapped[int]
    no_loteria: Mapped[str]
    no_apelido: Mapped[str]
    id_loteria: Mapped[int]
    tempo_restante_segundos: Mapped[int]
    
    # Campo extra para sabermos quando este dado foi extraído (bom para Data Science)
    criado_em: Mapped[datetime] = mapped_column(default=datetime.utcnow)