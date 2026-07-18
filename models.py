import uuid
from enum import Enum as PyEnum
from datetime import datetime, date, time
from typing import List, Optional, Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import (
    UniqueConstraint, 
    ForeignKey, 
    ARRAY, 
    String, 
    Integer, 
    SmallInteger, 
    BigInteger, 
    Identity, 
    Date, 
    Time, 
    DateTime, 
    Text,
    Index, 
    CheckConstraint, 
    Enum as SQLEnum,
    Computed,          
    case, 
    cast, 
    func,
    text               # ✅ ADICIONADO: Para definições explícitas de DDL nativo
)

class Base(DeclarativeBase):
    pass

# ==============================================================================
# 🌡️ ENUMS ESTRUTURADOS (GOVERNANÇA E DEFESA CONTRA TYPOS)
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
# 🏢 1. TABELAS DIMENSIONAIS (CHAVES LEVES SMALLINT COM RELACIONAMENTOS REVERSOS)
# ==============================================================================

class Loteria(Base):
    """Metadados de identificação das loterias (Nacional, 26 da Sorte)."""
    __tablename__ = 'loterias'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)     
    apelido: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  

    resultados: Mapped[List["ResultadoLoteria"]] = relationship("ResultadoLoteria", back_populates="loteria_ref", lazy="raise")
    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="loteria_ref", lazy="raise")


class TipoResultado(Base):
    """Modalidades de extração (PTM, PT, PPT, etc.)."""
    __tablename__ = 'tipos_resultado'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    resultados: Mapped[List["ResultadoLoteria"]] = relationship("ResultadoLoteria", back_populates="tipo_ref", lazy="raise")


class TipoPredicao(Base):
    """Normalização analítica das modalidades de palpites (Duque, Terno, etc.)."""
    __tablename__ = 'tipos_predicao'

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="tipo_pred_ref", lazy="raise")


class BichoGrupoDezena(Base):
    """Tabela estática de referência para mapeamento de grupos."""
    __tablename__ = 'tabela_bicho_grupo_dezenas'

    grupo: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    bicho: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dezenas: Mapped[List[str]] = mapped_column(ARRAY(String(2)), nullable=False)

    resultados: Mapped[List["ResultadoLoteria"]] = relationship(
        "ResultadoLoteria", back_populates="grupo_ref", lazy="raise"
    )

# ==============================================================================
# ⚡ 2. CADERNO DE LINHAGEM E RASTREABILIDADE MLOps (GOVERNANÇA)
# ==============================================================================

class PipelineExecucao(Base):
    """Tabela de governança MLOps. Mapeia a linhagem de processamento de cada lote de IA."""
    __tablename__ = 'pipeline_execucoes'

    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, server_default=func.gen_random_uuid())
    
    # ✅ CORRIGIDO: DDLs gerados com aspas explícitas via text() para consistência cross-dialeto
    versao_modelo: Mapped[str] = mapped_column(String(20), server_default=text("'1.0.0'"))
    versao_algoritmo: Mapped[str] = mapped_column(String(20), server_default=text("'v1'"))
    
    # ✅ CORRIGIDO: index=True adicionado explicitamente junto ao unique=True por fins de clareza documental[cite: 1]
    hash_execucao: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, 
        comment="Hash SHA-256 de controle de integridade da execução" # ✅ ADICIONADO: Comentário SQL nativo[cite: 1]
    )
    
    # ✅ ADICIONADO: Identificador de telemetria para ambiente Docker/K8s distribuído[cite: 1]
    worker_execucao: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, 
        comment="Identificador da instância Docker/Worker responsável pelo processamento"
    )
    
    inicio_processamento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fim_processamento: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # ✅ CORRIGIDO: status definido estritamente como nullable=False para bloquear estados inconsistentes[cite: 1]
    status: Mapped[StatusExecucao] = mapped_column(
        SQLEnum(StatusExecucao, name='status_execucao_enum', create_constraint=True),
        server_default=StatusExecucao.PENDENTE.value,
        nullable=False
    )
    
    mensagem_erro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    predicoes: Mapped[List["PredicaoLoteria"]] = relationship("PredicaoLoteria", back_populates="execucao_ref", lazy="raise")

# ==============================================================================
# 📊 3. TABELA DE FATOS (HISTÓRICO ATÔMICO COM COMPUTAÇÃO EM DISCO NATIVA)
# ==============================================================================

class ResultadoLoteria(Base):
    """Tabela de fatos volumétrica principal. Toda a segmentação numérica e temporal
    é gerada deterministicamente por hardware via expressões SQL nativas do Postgres[cite: 1]."""
    __tablename__ = 'resultados_loteria'

    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, server_default=func.gen_random_uuid())
    
    resultado: Mapped[str] = mapped_column(
        String(4), nullable=False, 
        comment="String imutável de 4 dígitos extraídos diretamente da extração" # ✅ ADICIONADO: Comentário SQL nativo[cite: 1]
    )
    
    # ✅ CORRIGIDO: Otimização de Computed utilizando casting nativo em String ("column::type")[cite: 1]
    # Evita que o SQLAlchemy gere construções pesadas ou traduções desnecessárias.
    dt_sorteio: Mapped[date] = mapped_column(Date, Computed("data_hora::date", stored=True))
    horario: Mapped[time] = mapped_column(Time, Computed("data_hora::time", stored=True))
    
    # ✅ CORRIGIDO: Otimização utilizando sintaxe nativa do dialeto PostgreSQL (substring)[cite: 1]
    milhar_inicio: Mapped[str] = mapped_column(String(1), Computed("substring(resultado from 1 for 1)", stored=True))
    centena: Mapped[str] = mapped_column(String(3), Computed("substring(resultado from 2 for 3)", stored=True))
    dezena: Mapped[str] = mapped_column(String(2), Computed("substring(resultado from 3 for 2)", stored=True))
    
    # ✅ CORRIGIDO: Substituição por divisão inteira implícita truncada nativa do Postgres (evita flutuações numéricas)[cite: 1]
    _sql_grupo = "CASE WHEN substring(resultado from 3 for 2) = '00' THEN 25 ELSE ((substring(resultado from 3 for 2)::integer - 1) / 4) + 1 END"
    grupo: Mapped[Optional[int]] = mapped_column(
        SmallInteger, Computed(_sql_grupo, stored=True), nullable=True,
        comment="Grupo identificador do bicho (1 a 25) gerado via hardware" # ✅ ADICIONADO: Comentário SQL nativo[cite: 1]
    )
    
    premio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    id_concurso: Mapped[int] = mapped_column(Integer, nullable=False) 
    
    # ✅ NOTA DE ENGENHARIA: Campo de telemetria mantido para auditoria de atraso (delay) da ingestão[cite: 1]
    tempo_restante_segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    
    id_loteria: Mapped[int] = mapped_column(ForeignKey('loterias.id'), nullable=False, type_=SmallInteger)
    tipo_resultado_id: Mapped[int] = mapped_column(ForeignKey('tipos_resultado.id'), nullable=False, type_=SmallInteger)
    
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # 🚨 NOTA DE INFRAESTRUTURA: Sincronizado exclusivamente por trigger SQL Before Update do Postgres.
    # O ORM não gerencia mutações neste campo.[cite: 1]
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    grupo_ref: Mapped[Optional[BichoGrupoDezena]] = relationship("BichoGrupoDezena", back_populates="resultados", lazy="raise")
    loteria_ref: Mapped[Loteria] = relationship("Loteria", back_populates="resultados", lazy="raise")
    tipo_ref: Mapped[TipoResultado] = relationship("TipoResultado", back_populates="resultados", lazy="raise")

    __table_args__ = (
        UniqueConstraint('id_loteria', 'data_hora', 'premio', name='uix_loteria_data_premio'),
        
        # ✅ ADICIONADO: Trava rígida de integridade de negócio - Concurso único por turno de loteria[cite: 1]
        UniqueConstraint('id_loteria', 'id_concurso', name='uix_loteria_id_concurso'),
        
        # 🛡️ Validação Master de Entrada
        CheckConstraint("resultado ~ '^[0-9]{4}$'", name='chk_resultado_formato_regex'),
        
        # Restrições de Domínio Estáticas
        CheckConstraint('grupo BETWEEN 1 AND 25', name='chk_resultado_grupo_valido'),
        CheckConstraint('premio BETWEEN 1 AND 10', name='chk_resultado_premio_valido'),
        CheckConstraint('tempo_restante_segundos >= 0', name='chk_resultado_tempo_positivo'),
        
        # 📈 Índices de Cobertura Analítica (Alinhados estritamente com os Motores do Jupyter)
        Index('idx_resultado_loteria_data', 'id_loteria', 'data_hora'),     
        Index('idx_resultado_grupo_data', 'grupo', 'data_hora'),             
        Index('idx_resultado_milhar_data', 'milhar_inicio', 'data_hora'),     
        Index('idx_resultado_data_hora_solo', 'data_hora'),                 
        Index('idx_resultado_concurso', 'id_concurso'),                     
        
        {"postgresql_partition_by": "RANGE (data_hora)"}
    )

# ==============================================================================
# 🔮 4. TABELA DE COMPUTAÇÃO ANALÍTICA (PREDIÇÕES CONSOLIDADAS)
# ==============================================================================

class PredicaoLoteria(Base):
    """Armazena as assinaturas preditivas estruturadas atreladas a uma execução física do pipeline."""
    __tablename__ = 'predicoes_loteria' 

    id: Mapped[int] = mapped_column(BigInteger, Identity(by_default=True), primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, server_default=func.gen_random_uuid())
    
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    id_loteria: Mapped[int] = mapped_column(ForeignKey('loterias.id'), nullable=False, type_=SmallInteger)
    tipo_predicao_id: Mapped[int] = mapped_column(ForeignKey('tipos_predicao.id'), nullable=False, type_=SmallInteger)
    
    temperatura: Mapped[TemperaturaPalpite] = mapped_column(
        SQLEnum(TemperaturaPalpite, name='temperatura_enum', create_constraint=True), 
        nullable=False
    )
    
    ranking: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    
    # ✅ NOTA DE DESENVOLVIMENTO: O payload JSONB deve ser validado via esquema Pydantic antes da ingestão[cite: 1]
    palpite: Mapped[Any] = mapped_column(
        JSONB, nullable=False,
        comment="Payload JSON estruturado contendo a matriz de palpites gerada" # ✅ ADICIONADO: Comentário SQL nativo[cite: 1]
    ) 
    
    # ✅ ADICIONADO: Score de confiança preditiva para suportar calibração de modelos analíticos avançados[cite: 1]
    score_confianca: Mapped[Optional[float]] = mapped_column(
        comment="Métrica decimal (0.00 a 1.00) avaliando a precisão probabilística calculada pela IA"
    )
    
    pipeline_execucao_id: Mapped[int] = mapped_column(ForeignKey('pipeline_execucoes.id'), nullable=False)
    
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # 🚨 NOTA DE INFRAESTRUTURA: Sincronizado exclusivamente por trigger SQL Before Update do Postgres.
    # O ORM não gerencia mutações neste campo.[cite: 1]
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    execucao_ref: Mapped[PipelineExecucao] = relationship("PipelineExecucao", back_populates="predicoes", lazy="raise")
    tipo_pred_ref: Mapped[TipoPredicao] = relationship("TipoPredicao", back_populates="predicoes", lazy="raise")
    loteria_ref: Mapped[Loteria] = relationship("Loteria", back_populates="predicoes", lazy="raise")

    __table_args__ = (
        UniqueConstraint(
            'data_referencia', 
            'id_loteria', 
            'tipo_predicao_id', 
            'temperatura', 
            'ranking', 
            name='uix_predicao_unica_v5'
        ),
        Index('idx_predicoes_busca_rapida', 'id_loteria', 'data_referencia')
    )