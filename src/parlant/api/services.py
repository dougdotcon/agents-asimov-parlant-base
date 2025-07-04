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

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional, Sequence, TypeAlias, cast
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import Field

from Daneel.api.common import apigen_config, ExampleJson, ServiceNameField, ToolNameField
from Daneel.core.common import DefaultBaseModel
from Daneel.core.services.tools.plugins import PluginClient
from Daneel.core.tools import Tool, ToolParameterDescriptor
from Daneel.core.services.tools.openapi import OpenAPIClient
from Daneel.core.services.tools.service_registry import ServiceRegistry, ToolServiceKind
from Daneel.core.tools import ToolService

API_GROUP = "services"


class ToolServiceKindDTO(Enum):
    """
    The type of service integration available in the system.

    Attributes:
        "sdk": Native integration using the Daneel SDK protocol. Enables advanced features
            like bidirectional communication and streaming results.
        "openapi": Integration via OpenAPI specification. Simpler to set up but limited
            to basic request/response patterns.
    """

    SDK = "sdk"
    OPENAPI = "openapi"


class ToolParameterTypeDTO(Enum):
    """
    The supported data types for tool parameters.

    Each type corresponds to a specific JSON Schema type and validation rules.
    """

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"


ServiceParamsURLField: TypeAlias = Annotated[
    str,
    Field(
        description="Base URL for the service. Must include http:// or https:// scheme.",
        examples=["https://example.com/api/v1"],
    ),
]


sdk_service_params_example: ExampleJson = {"url": "https://email-service.example.com/api/v1"}


class SDKServiceParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": sdk_service_params_example},
):
    """
    Configuration parameters for SDK-based service integration.

    SDK services must implement the Daneel SDK protocol for advanced features
    like streaming and bidirectional communication.
    """

    url: ServiceParamsURLField


ServiceOpenAPIParamsSourceField: TypeAlias = Annotated[
    str,
    Field(
        description="""URL or filesystem path to the OpenAPI specification.
        For URLs, must be publicly accessible.
        For filesystem paths, the server must have read permissions.""",
        examples=["https://api.example.com/openapi.json", "/etc/Daneel/specs/example-api.yaml"],
    ),
]


openapi_service_params_example: ExampleJson = {
    "url": "https://email-service.example.com/api/v1",
    "source": "https://email-service.example.com/api/openapi.json",
}


class OpenAPIServiceParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": openapi_service_params_example},
):
    """
    Configuration parameters for OpenAPI-based service integration.

    OpenAPI services are integrated using their OpenAPI/Swagger specification,
    enabling automatic generation of client code and documentation.
    """

    url: ServiceParamsURLField
    source: ServiceOpenAPIParamsSourceField


ServiceUpdateSDKServiceParamsField: TypeAlias = Annotated[
    SDKServiceParamsDTO,
    Field(
        description="SDK service configuration parameters. Required when kind is 'sdk'.",
    ),
]

ServiceUpdateOpenAPIServiceParamsField: TypeAlias = Annotated[
    OpenAPIServiceParamsDTO,
    Field(
        description="OpenAPI service configuration parameters. Required when kind is 'openapi'.",
    ),
]


service_update_params_example: ExampleJson = {
    "kind": "openapi",
    "openapi": {
        "url": "https://email-service.example.com/api/v1",
        "source": "https://email-service.example.com/api/openapi.json",
    },
}


class ServiceUpdateParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": service_update_params_example},
):
    """
    Parameters for creating or updating a service integration.

    The appropriate params field (sdk or openapi) must be provided based on the
    service kind. Service tools become temporarily unavailable during updates
    and reconnect automatically.
    """

    kind: ToolServiceKindDTO
    sdk: Optional[ServiceUpdateSDKServiceParamsField] = None
    openapi: Optional[ServiceUpdateOpenAPIServiceParamsField] = None


EnumValueTypeDTO: TypeAlias = str | int

ToolParameterDescriptionField: TypeAlias = Annotated[
    str,
    Field(
        description="Detailed description of what the parameter does and how it should be used",
        examples=["Email address of the recipient", "Maximum number of retries allowed"],
    ),
]

ToolParameterEnumField: TypeAlias = Annotated[
    Sequence[EnumValueTypeDTO],
    Field(
        description="List of allowed values for string or integer parameters. If provided, the parameter value must be one of these options.",
        examples=[["high", "medium", "low"], [1, 2, 3, 5, 8, 13]],
    ),
]


tool_parameter_example: ExampleJson = {
    "type": "string",
    "description": "Priority level for the email",
    "enum": ["high", "medium", "low"],
}


class ToolParameterDTO(
    DefaultBaseModel,
    json_schema_extra={"example": tool_parameter_example},
):
    """
    Defines a parameter that can be passed to a tool.

    Parameters can have different types with optional constraints like enums.
    Each parameter can include a description to help users understand its purpose.
    """

    type: ToolParameterTypeDTO
    description: Optional[ToolParameterDescriptionField] = None
    enum: Optional[ToolParameterEnumField] = None


ToolCreationUTCField: TypeAlias = Annotated[
    datetime,
    Field(
        description="UTC timestamp when the tool was first registered with the system",
        examples=["2024-03-24T12:00:00Z"],
    ),
]

ToolDescriptionField: TypeAlias = Annotated[
    str,
    Field(
        description="Detailed description of the tool's purpose and behavior",
        examples=[
            "Sends an email to specified recipients with optional attachments",
            "Processes a payment transaction and returns confirmation details",
        ],
    ),
]

ToolParametersField: TypeAlias = Annotated[
    dict[str, ToolParameterDTO],
    Field(
        description="Dictionary mapping parameter names to their definitions",
        examples=[
            {
                "recipient": {"type": "string", "description": "Email address to send to"},
                "amount": {"type": "number", "description": "Payment amount in dollars"},
            }
        ],
    ),
]

ToolRequiredField: TypeAlias = Annotated[
    Sequence[str],
    Field(
        description="List of parameter names that must be provided when calling the tool",
        examples=[["recipient", "subject"], ["payment_id", "amount"]],
    ),
]


tool_example: ExampleJson = {
    "creation_utc": "2024-03-24T12:00:00Z",
    "name": "send_email",
    "description": "Sends an email to specified recipients with configurable priority",
    "parameters": {
        "to": {"type": "string", "description": "Recipient email address"},
        "subject": {"type": "string", "description": "Email subject line"},
        "body": {"type": "string", "description": "Email body content"},
        "priority": {
            "type": "string",
            "description": "Priority level for the email",
            "enum": ["high", "medium", "low"],
        },
    },
    "required": ["to", "subject", "body"],
}


class ToolDTO(
    DefaultBaseModel,
    json_schema_extra={"example": tool_example},
):
    """
    Represents a single function provided by an integrated service.

    Tools are the primary way for agents to interact with external services.
    Each tool has defined parameters and can be invoked when those parameters
    are satisfied.
    """

    creation_utc: ToolCreationUTCField
    name: ToolNameField
    description: ToolDescriptionField
    parameters: ToolParametersField
    required: ToolRequiredField


ServiceURLField: TypeAlias = Annotated[
    str,
    Field(
        description="Base URL where the service is hosted",
        examples=["https://api.example.com/v1", "https://email-service.internal:8080"],
    ),
]

ServiceToolsField: TypeAlias = Annotated[
    Sequence[ToolDTO],
    Field(
        default=None,
        description="List of tools provided by this service. Only included when retrieving a specific service.",
    ),
]


service_example: ExampleJson = {
    "name": "email-service",
    "kind": "openapi",
    "url": "https://email-service.example.com/api/v1",
    "tools": [
        {
            "creation_utc": "2024-03-24T12:00:00Z",
            "name": "send_email",
            "description": "Sends an email to specified recipients with configurable priority",
            "parameters": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
                "priority": {
                    "type": "string",
                    "description": "Priority level for the email",
                    "enum": ["high", "medium", "low"],
                },
            },
            "required": ["to", "subject", "body"],
        }
    ],
}


class ServiceDTO(
    DefaultBaseModel,
    json_schema_extra={"example": service_example},
):
    """
    Details about an integrated service and its available tools.

    Services can be either SDK-based for advanced features or OpenAPI-based
    for simpler integrations. The tools list is only included when retrieving
    a specific service, not in list operations.
    """

    name: ServiceNameField
    kind: ToolServiceKindDTO
    url: ServiceURLField
    tools: Optional[ServiceToolsField] = None


def _tool_parameters_to_dto(parameters: ToolParameterDescriptor) -> ToolParameterDTO:
    return ToolParameterDTO(
        type=ToolParameterTypeDTO(parameters["type"]),
        description=parameters["description"] if "description" in parameters else None,
        enum=parameters["enum"] if "enum" in parameters else None,
    )


def _tool_to_dto(tool: Tool) -> ToolDTO:
    return ToolDTO(
        creation_utc=tool.creation_utc,
        name=tool.name,
        description=tool.description,
        parameters={
            name: _tool_parameters_to_dto(descriptor)
            for name, (descriptor, _) in tool.parameters.items()
        },
        required=tool.required,
    )


def _get_service_kind(service: ToolService) -> ToolServiceKindDTO:
    return (
        ToolServiceKindDTO.OPENAPI if isinstance(service, OpenAPIClient) else ToolServiceKindDTO.SDK
    )


def _get_service_url(service: ToolService) -> str:
    return (
        service.server_url
        if isinstance(service, OpenAPIClient)
        else cast(PluginClient, service).url
    )


def _tool_service_kind_dto_to_tool_service_kind(dto: ToolServiceKindDTO) -> ToolServiceKind:
    return cast(
        ToolServiceKind,
        {
            ToolServiceKindDTO.OPENAPI: "openapi",
            ToolServiceKindDTO.SDK: "sdk",
        }[dto],
    )


def _tool_service_kind_to_dto(kind: ToolServiceKind) -> ToolServiceKindDTO:
    return {
        "openapi": ToolServiceKindDTO.OPENAPI,
        "sdk": ToolServiceKindDTO.SDK,
    }[kind]


ServiceNamePath: TypeAlias = Annotated[
    str,
    Path(
        description="Unique identifier for the service",
        examples=["email-service", "payment-processor"],
    ),
]


def create_router(service_registry: ServiceRegistry) -> APIRouter:
    """
    Creates a router instance for service-related operations.

    The router provides endpoints for managing service integrations,
    including both SDK and OpenAPI based services. It handles service
    registration, updates, and querying available tools.
    """
    router = APIRouter()

    @router.put(
        "/{name}",
        operation_id="update_service",
        response_model=ServiceDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Service successfully created or updated. The service may take a few seconds to become fully operational as it establishes connections.",
                "content": {"application/json": {"example": service_example}},
            },
            status.HTTP_404_NOT_FOUND: {"description": "No service found with the given name"},
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Invalid service configuration parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="create_or_update"),
    )
    async def update_service(
        name: ServiceNamePath,
        params: ServiceUpdateParamsDTO,
    ) -> ServiceDTO:
        """
        Creates a new service or updates an existing one.

        For SDK services:
        - Target server must implement the Daneel SDK protocol
        - Supports bidirectional communication and streaming

        For OpenAPI services:
        - Spec must be accessible and compatible with OpenAPI 3.0
        - Limited to request/response patterns

        Common requirements:
        - Service names must be unique and kebab-case
        - URLs must include http:// or https:// scheme
        - Updates cause brief service interruption while reconnecting
        """
        if params.kind == ToolServiceKindDTO.SDK:
            if not params.sdk:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Missing SDK parameters",
                )

            if not (params.sdk.url.startswith("http://") or params.sdk.url.startswith("https://")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Service URL is missing schema (http:// or https://)",
                )
        elif params.kind == ToolServiceKindDTO.OPENAPI:
            if not params.openapi:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Missing OpenAPI parameters",
                )
            if not (
                params.openapi.url.startswith("http://")
                or params.openapi.url.startswith("https://")
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Service URL is missing schema (http:// or https://)",
                )
        else:
            raise Exception("Should never logically get here")

        if params.kind == ToolServiceKindDTO.SDK:
            assert params.sdk
            url = params.sdk.url
            source = None
        elif params.kind == ToolServiceKindDTO.OPENAPI:
            assert params.openapi
            url = params.openapi.url
            source = params.openapi.source
        else:
            raise Exception("Should never logically get here")

        service = await service_registry.update_tool_service(
            name=name,
            kind=_tool_service_kind_dto_to_tool_service_kind(params.kind),
            url=url,
            source=source,
        )

        return ServiceDTO(
            name=name,
            kind=_get_service_kind(service),
            url=_get_service_url(service),
        )

    @router.delete(
        "/{name}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_service",
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Service successfully removed. Any active connections are terminated."
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Service not found. May have been deleted by another request."
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_service(
        name: ServiceNamePath,
    ) -> None:
        """
        Removes a service integration.

        Effects:
        - Active connections are terminated immediately
        - Service tools become unavailable to agents
        - Historical data about tool usage is preserved
        - Running operations may fail
        """
        await service_registry.read_tool_service(name)

        await service_registry.delete_service(name)

    @router.get(
        "",
        operation_id="list_services",
        response_model=Sequence[ServiceDTO],
        responses={
            status.HTTP_200_OK: {
                "description": """List of all registered services. Tool lists are not
                included for performance - use the retrieve endpoint to get tools
                for a specific service.""",
                "content": {"application/json": {"example": [service_example]}},
            }
        },
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_services() -> Sequence[ServiceDTO]:
        """
        Returns basic info about all registered services.

        For performance reasons, tool details are omitted from the response.
        Use the retrieve endpoint to get complete information including
        tools for a specific service.
        """
        return [
            ServiceDTO(
                name=name,
                kind=_get_service_kind(service),
                url=_get_service_url(service),
            )
            for name, service in await service_registry.list_tool_services()
            if type(service) in [OpenAPIClient, PluginClient]
        ]

    @router.get(
        "/{name}",
        operation_id="read_service",
        response_model=ServiceDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Service details including all available tools",
                "content": {"application/json": {"example": service_example}},
            },
            status.HTTP_404_NOT_FOUND: {"description": "Service not found"},
            status.HTTP_503_SERVICE_UNAVAILABLE: {
                "description": "Service is registered but currently unavailable"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_service(
        name: ServiceNamePath,
    ) -> ServiceDTO:
        """
        Get details about a specific service including all its tools.

        The response includes:
        - Basic service information (name, kind, URL)
        - Complete list of available tools
        - Parameter definitions for each tool

        Notes:
        - Tools list may be empty if service is still initializing
        - Parameters marked as required must be provided when using a tool
        - Enum parameters restrict inputs to the listed values
        """
        service = await service_registry.read_tool_service(name)

        return ServiceDTO(
            name=name,
            kind=_get_service_kind(service),
            url=_get_service_url(service),
            tools=[_tool_to_dto(t) for t in await service.list_tools()],
        )

    return router
