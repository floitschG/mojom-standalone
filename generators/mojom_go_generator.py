# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Generates Go source files from a mojom.Module.'''

from itertools import chain
import os
import re

from mojom.generate.template_expander import UseJinja

import mojom.generate.generator as generator
import mojom.generate.module as mojom
import mojom.generate.pack as pack

class KindInfo(object):
  def __init__(self, go_type, encode_suffix, decode_suffix, bit_size):
    self.go_type = go_type
    self.encode_suffix = encode_suffix
    self.decode_suffix = decode_suffix
    self.bit_size = bit_size

_kind_infos = {
  mojom.BOOL:                  KindInfo('bool', 'Bool', 'Bool', 1),
  mojom.INT8:                  KindInfo('int8', 'Int8', 'Int8', 8),
  mojom.UINT8:                 KindInfo('uint8', 'Uint8', 'Uint8', 8),
  mojom.INT16:                 KindInfo('int16', 'Int16', 'Int16', 16),
  mojom.UINT16:                KindInfo('uint16', 'Uint16', 'Uint16', 16),
  mojom.INT32:                 KindInfo('int32', 'Int32', 'Int32', 32),
  mojom.UINT32:                KindInfo('uint32', 'Uint32', 'Uint32', 32),
  mojom.FLOAT:                 KindInfo('float32', 'Float32', 'Float32', 32),
  mojom.HANDLE:                KindInfo(
      'system.Handle', 'Handle', 'Handle', 32),
  mojom.DCPIPE:                KindInfo(
      'system.ConsumerHandle', 'Handle', 'ConsumerHandle', 32),
  mojom.DPPIPE:                KindInfo(
      'system.ProducerHandle', 'Handle', 'ProducerHandle', 32),
  mojom.MSGPIPE:               KindInfo(
      'system.MessagePipeHandle', 'Handle', 'MessagePipeHandle', 32),
  mojom.SHAREDBUFFER:          KindInfo(
      'system.SharedBufferHandle', 'Handle', 'SharedBufferHandle', 32),
  mojom.NULLABLE_HANDLE:       KindInfo(
      'system.Handle', 'Handle', 'Handle', 32),
  mojom.NULLABLE_DCPIPE:       KindInfo(
      'system.ConsumerHandle', 'Handle', 'ConsumerHandle', 32),
  mojom.NULLABLE_DPPIPE:       KindInfo(
      'system.ProducerHandle', 'Handle', 'ProducerHandle', 32),
  mojom.NULLABLE_MSGPIPE:      KindInfo(
      'system.MessagePipeHandle', 'Handle', 'MessagePipeHandle', 32),
  mojom.NULLABLE_SHAREDBUFFER: KindInfo(
      'system.SharedBufferHandle', 'Handle', 'SharedBufferHandle', 32),
  mojom.INT64:                 KindInfo('int64', 'Int64', 'Int64', 64),
  mojom.UINT64:                KindInfo('uint64', 'Uint64', 'Uint64', 64),
  mojom.DOUBLE:                KindInfo('float64', 'Float64', 'Float64', 64),
  mojom.STRING:                KindInfo('string', 'String', 'String', 64),
  mojom.NULLABLE_STRING:       KindInfo('string', 'String', 'String', 64),
}

# _imports keeps track of the imports that the .go.mojom file needs to import.
_imports = {}

# _mojom_imports keeps a list of the other .mojom files imported by this one.
_mojom_imports = {}

# The mojom_types.mojom and service_describer.mojom files are special because
# they are used to generate mojom Type's and ServiceDescription implementations.
_service_describer_pkg_short = "service_describer"
_service_describer_pkg = "mojo/public/interfaces/bindings/%s" % \
  _service_describer_pkg_short
_mojom_types_pkg_short = "mojom_types"
_mojom_types_pkg = "mojo/public/interfaces/bindings/%s" % _mojom_types_pkg_short

def GetBitSize(kind):
  if isinstance(kind, (mojom.Union)):
    return 128
  if isinstance(kind, (mojom.Array, mojom.Map, mojom.Struct, mojom.Interface)):
    return 64
  if mojom.IsUnionKind(kind):
    return 2*64
  if isinstance(kind, (mojom.InterfaceRequest)):
    kind = mojom.MSGPIPE
  if isinstance(kind, mojom.Enum):
    kind = mojom.INT32
  return _kind_infos[kind].bit_size

# Returns go type corresponding to provided kind. If |nullable| is true
# and kind is nullable adds an '*' to type (example: ?string -> *string).
def GetGoType(kind, nullable = True):
  if nullable and mojom.IsNullableKind(kind) and not mojom.IsUnionKind(kind):
    return '*%s' % GetNonNullableGoType(kind)
  return GetNonNullableGoType(kind)

# Returns go type corresponding to provided kind. Ignores nullability of
# top-level kind.
def GetNonNullableGoType(kind):
  if mojom.IsStructKind(kind) or mojom.IsUnionKind(kind):
    return '%s' % GetFullName(kind)
  if mojom.IsArrayKind(kind):
    if kind.length:
      return '[%s]%s' % (kind.length, GetGoType(kind.kind))
    return '[]%s' % GetGoType(kind.kind)
  if mojom.IsMapKind(kind):
    return 'map[%s]%s' % (GetGoType(kind.key_kind), GetGoType(kind.value_kind))
  if mojom.IsInterfaceKind(kind):
    return '%s_Pointer' % GetFullName(kind)
  if mojom.IsInterfaceRequestKind(kind):
    return '%s_Request' % GetFullName(kind.kind)
  if mojom.IsEnumKind(kind):
    return GetNameForNestedElement(kind)
  return _kind_infos[kind].go_type

def IsPointer(kind):
  return mojom.IsObjectKind(kind) and not mojom.IsUnionKind(kind)

# Splits name to lower-cased parts used for camel-casing
# (example: HTTPEntry2FooBar -> ['http', 'entry2', 'foo', 'bar']).
def NameToComponent(name):
  # insert '_' between anything and a Title name (e.g, HTTPEntry2FooBar ->
  # HTTP_Entry2_FooBar)
  name = re.sub('([^_])([A-Z][^A-Z_]+)', r'\1_\2', name)
  # insert '_' between non upper and start of upper blocks (e.g.,
  # HTTP_Entry2_FooBar -> HTTP_Entry2_Foo_Bar)
  name = re.sub('([^A-Z_])([A-Z])', r'\1_\2', name)
  return [x.lower() for x in name.split('_')]

def UpperCamelCase(name):
  return ''.join([x.capitalize() for x in NameToComponent(name)])

# Formats a name. If |exported| is true makes name camel-cased with first
# letter capital, otherwise does no camel-casing and makes first letter
# lower-cased (which is used for making internal names more readable).
def FormatName(name, exported=True):
  if exported:
    return UpperCamelCase(name)
  # Leave '_' symbols for unexported names.
  return name[0].lower() + name[1:]

# Returns full name of an imported element based on prebuilt dict |_imports|.
# If the |element| is not imported returns formatted name of it.
# |element| should have attr 'name'. |exported| argument is used to make
# |FormatName()| calls only.
def GetFullName(element, exported=True):
  return GetQualifiedName(
      element.name, GetPackageNameForElement(element), exported)

def GetUnqualifiedNameForElement(element, exported=True):
  return FormatName(element.name, exported)

# Returns a name for nested elements like enum field or constant.
# The returned name consists of camel-cased parts separated by '_'.
def GetNameForNestedElement(element):
  if element.parent_kind:
    return "%s_%s" % (GetNameForElement(element.parent_kind),
        FormatName(element.name))
  return GetFullName(element)

def GetNameForElement(element, exported=True):
  if (mojom.IsInterfaceKind(element) or mojom.IsStructKind(element)
      or mojom.IsUnionKind(element)):
    return GetFullName(element, exported)
  if isinstance(element, (mojom.EnumField,
                          mojom.Field,
                          mojom.Method,
                          mojom.Parameter)):
    return FormatName(element.name, exported)
  if isinstance(element, (mojom.Enum,
                          mojom.Constant,
                          mojom.ConstantValue)):
    return GetNameForNestedElement(element)
  raise Exception('Unexpected element: %s' % element)

def ExpressionToText(token):
  if isinstance(token, mojom.EnumValue):
    return "%s_%s" % (GetNameForNestedElement(token.enum),
        FormatName(token.name, True))
  if isinstance(token, mojom.ConstantValue):
    return GetNameForNestedElement(token)
  if isinstance(token, mojom.Constant):
    return ExpressionToText(token.value)
  return token

def DecodeSuffix(kind):
  if mojom.IsEnumKind(kind):
    return DecodeSuffix(mojom.INT32)
  if mojom.IsInterfaceKind(kind):
    return 'Interface'
  if mojom.IsInterfaceRequestKind(kind):
    return DecodeSuffix(mojom.MSGPIPE)
  return _kind_infos[kind].decode_suffix

def EncodeSuffix(kind):
  if mojom.IsEnumKind(kind):
    return EncodeSuffix(mojom.INT32)
  if mojom.IsInterfaceKind(kind):
    return 'Interface'
  if mojom.IsInterfaceRequestKind(kind):
    return EncodeSuffix(mojom.MSGPIPE)
  return _kind_infos[kind].encode_suffix

# This helper assists in the production of mojom_types.Type for simple kinds.
# See _kind_infos above.
def GetMojomTypeValue(kind, typepkg=''):
  if not kind in _kind_infos:
    return ''

  nullable = 'true' if mojom.IsNullableKind(kind) else 'false'
  if kind == mojom.BOOL or kind == mojom.FLOAT or kind == mojom.DOUBLE or \
    mojom.IsIntegralKind(kind):

    kind_name = UpperCamelCase(_kind_infos[kind].decode_suffix.upper())
    if kind == mojom.FLOAT:
      kind_name = "Float"
    elif kind == mojom.DOUBLE:
      kind_name = "Double"
    return '%sTypeSimpleType{%sSimpleType_%s}' % (typepkg, typepkg, kind_name)
  elif mojom.IsAnyHandleKind(kind):
    kind_name = 'Unspecified'
    if kind == mojom.DCPIPE:
      kind_name = 'DataPipeConsumer'
    elif kind == mojom.DPPIPE:
      kind_name = 'DataPipeProducer'
    elif kind == mojom.MSGPIPE:
      kind_name = 'MessagePipe'
    elif kind == mojom.SHAREDBUFFER:
      kind_name = 'SharedBuffer'
    return '%sTypeHandleType{%sHandleType{' \
      'Nullable: %s, Kind: %sHandleType_Kind_%s}}' % \
      (typepkg, typepkg, nullable, typepkg, kind_name)
  elif mojom.IsStringKind(kind):
    return '%sTypeStringType{%sStringType{%s}}' % (typepkg, typepkg, nullable)
  else:
    raise Exception('Missing case for kind: %s' % kind)

def GetPackageName(module):
  return module.name.split('.')[0]

def GetPackageNameForElement(element):
  if not hasattr(element, 'imported_from') or not element.imported_from:
    return ''
  path = ''
  if element.imported_from['module'].path:
    path += GetPackagePath(element.imported_from['module'])
  if path in _imports:
    return _imports[path]
  return ''

def GetQualifiedName(name, package=None, exported=True):
  if not package:
    return FormatName(name, exported)
  return '%s.%s' % (package, FormatName(name, exported))

def GetPackagePath(module):
  name = module.name.split('.')[0]
  return '/'.join(module.path.split('/')[:-1] + [name])

def GetAllConstants(module):
  data = [module] + module.structs + module.interfaces
  constants = [x.constants for x in data]
  return [i for i in chain.from_iterable(constants)]

def GetAllEnums(module):
  data = [module] + module.structs + module.interfaces
  enums = [x.enums for x in data]
  return [i for i in chain.from_iterable(enums)]

# Adds an import required to use the provided |element|.
# The required import is stored at '_imports'.
# The mojom imports are also stored separately in '_mojom_imports'.
def AddImport(module, element):
  if not isinstance(element, mojom.Kind):
    return

  if mojom.IsArrayKind(element) or mojom.IsInterfaceRequestKind(element):
    AddImport(module, element.kind)
    return
  if mojom.IsMapKind(element):
    AddImport(module, element.key_kind)
    AddImport(module, element.value_kind)
    return
  if mojom.IsAnyHandleKind(element):
    _imports['mojo/public/go/system'] = 'system'
    return

  if not hasattr(element, 'imported_from') or not element.imported_from:
    return
  imported = element.imported_from
  if GetPackagePath(imported['module']) == GetPackagePath(module):
    return
  path = GetPackagePath(imported['module'])
  if path in _imports:
    return
  name = GetPackageName(imported['module'])
  while name in _imports.values(): # This avoids repeated names.
    name += '_'
  _imports[path] = name
  _mojom_imports[path] = name

# The identifier cache is used by the Type generator to determine if a type has
# already been generated or not. This prevents over-generation of the same type
# when it is referred to in multiple ways.
identifier_cache = {}
def GetIdentifier(kind):
  # Use the kind's module to determine the package name.
  if hasattr(kind, 'module'):
    package = GetPackageName(kind.module)
  elif mojom.IsInterfaceRequestKind(kind):
    package = GetPackageName(kind.kind.module)
  else:
    return ''

  # Most kinds have a name, but those that don't should rely on their spec.
  # Since spec can have : and ? characters, these must be replaced. Since ? is
  # replaced with '', the caller must keep track of optionality on its own.
  name_or_spec = (kind.name if hasattr(kind, 'name') else kind.spec)
  package_unique = name_or_spec.replace(':', '_').replace('?', '')
  return '%s_%s' % (package, package_unique)

def StoreIdentifier(identifier, cache_name):
  if not cache_name in identifier_cache:
    identifier_cache[cache_name] = {}
  identifier_cache[cache_name][identifier] = True
  return ''

def CheckIdentifier(identifier, cache_name):
  if not cache_name in identifier_cache:
    identifier_cache[cache_name] = {}
  return identifier in identifier_cache[cache_name]

# Get the mojom type's identifier suffix.
def GetMojomTypeIdentifier(kind):
  # Since this should be unique, it is based on the type's identifier.
  return "%s__" % GetIdentifier(kind)

class Generator(generator.Generator):
  go_filters = {
    'array': lambda kind: mojom.Array(kind),
    'bit_size': GetBitSize,
    'decode_suffix': DecodeSuffix,
    'encode_suffix': EncodeSuffix,
    'go_type': GetGoType,
    'expression_to_text': ExpressionToText,
    'has_response': lambda method: method.response_parameters is not None,
    'identifier': GetIdentifier,
    'identifier_check': CheckIdentifier,
    'identifier_store': StoreIdentifier,
    'is_array': mojom.IsArrayKind,
    'is_enum': mojom.IsEnumKind,
    'is_handle': mojom.IsAnyHandleKind,
    'is_interface': mojom.IsInterfaceKind,
    'is_interface_request': mojom.IsInterfaceRequestKind,
    'is_map': mojom.IsMapKind,
    'is_none_or_empty': lambda array: array is None or len(array) == 0,
    'is_nullable': mojom.IsNullableKind,
    'is_pointer': IsPointer,
    'is_object': mojom.IsObjectKind,
    'is_struct': mojom.IsStructKind,
    'is_union': mojom.IsUnionKind,
    'qualified': GetQualifiedName,
    'mojom_type': GetMojomTypeValue,
    'mojom_type_identifier': GetMojomTypeIdentifier,
    'name': GetNameForElement,
    'unqualified_name': GetUnqualifiedNameForElement,
    'package': GetPackageNameForElement,
    'tab_indent': lambda s, size = 1: ('\n' + '\t' * size).join(s.splitlines())
  }

  # TODO: This value should be settable via arguments. If False, then mojom type
  # information will not be generated.
  should_gen_mojom_types = True

  def GetParameters(self):
    package = GetPackageName(self.module)
    return {
      'enums': GetAllEnums(self.module),
      'imports': self.GetImports()[0],
      'interfaces': self.GetInterfaces(),
      'mojom_imports': self.GetMojomImports(),
      'package': package,
      'structs': self.GetStructs(),
      'descpkg': '%s.' % _service_describer_pkg_short \
        if package != _service_describer_pkg_short else '',
      'typepkg': '%s.' % _mojom_types_pkg_short \
        if package != _mojom_types_pkg_short else '',
      'unions': self.GetUnions()
    }

  @UseJinja('go_templates/source.tmpl', filters=go_filters)
  def GenerateSource(self):
    return self.GetParameters()

  def GenerateFiles(self, args):
    self.Write(self.GenerateSource(), os.path.join("go", "src",
        GetPackagePath(self.module), "%s.go" % self.module.name))

  def GetJinjaParameters(self):
    return {
      'lstrip_blocks': True,
      'trim_blocks': True,
    }

  def GetGlobals(self):
    return {
      'namespace': self.module.namespace,
      'module': self.module,
      'should_gen_mojom_types': self.should_gen_mojom_types,
    }

  # Scans |self.module| for elements that require imports and adds all found
  # imports to '_imports' dict. Mojom imports are stored in the '_mojom_imports'
  # dict. This operation is idempotent.
  # Returns a tuple:
  # - list of imports that should include the generated go file
  # - the dictionary of _mojom_imports
  def GetImports(self):
    # Imports can only be used in structs, constants, enums, interfaces.
    all_structs = list(self.module.structs)
    for i in self.module.interfaces:
      for method in i.methods:
        all_structs.append(self._GetStructFromMethod(method))
        if method.response_parameters:
          all_structs.append(self._GetResponseStructFromMethod(method))

    if (len(all_structs) > 0 or len(self.module.interfaces) > 0
        or len(self.module.unions) > 0):
      _imports['fmt'] = 'fmt'
      _imports['mojo/public/go/bindings'] = 'bindings'
    if len(self.module.interfaces) > 0:
      _imports['mojo/public/go/system'] = 'system'
    if len(all_structs) > 0:
      _imports['sort'] = 'sort'

    for union in self.module.unions:
      for field in union.fields:
        AddImport(self.module, field.kind)

    for struct in all_structs:
      for field in struct.fields:
        AddImport(self.module, field.kind)
# TODO(rogulenko): add these after generating constants and struct defaults.
#        if field.default:
#          AddImport(self.module, field.default)

    for enum in GetAllEnums(self.module):
      for field in enum.fields:
        if field.value:
          AddImport(self.module, field.value)

    # Mojom Type generation requires additional imports.
    defInterface = len(self.module.interfaces) > 0
    defOtherType = len(self.module.unions) + len(all_structs) + \
      len(GetAllEnums(self.module)) > 0

    if GetPackageName(self.module) != _mojom_types_pkg_short:
      if defInterface:
        # Each Interface has a service description that uses this.
        _imports[_mojom_types_pkg] = _mojom_types_pkg_short
      if defOtherType and self.should_gen_mojom_types:
        # This import is needed only if generating mojom type definitions.
        _imports[_mojom_types_pkg] = _mojom_types_pkg_short

    if GetPackageName(self.module) != _service_describer_pkg_short and \
      defInterface:
      # Each Interface has a service description that uses this.
      _imports[_service_describer_pkg] = _service_describer_pkg_short

# TODO(rogulenko): add these after generating constants and struct defaults.
#    for constant in GetAllConstants(self.module):
#      AddImport(self.module, constant.value)

    imports_list = []
    for i in _imports:
      if i.split('/')[-1] == _imports[i]:
        imports_list.append('"%s"' % i)
      else:
        imports_list.append('%s "%s"' % (_imports[i], i))
    return sorted(imports_list), _mojom_imports

  def GetMojomImports(self):
    # GetImports (idempotent) prepares the _imports and _mojom_imports maps.
    return self.GetImports()[1]

  # Overrides the implementation from the base class in order to customize the
  # struct and field names.
  def _GetStructFromMethod(self, method):
    params_class = "%s_%s_Params" % (GetNameForElement(method.interface),
        GetNameForElement(method))
    struct = mojom.Struct(params_class, module=method.interface.module)
    for param in method.parameters:
      struct.AddField("in%s" % GetNameForElement(param),
          param.kind, param.ordinal, attributes=param.attributes)
    return self._AddStructComputedData(False, struct)

  # Overrides the implementation from the base class in order to customize the
  # struct and field names.
  def _GetResponseStructFromMethod(self, method):
    params_class = "%s_%s_ResponseParams" % (
        GetNameForElement(method.interface), GetNameForElement(method))
    struct = mojom.Struct(params_class, module=method.interface.module)
    for param in method.response_parameters:
      struct.AddField("out%s" % GetNameForElement(param),
          param.kind, param.ordinal, attributes=param.attributes)
    return self._AddStructComputedData(False, struct)
