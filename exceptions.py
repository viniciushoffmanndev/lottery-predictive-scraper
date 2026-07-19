from dataclasses import dataclass

class DatabaseInitializationError(RuntimeError):
    """Lançada quando ocorre falha física, timeout ou erro de credenciais no SGBD."""
    pass

@dataclass
class MissingReference:
    """Estrutura rica para indexação em ferramentas de Observabilidade (APMs)."""
    name: str
    expected: int
    found: int

class MissingReferenceDataError(RuntimeError):
    """Lançada quando a infraestrutura não possui os dados de domínio necessários."""
    def __init__(self, missing_refs: list[MissingReference]):
        self.missing_refs = missing_refs  
        missing_list_str = "\n".join(
            f"- {ref.name} (Esperado: {ref.expected}, Encontrado: {ref.found})" 
            for ref in missing_refs
        )
        super().__init__(
            f"As seguintes referências de domínio não foram encontradas:\n{missing_list_str}\n\n"
            "Certifique-se de aplicar as migrações e cargas de semente do Alembic."
        )