#     Copyright 2012, Kay Hayen, mailto:kayhayen@gmx.de
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     If you submit patches or make the software available to licensors of
#     this software in either form, you automatically them grant them a
#     license for your part of the code under "Apache License 2.0" unless you
#     choose to remove this notice.
#
#     Kay Hayen uses the right to license his code under only GPL version 3,
#     to discourage a fork of Nuitka before it is "finished". He will later
#     make a new "Nuitka" release fully under "Apache License 2.0".
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, version 3 of the License.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#     Please leave the whole of this copyright notice intact.
#
""" Code generation contexts.

"""

from .Identifiers import (
    Identifier,
    ConstantIdentifier,
    TempObjectIdentifier,
    LocalVariableIdentifier,
    ClosureVariableIdentifier
)

from .Namify import namifyConstant

from ..Constants import HashableConstant

# Many methods won't use self, but it's the interface. pylint: disable=R0201

class PythonContextBase:
    def __init__( self ):
        self.while_loop_count = 0
        self.for_loop_count = 0

        self.try_count = 0
        self.with_count = 0

        self.preservations = {}

    def allocateForLoopNumber( self ):
        self.for_loop_count += 1

        return self.for_loop_count

    def allocateWhileLoopNumber( self ):
        self.while_loop_count += 1

        return self.while_loop_count

    def allocateTryNumber( self ):
        self.try_count += 1

        return self.try_count

    def allocateWithNumber( self ):
        self.with_count += 1

        return self.with_count

    def isClosureViaContext( self ):
        return True

    def isParametersViaContext( self ):
        return False

    def hasLocalsDict( self ):
        return False

    def needsFrameExceptionKeeper( self ):
        return False

    def getTempHandle( self, var_name ):
        return TempObjectIdentifier( var_name, from_context = "" )


class PythonChildContextBase( PythonContextBase ):
    def __init__( self, parent ):
        PythonContextBase.__init__( self )

        self.parent = parent

    def addEvalOrderUse( self, value ):
        self.parent.addEvalOrderUse( value )

    def getParent( self ):
        return self.parent

    def getConstantHandle( self, constant ):
        return self.parent.getConstantHandle( constant )

    def addFunctionCodes( self, code_name, function_decl, function_code ):
        self.parent.addFunctionCodes( code_name, function_decl, function_code )

    def addContractionCodes( self, code_name, contraction_decl, contraction_code ):
        self.parent.addContractionCodes( code_name, contraction_decl, contraction_code )

    def addClassCodes( self, code_name, class_decl, class_code ):
        self.parent.addClassCodes( code_name, class_decl, class_code )

    def addGlobalVariableNameUsage( self, var_name ):
        self.parent.addGlobalVariableNameUsage( var_name )

    def getModuleCodeName( self ):
        return self.parent.getModuleCodeName()

    def getModuleName( self ):
        return self.parent.getModuleName()

class PythonGlobalContext:
    def __init__( self ):
        self.constants = {}

        # Basic values that the code uses all the times.
        self.getConstantHandle( () )
        self.getConstantHandle( {} )
        self.getConstantHandle( "" )
        self.getConstantHandle( True )
        self.getConstantHandle( False )
        self.getConstantHandle( 0 )
        # For Python3 empty bytes, no effect for Python2, same as ""
        self.getConstantHandle( b"" )

        # Python mechanics.
        self.getConstantHandle( "__module__" )
        self.getConstantHandle( "__class__" )
        self.getConstantHandle( "__dict__" )
        self.getConstantHandle( "__doc__" )
        self.getConstantHandle( "__file__" )
        self.getConstantHandle( "__enter__" )
        self.getConstantHandle( "__exit__" )
        self.getConstantHandle( "__builtins__" )
        # For Python3 modules
        self.getConstantHandle( "__cached__" )

        # Patched module name.
        self.getConstantHandle( "inspect" )

        # Names of builtins used in helper code.
        self.getConstantHandle( "compile" )
        self.getConstantHandle( "range" )
        self.getConstantHandle( "open" )
        self.getConstantHandle( "print" )
        self.getConstantHandle( "__import__" )

        # The print builtin needs some argument names.
        self.getConstantHandle( "end" )
        self.getConstantHandle( "file" )

        # COMPILE_CODE uses read/strip method lookups.
        self.getConstantHandle( "read" )
        self.getConstantHandle( "strip" )

        self.eval_orders_used = set( range( 2, 6 ) )


    def getConstantHandle( self, constant ):
        if constant is None:
            return Identifier( "Py_None", 0 )
        elif constant is True:
            return Identifier( "Py_True", 0 )
        elif constant is False:
            return Identifier( "Py_False", 0 )
        elif constant is Ellipsis:
            return Identifier( "Py_Ellipsis", 0 )
        else:
            key = ( type( constant ), HashableConstant( constant ) )

            if key not in self.constants:
                self.constants[ key ] = "_python_" + namifyConstant( constant )

            return ConstantIdentifier( self.constants[ key ], constant )

    def getConstants( self ):
        return sorted( self.constants.items(), key = lambda x: x[1] )

    def addEvalOrderUse( self, value ):
        assert type( value ) is int

        self.eval_orders_used.add( value )

    def getEvalOrdersUsed( self ):
        return self.eval_orders_used

class PythonModuleContext( PythonContextBase ):
    # Plent of attributes, because it's storing so many different things.
    # pylint: disable=R0902

    def __init__( self, module_name, code_name, filename, global_context ):
        PythonContextBase.__init__( self )

        self.name = module_name
        self.code_name = code_name
        self.filename = filename

        self.global_context = global_context

        self.class_codes = {}
        self.function_codes = {}
        self.contraction_codes = {}

        self.global_var_names = set()
        self.temp_var_names = set()

    def __repr__( self ):
        return "<PythonModuleContext instance for module %s>" % self.filename

    def getFrameHandle( self ):
        return Identifier( "frame_guard.getFrame()", 1 )

    def hasFrameGuard( self ):
        return True

    def getParent( self ):
        return None

    def getConstantHandle( self, constant ):
        return self.global_context.getConstantHandle( constant )

    def addFunctionCodes( self, code_name, function_decl, function_code ):
        assert code_name not in self.function_codes

        self.function_codes[ code_name ] = ( function_decl, function_code )

    def getFunctionsCodes( self ):
        return self.function_codes

    def addContractionCodes( self, code_name, contraction_decl, contraction_code ):
        assert code_name not in self.contraction_codes

        self.contraction_codes[ code_name ] = ( contraction_decl, contraction_code )

    def getContractionsCodes( self ):
        return self.contraction_codes

    def addClassCodes( self, code_name, class_decl, class_code ):
        assert code_name not in self.class_codes

        self.class_codes[ code_name ] = ( class_decl, class_code )

    def getClassesCodes( self ):
        return self.class_codes

    def getName( self ):
        return self.name

    getModuleName = getName

    def getModuleCodeName( self ):
        return self.getCodeName()

    # There cannot ne local variable in modules no need to consider the name.
    # pylint: disable=W0613
    def hasLocalVariable( self, var_name ):
        return False

    def hasClosureVariable( self, var_name ):
        return False
    # pylint: enable=W0613

    def canHaveLocalVariables( self ):
        return False

    def addGlobalVariableNameUsage( self, var_name ):
        self.global_var_names.add( var_name )

    def getGlobalVariableNames( self ):
        return self.global_var_names

    def getCodeName( self ):
        return self.code_name

    def getTracebackName( self ):
        return "<module>"

    def getTracebackFilename( self ):
        return self.filename

    def addEvalOrderUse( self, value ):
        self.global_context.addEvalOrderUse( value )

class PythonFunctionContext( PythonChildContextBase ):
    def __init__( self, parent, function ):
        PythonChildContextBase.__init__( self, parent = parent )

        self.function = function

        # Make sure the local names are available as constants
        for local_name in function.getLocalVariableNames():
            self.getConstantHandle( constant = local_name )

    def __repr__( self ):
        return "<PythonFunctionContext for function '%s'>" % self.function.getName()

    def hasLocalsDict( self ):
        return self.function.hasLocalsDict()

    def hasLocalVariable( self, var_name ):
        return var_name in self.function.getLocalVariableNames()

    def hasClosureVariable( self, var_name ):
        return var_name in self.function.getClosureVariableNames()

    def canHaveLocalVariables( self ):
        return True

    def isParametersViaContext( self ):
        return self.function.isGenerator()

    def getFrameHandle( self ):
        if self.function.isGenerator():
            return Identifier( "generator->m_frame", 0 )
        else:
            return Identifier( "frame_guard.getFrame()", 1 )

    def hasFrameGuard( self ):
        return not self.function.isGenerator()

    def getLocalHandle( self, var_name ):
        return LocalVariableIdentifier( var_name, from_context = self.function.isGenerator() )

    def getClosureHandle( self, var_name ):
        if not self.function.isGenerator():
            return ClosureVariableIdentifier( var_name, from_context = "_python_context->" )
        else:
            return ClosureVariableIdentifier( var_name, from_context = "_python_context->common_context->" )

    def getTempHandle( self, var_name ):
        if self.function.isGenerator():
            return TempObjectIdentifier( var_name, from_context = "_python_context->" )
        else:
            return TempObjectIdentifier( var_name, from_context = "" )

    def getCodeName( self ):
        return self.function.getCodeName()

    def getTracebackName( self ):
        return self.function.getName()

    # TODO: Memoize would do wonders for these things mayhaps.
    def getTracebackFilename( self ):
        return self.function.getParentModule().getFilename()

    def needsFrameExceptionKeeper( self ):
        return self.function.needsFrameExceptionKeeper()

class PythonContractionBase( PythonChildContextBase ):
    def __init__( self, parent, contraction ):
        PythonChildContextBase.__init__( self, parent = parent )

        self.contraction = contraction

    def isClosureViaContext( self ):
        return False

    def isGeneratorExpression( self ):
        return self.__class__ == PythonGeneratorExpressionContext

    def getTracebackFilename( self ):
        return self.contraction.getParentModule().getFilename()

    def getTracebackName( self ):
        return self.contraction.getName()

class PythonListContractionContext( PythonContractionBase ):
    def __init__( self, parent, contraction ):
        PythonContractionBase.__init__(
            self,
            parent      = parent,
            contraction = contraction
        )

    def getClosureHandle( self, var_name ):
        return ClosureVariableIdentifier( var_name, from_context = "" )

    def getLocalHandle( self, var_name ):
        return self.getClosureHandle( var_name )

    def hasFrameGuard( self ):
        return True

class PythonGeneratorExpressionContext( PythonContractionBase ):
    def __init__( self, parent, contraction ):
        PythonContractionBase.__init__(
            self,
            parent      = parent,
            contraction = contraction
        )

    def getClosureHandle( self, var_name ):
        return ClosureVariableIdentifier( var_name, from_context = "_python_context->" )

    def getLocalHandle( self, var_name ):
        return LocalVariableIdentifier( var_name, from_context = True )

    def getTempHandle( self, var_name ):
        return TempObjectIdentifier( var_name, from_context = "_python_context->" )

    def hasFrameGuard( self ):
        return False

class PythonSetContractionContext( PythonContractionBase ):
    def __init__( self, parent, contraction ):
        PythonContractionBase.__init__(
            self,
            parent      = parent,
            contraction = contraction
        )

    def getClosureHandle( self, var_name ):
        return ClosureVariableIdentifier( var_name, from_context = "" )

    def getLocalHandle( self, var_name ):
        return LocalVariableIdentifier( var_name, from_context = False )

    def hasFrameGuard( self ):
        return True

class PythonDictContractionContext( PythonContractionBase ):
    def __init__( self, parent, contraction ):
        PythonContractionBase.__init__(
            self,
            parent      = parent,
            contraction = contraction
        )

    def getClosureHandle( self, var_name ):
        return ClosureVariableIdentifier( var_name, from_context = "" )

    def getLocalHandle( self, var_name ):
        return LocalVariableIdentifier( var_name, from_context = False )

    def hasFrameGuard( self ):
        return True

class PythonClassContext( PythonChildContextBase ):
    def __init__( self, parent, class_def ):
        PythonChildContextBase.__init__( self, parent = parent )

        self.class_def = class_def

    def hasLocalVariable( self, var_name ):
        return var_name in self.class_def.getClassVariableNames()

    def hasClosureVariable( self, var_name ):
        return var_name in self.class_def.getClosureVariableNames()

    def getFrameHandle( self ):
        return Identifier( "frame_guard.getFrame()", 1 )

    def hasFrameGuard( self ):
        return True

    def getLocalHandle( self, var_name ):
        return LocalVariableIdentifier( var_name )

    def getClosureHandle( self, var_name ):
        return ClosureVariableIdentifier( var_name, from_context = "" )

    def isClosureViaContext( self ):
        return False

    def getTracebackName( self ):
        return self.class_def.getName()

    def getTracebackFilename( self ):
        return self.class_def.getParentModule().getFilename()

    def getCodeName( self ):
        return self.class_def.getCodeName()

    def hasLocalsDict( self ):
        return self.class_def.hasLocalsDict()

    def needsFrameExceptionKeeper( self ):
        return self.class_def.needsFrameExceptionKeeper()


class PythonExecInlineContext( PythonChildContextBase ):
    def __init__( self, parent ):
        PythonChildContextBase.__init__( self, parent = parent )

    def canHaveLocalVariables( self ):
        return self.parent.canHaveLocalVariables()

    def getClosureHandle( self, var_name ):
        return self.parent.getLocalHandle( var_name )

    def getLocalHandle( self, var_name ):
        return self.parent.getLocalHandle( var_name )

    def hasLocalsDict( self ):
        return self.parent.hasLocalsDict()
