import asyncio
import httpx
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import List

# Importações do nosso banco e modelos
from database import init_db, AsyncSessionLocal
from models import ResultadoLoteria

# ---------------------------------------------------------
# 1. MODELOS DO PYDANTIC (Mantidos)
# ---------------------------------------------------------
class ResultadoLoteriaSchema(BaseModel):
    data_hora_formatado: str = Field(alias="DATA_HORA_FORMATADO")
    data_hora: datetime = Field(alias="DATA_HORA")
    dt_horario_sorteio: datetime = Field(alias="DT_HORARIO_SORTEIO")
    horario: str = Field(alias="HORARIO")
    dt_sorteio: str = Field(alias="DT_SORTEIO")
    resultado: str = Field(alias="RESULTADO")
    premio: int = Field(alias="PREMIO")
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
# 2. FUNÇÃO DE INSERÇÃO NO BANCO DE DADOS
# ---------------------------------------------------------
async def salvar_no_banco(dados_pydantic: List[ResultadoLoteriaSchema]):
    print(f"Iniciando inserção de {len(dados_pydantic)} registros no NeonDB...")
    
    async with AsyncSessionLocal() as session:
        # Transformando a lista de Pydantic Models em SQLAlchemy Models
        registros_db = [
            ResultadoLoteria(
                data_hora=item.data_hora,
                dt_horario_sorteio=item.dt_horario_sorteio,
                horario=item.horario,
                dt_sorteio=item.dt_sorteio,
                resultado=item.resultado,
                premio=item.premio,
                tipo_resultado=item.tipo_resultado,
                id_concurso=item.id_concurso,
                no_loteria=item.no_loteria,
                no_apelido=item.no_apelido,
                id_loteria=item.id_loteria,
                tempo_restante_segundos=item.tempo_restante_segundos
            ) for item in dados_pydantic
        ]
        
        try:
            # Adiciona todos de uma vez e faz o commit
            session.add_all(registros_db)
            await session.commit()
            print("✅ Todos os dados foram salvos com sucesso no banco!")
        except Exception as erro:
            await session.rollback() # Em caso de erro, desfaz a transação
            print(f"❌ Falha ao salvar no banco: {erro}")

# ---------------------------------------------------------
# 3. FUNÇÃO DE BUSCA E INTEGRAÇÃO
# ---------------------------------------------------------
async def buscar_resultados():
    url = "https://resultadonacional.com/resultado/busca"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://resultadonacional.com",
        "referer": "https://resultadonacional.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }
    payload = {
        "dtSorteio": "15/07/2026",
        "horario": ""
    }
    
    print("Iniciando extração assíncrona da web...")
    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(url, headers=headers, data=payload)
            resposta.raise_for_status()
            
            dados_validados = RespostaBuscaSchema(**resposta.json())
            
            if dados_validados.success:
                # Chama a função para salvar os dados validados
                await salvar_no_banco(dados_validados.data)
            else:
                print("❌ API retornou falha (success=False).")
                
        except httpx.HTTPError as erro_http:
            print(f"❌ Erro HTTP: {erro_http}")
        except ValidationError as erro_pydantic:
            print(f"❌ Erro Pydantic: {erro_pydantic}")

# ---------------------------------------------------------
# 4. ORQUESTRADOR PRINCIPAL
# ---------------------------------------------------------
async def main():
    # Primeiro garante que as tabelas existem
    await init_db()
    # Depois faz a extração e inserção
    await buscar_resultados()

if __name__ == "__main__":
    asyncio.run(main())