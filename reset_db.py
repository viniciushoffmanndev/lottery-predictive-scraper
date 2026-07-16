import asyncio
from database import engine
from models import Base

async def resetar_banco():
    print("⚠️ INICIANDO O RESET DO BANCO DE DADOS...")
    async with engine.begin() as conn:
        # Apaga todas as tabelas (CASCADE) para limpar sujeira e chaves estrangeiras
        print("🗑️ Apagando tabelas antigas...")
        await conn.run_sync(Base.metadata.drop_all)
        
        # Recria as tabelas do zero com a nova estrutura e colunas
        print("🏗️ Recriando tabelas com a nova estrutura...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("✅ Banco de dados zerado e estruturado com sucesso!")

if __name__ == "__main__":
    asyncio.run(resetar_banco())