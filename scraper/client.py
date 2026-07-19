import logging
from types import MappingProxyType
from typing import Optional
import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception
)

from config import settings
from schemas import RespostaBuscaSchema

logger = logging.getLogger(__name__)

# ==============================================================================
# DTOs E CONTRATOS
# ==============================================================================

class BuscaResultadoRequest(BaseModel):
    """Contrato rigoroso para a requisição de saída (Outbound DTO)."""
    dtSorteio: str
    horario: str = ""

# ==============================================================================
# POLÍTICAS DE RESILIÊNCIA E RETRY
# ==============================================================================

def is_transient_error(exception: BaseException) -> bool:
    """
    Política de Circuit Breaking: Decide inteligentemente se a falha merece Retry.
    Rejeita repetições inócuas (400, 401, 404), mas acolhe falhas de trânsito.
    """
    if isinstance(exception, httpx.RequestError):
        return True  # DNS, Timeout, TCP Drop, Socket Exhaustion
    if isinstance(exception, httpx.HTTPStatusError):
        # Tenta novamente APENAS Rate Limits e Erros Internos de Servidor Remoto
        return exception.response.status_code in {429, 500, 502, 503, 504}
    return False

# ==============================================================================
# TRANSPORT LAYER (GATEWAY)
# ==============================================================================

class ResultadoNacionalClient:
    """Gateway de integração HTTP resiliente e estrito."""
    
    def __init__(self):
        self.base_url = f"{settings.scraper.base_url.rstrip('/')}/resultado/busca"
        
        # MappingProxyType garante que os headers não sofrerão mutação acidental em runtime
        self.headers = MappingProxyType({
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": settings.scraper.base_url,
            "referer": f"{settings.scraper.base_url}/",
            "user-agent": settings.scraper.user_agent,
            "x-requested-with": "XMLHttpRequest"
        })
        
        # Timeouts granulares precisos desacoplados em config.py
        self.timeout = httpx.Timeout(
            connect=settings.scraper.timeout_connect,
            read=settings.scraper.timeout_read,
            write=settings.scraper.timeout_write,
            pool=settings.scraper.timeout_pool
        )

    @retry(
        stop=stop_after_attempt(settings.scraper.max_retries),
        wait=wait_exponential_jitter(initial=1, max=10),  # Backoff progressivo com variação caótica (Jitter)
        retry=retry_if_exception(is_transient_error),
        reraise=True
    )
    async def _execute_post(self, client: httpx.AsyncClient, payload: dict) -> httpx.Response:
        """Núcleo blindado. Delega o I/O para a biblioteca Tenacity lidar com o Jitter e o Backoff."""
        response = await client.post(
            self.base_url, 
            headers=self.headers, 
            data=payload, 
            timeout=self.timeout
        )
        response.raise_for_status()
        return response

    async def fetch_resultados_por_data(self, client: httpx.AsyncClient, data_alvo: str) -> Optional[RespostaBuscaSchema]:
        """Extrai os dados da API respeitando rigorosamente o contrato de esquema de entrada/saída."""
        req_payload = BuscaResultadoRequest(dtSorteio=data_alvo).model_dump()
        
        try:
            response = await self._execute_post(client, req_payload)
            return RespostaBuscaSchema(**response.json())
            
        # OTIMIZAÇÃO MAX: Logging Estruturado (JSON-Ready) por domínios de erro
        except httpx.HTTPStatusError as err:
            logger.error(
                "http_status_error", 
                extra={"data_alvo": data_alvo, "status_code": err.response.status_code, "url": self.base_url}
            )
        except httpx.RequestError as err:
            logger.error(
                "http_network_timeout_ou_drop", 
                extra={"data_alvo": data_alvo, "error_type": type(err).__name__, "url": self.base_url}
            )
        except (ValueError, ValidationError) as err:
            logger.error(
                "contract_violation_error", 
                extra={"data_alvo": data_alvo, "error": str(err), "url": self.base_url}
            )
            
        return None