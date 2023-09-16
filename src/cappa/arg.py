"""Define the external facing argument definition types provided by a user."""
from __future__ import annotations

import dataclasses
import typing
from collections.abc import Callable
from typing import Generic

from typing_extensions import Self
from typing_inspect import is_optional_type, is_union_type

from cappa.class_inspect import Field
from cappa.typing import MISSING, T, find_type_annotation, missing


@dataclasses.dataclass
class Arg(Generic[T]):
    short: bool | str = False
    long: bool | str = False
    count: bool = False
    required: bool | None = None
    default: T | None | MISSING = ...
    help: str | None = None

    parse: Callable[[str], T] | None = None

    @classmethod
    def collect(cls, field: Field, type_hint: type) -> tuple[Self, type]:
        arg, annotation = find_type_annotation(type_hint, cls)
        if arg is None:
            arg = cls()

        # Dataclass field metatdata takes precedence if it exists.
        field_metadata = extract_dataclass_metadata(field)
        assert not isinstance(field_metadata, Subcommand)

        if field_metadata:
            arg = field_metadata  # type: ignore

        if arg.default is ...:
            if field.default is not missing:
                arg = dataclasses.replace(arg, default=field.default)

            if field.default_factory is not missing:
                default = field.default_factory()
                arg = dataclasses.replace(arg, default=default)

        if arg.required is None and arg.default is missing:
            arg = dataclasses.replace(arg, required=not is_optional_type(annotation))

        return (arg, annotation)


@dataclasses.dataclass
class Subcommand:
    name: str | MISSING = ...
    required: bool | None = None
    types: typing.Iterable[type] | MISSING = ...
    help: str = ""

    @classmethod
    def collect(cls, field: Field, type_hint: type) -> Self | None:
        subcommand, annotation = find_type_annotation(type_hint, cls)
        field_metadata = extract_dataclass_metadata(field)
        if field_metadata:
            if not isinstance(field_metadata, Subcommand):
                return None

            subcommand = field_metadata  # type: ignore

        if subcommand is None:
            return None

        has_none = False
        kwargs: dict[str, typing.Any] = {}
        if subcommand.types is ...:
            if is_union_type(annotation):
                types = typing.get_args(annotation)
                if is_optional_type(annotation):
                    has_none = True
                    types = tuple([t for t in types if not is_optional_type(t)])
            else:
                types = (annotation,)

            kwargs["types"] = types

        if subcommand.required is None:
            kwargs["required"] = not has_none

        kwargs["name"] = field.name

        return dataclasses.replace(subcommand, **kwargs)


def extract_dataclass_metadata(field: Field) -> Arg | Subcommand | None:
    field_metadata = field.metadata.get("cappa")
    if not field_metadata:
        return None

    if not isinstance(field_metadata, (Arg, Subcommand)):
        raise ValueError(
            '`metadata={"cappa": <x>}` must be of type `Arg` or `Subcommand`'
        )

    return field_metadata
