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
# 2. MOTOR PREDITIVO - FUNÇÕES AUXILIARES
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

def obter_dezenas_do_grupo(grupo_int):
    """Retorna as 4 dezenas de um grupo para montarmos os milhares."""
    if grupo_int == 25:
        return ['97', '98', '99', '00']
    inicio = (grupo_int - 1) * 4 + 1
    return [str(inicio + i).zfill(2) for i in range(4)]

# ---------------------------------------------------------
# 3. MOTOR PREDITIVO 1: DUQUES DE GRUPO (10 JOGOS ESTRUTURADOS)
# ---------------------------------------------------------
async def recalcular_duques_grupo(session):
    print("\n🧠 [IA] Iniciando Matriz de Duques de Grupo (Quentes, Mornos e Frios)...")
    
    res = await session.execute(select(ResultadoLoteria))
    df = pd.DataFrame([item.__dict__ for item in res.scalars().all()])
    if df.empty: return

    df['data_hora'] = pd.to_datetime(df['data_hora'])
    df['dezena'] = df['resultado'].str[-2:]
    df['grupo'] = df['dezena'].apply(converter_para_grupo)
    
    data_recente = df['data_hora'].max()
    data_alvo = date.today() if data_recente.hour < 23 else date.today() + timedelta(days=1)
    
    # Define as janelas de tempo (Macro = 15 dias, Curto = 3 dias)
    df_macro = df[df['data_hora'] >= (data_recente - pd.Timedelta(days=15))].copy()
    df_curto = df_macro[df_macro['data_hora'] >= (data_recente - pd.Timedelta(days=3))].copy()

    for loteria in ['Nacional', '26 da Sorte']:
        df_l_macro = df_macro[df_macro['no_loteria'] == loteria]
        df_l_curto = df_curto[df_curto['no_loteria'] == loteria]
        if df_l_macro.empty: continue
        
        # --- CÁLCULO QUENTES (Casais que saem juntos no radar curto) ---
        sorteios_curto = df_l_curto.groupby('data_hora')['grupo'].unique()
        freq_casais = Counter()
        for grupos in sorteios_curto:
            validos = [g for g in grupos if pd.notnull(g)]
            if len(validos) >= 2:
                freq_casais.update(list(itertools.combinations(sorted(validos), 2)))
        top_casais = [c for c, _ in freq_casais.most_common(4)]
        
        # --- CÁLCULO MORNOS E FRIOS (Frequência individual no macro) ---
        freq_grupos = df_l_macro['grupo'].value_counts().index.tolist()
        if len(freq_grupos) < 15: continue # Segurança contra falta de dados
        
        grupo_rei = freq_grupos[0]
        grupos_perifericos = freq_grupos[5:8] # Mornos (Dispersão)
        grupos_esquecidos = freq_grupos[-3:]  # Frios (Atrasados)
        
        # Montagem dos 10 Jogos
        jogos = []
        # 4 Quentes (Força bruta recente)
        for i, casal in enumerate(top_casais[:4]):
            jogos.append(('Quente', i+1, f"{str(casal[0]).zfill(2)} & {str(casal[1]).zfill(2)}"))
        
        # 3 Mornos (Cruzamento de dispersão)
        for i, g_perif in enumerate(grupos_perifericos):
            jogos.append(('Morno', i+1, f"{str(grupo_rei).zfill(2)} & {str(g_perif).zfill(2)}"))
            
        # 3 Frios (Ressaca/Atrasados)
        pares_frios = list(itertools.combinations(grupos_esquecidos, 2))
        for i, casal in enumerate(pares_frios[:3]):
            jogos.append(('Frio', i+1, f"{str(casal[0]).zfill(2)} & {str(casal[1]).zfill(2)}"))

        # Inserção no NeonDB com UPSERT e nova trava `temperatura`
        for temp, ranking, palpite in jogos:
            stmt = insert(PredicaoLoteria).values(
                data_referencia=data_alvo, no_loteria=loteria, tipo_predicao='Duque de Grupo',
                temperatura=temp, ranking=ranking, palpite=palpite
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'no_loteria', 'tipo_predicao', 'temperatura', 'ranking'],
                set_=dict(palpite=palpite)
            )
            await session.execute(stmt)
            
        print(f"   ✅ Duques de Grupo (10 Jogos) da {loteria} calculados!")

# ---------------------------------------------------------
# 4. MOTOR PREDITIVO 2: TERNOS DE MILHAR COM ROTAÇÃO
# ---------------------------------------------------------
async def recalcular_ternos_milhar(session):
    print("\n🎯 [IA] Iniciando Matriz de Ternos de Milhar (Rotação de Centenas)...")
    
    res = await session.execute(select(ResultadoLoteria))
    df = pd.DataFrame([item.__dict__ for item in res.scalars().all()])
    if df.empty: return

    df['data_hora'] = pd.to_datetime(df['data_hora'])
    df['resultado_str'] = df['resultado'].astype(str).str.zfill(4)
    df['milhar_inicio'] = df['resultado_str'].str[0]
    df['dezena'] = df['resultado_str'].str[-2:]
    df['grupo'] = df['dezena'].apply(converter_para_grupo)

    data_recente = df['data_hora'].max()
    data_alvo = date.today() if data_recente.hour < 23 else date.today() + timedelta(days=1)
    df_macro = df[df['data_hora'] >= (data_recente - pd.Timedelta(days=15))].copy()

    for loteria in ['Nacional', '26 da Sorte']:
        df_lot = df_macro[df_macro['no_loteria'] == loteria]
        if df_lot.empty: continue
        
        # Extrai a assinatura do servidor (Dígitos Iniciais Quentes, Mornos e Frios)
        freq_digitos = df_lot['milhar_inicio'].value_counts().index.tolist()
        if len(freq_digitos) < 3: continue
        
        digito_quente = freq_digitos[0]
        digito_morno = freq_digitos[1]
        digito_frio = freq_digitos[-1]
        
        # Extrai os grupos para servirem de âncora
        freq_grupos = df_lot['grupo'].value_counts().index.tolist()
        grupos_quentes = freq_grupos[:4]
        grupos_mornos = freq_grupos[4:7]
        grupos_frios = freq_grupos[-3:]

        # Função interna para gerar a Matriz de Rotação
        def girar_centena(digito, grupo, offset):
            dezenas = obter_dezenas_do_grupo(grupo)
            # Gira o dígito da centena (0 a 9) com base no offset para não ficar igual
            centenas = [str((offset + i) % 10) for i in range(3)]
            # Monta o terno: [Dígito Inicial] + [Centena Rotacionada] + [Dezena Fixa do Bicho]
            m1 = f"{digito}{centenas[0]}{dezenas[0]}"
            m2 = f"{digito}{centenas[1]}{dezenas[1]}"
            m3 = f"{digito}{centenas[2]}{dezenas[2]}"
            return f"{m1} - {m2} - {m3}"

        jogos = []
        # 🔥 4 Jogos Quentes (Dígito Rei + Grupos do Topo)
        for i, g in enumerate(grupos_quentes):
            jogos.append(('Quente', i+1, girar_centena(digito_quente, g, offset=i)))
            
        # 🫖 3 Jogos Mornos (2º Dígito + Grupos de Dispersão)
        for i, g in enumerate(grupos_mornos):
            jogos.append(('Morno', i+1, girar_centena(digito_morno, g, offset=i+4)))
            
        # ❄️ 3 Jogos Frios (Dígito Atrasado + Grupos Esquecidos)
        for i, g in enumerate(grupos_frios):
            jogos.append(('Frio', i+1, girar_centena(digito_frio, g, offset=i+7)))

        # Inserção no NeonDB
        for temp, ranking, palpite in jogos:
            stmt = insert(PredicaoLoteria).values(
                data_referencia=data_alvo, no_loteria=loteria, tipo_predicao='Terno de Milhar',
                temperatura=temp, ranking=ranking, palpite=palpite
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['data_referencia', 'no_loteria', 'tipo_predicao', 'temperatura', 'ranking'],
                set_=dict(palpite=palpite)
            )
            await session.execute(stmt)
            
        print(f"   ✅ Ternos de Milhar Rotacionados da {loteria} calculados!")

# ---------------------------------------------------------
# 5. FUNÇÃO DE INSERÇÃO NO BANCO DE DADOS
# ---------------------------------------------------------
async def salvar_no_banco(dados_pydantic: List[ResultadoLoteriaSchema]):
    async with AsyncSessionLocal() as session:
        valores = []
        for item in dados_pydantic:
            dezena_str = str(item.resultado).zfill(2)[-2:]
            grupo_calculado = converter_para_grupo(dezena_str)

            valores.append({
                "data_hora": item.data_hora, "dt_horario_sorteio": item.dt_horario_sorteio,
                "horario": item.horario, "dt_sorteio": item.dt_sorteio,
                "resultado": item.resultado, "premio": item.premio,
                "tipo_resultado": item.tipo_resultado, "id_concurso": item.id_concurso,
                "no_loteria": item.no_loteria, "no_apelido": item.no_apelido,
                "id_loteria": item.id_loteria, "tempo_restante_segundos": item.tempo_restante_segundos,
                "grupo": grupo_calculado 
            })
        
        try:
            stmt = insert(ResultadoLoteria).values(valores)
            stmt = stmt.on_conflict_do_nothing(index_elements=['id_loteria', 'data_hora', 'premio'])
            await session.execute(stmt)
            await session.commit()
            print("✅ Lote processado! Registros salvos.")
        except Exception as erro:
            await session.rollback()
            print(f"❌ Falha ao salvar no banco: {erro}")

# ---------------------------------------------------------
# 6. FUNÇÃO DE BUSCA E ORQUESTRADOR
# ---------------------------------------------------------
async def buscar_resultados_por_data(client: httpx.AsyncClient, data_sorteio: str):
    url = "https://resultadonacional.com/resultado/busca"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://resultadonacional.com", "referer": "https://resultadonacional.com/",
        "user-agent": "Mozilla/5.0", "x-requested-with": "XMLHttpRequest"
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

async def extrair_historico(dias_para_voltar: int = 320):
    hoje = datetime.now()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i in range(dias_para_voltar):
            data_formatada = (hoje - timedelta(days=i)).strftime("%d/%m/%Y")
            await buscar_resultados_por_data(client, data_formatada)
            await asyncio.sleep(1.5)

async def main():
    await init_db()
    await extrair_historico(dias_para_voltar=320)
    
    # Executa a inteligência estruturada de 10 Jogos
    async with AsyncSessionLocal() as session:
        await recalcular_duques_grupo(session)
        await recalcular_ternos_milhar(session)
        await session.commit()
        
    print("🚀 Fim da rotina! Banco atualizado e Matrizes de 10 Jogos geradas com sucesso.")

if __name__ == "__main__":
    asyncio.run(main())