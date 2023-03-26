"""MongORM exceptions"""

from typing import TYPE_CHECKING, Any, Mapping, Type

if TYPE_CHECKING:
    from mongorm.mongorm import BaseModel


class MongOrmException(Exception):
    """Mongo ORM-related exception"""


class DocumentNotFound(MongOrmException):
    """Document was not found"""

    def __init__(self, collection: str, query: dict[str, Any]):
        self.collection = collection
        self.query = query
        super().__init__(f"Document specified by query {query} was not found in collection '{collection}'")


class DuplicateDocument(MongOrmException):
    """Document is duplicate given unique index"""

    def __init__(self, collection: str, code: int | None, detail: Mapping[str, Any] | None = None):
        self.collection = collection
        self.code = code
        self.detail = detail
        super().__init__(f"Operation failed due to a duplicate key on collection '{collection}' - {code}: {detail}")


class MissingClientException(MongOrmException):
    """A model is missing client definition"""

    def __init__(self, model: "Type[BaseModel]"):
        super().__init__(f"Model {model} is missing Meta.client definition")
