"""
    Using For Top Level module
"""
import logging
from typing import TYPE_CHECKING, Dict, Union, Any

from slither.core.compilation_unit import SlitherCompilationUnit
from slither.core.declarations.using_for_top_level import UsingForTopLevel
from slither.core.scope.scope import FileScope
from slither.core.solidity_types import TypeAliasTopLevel
from slither.core.declarations import (
    StructureTopLevel,
    EnumTopLevel,
)
from slither.solc_parsing.declarations.caller_context import CallerContextExpression
from slither.solc_parsing.solidity_types.type_parsing import parse_type
from slither.core.solidity_types.user_defined_type import UserDefinedType

if TYPE_CHECKING:
    from slither.solc_parsing.slither_compilation_unit_solc import SlitherCompilationUnitSolc

LOGGER = logging.getLogger("UsingForTopLevelSolc")


class UsingForTopLevelSolc(CallerContextExpression):  # pylint: disable=too-few-public-methods
    """
    UsingFor class
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        uftl: UsingForTopLevel,
        top_level_data: Dict,
        slither_parser: "SlitherCompilationUnitSolc",
    ):
        self._type_name = top_level_data["typeName"]
        self._global = top_level_data["global"]

        if "libraryName" in top_level_data:
            self._library_name = top_level_data["libraryName"]
        else:
            self._functions = top_level_data["functionList"]

        self._using_for = uftl
        self._slither_parser = slither_parser

    def analyze(self) -> None:
        type_name = parse_type(self._type_name, self)
        self._using_for.using_for[type_name] = []

        if hasattr(self, "_library_name"):
            library_name = parse_type(self._library_name, self)
            self._using_for.using_for[type_name].append(library_name)
            self._propagate_global(type_name)
        else:
            for f in self._functions:
                full_name_split = f["function"]["name"].split(".")
                if len(full_name_split) == 1:
                    # Top level function
                    function_name = full_name_split[0]
                    self._analyze_top_level_function(function_name, type_name)
                elif len(full_name_split) == 2:
                    # Library function
                    library_name = full_name_split[0]
                    function_name = full_name_split[1]
                    self._analyze_library_function(function_name, library_name, type_name)
                else:
                    # probably case if there is an import with an alias we don't handle it for now
                    # e.g. MyImport.MyLib.a
                    LOGGER.warning(
                        f"Using for directive for function {f['function']['name']} not supported"
                    )
                    continue

    def _analyze_top_level_function(
        self, function_name: str, type_name: Union[TypeAliasTopLevel, UserDefinedType]
    ) -> None:
        for tl_function in self.compilation_unit.functions_top_level:
            if tl_function.name == function_name:
                self._using_for.using_for[type_name].append(tl_function)
                self._propagate_global(type_name)
                break

    def _analyze_library_function(
        self,
        function_name: str,
        library_name: str,
        type_name: Union[TypeAliasTopLevel, UserDefinedType],
    ) -> None:
        found = False
        for c in self.compilation_unit.contracts:
            if found:
                break
            if c.name == library_name:
                for cf in c.functions:
                    if cf.name == function_name:
                        self._using_for.using_for[type_name].append(cf)
                        self._propagate_global(type_name)
                        found = True
                        break
        if not found:
            LOGGER.warning(f"Library {library_name} - function {function_name} not found")

    def _propagate_global(self, type_name: Union[TypeAliasTopLevel, UserDefinedType]) -> None:
        if self._global:
            for scope in self.compilation_unit.scopes.values():
                if isinstance(type_name, TypeAliasTopLevel):
                    for alias in scope.user_defined_types.values():
                        if alias == type_name:
                            scope.using_for_directives.add(self._using_for)
                elif isinstance(type_name, UserDefinedType):
                    self._propagate_global_UserDefinedType(scope, type_name)
                else:
                    LOGGER.error(
                        f"Error when propagating global using for {type_name} {type(type_name)}"
                    )

    def _propagate_global_UserDefinedType(
        self, scope: Dict[Any, FileScope], type_name: UserDefinedType
    ):
        underlying = type_name.type
        if isinstance(underlying, StructureTopLevel):
            for struct in scope.structures.values():
                if struct == underlying:
                    scope.using_for_directives.add(self._using_for)
        elif isinstance(underlying, EnumTopLevel):
            for enum in scope.enums.values():
                if enum == underlying:
                    scope.using_for_directives.add(self._using_for)
        else:
            LOGGER.error(
                f"Error when propagating global {underlying} {type(underlying)} not a StructTopLevel or EnumTopLevel"
            )

    @property
    def is_compact_ast(self) -> bool:
        return self._slither_parser.is_compact_ast

    @property
    def compilation_unit(self) -> SlitherCompilationUnit:
        return self._slither_parser.compilation_unit

    def get_key(self) -> str:
        return self._slither_parser.get_key()

    @property
    def slither_parser(self) -> "SlitherCompilationUnitSolc":
        return self._slither_parser

    @property
    def underlying_using_for(self) -> UsingForTopLevel:
        return self._using_for
