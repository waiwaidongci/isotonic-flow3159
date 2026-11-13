from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReadingInput(BaseModel):
 model_config = ConfigDict(allow_inf_nan=False)
 specimen_ref: str = Field(min_length=1, max_length=80)
 pressure: float = Field(ge=0, le=1000000)
 measurement_note: str = Field(default='', max_length=1000)
 production_batch: str | None = Field(default=None, max_length=80)

 @field_validator('production_batch')
 @classmethod
 def blank_batch_is_missing(cls, value):
  if value is None:
   return None
  value = value.strip()
  return value or None


class ReadingPatch(BaseModel):
 model_config = ConfigDict(allow_inf_nan=False)
 pressure: float = Field(ge=0, le=1000000)
 measurement_note: str = Field(default='', max_length=1000)
