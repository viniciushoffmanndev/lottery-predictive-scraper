from pydantic import BaseModel, Field, ConfigDict  # ✅ ADICIONADO: ConfigDict
from datetime import datetime

class ResultadoLoteriaSchema(BaseModel):
    # ✅ OTIMIZADO: Permite que o modelo seja instanciado usando as aliases OR o nome do campo
    model_config = ConfigDict(populate_by_name=True)

    data_hora: datetime = Field(alias="DATA_HORA")
    horario: str = Field(alias="HORARIO")
    dt_sorteio: str = Field(alias="DT_SORTEIO")
    resultado: str = Field(alias="RESULTADO")
    premio: int = Field(alias="PREMIO")
    tipo_resultado: str = Field(alias="TIPO_RESULTADO")
    id_concurso: int = Field(alias="ID_CONCURSO")
    no_loteria: str = Field(alias="NO_LOTERIA")
    id_loteria: int = Field(alias="ID_LOTERIA")
    tempo_restante_segundos: int = Field(alias="TEMPO_RESTANTE_SEGUNDOS")

class RespostaBuscaSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    success: bool
    data: list[ResultadoLoteriaSchema]  # ✅ OTIMIZADO: Uso de 'list' built-in em vez de typing.List