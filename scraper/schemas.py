from enum import Enum
from datetime import datetime, date, time
from typing import Annotated, Any
from pydantic import (
    BaseModel, 
    Field, 
    ConfigDict, 
    PositiveInt, 
    NonNegativeInt, 
    StringConstraints, 
    field_validator
)

# ==============================================================================
# 📚 VOCABULÁRIOS FECHADOS (DOMAIN SETS)
# =========================================================================
class LoteriaNome(str, Enum):
    NACIONAL = "Nacional"
    SORTE26 = "26 da Sorte"

class TipoResultadoEnum(str, Enum):
    PTM = "PTM"
    PT = "PT"
    PPT = "PPT"
    PTN = "PTN"
    COR = "COR"
    FED = "FED"

# ==============================================================================
# ⚙️ ALIASES DE TIPAGEM ESTRUTURAL
# =========================================================================
ResultadoFormatado = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]

class ResultadoLoteriaSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data_hora: datetime = Field(alias="DATA_HORA")
    dt_sorteio: date = Field(alias="DT_SORTEIO")
    horario: time = Field(alias="HORARIO")
    
    # Validação estrutural reaproveitável
    resultado: ResultadoFormatado = Field(alias="RESULTADO")
    
    premio: PositiveInt = Field(alias="PREMIO")
    id_concurso: PositiveInt = Field(alias="ID_CONCURSO")
    id_loteria: PositiveInt = Field(alias="ID_LOTERIA")
    tempo_restante_segundos: NonNegativeInt = Field(alias="TEMPO_RESTANTE_SEGUNDOS")
    
    # Vocabulários centralizados em Enums
    tipo_resultado: TipoResultadoEnum = Field(alias="TIPO_RESULTADO")
    no_loteria: LoteriaNome = Field(alias="NO_LOTERIA")

    @field_validator("dt_sorteio", mode="before")
    @classmethod
    def parse_data_br(cls, v: Any) -> Any:
        if isinstance(v, str):
            try: 
                return datetime.strptime(v, "%d/%m/%Y").date()
            except ValueError: 
                pass
        return v
        
    @field_validator("horario", mode="before")
    @classmethod
    def parse_horario_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            try: 
                return datetime.strptime(v, "%H:%M").time()
            except ValueError: 
                pass
        return v


class RespostaBuscaSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    
    success: bool
    data: list[ResultadoLoteriaSchema]