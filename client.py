import logging
import httpx
from typing import Optional
from pydantic import ValidationError  # ✅ ADICIONADO: Tratamento explícito de quebra de contrato
from schemas import RespostaBuscaSchema

logger = logging.getLogger(__name__)

class ResultadoNacionalClient:
    """Cliente HTTP resiliente focado na extração e parsing de dados brutos da API."""
    
    def __init__(self, base_url: str = "https://resultadonacional.com"):
        self.base_url = f"{base_url.rstrip('/')}/resultado/busca"
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://resultadonacional.com",
            "referer": "https://resultadonacional.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "x-requested-with": "XMLHttpRequest"
        }
        # Configuração enterprise de limites de concorrência para evitar rate-limits e socket exhaustion
        self.limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async def fetch_resultados_por_data(self, client: httpx.AsyncClient, data_alvo: str) -> Optional[RespostaBuscaSchema]:
        payload = {"dtSorteio": data_alvo, "horario": ""}
        try:
            response = await client.post(self.base_url, headers=self.headers, data=payload, timeout=10.0)
            response.raise_for_status()
            return RespostaBuscaSchema(**response.json())
        except httpx.HTTPError:
            # ✅ OTIMIZADO: Separação entre falha de rede...
            logger.exception(f"Falha de conectividade ou Timeout ao buscar a data: {data_alvo}")
        except (ValueError, ValidationError):
            # ✅ OTIMIZADO: ...e falha de quebra de payload/parsing da API terceira
            logger.exception(f"Quebra de contrato ou JSON inválido recebido para a data: {data_alvo}")
            
        return None