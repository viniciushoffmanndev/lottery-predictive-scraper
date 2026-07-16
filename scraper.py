import asyncio
import httpx
import pandas as pd
import itertools
from collections import Counter
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, date
from typing import List
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from database import init_db, AsyncSessionLocal
from models import ResultadoLoteria, PredicaoLoteria

# ---------------------------------------------------------
# 1. MODELOS DO PYDANTIC
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
# 2. MOTOR PREDITIVO AUTOMÁTICO (GRUPOS)
# ---------------------------------------------------------
TABELA_BICHOS = {
    1: "AVESTRUZ", 2: "ÁGUIA", 3: "BURRO", 4: "BORBOLETA", 5: "CACHORRO",
    6: "CABRA", 7: "CARNEIRO", 8: "CAMELO", 9: "COBRA", 10: "COELHO",
    11: "CAVALO", 12: "ELEFANTE", 13: "GALO", 14: "GATO", 15: "JACARÉ",
    16: "LEÃO", 17: "MACACO", 18: "PORCO", 19: "PAVÃO", 20: "PERU",
    21: "TOURO", 22: "TIGRE", 23: "URSO", 24: "VEADO", 25: "VACA"
}

def converter_para_grupo(dezena_str):
    try:
        dezena_int = int(dezena_str)
        if dezena_int == 0:
            return 25
        return ((dezena_int - 1) // 4) + 1
    except ValueError:
        return None

async def recalcular_predicoes(session):
    """Lê o histórico recente de 15 dias e atualiza a inteligência de Duques de Grupo."""
    print("\n🧠 [IA] Iniciando recalculo automatizado das predições de GRUPOS...")
    
    res = await session.execute(select(ResultadoLoteria))
    df = pd.DataFrame([item.__dict__ for item in res.scalars().all()])
    if df.empty:
        return

    df['data_hora'] = pd.to_datetime(df['data_hora'])
    df['dezena'] = df['resultado'].str[-2:]
    df['grupo'] = df['dezena'].apply(converter_para_grupo)
    df['bicho'] = df['grupo'].map(TABELA_BICHOS)

    data_recente = df['data_hora'].max()
    data_limite = data_recente - pd.Timedelta(days=15)
    df_15_dias = df[df['data_hora'] >= data_limite].copy()

    # O alvo preditivo padrão é o dia atual (ou o próximo se passar das 23h)
    data_alvo = date.today()
    if data_recente.hour >= 23:
        data_alvo = data_alvo + timedelta(days=1)

    for loteria in ['Nacional', '26 da Sorte']:
        df_loteria = df_15_dias[df_15_dias['no_loteria'] == loteria]
        if df_loteria.empty:
            continue
            
        sorteios = df_loteria.groupby('data_hora')['bicho'].unique()
        frequencia_casais = Counter()
        
        for bichos in sorteios:
            validos = [b for b in bichos if b]
            if len(validos) >= 2:
                pares = list(itertools.combinations(sorted(validos), 2))
                frequencia_casais.update(pares)
                
        top_3 = frequencia_casais.most_common(3)
        
        for i, (casal, freq) in enumerate(top_3, 1):
            palpite_str = f"{casal[0]} & {casal[1]}"
            
            stmt = insert(PredicaoLoteria).values(
                data_referencia=data_alvo,
                no_loteria=loteria,
                tipo_predicao='Duque de Grupo',
                ranking=i,
                palpite=palpite_str
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'no_loteria', 'tipo_predicao', 'ranking'],
                set_=dict(palpite=palpite_str)
            )
            await session.execute(stmt)
            
        print(f"   🔮 [IA] Duques de Grupo da {loteria} atualizados para {data_alvo.strftime('%d/%m/%Y')}!")

# ---------------------------------------------------------
# 2.1 MOTOR PREDITIVO AUTOMÁTICO (TERNO DE DEZENA)
# ---------------------------------------------------------
async def recalcular_ternos_dezena(session):
    """Lê o histórico recente de 15 dias e gera o Top 3 de Ternos de Dezena no NeonDB."""
    print("\n🎯 [IA] Iniciando recalculo automatizado de TERNOS DE DEZENA...")
    
    res = await session.execute(select(ResultadoLoteria))
    df = pd.DataFrame([item.__dict__ for item in res.scalars().all()])
    if df.empty:
        return

    df['data_hora'] = pd.to_datetime(df['data_hora'])
    # Isola a dezena garantindo que sempre tenha 2 dígitos numéricos corretos (ex: '05')
    df['dezena'] = df['resultado'].astype(str).str.zfill(2).str[-2:]

    data_recente = df['data_hora'].max()
    data_limite = data_recente - pd.Timedelta(days=15)
    df_15_dias = df[df['data_hora'] >= data_limite].copy()

    # O alvo preditivo padrão é o dia atual (ou o próximo se passar das 23h)
    data_alvo = date.today()
    if data_recente.hour >= 23:
        data_alvo = data_alvo + timedelta(days=1)

    for loteria in ['Nacional', '26 da Sorte']:
        df_loteria = df_15_dias[df_15_dias['no_loteria'] == loteria]
        if df_loteria.empty:
            continue
            
        # Agrupa as dezenas únicas de cada sorteio do mesmo horário
        sorteios = df_loteria.groupby('data_hora')['dezena'].unique()
        frequencia_ternos = Counter()
        
        for dezenas in sorteios:
            validas = [d for d in dezenas if d and d.isdigit()]
            # Só faz o cálculo combinatório se o sorteio teve pelo menos 3 dezenas diferentes
            if len(validas) >= 3:
                # Cria todos os grupos de 3 possíveis naquele sorteio
                ternos = list(itertools.combinations(sorted(validas), 3))
                frequencia_ternos.update(ternos)
                
        # Pega os 3 Ternos mais repetidos na janela
        top_3 = frequencia_ternos.most_common(3)
        
        for i, (terno, freq) in enumerate(top_3, 1):
            palpite_str = f"{terno[0]} & {terno[1]} & {terno[2]}"
            
            # Comando de Upsert para a nova predição
            stmt = insert(PredicaoLoteria).values(
                data_referencia=data_alvo,
                no_loteria=loteria,
                tipo_predicao='Terno de Dezena',
                ranking=i,
                palpite=palpite_str
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'no_loteria', 'tipo_predicao', 'ranking'],
                set_=dict(palpite=palpite_str)
            )
            await session.execute(stmt)
            
        print(f"   🎯 [IA] Ternos de Dezena da {loteria} atualizados para {data_alvo.strftime('%d/%m/%Y')}!")

# ---------------------------------------------------------
# 3. FUNÇÃO DE INSERÇÃO NO BANCO DE DADOS (ATUALIZADA COM AMARRAÇÃO)
# ---------------------------------------------------------
async def salvar_no_banco(dados_pydantic: List[ResultadoLoteriaSchema]):
    async with AsyncSessionLocal() as session:
        valores = []
        for item in dados_pydantic:
            # Extrai as duas últimas posições do resultado para calcular e salvar a amarração
            dezena_str = str(item.resultado).zfill(2)[-2:]
            grupo_calculado = converter_para_grupo(dezena_str)

            valores.append({
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
                "tempo_restante_segundos": item.tempo_restante_segundos,
                "grupo": grupo_calculado # Grava a amarração do ID do Grupo diretamente na tabela!
            })
        
        try:
            stmt = insert(ResultadoLoteria).values(valores)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['id_loteria', 'data_hora', 'premio']
            )
            await session.execute(stmt)
            await session.commit()
            print("✅ Lote processado! Registros novos salvos com relacionamento, duplicatas ignoradas.")
        except Exception as erro:
            await session.rollback()
            print(f"❌ Falha ao salvar no banco: {erro}")

# ---------------------------------------------------------
# 4. FUNÇÃO DE BUSCA REFATORADA
# ---------------------------------------------------------
async def buscar_resultados_por_data(client: httpx.AsyncClient, data_sorteio: str):
    url = "https://resultadonacional.com/resultado/busca"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://resultadonacional.com",
        "referer": "https://resultadonacional.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-requested-with": "XMLHttpRequest"
    }
    payload = {"dtSorteio": data_sorteio, "horario": ""}
    
    print(f"🔎 Buscando resultados para a data: {data_sorteio}...")
    try:
        resposta = await client.post(url, headers=headers, data=payload)
        resposta.raise_for_status()
        dados_validados = RespostaBuscaSchema(**resposta.json())
        
        if dados_validados.success and dados_validados.data:
            await salvar_no_banco(dados_validados.data)
        else:
            print(f"⚠️ Nenhum resultado encontrado para {data_sorteio}.")
            
    except Exception as erro:
        print(f"❌ Erro na data {data_sorteio}: {erro}")

# ---------------------------------------------------------
# 5. ORQUESTRADOR DE HISTÓRICO
# ---------------------------------------------------------
async def extrair_historico(dias_para_voltar: int = 2):
    hoje = datetime.now()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(dias_para_voltar):
            data_alvo = hoje - timedelta(days=i)
            data_formatada = data_alvo.strftime("%d/%m/%Y")
            await buscar_resultados_por_data(client, data_formatada)
            await asyncio.sleep(1.5)
            print("-" * 50)

# ---------------------------------------------------------
# 6. ORQUESTRADOR PRINCIPAL
# ---------------------------------------------------------
async def main():
    await init_db()
    
    # 1º Passo: ATUALIZAÇÃO INCREMENTAL 
    # Em vez de 60, agora ele busca apenas Hoje (0) e Ontem (1)
    # Isso deixa o script extremamente rápido (roda em 2 segundos!)
    await extrair_historico(dias_para_voltar=2)
    
    # 2º Passo: Com o banco atualizado com o último horário, recalcula a inteligência
    async with AsyncSessionLocal() as session:
        await recalcular_predicoes(session)         # Recalcula Duques de Grupo
        await recalcular_ternos_dezena(session)     # Recalcula Ternos de Dezena
        await session.commit()
        
    print("🚀 Fim da rotina! Banco atualizado de forma incremental e Inteligências renovadas.")

if __name__ == "__main__":
    asyncio.run(main())