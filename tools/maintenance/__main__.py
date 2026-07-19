import asyncio
import argparse
import logging
from db.database import close_db
from tools.maintenance.truncate import run_truncate
from tools.maintenance.hotfix import run_hotfix

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s")
logger = logging.getLogger("cli")

async def cli_entrypoint():
    parser = argparse.ArgumentParser(description="🛠️ Lottery Platform Maintenance CLI")
    parser.add_argument("--force", action="store_true", help="Ignora travas de segurança. Obrigatório em Produção.")
    parser.add_argument("--dry-run", action="store_true", help="Simula a execução sem efetivar transações no banco.")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ✅ CORRIGIDO: Remoção da variável não utilizada
    subparsers.add_parser("truncate", help="Expurga dados operacionais transacionais.")
    
    # Comando: HOTFIX (mantém a variável pois recebe um argumento na linha de baixo)
    hotfix_parser = subparsers.add_parser("hotfix", help="Aplica uma intervenção DML versionada no banco.")
    hotfix_parser.add_argument("name", type=str, help="Nome do hotfix registrado (ex: fix_ranking).")

    args = parser.parse_args()

    # 🔒 Trava de Segurança Padrão
    if not args.dry_run and not args.force:
        logger.error("🚫 OPERAÇÃO BLOQUEADA: Você deve usar '--dry-run' para simular ou '--force' para confirmar a execução destrutiva.")
        return

    try:
        if args.command == "truncate":
            await run_truncate(dry_run=args.dry_run)
        elif args.command == "hotfix":
            await run_hotfix(name=args.name, dry_run=args.dry_run)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(cli_entrypoint())