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

from __future__ import annotations
import hashlib
from typing import Any, Mapping, NewType, Optional, Sequence, TypeAlias, Union
import nanoid  # type: ignore
from pydantic import BaseModel, ConfigDict
import semver  # type: ignore


def _without_dto_suffix(obj: Any, *args: Any) -> str:
    if isinstance(obj, str):
        name = obj
        if name.endswith("DTO"):
            return name[:-3]
        return name
    if isinstance(obj, type):
        name = obj.__name__
        if name.endswith("DTO"):
            return name[:-3]
        return name
    else:
        raise Exception("Invalid input to _without_dto_suffix()")


class DefaultBaseModel(BaseModel):
    """
    Base class for all Daneel Pydantic models.
    """

    model_config = ConfigDict(
        validate_default=True,
        model_title_generator=_without_dto_suffix,
    )


JSONSerializable: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    Mapping[str, "JSONSerializable"],
    Sequence["JSONSerializable"],
    Optional[str],
    Optional[int],
    Optional[float],
    Optional[bool],
    Optional[None],
    Optional[Mapping[str, "JSONSerializable"]],
    Optional[Sequence["JSONSerializable"]],
]

UniqueId = NewType("UniqueId", str)


class Version:
    String = NewType("String", str)

    @staticmethod
    def from_string(version_string: Version.String | str) -> Version:
        result = Version(major=0, minor=0, patch=0)
        result._v = semver.Version.parse(version_string)
        return result

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: Optional[str] = None,
    ) -> None:
        self._v = semver.Version(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
        )

    def to_string(self) -> Version.String:
        return Version.String(str(self._v))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._v == other._v

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._v < other._v

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._v > other._v


class ItemNotFoundError(Exception):
    def __init__(self, item_id: UniqueId, message: Optional[str] = None) -> None:
        if message:
            super().__init__(f"{message} (id='{item_id}')")
        else:
            super().__init__(f"Item '{item_id}' not found")


def generate_id() -> UniqueId:
    while True:
        new_id = nanoid.generate(size=10)
        if "-" not in (new_id[0], new_id[-1]) and "_" not in new_id:
            return UniqueId(new_id)


def md5_checksum(input: str) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input.encode("utf-8"))

    return md5_hash.hexdigest()
