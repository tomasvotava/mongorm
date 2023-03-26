"""Models"""

import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Optional, Sequence, Type, TypeVar, Union

import bson
import pydantic
import pymongo
import pymongo.errors
import pymongo.results
from motor.motor_asyncio import AsyncIOMotorClient

from mongorm.exceptions import DocumentNotFound, MissingClientException
from mongorm.index import MongoIndex

if TYPE_CHECKING:
    from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
    from pydantic.main import AbstractSetIntStr, MappingIntStrAny

ModelType = TypeVar("ModelType", bound="BaseModel")  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)


class SortDirection(Enum):
    """Sort direction"""

    ASCENDING = pymongo.ASCENDING
    DESCENDING = pymongo.DESCENDING


class ObjectId(bson.objectid.ObjectId):
    """Validated ObjectId to be used with pydantic"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, val) -> bson.objectid.ObjectId:
        """Validate ObjectId"""
        if isinstance(val, str):
            return bson.objectid.ObjectId(val)
        if isinstance(val, bson.objectid.ObjectId):
            return val
        raise TypeError(f"Expected str or ObjectId, got '{type(val)}'")


class BaseModel(pydantic.BaseModel):
    """Base model for all models"""

    class Meta:
        """Indexes and meta definition"""

        client: "MongORM | None" = None
        collection: str | None = None

    class Config:
        """json encoders"""

        json_encoders = {bson.objectid.ObjectId: str}
        allow_population_by_field_name = True

    @classmethod
    def list_indexes(cls) -> list[MongoIndex]:
        """List indexes associated with this model"""
        indexes: list[MongoIndex] = []
        for handle, index in cls.Meta.__dict__.items():
            if handle.startswith("__") or handle in ("client", "collection"):
                continue
            if not isinstance(index, MongoIndex):
                logger.warning(
                    "Skipping index specified by handle '%s' - is of type '%s', 'MongoIndex' was expected.",
                    handle,
                    type(index),
                )
                continue
            indexes.append(index)
        return indexes

    async def save(self):
        """Update document or insert a new one"""
        await self._get_client().save(self)

    @classmethod
    async def find_one(
        cls: Type[ModelType], oid: str | ObjectId | None = None, query: dict[str, Any] | None = None, **kwargs
    ) -> ModelType | None:
        """Find one either by its oid, by mongo filter query or by specified
        fields and their values using kwargs"""
        return await cls._get_client().find_one(cls, oid=oid, query=query, **kwargs)

    @classmethod
    async def find(
        cls: Type[ModelType],
        query: dict[str, Any] | None = None,
        sort: Sequence[tuple[str, "SortDirection"]] | None = None,
        skip: int = 0,
        limit: int = 0,
        **kwargs,
    ) -> AsyncGenerator[ModelType, None]:
        """Find all instances (or specify query to search)"""
        async for model in cls._get_client().find(cls, query=query, sort=sort, skip=skip, limit=limit, **kwargs):
            yield model

    @classmethod
    async def find_and_delete(cls: Type[ModelType], instance_or_oid: "BaseModel | str | ObjectId"):
        """Delete instance from collection"""
        oid: str | ObjectId
        if isinstance(instance_or_oid, BaseModel):
            oid = instance_or_oid.id
        else:
            oid = instance_or_oid
        await cls._get_client().delete(instance_or_model=cls, oid=oid)

    async def delete(self):
        """Delete current instance from collection"""
        await self._get_client().delete(self)

    async def exists(self) -> bool:
        """Check whether instance exists in the collection"""
        return (await self.find_one(oid=self.id)) is not None

    @classmethod
    def _get_client(cls) -> "MongORM":
        """Get client from model's Meta"""
        if not hasattr(cls.Meta, "client") or cls.Meta.client is None:
            raise MissingClientException(cls)
        return cls.Meta.client

    def json(
        self,
        *,
        include: Optional[Union["AbstractSetIntStr", "MappingIntStrAny"]] = None,
        exclude: Optional[Union["AbstractSetIntStr", "MappingIntStrAny"]] = None,
        by_alias: bool = False,
        skip_defaults: Optional[bool] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = True,
        encoder: Optional[Callable[[Any], Any]] = None,
        models_as_dict: bool = True,
        **dumps_kwargs: Any,
    ) -> str:
        """Override pydantic's json method to use str as default for ObjectId and exclude none by default"""
        encoder = encoder or str
        return super().json(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            encoder=encoder,
            models_as_dict=models_as_dict,
            **dumps_kwargs,
        )

    id: ObjectId = pydantic.Field(alias="_id", default_factory=bson.objectid.ObjectId)
    created: datetime = pydantic.Field(default_factory=datetime.utcnow)


class MongORM:
    """MongoDB abstraction to work with pydantic models"""

    def __init__(self, url: str, database: str):
        self.url = url
        self.client: "AgnosticClient" = AsyncIOMotorClient(self.url)
        self.database: "AgnosticDatabase" = self.client[database]

    def _get_collection(self, instance_or_model: BaseModel | Type[BaseModel]) -> "AgnosticCollection":
        """Get collection associated with instance (or model)"""
        if not hasattr(instance_or_model.Meta, "collection") or instance_or_model.Meta.collection is None:
            raise ValueError("Instance must be a valid root model with '__collection__' ClassVar")
        return self.database[instance_or_model.Meta.collection]

    async def find_one(
        self, model: Type[ModelType], oid: str | ObjectId | None = None, query: dict[str, Any] | None = None, **kwargs
    ) -> ModelType | None:
        """Find one either by its oid, by mongo filter query or by specifying
        fields and their values using kwargs"""
        collection = self._get_collection(model)
        query = query or {}
        if oid:
            if isinstance(oid, str):
                oid = ObjectId(oid)
            query.update({"_id": oid})
        if kwargs:
            query.update(kwargs)
        found = await collection.find_one(query)
        if found is None:
            return None
        return model(**found)

    # pylint: disable=too-many-arguments
    async def find(
        self,
        model: Type[ModelType],
        query: dict[str, Any] | None = None,
        sort: Sequence[tuple[str, SortDirection]] | None = None,
        skip: int = 0,
        limit: int = 0,
        **kwargs,
    ) -> AsyncGenerator[ModelType, None]:
        """Find all instances (or specify query to search)"""
        sort_by = [(field, direction.value) for field, direction in (sort or [("created", SortDirection.ASCENDING)])]
        query = query or {}
        query.update(kwargs)
        collection = self._get_collection(model)
        cursor = collection.find(
            filter=query,
            skip=skip,
            limit=limit,
            sort=sort_by,
        )
        async for item in cursor:
            yield model(**item)

    async def update(self, instance: ModelType):
        """Update existing document in the collection"""
        collection = self._get_collection(instance)
        query = {"_id": instance.id}
        updated = await collection.replace_one(filter=query, replacement=instance.dict(by_alias=True))
        if updated.matched_count == 0:
            raise DocumentNotFound(collection.name, query)

    async def save(self, instance: ModelType):
        """Update existing document or insert a new one"""
        collection = self._get_collection(instance)
        await collection.replace_one(filter={"_id": instance.id}, replacement=instance.dict(by_alias=True), upsert=True)

    async def delete(
        self,
        instance_or_model: BaseModel | Type[BaseModel],
        oid: str | ObjectId | None = None,
    ):
        """Delete document by its oid"""
        if isinstance(instance_or_model, BaseModel):
            oid = instance_or_model.id
        else:
            if not oid:
                raise ValueError("oid must be specified if not providing model instance")
            if isinstance(oid, str):
                oid = ObjectId(oid)
        collection = self._get_collection(instance_or_model)
        result: pymongo.results.DeleteResult = await collection.delete_one(filter={"_id": oid})
        if result.deleted_count == 0:
            raise DocumentNotFound(collection=collection.name, query={"_id": oid})

    async def create_schema(self, models: Sequence[BaseModel]):
        """Create collections and indexes for specified models"""
        for model in models:
            indexes = model.list_indexes()
            if not indexes:
                continue
            collection = self._get_collection(model)
            for ind in indexes:
                await ind.create(collection)
