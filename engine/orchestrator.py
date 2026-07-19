import logging
import hashlib
import asyncio
import httpx
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, NamedTuple
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PipelineExecucao, StatusExecucao
from scraper.schemas import RespostaBuscaSchema, LoteriaNome
from scraper.client import ResultadoNacionalClient
from db.repository import DataRepository
from analytics import PredictionEngine

logger = logging.getLogger(__name__)

# ==============================================================================
# 📊 MONADS (ADT) E TELEMETRIA
# ==============================================================================

class IngestionResult(NamedTuple):
    """Abstract Data Type (Monad-like) para fluxo controlado de I/O de rede."""
    data_alvo: str
    payload: Optional[RespostaBuscaSchema]
    sucesso: bool
    error_reason: Optional[str] = None

@dataclass
class PipelineMetrics:
    """Coletor estruturado de métricas para Observabilidade."""
    scraper_requests_total: int = 0
    scraper_success_total: int = 0
    scraper_failed_total: int = 0
    payload_validation_errors: int = 0
    records_persisted: int = 0

# ==============================================================================
# 🚂 CORE ORCHESTRATOR
# ==============================================================================

class LotteryPipelineOrchestrator:
    """Coordenador agnóstico de Ingestão em Lotes, IoC e Auditoria Analítica."""

    # 🚦 Configuração de Batching para Streaming Controlado de RAM
    BATCH_CHUNK_SIZE = 30  

    def __init__(
        self, 
        session: AsyncSession, 
        client: ResultadoNacionalClient, 
        repo: DataRepository, 
        analytics: PredictionEngine
    ):
        # 🧩 INJEÇÃO DE DEPENDÊNCIA (IoC)
        self.session = session
        self.client = client
        self.repo = repo
        self.analytics = analytics
        self.semaphore = asyncio.Semaphore(15)

    def _gerar_hash_determinismo(self, data_alvo: datetime, versao_algo: str = "v1") -> str:
        """Gera assinatura idempotente para a execução do ML (Reprodutibilidade)."""
        string_base = f"pipeline-{versao_algo}-{data_alvo.date().isoformat()}"
        return hashlib.sha256(string_base.encode()).hexdigest()

    async def _fetch_bounded(self, http_client: httpx.AsyncClient, data_formatada: str) -> IngestionResult:
        """Worker atômico limitando conexões simultâneas da aplicação."""
        async with self.semaphore:
            payload = await self.client.fetch_resultados_por_data(http_client, data_formatada)
            if payload and payload.success:
                return IngestionResult(data_alvo=data_formatada, payload=payload, sucesso=True)
            return IngestionResult(data_alvo=data_formatada, payload=None, sucesso=False, error_reason="HTTP/Contract Failure")

    async def run_ingestao(self, dias_historico: int = 320) -> PipelineMetrics:
        """
        Executa raspagem fatiada em lotes (Batching/Streaming Memory Pattern).
        Evita a criação de milhares de Tasks no Event Loop.
        """
        logger.info(f"🚀 Iniciando orquestração de Ingestão Fatiada (Lotes de {self.BATCH_CHUNK_SIZE}) para {dias_historico} dias.")
        hoje = datetime.now()
        metrics = PipelineMetrics()
        
        # O Repository localiza o Enum em ID sem sobrecarregar a orquestração
        id_lot_nacional = await self.repo.resolver_id_loteria(LoteriaNome.NACIONAL.value)
        if not id_lot_nacional:
            raise ValueError("O domínio LoteriaNacional não foi registrado no banco de dados.")

        async with httpx.AsyncClient(limits=self.client.limits, timeout=15.0) as http_client:
            
            # 🔪 Fatiamento (Chunking) para proteção de RAM e Transações Menores no PG
            for offset_lote in range(0, dias_historico, self.BATCH_CHUNK_SIZE):
                chunk_fim = min(offset_lote + self.BATCH_CHUNK_SIZE, dias_historico)
                tarefas_do_lote = []
                
                # FAN-OUT do Lote
                for i in range(offset_lote, chunk_fim):
                    data_form = (hoje - timedelta(days=i)).strftime("%d/%m/%Y")
                    tarefas_do_lote.append(self._fetch_bounded(http_client, data_form))
                    metrics.scraper_requests_total += 1
                
                res_lote = await asyncio.gather(*tarefas_do_lote)

                # FAN-IN (Redução do Lote) e Construção de Registros Agnósticos
                registros_prontos = []
                for res in res_lote:
                    if not res.sucesso or not res.payload:
                        metrics.scraper_failed_total += 1
                        continue
                        
                    metrics.scraper_success_total += 1
                    for item in res.payload.data:
                        # Resolução de ID delegada para a Base de Dados/Repository
                        id_tipo = await self.repo.resolver_id_tipo_resultado(item.tipo_resultado.value)
                        if not id_tipo:
                            metrics.payload_validation_errors += 1
                            continue

                        registros_prontos.append({
                            "data_hora": item.data_hora, "resultado": item.resultado,
                            "premio": item.premio, "id_concurso": item.id_concurso,
                            "id_loteria": id_lot_nacional, "tipo_resultado_id": id_tipo,
                            "tempo_restante_segundos": item.tempo_restante_segundos
                        })

                # COMITA E LIBERA A MEMÓRIA DO LOTE (Garbage Collection)
                if registros_prontos:
                    await self.repo.salvar_resultados_bulk(registros_prontos)
                    await self.session.commit()
                    metrics.records_persisted += len(registros_prontos)
                    
                # Respiro entre os lotes de Ingestão (Despressuriza Sockets)
                await asyncio.sleep(0.5)
                
        logger.info("📊 Fim da Ingestão. Métricas de Pipeline: %s", metrics)
        return metrics

    async def run_analytics(self) -> None:
        """Linhagem determinística e Orquestração de Cálculo Direcionado."""
        logger.info("🧠 Executando pipeline analítico sob auditoria Idempotente de MLOps...")
        
        max_data, data_macro = await self.analytics.obter_janela_temporal_macro()
        data_ref = date.today() if max_data.hour < 23 else date.today() + timedelta(days=1)

        # Assinatura MLOps Determinística (Pode ser reproduzida se apagada)
        execucao = PipelineExecucao(
            hash_execucao=self._gerar_hash_determinismo(max_data, versao_algo="v1"),
            inicio_processamento=datetime.now(),
            status=StatusExecucao.EXECUTANDO
        )
        self.session.add(execucao)
        await self.session.flush()

        try:
            predicoes_lote = []
            
            # Sem IDs físicos engessados. A infra estrutura dinamicamente.
            id_lot_nacional = await self.repo.resolver_id_loteria(LoteriaNome.NACIONAL.value)
            
            if id_lot_nacional:
                # Rotinas acopladas sem conhecimento profundo de tabelas
                duques = await self.analytics.processar_duques_de_grupo(id_lot_nacional, max_data, data_macro)
                for temp, rank, palpite in duques:
                    predicoes_lote.append({
                        "data_referencia": data_ref, "id_loteria": id_lot_nacional,
                        "tipo_predicao_id": self.analytics.TIPO_PREDICAO_DUQUE, 
                        "temperatura": temp, "ranking": rank,
                        "palpite": palpite, "pipeline_execucao_id": execucao.id
                    })

                ternos = await self.analytics.processar_ternos_de_milhar(id_lot_nacional, data_macro)
                for temp, rank, palpite in ternos:
                    predicoes_lote.append({
                        "data_referencia": data_ref, "id_loteria": id_lot_nacional,
                        "tipo_predicao_id": self.analytics.TIPO_PREDICAO_TERNO, 
                        "temperatura": temp, "ranking": rank,
                        "palpite": palpite, "pipeline_execucao_id": execucao.id
                    })

            await self.repo.salvar_predicoes_bulk(predicoes_lote)
            execucao.status = StatusExecucao.SUCESSO
            execucao.fim_processamento = datetime.now()
            await self.session.commit()
            
            logger.info("✅ Computação Analítica Concluída (Hash ID: %s)", execucao.hash_execucao)

        except Exception as err:
            await self.session.rollback()
            execucao.status = StatusExecucao.ERRO
            execucao.fim_processamento = datetime.now()
            execucao.mensagem_erro = str(err)
            self.session.add(execucao)
            await self.session.commit()
            logger.exception("🚨 Engine Predutiva reportou falha crítica e realizou Rollback Preventivo.")
            raise