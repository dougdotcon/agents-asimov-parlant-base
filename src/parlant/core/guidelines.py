# Copyright 2025 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Mapping, NewType, Optional, Sequence, cast
from typing_extensions import override, TypedDict, Self
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from Daneel.core.async_utils import ReaderWriterLock
from Daneel.core.common import ItemNotFoundError, JSONSerializable, UniqueId, Version, generate_id
from Daneel.core.persistence.common import ObjectId, Where
from Daneel.core.persistence.document_database import (
    BaseDocument,
    DocumentDatabase,
    DocumentCollection,
)
from Daneel.core.persistence.document_database_helper import (
    DocumentStoreMigrationHelper,
    DocumentMigrationHelper,
)
from Daneel.core.tags import TagId

GuidelineId = NewType("GuidelineId", str)


@dataclass(frozen=True)
class GuidelineContent:
    condition: str
    action: str


@dataclass(frozen=True)
class Guideline:
    id: GuidelineId
    creation_utc: datetime
    content: GuidelineContent
    enabled: bool
    tags: Sequence[TagId]
    metadata: Mapping[str, JSONSerializable]

    def __str__(self) -> str:
        return f"When {self.content.condition}, then {self.content.action}"

    def __hash__(self) -> int:
        return hash(self.id)


class GuidelineUpdateParams(TypedDict, total=False):
    condition: str
    action: str
    enabled: bool
    metadata: Mapping[str, JSONSerializable]


class GuidelineStore(ABC):
    @abstractmethod
    async def create_guideline(
        self,
        condition: str,
        action: str,
        metadata: Mapping[str, JSONSerializable] = {},
        creation_utc: Optional[datetime] = None,
        enabled: bool = True,
        tags: Optional[Sequence[TagId]] = None,
    ) -> Guideline: ...

    @abstractmethod
    async def list_guidelines(
        self,
        tags: Optional[Sequence[TagId]] = None,
    ) -> Sequence[Guideline]: ...

    @abstractmethod
    async def read_guideline(
        self,
        guideline_id: GuidelineId,
    ) -> Guideline: ...

    @abstractmethod
    async def delete_guideline(
        self,
        guideline_id: GuidelineId,
    ) -> None: ...

    @abstractmethod
    async def update_guideline(
        self,
        guideline_id: GuidelineId,
        params: GuidelineUpdateParams,
    ) -> Guideline: ...

    @abstractmethod
    async def find_guideline(
        self,
        guideline_content: GuidelineContent,
    ) -> Guideline: ...

    @abstractmethod
    async def upsert_tag(
        self,
        guideline_id: GuidelineId,
        tag_id: TagId,
        creation_utc: Optional[datetime] = None,
    ) -> bool: ...

    @abstractmethod
    async def remove_tag(
        self,
        guideline_id: GuidelineId,
        tag_id: TagId,
    ) -> None: ...

    @abstractmethod
    async def add_metadata(
        self,
        guideline_id: GuidelineId,
        metadata: Mapping[str, JSONSerializable],
    ) -> Guideline: ...

    @abstractmethod
    async def remove_metadata(
        self,
        guideline_id: GuidelineId,
        keys: Sequence[str],
    ) -> Guideline: ...


class GuidelineDocument_v0_1_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    guideline_set: str
    condition: str
    action: str


class GuidelineDocument_v0_2_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    guideline_set: str
    condition: str
    action: str
    enabled: bool


class GuidelineDocument_v0_3_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    condition: str
    action: str
    enabled: bool


class GuidelineDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    condition: str
    action: str
    enabled: bool
    metadata: Mapping[str, JSONSerializable]


class GuidelineTagAssociationDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    guideline_id: GuidelineId
    tag_id: TagId


async def guideline_document_converter_0_1_0_to_0_2_0(doc: BaseDocument) -> Optional[BaseDocument]:
    d = cast(GuidelineDocument_v0_1_0, doc)
    return GuidelineDocument_v0_2_0(
        id=d["id"],
        version=Version.String("0.2.0"),
        creation_utc=d["creation_utc"],
        guideline_set=d["guideline_set"],
        condition=d["condition"],
        action=d["action"],
        enabled=True,
    )


class GuidelineDocumentStore(GuidelineStore):
    VERSION = Version.from_string("0.4.0")

    def __init__(self, database: DocumentDatabase, allow_migration: bool = False) -> None:
        self._database = database
        self._collection: DocumentCollection[GuidelineDocument]
        self._tag_association_collection: DocumentCollection[GuidelineTagAssociationDocument]

        self._allow_migration = allow_migration
        self._lock = ReaderWriterLock()

    async def _document_loader(self, doc: BaseDocument) -> Optional[GuidelineDocument]:
        async def v0_3_0_to_v0_4_0(doc: BaseDocument) -> Optional[BaseDocument]:
            d = cast(GuidelineDocument_v0_3_0, doc)
            return GuidelineDocument(
                id=d["id"],
                version=Version.String("0.4.0"),
                creation_utc=d["creation_utc"],
                condition=d["condition"],
                action=d["action"],
                enabled=d["enabled"],
                metadata={},
            )

        async def v0_2_0_to_v_0_3_0(doc: BaseDocument) -> Optional[BaseDocument]:
            raise Exception(
                "This code should not be reached! Please run the 'Daneel-prepare-migration' script."
            )

        return await DocumentMigrationHelper[GuidelineDocument](
            self,
            {
                "0.1.0": guideline_document_converter_0_1_0_to_0_2_0,
                "0.2.0": v0_2_0_to_v_0_3_0,
                "0.3.0": v0_3_0_to_v0_4_0,
            },
        ).migrate(doc)

    async def _association_document_loader(
        self, doc: BaseDocument
    ) -> Optional[GuidelineTagAssociationDocument]:
        if doc["version"] == "0.3.0":
            d = cast(GuidelineTagAssociationDocument, doc)
            return GuidelineTagAssociationDocument(
                id=d["id"],
                version=Version.String("0.4.0"),
                creation_utc=d["creation_utc"],
                guideline_id=d["guideline_id"],
                tag_id=d["tag_id"],
            )

        if doc["version"] == "0.4.0":
            return cast(GuidelineTagAssociationDocument, doc)

        return None

    async def __aenter__(self) -> Self:
        async with DocumentStoreMigrationHelper(
            store=self,
            database=self._database,
            allow_migration=self._allow_migration,
        ):
            self._collection = await self._database.get_or_create_collection(
                name="guidelines",
                schema=GuidelineDocument,
                document_loader=self._document_loader,
            )

            self._tag_association_collection = await self._database.get_or_create_collection(
                name="guideline_tag_associations",
                schema=GuidelineTagAssociationDocument,
                document_loader=self._association_document_loader,
            )

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass

    def _serialize(
        self,
        guideline: Guideline,
    ) -> GuidelineDocument:
        return GuidelineDocument(
            id=ObjectId(guideline.id),
            version=self.VERSION.to_string(),
            creation_utc=guideline.creation_utc.isoformat(),
            condition=guideline.content.condition,
            action=guideline.content.action,
            enabled=guideline.enabled,
            metadata=guideline.metadata,
        )

    async def _deserialize(
        self,
        guideline_document: GuidelineDocument,
    ) -> Guideline:
        tag_ids = [
            d["tag_id"]
            for d in await self._tag_association_collection.find(
                {"guideline_id": {"$eq": guideline_document["id"]}}
            )
        ]

        return Guideline(
            id=GuidelineId(guideline_document["id"]),
            creation_utc=datetime.fromisoformat(guideline_document["creation_utc"]),
            content=GuidelineContent(
                condition=guideline_document["condition"], action=guideline_document["action"]
            ),
            enabled=guideline_document["enabled"],
            tags=[TagId(tag_id) for tag_id in tag_ids],
            metadata=guideline_document["metadata"],
        )

    @override
    async def create_guideline(
        self,
        condition: str,
        action: str,
        metadata: Mapping[str, JSONSerializable] = {},
        creation_utc: Optional[datetime] = None,
        enabled: bool = True,
        tags: Optional[Sequence[TagId]] = None,
    ) -> Guideline:
        async with self._lock.writer_lock:
            creation_utc = creation_utc or datetime.now(timezone.utc)

            guideline = Guideline(
                id=GuidelineId(generate_id()),
                creation_utc=creation_utc,
                content=GuidelineContent(
                    condition=condition,
                    action=action,
                ),
                enabled=enabled,
                tags=tags or [],
                metadata=metadata,
            )

            await self._collection.insert_one(
                document=self._serialize(
                    guideline=guideline,
                )
            )

            for tag in tags or []:
                await self._tag_association_collection.insert_one(
                    document={
                        "id": ObjectId(generate_id()),
                        "version": self.VERSION.to_string(),
                        "creation_utc": creation_utc.isoformat(),
                        "guideline_id": guideline.id,
                        "tag_id": tag,
                    }
                )

        return guideline

    @override
    async def list_guidelines(
        self,
        tags: Optional[Sequence[TagId]] = None,
    ) -> Sequence[Guideline]:
        filters: Where = {}

        async with self._lock.reader_lock:
            if tags is not None:
                if len(tags) == 0:
                    guideline_ids = {
                        doc["guideline_id"]
                        for doc in await self._tag_association_collection.find(filters={})
                    }
                    filters = (
                        {"$and": [{"id": {"$ne": id}} for id in guideline_ids]}
                        if guideline_ids
                        else {}
                    )
                else:
                    tag_filters: Where = {"$or": [{"tag_id": {"$eq": tag}} for tag in tags]}
                    tag_associations = await self._tag_association_collection.find(
                        filters=tag_filters
                    )
                    guideline_ids = {assoc["guideline_id"] for assoc in tag_associations}

                    if not guideline_ids:
                        return []

                    filters = {"$or": [{"id": {"$eq": id}} for id in guideline_ids]}

            return [
                await self._deserialize(d) for d in await self._collection.find(filters=filters)
            ]

    @override
    async def read_guideline(
        self,
        guideline_id: GuidelineId,
    ) -> Guideline:
        async with self._lock.reader_lock:
            guideline_document = await self._collection.find_one(
                filters={
                    "id": {"$eq": guideline_id},
                }
            )

        if not guideline_document:
            raise ItemNotFoundError(item_id=UniqueId(guideline_id))

        return await self._deserialize(guideline_document=guideline_document)

    @override
    async def delete_guideline(
        self,
        guideline_id: GuidelineId,
    ) -> None:
        async with self._lock.writer_lock:
            result = await self._collection.delete_one(
                filters={
                    "id": {"$eq": guideline_id},
                }
            )

            for doc in await self._tag_association_collection.find(
                filters={
                    "guideline_id": {"$eq": guideline_id},
                }
            ):
                await self._tag_association_collection.delete_one(
                    filters={"id": {"$eq": doc["id"]}}
                )

        if not result.deleted_document:
            raise ItemNotFoundError(item_id=UniqueId(guideline_id))

    @override
    async def update_guideline(
        self,
        guideline_id: GuidelineId,
        params: GuidelineUpdateParams,
    ) -> Guideline:
        async with self._lock.writer_lock:
            guideline_document = GuidelineDocument(
                {
                    **({"condition": params["condition"]} if "condition" in params else {}),
                    **({"action": params["action"]} if "action" in params else {}),
                    **({"enabled": params["enabled"]} if "enabled" in params else {}),
                }
            )

            result = await self._collection.update_one(
                filters={"id": {"$eq": guideline_id}},
                params=guideline_document,
            )

        assert result.updated_document

        return await self._deserialize(guideline_document=result.updated_document)

    @override
    async def find_guideline(
        self,
        guideline_content: GuidelineContent,
    ) -> Guideline:
        async with self._lock.reader_lock:
            guideline_document = await self._collection.find_one(
                filters={
                    "condition": {"$eq": guideline_content.condition},
                    "action": {"$eq": guideline_content.action},
                }
            )

        if not guideline_document:
            raise ItemNotFoundError(
                item_id=UniqueId(f"{guideline_content.condition}{guideline_content.action}")
            )

        return await self._deserialize(guideline_document=guideline_document)

    @override
    async def upsert_tag(
        self,
        guideline_id: GuidelineId,
        tag_id: TagId,
        creation_utc: Optional[datetime] = None,
    ) -> bool:
        async with self._lock.writer_lock:
            guideline = await self.read_guideline(guideline_id)

            if tag_id in guideline.tags:
                return False

            creation_utc = creation_utc or datetime.now(timezone.utc)

            association_document: GuidelineTagAssociationDocument = {
                "id": ObjectId(generate_id()),
                "version": self.VERSION.to_string(),
                "creation_utc": creation_utc.isoformat(),
                "guideline_id": GuidelineId(guideline_id),
                "tag_id": tag_id,
            }

            _ = await self._tag_association_collection.insert_one(document=association_document)

            guideline_document = await self._collection.find_one({"id": {"$eq": guideline_id}})

        if not guideline_document:
            raise ItemNotFoundError(item_id=UniqueId(guideline_id))

        return True

    @override
    async def remove_tag(
        self,
        guideline_id: GuidelineId,
        tag_id: TagId,
    ) -> None:
        async with self._lock.writer_lock:
            delete_result = await self._tag_association_collection.delete_one(
                {
                    "guideline_id": {"$eq": guideline_id},
                    "tag_id": {"$eq": tag_id},
                }
            )

            if delete_result.deleted_count == 0:
                raise ItemNotFoundError(item_id=UniqueId(tag_id))

            guideline_document = await self._collection.find_one({"id": {"$eq": guideline_id}})

        if not guideline_document:
            raise ItemNotFoundError(item_id=UniqueId(guideline_id))

    @override
    async def add_metadata(
        self,
        guideline_id: GuidelineId,
        metadata: Mapping[str, JSONSerializable],
    ) -> Guideline:
        async with self._lock.writer_lock:
            guideline_document = await self._collection.find_one({"id": {"$eq": guideline_id}})

            if not guideline_document:
                raise ItemNotFoundError(item_id=UniqueId(guideline_id))

            updated_metadata = {**guideline_document["metadata"], **metadata}

            result = await self._collection.update_one(
                filters={"id": {"$eq": guideline_id}},
                params={
                    "metadata": updated_metadata,
                },
            )

        assert result.updated_document

        return await self._deserialize(guideline_document=result.updated_document)

    @override
    async def remove_metadata(
        self,
        guideline_id: GuidelineId,
        keys: Sequence[str],
    ) -> Guideline:
        async with self._lock.writer_lock:
            guideline_document = await self._collection.find_one({"id": {"$eq": guideline_id}})

            if not guideline_document:
                raise ItemNotFoundError(item_id=UniqueId(guideline_id))

            updated_metadata = {
                k: v for k, v in guideline_document["metadata"].items() if k not in keys
            }

            result = await self._collection.update_one(
                filters={"id": {"$eq": guideline_id}},
                params={
                    "metadata": updated_metadata,
                },
            )

        assert result.updated_document

        return await self._deserialize(guideline_document=result.updated_document)
