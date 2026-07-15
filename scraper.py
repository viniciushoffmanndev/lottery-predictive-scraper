import asyncio
import httpx
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.dialects.postgresql import insert
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
# 2. FUNÇÃO DE INSERÇÃO NO BANCO DE DADOS (ATUALIZADA)
# ---------------------------------------------------------
async def salvar_no_banco(dados_pydantic: List[ResultadoLoteriaSchema]):
    async with AsyncSessionLocal() as session:
        # Transformamos em dicionários em vez de objetos instanciados para o bulk insert
        valores = [
            {
                "data_hora": item.data_hora,
                "dt_horario_sorteio": item.dt_horario_sorteio,
                "horario": item.horario,
                "dt_sorteio": item.dt_sorteio,
                "resultado": item.resultado,
                "premio": item.premio,
                "tipo_resultado": item.tipo_resultado,
                "id_concurso": item.id_concurso,
                "no_loteria": item.no_loteria,
                "no_apelido": item.no_apelido,
                "id_loteria": item.id_loteria,
                "tempo_restante_segundos": item.tempo_restante_segundos
            } for item in dados_pydantic
        ]
        
        try:
            # Prepara o comando de inserção
            stmt = insert(ResultadoLoteria).values(valores)
            
            # Aplica a regra: Se bater na nossa restrição única, apenas ignore
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['id_loteria', 'data_hora', 'premio']
            )
            
            await session.execute(stmt)
            await session.commit()
            print("✅ Lote processado! Registros novos salvos, duplicatas ignoradas.")
        except Exception as erro:
            await session.rollback()
            print(f"❌ Falha ao salvar no banco: {erro}")

# ---------------------------------------------------------
# 3. FUNÇÃO DE BUSCA REFATORADA (Recebe Data e Cliente)
# ---------------------------------------------------------
async def buscar_resultados_por_data(client: httpx.AsyncClient, data_sorteio: str):
    url = "https://resultadonacional.com/resultado/busca"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://resultadonacional.com",
        "referer": "https://resultadonacional.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }
    # Agora o payload usa a variável de data!
    payload = {
        "dtSorteio": data_sorteio,
        "horario": ""
    }
    
    print(f"🔎 Buscando resultados para a data: {data_sorteio}...")
    try:
        resposta = await client.post(url, headers=headers, data=payload)
        resposta.raise_for_status()
        
        dados_validados = RespostaBuscaSchema(**resposta.json())
        
        if dados_validados.success and dados_validados.data:
            await salvar_no_banco(dados_validados.data)
        else:
            print(f"⚠️ Nenhum resultado encontrado ou API retornou falha para {data_sorteio}.")
            
    except httpx.HTTPError as erro_http:
        print(f"❌ Erro HTTP na data {data_sorteio}: {erro_http}")
    except ValidationError as erro_pydantic:
        print(f"❌ Erro de validação Pydantic na data {data_sorteio}: {erro_pydantic}")

# ---------------------------------------------------------
# 4. ORQUESTRADOR DE HISTÓRICO (NOVO)
# ---------------------------------------------------------
async def extrair_historico(dias_para_voltar: int = 15):
    """Varre os últimos 'N' dias a partir de hoje e extrai os resultados."""
    hoje = datetime.now()
    
    # Criamos o client UMA VEZ e passamos adiante (melhor performance)
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(dias_para_voltar):
            # Subtrai os dias da data atual
            data_alvo = hoje - timedelta(days=i)
            # Formata para o padrão esperado pelo Payload: DD/MM/YYYY
            data_formatada = data_alvo.strftime("%d/%m/%Y")
            
            await buscar_resultados_por_data(client, data_formatada)
            
            # Pausa de 1.5 segundos entre as requisições para evitar bloqueios do Cloudflare
            await asyncio.sleep(1.5)
            print("-" * 50)

# ---------------------------------------------------------
# 5. ORQUESTRADOR PRINCIPAL
# ---------------------------------------------------------
async def main():
    await init_db()
    # Vamos rodar extraindo os últimos 5 dias como um teste inicial!
    await extrair_historico(dias_para_voltar=15)
    print("🚀 Fim da extração de histórico!")

if __name__ == "__main__":
    asyncio.run(main())