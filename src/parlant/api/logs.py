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

from fastapi import APIRouter, WebSocket

from Daneel.adapters.loggers.websocket import WebSocketLogger


def create_router(
    websocket_logger: WebSocketLogger,
) -> APIRouter:
    router = APIRouter()

    @router.websocket("/logs")
    async def stream_logs(websocket: WebSocket) -> None:
        await websocket.accept()
        subscription = await websocket_logger.subscribe(websocket)
        await subscription.expiration.wait()

    return router
