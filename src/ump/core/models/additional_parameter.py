from pydantic import BaseModel
from typing import List, Optional


from typing import List, Union

class AdditionalParameter(BaseModel):
    name: str
    value: List[Union[str, float, int, list, dict]]
