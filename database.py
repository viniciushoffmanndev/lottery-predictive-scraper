import os
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base

# Carrega as variáveis do arquivo .env para a memória
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi encontrada no arquivo .env.")

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dados de semente estáticos baseados na Tabela Oficial de Bichos, Grupos e Dezenas
BICHOS_SEED = [
    {"grupo": 1, "bicho": "AVESTRUZ", "dezenas": ["01", "02", "03", "04"]},
    {"grupo": 2, "bicho": "ÁGUIA", "dezenas": ["05", "06", "07", "08"]},
    {"grupo": 3, "bicho": "BURRO", "dezenas": ["09", "10", "11", "12"]},
    {"grupo": 4, "bicho": "BORBOLETA", "dezenas": ["13", "14", "15", "16"]},
    {"grupo": 5, "bicho": "CACHORRO", "dezenas": ["17", "18", "19", "20"]},
    {"grupo": 6, "bicho": "CABRA", "dezenas": ["21", "22", "23", "24"]},
    {"grupo": 7, "bicho": "CARNEIRO", "dezenas": ["25", "26", "27", "28"]},
    {"grupo": 8, "bicho": "CAMELO", "dezenas": ["29", "30", "31", "32"]},
    {"grupo": 9, "bicho": "COBRA", "dezenas": ["33", "34", "35", "36"]},
    {"grupo": 10, "bicho": "COELHO", "dezenas": ["37", "38", "39", "40"]},
    {"grupo": 11, "bicho": "CAVALO", "dezenas": ["41", "42", "43", "44"]},
    {"grupo": 12, "bicho": "ELEFANTE", "dezenas": ["45", "46", "47", "48"]},
    {"grupo": 13, "bicho": "GALO", "dezenas": ["49", "50", "51", "52"]},
    {"grupo": 14, "bicho": "GATO", "dezenas": ["53", "54", "55", "56"]},
    {"grupo": 15, "bicho": "JACARÉ", "dezenas": ["57", "58", "59", "60"]},
    {"grupo": 16, "bicho": "LEÃO", "dezenas": ["61", "62", "63", "64"]},
    {"grupo": 17, "bicho": "MACACO", "dezenas": ["65", "66", "67", "68"]},
    {"grupo": 18, "bicho": "PORCO", "dezenas": ["69", "70", "71", "72"]},
    {"grupo": 19, "bicho": "PAVÃO", "dezenas": ["73", "74", "75", "76"]},
    {"grupo": 20, "bicho": "PERU", "dezenas": ["77", "78", "79", "80"]},
    {"grupo": 21, "bicho": "TOURO", "dezenas": ["81", "82", "83", "84"]},
    {"grupo": 22, "bicho": "TIGRE", "dezenas": ["85", "86", "87", "88"]},
    {"grupo": 23, "bicho": "URSO", "dezenas": ["89", "90", "91", "92"]},
    {"grupo": 24, "bicho": "VEADO", "dezenas": ["93", "94", "95", "96"]},
    {"grupo": 25, "bicho": "VACA", "dezenas": ["97", "98", "99", "00"]}
]

async def init_db():
    """Cria tabelas no banco de dados e semeia a tabela de referência dos bichos."""
    print("Verificando a estrutura do banco de dados no NeonDB...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados estruturado com segurança!")

    # Rotina dinâmica de Seed
    from models import BichoGrupoDezena
    async with AsyncSessionLocal() as session:
        # Verifica se a tabela já possui registros
        res = await session.execute(select(BichoGrupoDezena))
        if not res.scalars().first():
            print("🌱 Semeando tabela_bicho_grupo_dezenas...")
            try:
                novos_bichos = [BichoGrupoDezena(**item) for item in BICHOS_SEED]
                session.add_all(novos_bichos)
                await session.commit()
                print("✅ Tabela de Bichos semeada com sucesso no NeonDB!")
            except Exception as e:
                await session.rollback()
                print(f"❌ Erro ao semear tabela de bichos: {e}")
        else:
            print("ℹ️ Tabela de referência de Bichos já possui dados. Pulando Seed.")