import logging
import hashlib
import asyncio  # ✅ CORRIGIDO: Faltava o import
import httpx    # ✅ CORRIGIDO: Faltava o import
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from models import PipelineExecucao, StatusExecucao
from client import ResultadoNacionalClient
from repository import DataRepository
from analytics import PredictionEngine

logger = logging.getLogger(__name__)

class LotteryPipelineOrchestrator:
    """Orquestrador central responsável pelo ciclo de vida de ingestão, analytics e governança MLOps."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = ResultadoNacionalClient()

    def _gerar_hash_execucao(self, data_alvo: datetime) -> str:
        string_base = f"pipeline-execution-{data_alvo.isoformat()}-{datetime.now().timestamp()}"
        return hashlib.sha256(string_base.encode()).hexdigest()

    async def run_ingestao(self, dias_historico: int = 320) -> None:
        """Executa a raspagem cronológica distribuída em lote via HTTP Client."""
        logger.info(f"Iniciando varredura cronológica de dados de rede para os últimos {dias_historico} dias...")
        hoje = datetime.now()
        
        # ⚡ OTIMIZAÇÃO MAX (Fim do N+1): Cache local para evitar selects repetidos na mesma modalidade
        tipos_cache: dict[str, int] = {}
        
        async with httpx.AsyncClient(limits=self.client.limits, timeout=15.0) as http_client:
            for i in range(dias_historico):
                data_formatada = (hoje - timedelta(days=i)).strftime("%d/%m/%Y")
                payload_bruto = await self.client.fetch_resultados_por_data(http_client, data_formatada)
                
                if payload_bruto and payload_bruto.success and payload_bruto.data:
                    registros_formatados = []
                    for item in payload_bruto.data:
                        # ⚡ Cache de Domínio: Resolve IDs sem bombardear o banco
                        if item.tipo_resultado not in tipos_cache:
                            id_banco = await DataRepository.buscar_id_tipo_resultado(self.session, item.tipo_resultado)
                            if id_banco:
                                tipos_cache[item.tipo_resultado] = id_banco
                        
                        id_tipo = tipos_cache.get(item.tipo_resultado)
                        if not id_tipo:
                            continue

                        registros_formatados.append({
                            "data_hora": item.data_hora, "resultado": item.resultado,
                            "premio": item.premio, "id_concurso": item.id_concurso,
                            "id_loteria": item.id_loteria, "tipo_resultado_id": id_tipo,
                            "tempo_restante_segundos": item.tempo_restante_segundos
                        })
                    
                    if registros_formatados:
                        await DataRepository.salvar_resultados_bulk(self.session, registros_formatados)
                        # 🛡️ PROTEÇÃO TRANSACIONAL: Comita e libera os recursos após CADA lote diário
                        await self.session.commit()
                        
                await asyncio.sleep(1.0)

    async def run_analytics(self) -> None:
        """Orquestra a geração de inteligência analítica sob blindagem de linhagem MLOps."""
        logger.info("Inicializando pipeline analítico sob auditoria de linhagem MLOps...")
        
        engine_analitico = PredictionEngine(self.session)
        max_data, data_macro = await engine_analitico.obter_janela_temporal_macro()
        data_referencia = date.today() if max_data.hour < 23 else date.today() + timedelta(days=1)

        # 1. Registra o início do Pipeline de Linhagem no Banco (Estado Pendente)
        execucao = PipelineExecucao(
            hash_execucao=self._gerar_hash_execucao(max_data),
            inicio_processamento=datetime.now(),
            status=StatusExecucao.EXECUTANDO
        )
        self.session.add(execucao)
        await self.session.flush() # Obtém o ID autogerado sem commitar a transação

        try:
            predicoes_para_salvar = []
            
            # Executa o processamento para as loterias normalizadas (ID 1 e ID 2)
            for id_loteria in [1, 2]:
                duques = await engine_analitico.processar_duques_de_grupo(id_loteria, max_data, data_macro)
                for temp, rank, palpite in duques:
                    predicoes_para_salvar.append({
                        "data_referencia": data_referencia, "id_loteria": id_loteria,
                        "tipo_predicao_id": 1, "temperatura": temp, "ranking": rank,
                        "palpite": palpite, "pipeline_execucao_id": execucao.id
                    })

                ternos = await engine_analitico.processar_ternos_de_milhar(id_loteria, data_macro)
                for temp, rank, palpite in ternos:
                    predicoes_para_salvar.append({
                        "data_referencia": data_referencia, "id_loteria": id_loteria,
                        "tipo_predicao_id": 2, "temperatura": temp, "ranking": rank,
                        "palpite": palpite, "pipeline_execucao_id": execucao.id
                    })

            await DataRepository.salvar_predicoes_bulk(self.session, predicoes_para_salvar)
            
            # Atualiza os metadados de sucesso da auditoria
            execucao.status = StatusExecucao.SUCESSO
            execucao.fim_processamento = datetime.now()
            # 🛡️ PROTEÇÃO TRANSACIONAL: Comita a transação de Sucesso
            await self.session.commit()
            logger.info("Pipeline analítico executado e auditado com sucesso absoluto.")

        except Exception as err:
            # 🛡️ PROTEÇÃO MLOps: Em caso de pânico lógico, rollback dos dados processados pela metade...
            await self.session.rollback()
            
            # ... e abre uma nova mini-transação para salvar a falha na auditoria (Linha do Tempo)
            execucao.status = StatusExecucao.ERRO
            execucao.fim_processamento = datetime.now()
            execucao.mensagem_erro = str(err)
            self.session.add(execucao)
            await self.session.commit()
            
            logger.exception("Falha catastrófica durante a execução do motor analítico.")
            raise