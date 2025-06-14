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

from typing import cast
from typing_extensions import override

from Daneel.core.common import JSONSerializable
from Daneel.core.agents import Agent, AgentId, AgentStore
from Daneel.core.emissions import EmittedEvent, EventEmitter, EventEmitterFactory
from Daneel.core.sessions import (
    EventKind,
    EventSource,
    MessageEventData,
    SessionId,
    StatusEventData,
    ToolEventData,
)


class EventBuffer(EventEmitter):
    def __init__(self, emitting_agent: Agent) -> None:
        self.agent = emitting_agent
        self.events: list[EmittedEvent] = []

    @override
    async def emit_status_event(
        self,
        correlation_id: str,
        data: StatusEventData,
    ) -> EmittedEvent:
        event = EmittedEvent(
            source=EventSource.AI_AGENT,
            kind=EventKind.STATUS,
            correlation_id=correlation_id,
            data=cast(JSONSerializable, data),
        )

        self.events.append(event)

        return event

    @override
    async def emit_message_event(
        self,
        correlation_id: str,
        data: str | MessageEventData,
    ) -> EmittedEvent:
        if isinstance(data, str):
            message_data = cast(
                JSONSerializable,
                MessageEventData(
                    message=data,
                    participant={
                        "id": self.agent.id,
                        "display_name": self.agent.name,
                    },
                ),
            )
        else:
            message_data = cast(JSONSerializable, data)

        event = EmittedEvent(
            source=EventSource.AI_AGENT,
            kind=EventKind.MESSAGE,
            correlation_id=correlation_id,
            data=message_data,
        )

        self.events.append(event)

        return event

    @override
    async def emit_tool_event(
        self,
        correlation_id: str,
        data: ToolEventData,
    ) -> EmittedEvent:
        event = EmittedEvent(
            source=EventSource.SYSTEM,
            kind=EventKind.TOOL,
            correlation_id=correlation_id,
            data=cast(JSONSerializable, data),
        )

        self.events.append(event)

        return event


class EventBufferFactory(EventEmitterFactory):
    def __init__(self, agent_store: AgentStore) -> None:
        self._agent_store = agent_store

    @override
    async def create_event_emitter(
        self,
        emitting_agent_id: AgentId,
        session_id: SessionId,
    ) -> EventEmitter:
        _ = session_id
        agent = await self._agent_store.read_agent(emitting_agent_id)
        return EventBuffer(emitting_agent=agent)
