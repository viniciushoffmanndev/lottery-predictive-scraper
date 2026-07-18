import asyncio
from sqlalchemy import text
from database_backup import AsyncSessionLocal

async def cirurgia_banco():
    print("🛠️ Iniciando atualização cirúrgica do banco de dados...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Adiciona a coluna temperatura
            await session.execute(text("ALTER TABLE predicoes_loterias ADD COLUMN temperatura VARCHAR(20) DEFAULT 'Neutro';"))
            print("   ✅ Coluna 'temperatura' adicionada com sucesso.")
            
            # 2. Derruba a trava antiga
            await session.execute(text("ALTER TABLE predicoes_loterias DROP CONSTRAINT uix_predicao_unica;"))
            print("   ✅ Trava antiga removida.")
            
            # 3. Cria a nova trava incluindo a temperatura
            await session.execute(text("ALTER TABLE predicoes_loterias ADD CONSTRAINT uix_predicao_unica UNIQUE (data_referencia, no_loteria, tipo_predicao, temperatura, ranking);"))
            print("   ✅ Nova trava de unicidade estabelecida.")
            
            await session.commit()
            print("🚀 Cirurgia concluída! O banco está pronto para o modelo Quente/Morno/Frio.")
        except Exception as e:
            await session.rollback()
            print(f"⚠️ Atenção (a coluna já deve existir): {e}")

if __name__ == "__main__":
    asyncio.run(cirurgia_banco())