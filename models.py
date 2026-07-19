from decimal import Decimal
from enum import Enum as PyEnum
from datetime import datetime, date, time
from typing import List, Optional, Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import (
    UniqueConstraint, 
    ForeignKey, 
    ARRAY, 
    CHAR,              
    String, 
    Integer, 
    SmallInteger, 
    BigInteger,
    Numeric,           
    Identity, 
    Date, 
    Time, 
    DateTime, 
    Text,
    Index, 
    CheckConstraint, 
    Enum as SQLEnum,
    Computed,          
    text,
    func
)

class Base(DeclarativeBase):
    pass

# ==============================================================================
# MIXINS DE ARQUITETURA E AUDITORIA
# ==============================================================================

class AuditMixin:
    """
    Mixin centralizado para rastreabilidade de auditoria.
    """
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # NOTA: Atualizado nativamente via Trigger implementada nas migrações do Alembic.
    # Adicionado onupdate no nível do ORM como garantia redundante em operações Python.
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(),
        onupdate=func.now()
    )


# ==============================================================================
# ENUMS ESTRUTURADOS (GOVERNANÇA DE DOMÍNIO)
# ==============================================================================

class TemperaturaPalpite(PyEnum):
    QUENTE = "Quente"
    MORNO = "Morno"
    FRIO = "Frio"      

class StatusExecucao(PyEnum):
    PENDENTE = "Pendente"
    EXECUTANDO = "Executando" 
    SUCESSO = "Sucesso"
    ERRO = "Erro"
    CANCELADO = "Cancelado"

# ==============================================================================
# 1. TABELAS DIMENSIONAIS (CORE DOMAIN)
# ==============================================================================

class Loteria(Base):
    __tablename__ = 'loterias'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)     
    apelido: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  

    resultados: Mapped[List["ResultadoLoteria"]] = relationship("ResultadoLoteria", back_populates="loteria", lazy="raise")
    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="loteria", lazy="raise")


class TipoResultado(Base):
    __tablename__ = 'tipos_resultado'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    resultados: Mapped[List["ResultadoLoteria"]] = relationship("ResultadoLoteria", back_populates="tipo", lazy="raise")


class TipoPredicao(Base):
    __tablename__ = 'tipos_predicao'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="tipo_predicao", lazy="raise")


class BichoGrupoDezena(Base):
    __tablename__ = 'tabela_bicho_grupo_dezenas'

    grupo: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    bicho: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dezenas: Mapped[List[str]] = mapped_column(ARRAY(CHAR(2)), nullable=False)

    resultados: Mapped[List["ResultadoLoteria"]] = relationship(
        "ResultadoLoteria", back_populates="bicho", lazy="raise"
    )

    __table_args__ = (
        # Garantia física de que a matriz do bicho sempre terá 4 dezenas
        CheckConstraint('array_length(dezenas, 1) = 4', name='chk_bicho_dezenas_tamanho'),
    )

# ==============================================================================
# 2. CADERNO DE LINHAGEM E RASTREABILIDADE MLOps (ANALYTICS DOMAIN)
# ==============================================================================

class PipelineExecucao(AuditMixin, Base):
    __tablename__ = 'pipeline_execucoes'

    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    
    versao_modelo: Mapped[str] = mapped_column(String(20), server_default=text("'1.0.0'"))
    versao_algoritmo: Mapped[str] = mapped_column(String(20), server_default=text("'v1'"))
    
    # ADICIONADO: Rastreabilidade absoluta de infraestrutura e versão de código fonte
    git_commit: Mapped[Optional[str]] = mapped_column(CHAR(40), nullable=True, comment="Hash SHA-1 do commit do código fonte")
    
    # OTIMIZADO: CHAR(64) assegura 64 bytes constantes sem alocação dinâmica do String(Varchar) para o hexadecimal
    hash_execucao: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, unique=True, index=True, 
        comment="Hash SHA-256 (Hex) gerado via payload configuracional: 'pipeline-execution-' + data_alvo ISO + timestamp"
    )
    
    worker_execucao: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # --- MLOps Telemetria & Observabilidade ---
    qtd_resultados_lidos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qtd_predicoes_geradas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tempo_scraping_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tempo_analytics_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tempo_total_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    inicio_processamento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fim_processamento: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    status: Mapped[StatusExecucao] = mapped_column(
        SQLEnum(StatusExecucao, name='status_execucao_enum', create_constraint=True, native_enum=True),
        server_default=StatusExecucao.PENDENTE.value,
        nullable=False
    )
    mensagem_erro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="execucao", lazy="raise")

# ==============================================================================
# 3. TABELA DE FATOS (COMPUTAÇÃO EM DISCO NATIVA E PARTICIONADA)
# ==============================================================================

class ResultadoLoteria(AuditMixin, Base):
    __tablename__ = 'resultados_loteria'

    # =========================================================================
    # NOTA ARQUITETURAL IMPORTANTE (PARTICIONAMENTO POSTGRESQL)
    # A PK composta existe por exigência do mecanismo de particionamento RANGE 
    # do PostgreSQL. Todas as chaves únicas devem incluir a coluna de particionamento
    # para que o banco consiga garantir unicidade global entre as partições.
    # A identidade lógica da entidade para o domínio continua sendo apenas o `id`.
    # =========================================================================
    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    
    # CORRIGIDO: CHAR(4) estrito, economizando alocação dinâmica de memória no Postgres
    resultado: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    
    dt_sorteio: Mapped[date] = mapped_column(Date, Computed("data_hora::date", stored=True))
    horario: Mapped[time] = mapped_column(Time, Computed("data_hora::time", stored=True))
    
    milhar_inicio: Mapped[str] = mapped_column(CHAR(1), Computed("substring(resultado from 1 for 1)", stored=True))
    centena: Mapped[str] = mapped_column(CHAR(3), Computed("substring(resultado from 2 for 3)", stored=True))
    dezena: Mapped[str] = mapped_column(CHAR(2), Computed("substring(resultado from 3 for 2)", stored=True))
    
    _sql_grupo = "CASE WHEN substring(resultado from 3 for 2) = '00' THEN 25 ELSE ((substring(resultado from 3 for 2)::integer - 1) / 4) + 1 END"
    grupo: Mapped[Optional[int]] = mapped_column(SmallInteger, Computed(_sql_grupo, stored=True), nullable=True)
    
    premio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    id_concurso: Mapped[int] = mapped_column(Integer, nullable=False) 
    tempo_restante_segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    
    id_loteria: Mapped[int] = mapped_column(ForeignKey('loterias.id'), nullable=False, type_=SmallInteger)
    tipo_resultado_id: Mapped[int] = mapped_column(ForeignKey('tipos_resultado.id'), nullable=False, type_=SmallInteger)
    
    bicho: Mapped[Optional[BichoGrupoDezena]] = relationship("BichoGrupoDezena", back_populates="resultados", lazy="raise")
    loteria: Mapped[Loteria] = relationship("Loteria", back_populates="resultados", lazy="raise")
    tipo: Mapped[TipoResultado] = relationship("TipoResultado", back_populates="resultados", lazy="raise")

    __table_args__ = (
        UniqueConstraint('id_loteria', 'data_hora', 'premio', name='uix_loteria_data_premio'),
        UniqueConstraint('id_loteria', 'id_concurso', 'data_hora', name='uix_loteria_id_concurso'), 
        
        CheckConstraint("resultado ~ '^[0-9]{4}$'", name='chk_resultado_formato_regex'),
        CheckConstraint('grupo BETWEEN 1 AND 25', name='chk_resultado_grupo_valido'),
        CheckConstraint('premio BETWEEN 1 AND 10', name='chk_resultado_premio_valido'),
        CheckConstraint('tempo_restante_segundos >= 0', name='chk_resultado_tempo_positivo'),
        
        Index('idx_resultado_lot_grupo_data', 'id_loteria', 'grupo', 'data_hora'),     
        Index('idx_resultado_lot_tipo_data', 'id_loteria', 'tipo_resultado_id', 'data_hora'),
        Index('idx_resultado_milhar_data', 'milhar_inicio', 'data_hora'),     
        Index('idx_resultado_concurso', 'id_concurso'),                     
        
        {"postgresql_partition_by": "RANGE (data_hora)"}
    )

# ==============================================================================
# 4. TABELA DE COMPUTAÇÃO ANALÍTICA
# ==============================================================================

class PredicaoLoteria(AuditMixin, Base):
    __tablename__ = 'predicoes_loteria' 

    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    id_loteria: Mapped[int] = mapped_column(ForeignKey('loterias.id'), nullable=False, type_=SmallInteger)
    tipo_predicao_id: Mapped[int] = mapped_column(ForeignKey('tipos_predicao.id'), nullable=False, type_=SmallInteger)
    
    # ADICIONADO: Reprodutibilidade de Janela Preditiva
    janela_analise_dias: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, comment="Janela temporal retroativa utilizada (ex: 3, 15, 30)")
    
    temperatura: Mapped[TemperaturaPalpite] = mapped_column(
        SQLEnum(TemperaturaPalpite, name='temperatura_enum', create_constraint=True, native_enum=True), 
        nullable=False
    )
    
    ranking: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    palpite: Mapped[Any] = mapped_column(JSONB, nullable=False) 
    
    # Tipagem em Python alinhada com o Numeric (Decimal) do PostgreSQL
    score_confianca: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True,
        comment="Precisão probabilística (0.0000 a 1.0000)"
    )
    
    pipeline_execucao_id: Mapped[int] = mapped_column(ForeignKey('pipeline_execucoes.id'), nullable=False)
    
    execucao: Mapped[PipelineExecucao] = relationship("PipelineExecucao", back_populates="predicoes", lazy="raise")
    tipo_predicao: Mapped[TipoPredicao] = relationship("TipoPredicao", back_populates="predicoes", lazy="raise")
    loteria: Mapped[Loteria] = relationship("Loteria", back_populates="predicoes", lazy="raise")

    __table_args__ = (
        UniqueConstraint(
            'data_referencia', 'id_loteria', 'tipo_predicao_id', 'temperatura', 'ranking', 
            name='uix_predicao_unica_v5'
        ),
        Index('idx_predicoes_busca_rapida', 'id_loteria', 'data_referencia')
    )