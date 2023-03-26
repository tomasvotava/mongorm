"""MongORM index"""

from enum import Enum
from typing import TYPE_CHECKING

import pymongo

if TYPE_CHECKING:
    from motor.core import AgnosticCollection


class MongoIndexType(Enum):
    """Mongo Index Type"""

    ASCENDING = pymongo.ASCENDING
    DESCENDING = pymongo.DESCENDING
    GEO2D = pymongo.GEO2D
    GEOSPHERE = pymongo.GEOSPHERE
    HASHED = pymongo.HASHED
    TEXT = pymongo.TEXT


# pylint: disable=too-many-instance-attributes
class MongoIndex:
    """A mongo index"""

    def __init__(
        self,
        field: str,
        ftype: MongoIndexType = MongoIndexType.ASCENDING,
        *,
        unique: bool = False,
        sparse: bool = True,
        expire_seconds: int | None = None,
        compound_with: dict[str, MongoIndexType] | None = None,
        name: str | None = None,
        comment: str | None = None
    ):
        self.field = field
        self.type = ftype
        self.unique = unique
        self.sparse = sparse
        self.compound_with = compound_with or {}
        self.expire_seconds = expire_seconds
        self.name = name
        self.comment = comment

    async def create(self, collection: "AgnosticCollection", **kwargs):
        """Create the index in the specified collection"""
        keys = [(self.field, self.type.value)]
        if self.compound_with:
            keys.extend(((field, ftype.value)) for field, ftype in self.compound_with.items())
        if self.name:
            kwargs.setdefault("name", self.name)
        if self.comment:
            kwargs.setdefault("comment", self.comment)
        if self.expire_seconds is not None:
            kwargs.setdefault("expireAfterSeconds", self.expire_seconds)
        kwargs.setdefault("unique", self.unique)
        kwargs.setdefault("sparse", self.sparse)

        return await collection.create_index(keys, **kwargs)
