import asyncio
import httpx
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import List

# ---------------------------------------------------------
# 1. MODELOS DO PYDANTIC PARA VALIDAÇÃO E TIPAGEM
# ---------------------------------------------------------
class ResultadoLoteriaSchema(BaseModel):
    # Usamos o 'alias' para mapear a chave do JSON (MAIÚSCULA) para a nossa variável (minúscula)
    data_hora_formatado: str = Field(alias="DATA_HORA_FORMATADO")
    data_hora: datetime = Field(alias="DATA_HORA")
    dt_horario_sorteio: datetime = Field(alias="DT_HORARIO_SORTEIO")
    horario: str = Field(alias="HORARIO")
    dt_sorteio: str = Field(alias="DT_SORTEIO")
    resultado: str = Field(alias="RESULTADO")
    premio: int = Field(alias="PREMIO") # Pydantic converte a string "1" para o int 1
    tipo_resultado: str = Field(alias="TIPO_RESULTADO")
    id_concurso: int = Field(alias="ID_CONCURSO")
    no_loteria: str = Field(alias="NO_LOTERIA")
    no_apelido: str = Field(alias="NO_APELIDO")
    id_loteria: int = Field(alias="ID_LOTERIA")
    tempo_restante_segundos: int = Field(alias="TEMPO_RESTANTE_SEGUNDOS")

class RespostaBuscaSchema(BaseModel):
    success: bool
    data: List[ResultadoLoteriaSchema]

# ---------------------------------------------------------
# 2. FUNÇÃO ASSÍNCRONA DE BUSCA (HTTPX)
# ---------------------------------------------------------
async def buscar_resultados():
    url = "https://resultadonacional.com/resultado/busca"
    
    # Cabeçalhos baseados na sua captura de rede para evitar bloqueios
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://resultadonacional.com",
        "referer": "https://resultadonacional.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }
    
    # Payload capturado na aba de "Conteúdo"
    payload = {
        "dtSorteio": "15/07/2026",
        "horario": ""
    }
    
    print("Iniciando requisição assíncrona...")
    
    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(url, headers=headers, data=payload)
            resposta.raise_for_status() # Verifica se deu 200 OK
            
            # O httpx extrai o JSON bruto
            dados_json = resposta.json()
            
            # O Pydantic valida, converte e tipa os dados
            dados_validados = RespostaBuscaSchema(**dados_json)
            
            if dados_validados.success:
                print(f"✅ Sucesso! Foram encontrados {len(dados_validados.data)} resultados.\n")
                
                # Imprimindo os 3 primeiros para checarmos no console
                for item in dados_validados.data[:5]:
                    print(f"🎲 Loteria: {item.no_apelido}")
                    print(f"📅 Data/Hora (Convertido): {item.data_hora} (Tipo: {type(item.data_hora).__name__})")
                    print(f"🏆 Prêmio: {item.premio} | Resultado: {item.resultado}")
                    print("-" * 40)
            else:
                print("❌ A requisição foi feita, mas a API retornou success=False")
                
        except httpx.HTTPError as erro_http:
            print(f"❌ Erro de conexão HTTP: {erro_http}")
        except ValidationError as erro_pydantic:
            print(f"❌ Erro na validação dos dados JSON: {erro_pydantic}")

# ---------------------------------------------------------
# 3. EXECUÇÃO
# ---------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(buscar_resultados())