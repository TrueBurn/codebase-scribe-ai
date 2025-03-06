from pydantic import BaseModel
from datetime import datetime

class ModelDetails(BaseModel):
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str

class OllamaModel(BaseModel):
    model: str
    modified_at: datetime
    digest: str
    size: int
    details: ModelDetails

class ListResponse(BaseModel):
    models: list[OllamaModel] 