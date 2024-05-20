from typing import Any, TypedDict

# Stub classes here just for type-checking reasons... they are only moderately precise.
class VsiPayload(TypedDict):
  row_count: int
  data_array: list[tuple[str, float]]
class VectorSearchIndex:
  def similarity_search(self, **kwargs: list[str]|str|int|dict[str,list[str]]) -> dict[str, VsiPayload]: ...
  def __getattr__(self, name: str) -> Any: ... # incomplete
class VectorSearchClient: 
  def __init__(self, **kwargs: str|bool) -> None: ...
  def get_index(self, endpoint_name: str|None, index_name: str) -> VectorSearchIndex: ...
  def __getattr__(self, name: str) -> Any: ... # incomplete
