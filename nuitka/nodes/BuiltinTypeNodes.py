#     Copyright 2018, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Built-in type nodes tuple/list/set/float/str/unicode etc.

These are all very simple and have predictable properties, because we know their type and
that should allow some important optimizations.
"""

from nuitka.optimizations import BuiltinOptimization
from nuitka.PythonVersions import python_version

from .ExpressionBases import (
    ExpressionBuiltinSingleArgBase,
    ExpressionChildrenHavingBase,
    ExpressionSpecBasedComputationBase
)
from .NodeMakingHelpers import (
    makeConstantReplacementNode,
    wrapExpressionWithNodeSideEffects
)
from .shapes.BuiltinTypeShapes import (
    ShapeTypeBool,
    ShapeTypeBytearray,
    ShapeTypeBytes,
    ShapeTypeFloat,
    ShapeTypeStr,
    ShapeTypeUnicode
)


class ExpressionBuiltinTypeBase(ExpressionBuiltinSingleArgBase):
    pass


class ExpressionBuiltinContainerBase(ExpressionSpecBasedComputationBase):

    builtin_spec = None

    named_children = (
        "value",
    )

    def __init__(self, value, source_ref):
        ExpressionSpecBasedComputationBase.__init__(
            self,
            values     = {
                "value" : value,
            },
            source_ref = source_ref
        )

    getValue = ExpressionSpecBasedComputationBase.childGetter(
        "value"
    )

    def computeExpression(self, trace_collection):
        value = self.getValue()

        if value is None:
            return self.computeBuiltinSpec(
                trace_collection = trace_collection,
                given_values     = ()
            )
        elif value.isExpressionConstantXrangeRef():
            if value.getIterationLength() <= 256:
                return self.computeBuiltinSpec(
                    trace_collection = trace_collection,
                    given_values     = (value,)
                )
            else:
                return self, None, None
        else:
            return self.computeBuiltinSpec(
                trace_collection = trace_collection,
                given_values     = (value,)
            )


class ExpressionBuiltinTuple(ExpressionBuiltinContainerBase):
    kind = "EXPRESSION_BUILTIN_TUPLE"

    builtin_spec = BuiltinOptimization.builtin_tuple_spec


class ExpressionBuiltinList(ExpressionBuiltinContainerBase):
    kind = "EXPRESSION_BUILTIN_LIST"

    builtin_spec = BuiltinOptimization.builtin_list_spec


class ExpressionBuiltinSet(ExpressionBuiltinContainerBase):
    kind = "EXPRESSION_BUILTIN_SET"

    builtin_spec = BuiltinOptimization.builtin_set_spec


class ExpressionBuiltinFrozenset(ExpressionBuiltinContainerBase):
    kind = "EXPRESSION_BUILTIN_FROZENSET"

    builtin_spec = BuiltinOptimization.builtin_frozenset_spec


class ExpressionBuiltinFloat(ExpressionChildrenHavingBase):
    kind = "EXPRESSION_BUILTIN_FLOAT"

    named_children = ("value",)

    def __init__(self, value, source_ref):
        ExpressionChildrenHavingBase.__init__(
            self,
            values     = {
                "value" : value
            },
            source_ref = source_ref
        )

    def getTypeShape(self):
        return ShapeTypeFloat

    def computeExpression(self, trace_collection):
        return self.subnode_value.computeExpressionFloat(
            float_node       = self,
            trace_collection = trace_collection
        )

    def mayRaiseException(self, exception_type):
        return self.subnode_value.mayRaiseExceptionFloat(exception_type)

    getValue = ExpressionChildrenHavingBase.childGetter("value")


class ExpressionBuiltinBool(ExpressionBuiltinTypeBase):
    kind = "EXPRESSION_BUILTIN_BOOL"

    builtin_spec = BuiltinOptimization.builtin_bool_spec

    def computeExpression(self, trace_collection):
        value = self.getValue()

        if value is not None:
            truth_value = self.getValue().getTruthValue()

            if truth_value is not None:
                result = wrapExpressionWithNodeSideEffects(
                    new_node = makeConstantReplacementNode(
                        constant = truth_value,
                        node     = self,
                    ),
                    old_node = self.getValue()
                )

                return (
                    result,
                    "new_constant",
                    "Predicted truth value of built-in bool argument"
                )

        return ExpressionBuiltinTypeBase.computeExpression(self, trace_collection)

    def getTypeShape(self):
        return ShapeTypeBool


class ExpressionBuiltinUnicodeBase(ExpressionSpecBasedComputationBase):
    named_children = (
        "value",
        "encoding",
        "errors"
    )

    def __init__(self, value, encoding, errors, source_ref):
        ExpressionSpecBasedComputationBase.__init__(
            self,
            values     = {
                "value"    : value,
                "encoding" : encoding,
                "errors"   : errors
            },
            source_ref = source_ref
        )

    getValue = ExpressionSpecBasedComputationBase.childGetter("value")
    getEncoding = ExpressionSpecBasedComputationBase.childGetter("encoding")
    getErrors = ExpressionSpecBasedComputationBase.childGetter("errors")

    def computeExpression(self, trace_collection):
        args = [
            self.getValue(),
            self.getEncoding(),
            self.getErrors()
        ]

        while args and args[-1] is None:
            del args[-1]

        for arg in args:
            # The value of that node escapes and could change its contents.
            trace_collection.removeKnowledge(arg)

        # Any code could be run, note that.
        trace_collection.onControlFlowEscape(self)

        return self.computeBuiltinSpec(
            trace_collection = trace_collection,
            given_values     = tuple(args)
        )


if python_version < 300:
    class ExpressionBuiltinStr(ExpressionBuiltinTypeBase):
        kind = "EXPRESSION_BUILTIN_STR"

        builtin_spec = BuiltinOptimization.builtin_str_spec

        def computeExpression(self, trace_collection):
            new_node, change_tags, change_desc = ExpressionBuiltinTypeBase.computeExpression(
                self,
                trace_collection
            )

            if new_node is self:
                str_value = self.getValue().getStrValue()

                if str_value is not None:
                    new_node = wrapExpressionWithNodeSideEffects(
                        new_node = str_value,
                        old_node = self.getValue()
                    )

                    change_tags = "new_expression"
                    change_desc = "Predicted 'str' built-in result"

            return new_node, change_tags, change_desc

        def getTypeShape(self):
            return ShapeTypeStr


    class ExpressionBuiltinUnicode(ExpressionBuiltinUnicodeBase):
        kind = "EXPRESSION_BUILTIN_UNICODE"

        builtin_spec = BuiltinOptimization.builtin_unicode_spec

        def getTypeShape(self):
            return ShapeTypeUnicode

else:
    class ExpressionBuiltinStr(ExpressionBuiltinUnicodeBase):
        kind = "EXPRESSION_BUILTIN_STR"

        builtin_spec = BuiltinOptimization.builtin_str_spec

        def getTypeShape(self):
            return ShapeTypeStr

    class ExpressionBuiltinBytes(ExpressionBuiltinUnicodeBase):
        kind = "EXPRESSION_BUILTIN_BYTES"

        builtin_spec = BuiltinOptimization.builtin_bytes_spec

        def getTypeShape(self):
            return ShapeTypeBytes


class ExpressionBuiltinBytearray1(ExpressionBuiltinTypeBase):
    kind = "EXPRESSION_BUILTIN_BYTEARRAY1"

    builtin_spec = BuiltinOptimization.builtin_bytearray_spec

    def __init__(self, value, source_ref):
        ExpressionBuiltinTypeBase.__init__(
            self,
            value      = value,
            source_ref = source_ref
        )

    def getTypeShape(self):
        return ShapeTypeBytearray


class ExpressionBuiltinBytearray3(ExpressionChildrenHavingBase):
    kind = "EXPRESSION_BUILTIN_BYTEARRAY3"

    named_children = ("string", "encoding", "errors")

    builtin_spec = BuiltinOptimization.builtin_bytearray_spec

    def __init__(self, string, encoding, errors, source_ref):
        ExpressionChildrenHavingBase.__init__(
            self,
            values     = {
                "string"   : string,
                "encoding" : encoding,
                "errors"   : errors

            },
            source_ref = source_ref
        )

    getStringArg = ExpressionChildrenHavingBase.childGetter("string")
    getEncoding = ExpressionChildrenHavingBase.childGetter("encoding")
    getErrors = ExpressionChildrenHavingBase.childGetter("errors")

    def computeExpression(self, trace_collection):
        trace_collection.onExceptionRaiseExit(BaseException)

        return self, None, None

    def getTypeShape(self):
        return ShapeTypeBytearray


class ExpressionBuiltinComplex(ExpressionSpecBasedComputationBase):
    kind = "EXPRESSION_BUILTIN_COMPLEX"

    named_children = (
        "real",
        "imag",
    )

    builtin_spec = BuiltinOptimization.builtin_complex_spec

    def __init__(self, real, imag, source_ref):
        ExpressionSpecBasedComputationBase.__init__(
            self,
            values     = {
                "real" : real,
                "imag" : imag,
            },
            source_ref = source_ref
        )

    def computeExpression(self, trace_collection):
        start = self.getReal()
        stop = self.getImag()

        args = (
            start,
            stop,
        )

        return self.computeBuiltinSpec(
            trace_collection = trace_collection,
            given_values     = args
        )

    getReal = ExpressionSpecBasedComputationBase.childGetter("real")
    getImag = ExpressionSpecBasedComputationBase.childGetter("imag")
