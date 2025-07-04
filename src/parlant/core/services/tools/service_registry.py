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

from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Mapping, Optional, Sequence, cast
from typing_extensions import override, TypedDict, Self

import aiofiles
import httpx
from typing_extensions import Literal

from Daneel.core.async_utils import ReaderWriterLock
from Daneel.core.contextual_correlator import ContextualCorrelator
from Daneel.core.emissions import EventEmitterFactory
from Daneel.core.loggers import Logger
from Daneel.core.nlp.moderation import ModerationService
from Daneel.core.nlp.service import NLPService
from Daneel.core.persistence.document_database_helper import DocumentStoreMigrationHelper
from Daneel.core.services.tools.openapi import OpenAPIClient
from Daneel.core.services.tools.plugins import PluginClient
from Daneel.core.tools import LocalToolService, ToolService
from Daneel.core.common import ItemNotFoundError, Version, UniqueId
from Daneel.core.persistence.common import ObjectId
from Daneel.core.persistence.document_database import (
    BaseDocument,
    DocumentDatabase,
    DocumentCollection,
)


ToolServiceKind = Literal["openapi", "sdk", "local"]


class ServiceRegistry(ABC):
    @abstractmethod
    async def update_tool_service(
        self,
        name: str,
        kind: ToolServiceKind,
        url: str,
        source: Optional[str] = None,
        transient: bool = False,
    ) -> ToolService: ...

    @abstractmethod
    async def read_tool_service(
        self,
        name: str,
    ) -> ToolService: ...

    @abstractmethod
    async def list_tool_services(
        self,
    ) -> Sequence[tuple[str, ToolService]]: ...

    @abstractmethod
    async def read_moderation_service(
        self,
        name: str,
    ) -> ModerationService: ...

    @abstractmethod
    async def list_moderation_services(
        self,
    ) -> Sequence[tuple[str, ModerationService]]: ...

    @abstractmethod
    async def read_nlp_service(
        self,
        name: str,
    ) -> NLPService: ...

    @abstractmethod
    async def list_nlp_services(
        self,
    ) -> Sequence[tuple[str, NLPService]]: ...

    @abstractmethod
    async def delete_service(
        self,
        name: str,
    ) -> None: ...


class _ToolServiceDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    name: str
    kind: ToolServiceKind
    url: str
    source: Optional[str]


class ServiceDocumentRegistry(ServiceRegistry):
    VERSION = Version.from_string("0.1.0")

    def __init__(
        self,
        database: DocumentDatabase,
        event_emitter_factory: EventEmitterFactory,
        logger: Logger,
        correlator: ContextualCorrelator,
        nlp_services: Mapping[str, NLPService],
        allow_migration: bool = False,
    ):
        self._database = database
        self._tool_services_collection: DocumentCollection[_ToolServiceDocument]

        self._event_emitter_factory = event_emitter_factory
        self._logger = logger
        self._correlator = correlator
        self._nlp_services = nlp_services

        self._moderation_services: Mapping[str, ModerationService]
        self._exit_stack: AsyncExitStack
        self._running_services: dict[str, ToolService] = {}
        self._service_sources: dict[str, str] = {}

        self._allow_migration = allow_migration
        self._lock = ReaderWriterLock()

    def _cast_to_specific_tool_service_class(
        self,
        service: ToolService,
    ) -> OpenAPIClient | PluginClient:
        if isinstance(service, OpenAPIClient):
            return service
        else:
            return cast(PluginClient, service)

    async def _document_loader(self, doc: BaseDocument) -> Optional[_ToolServiceDocument]:
        if doc["version"] == "0.1.0":
            return cast(_ToolServiceDocument, doc)
        return None

    async def __aenter__(self) -> Self:
        async with DocumentStoreMigrationHelper(
            store=self,
            database=self._database,
            allow_migration=self._allow_migration,
        ):
            self._tool_services_collection = await self._database.get_or_create_collection(
                name="tool_services",
                schema=_ToolServiceDocument,
                document_loader=self._document_loader,
            )

        self._moderation_services = {
            name: await nlp_service.get_moderation_service()
            for name, nlp_service in self._nlp_services.items()
        }

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        documents = await self._tool_services_collection.find({})

        for document in documents:
            service = await self._deserialize_tool_service(document)
            await self._exit_stack.enter_async_context(
                self._cast_to_specific_tool_service_class(service)
            )
            self._running_services[document["name"]] = service
            if document["source"]:
                self._service_sources[document["name"]] = document["source"]

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        if self._exit_stack:
            await self._exit_stack.__aexit__(exc_type, exc_value, traceback)
            self._running_services.clear()
            self._service_sources.clear()
        return False

    async def _get_openapi_json_from_source(self, source: str) -> str:
        if source.startswith("http://") or source.startswith("https://"):
            async with httpx.AsyncClient() as client:
                response = await client.get(source)
                response.raise_for_status()
                return response.text
        else:
            async with aiofiles.open(source, "r") as f:
                return await f.read()

    def _serialize_tool_service(
        self,
        name: str,
        service: ToolService,
    ) -> _ToolServiceDocument:
        return _ToolServiceDocument(
            id=ObjectId(name),
            version=self.VERSION.to_string(),
            name=name,
            kind="openapi" if isinstance(service, OpenAPIClient) else "sdk",
            url=service.server_url
            if isinstance(service, OpenAPIClient)
            else cast(PluginClient, service).url,
            source=self._service_sources.get(name) if isinstance(service, OpenAPIClient) else None,
        )

    async def _deserialize_tool_service(self, document: _ToolServiceDocument) -> ToolService:
        if document["kind"] == "openapi":
            openapi_json = await self._get_openapi_json_from_source(cast(str, document["source"]))

            return OpenAPIClient(
                server_url=document["url"],
                openapi_json=openapi_json,
            )
        elif document["kind"] == "sdk":
            return PluginClient(
                url=document["url"],
                event_emitter_factory=self._event_emitter_factory,
                logger=self._logger,
                correlator=self._correlator,
            )
        else:
            raise ValueError("Unsupported ToolService kind.")

    @override
    async def update_tool_service(
        self,
        name: str,
        kind: ToolServiceKind,
        url: str,
        source: Optional[str] = None,
        transient: bool = False,
    ) -> ToolService:
        async with self._lock.writer_lock:
            service: ToolService

            if kind == "local":
                self._running_services[name] = LocalToolService()
                return self._running_services[name]
            elif kind == "openapi":
                assert source
                openapi_json = await self._get_openapi_json_from_source(source)
                service = OpenAPIClient(server_url=url, openapi_json=openapi_json)
                self._service_sources[name] = source
            else:
                service = PluginClient(
                    url=url,
                    event_emitter_factory=self._event_emitter_factory,
                    logger=self._logger,
                    correlator=self._correlator,
                )

            if name in self._running_services:
                await (
                    self._cast_to_specific_tool_service_class(self._running_services[name])
                ).__aexit__(None, None, None)

            await self._exit_stack.enter_async_context(
                self._cast_to_specific_tool_service_class(service)
            )

            self._running_services[name] = service

        await self._exit_stack.enter_async_context(
            self._cast_to_specific_tool_service_class(service)
        )

        self._running_services[name] = service

        if not transient:
            await self._tool_services_collection.update_one(
                filters={"name": {"$eq": name}},
                params=self._serialize_tool_service(name, service),
                upsert=True,
            )

        return service

    @override
    async def read_tool_service(
        self,
        name: str,
    ) -> ToolService:
        async with self._lock.reader_lock:
            if name not in self._running_services:
                raise ItemNotFoundError(item_id=UniqueId(name))

            return self._running_services[name]

    @override
    async def list_tool_services(
        self,
    ) -> Sequence[tuple[str, ToolService]]:
        async with self._lock.reader_lock:
            return list(self._running_services.items())

    @override
    async def read_moderation_service(
        self,
        name: str,
    ) -> ModerationService:
        if name not in self._moderation_services:
            raise ItemNotFoundError(item_id=UniqueId(name))

        return self._moderation_services[name]

    @override
    async def list_moderation_services(
        self,
    ) -> Sequence[tuple[str, ModerationService]]:
        async with self._lock.reader_lock:
            return list(self._moderation_services.items())

    @override
    async def read_nlp_service(
        self,
        name: str,
    ) -> NLPService:
        async with self._lock.reader_lock:
            if name not in self._nlp_services:
                raise ItemNotFoundError(item_id=UniqueId(name))

            return self._nlp_services[name]

    @override
    async def list_nlp_services(
        self,
    ) -> Sequence[tuple[str, NLPService]]:
        async with self._lock.reader_lock:
            return list(self._nlp_services.items())

    @override
    async def delete_service(self, name: str) -> None:
        async with self._lock.writer_lock:
            if name in self._running_services:
                if isinstance(self._running_services[name], LocalToolService):
                    del self._running_services[name]
                    return

                service = self._running_services[name]
                await (self._cast_to_specific_tool_service_class(service)).__aexit__(
                    None, None, None
                )
                del self._running_services[name]
                if name in self._service_sources:
                    del self._service_sources[name]

            result = await self._tool_services_collection.delete_one({"name": {"$eq": name}})

        if not result.deleted_count:
            raise ItemNotFoundError(item_id=UniqueId(name))
