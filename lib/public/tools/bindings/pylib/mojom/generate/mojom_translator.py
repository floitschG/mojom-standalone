#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This module is responsible for translating a MojomFileGraph (see
# mojom_files.mojom) to one or more module.Module.
#
# This module takes the output of the mojom parser, a MojomFileGraph  and
# translates it to the input of the code generators, a module.Module object.
# This is part of version 2 of the code generation pipeline. In version 1, the
# analogous functionality (translating from parser output to code generators
# input) is performed by the data module.
#
# The code generators remain from version 1 of the pipeline and so this module
# serves as an adapter between the v1 backends and the v2 frontend.
#
# The current version of this script does not validate the input data at all
# and instead trusts that it will be invoked with valid data produced by the
# frontend parser.
#
# NOTE: This module assumes that the python path contains the generated modules
# for mojom_files.mojom and mojom_types.mojom as well as their dependencies.
# It is the responsibility of the module's loader to handle this.

import os

from generated import mojom_files_mojom
from generated import mojom_types_mojom
import module
import operator


class FileTranslator(object):
  """FileTranslator translates a MojomFile to a module.Module."""
  def __init__(self, graph, file_name):
    """Initializes a FileTranslator.

    Args:
      graph: {mojom_files_mojom.MojomFileGraph} containing the file to be
          translated.
      file_name: {str} key to the file to be translated in graph.files.
    """
    assert isinstance(graph, mojom_files_mojom.MojomFileGraph)
    self._type_cache = {}
    self._value_cache = {}
    self._constant_cache = {}
    self._graph = graph
    self._file_name = file_name
    self._types = {}
    self._module = module.Module()
    self._transitive_imports = {}

  def Translate(self):
    """Translates the file specified in the constructor.

    Returns:
      {module.Module} representing the translated file.
    """
    mojom_file = self._graph.files[self._file_name]

    mod = self._module
    self.PopulateModuleMetadata(mod, mojom_file)

    mod.imports = []
    self._transitive_imports = self.GetTransitiveImports(mojom_file)
    mod.transitive_imports = self._transitive_imports.values()
    if mojom_file.imports:
      mod.imports = [
          self._transitive_imports[imp] for imp in mojom_file.imports]

    if mojom_file.declared_mojom_objects:
      if mojom_file.declared_mojom_objects.top_level_constants:
        mod.constants = [
            self.ConstantFromValueKey(key)
            for key in mojom_file.declared_mojom_objects.top_level_constants]

      user_defined_types = ['interfaces', 'structs', 'unions']
      for user_defined_type in user_defined_types:
        if getattr(mojom_file.declared_mojom_objects, user_defined_type):
          setattr(mod, user_defined_type, [self.UserDefinedFromTypeKey(key)
            for key in getattr(
              mojom_file.declared_mojom_objects, user_defined_type)])
      if mojom_file.declared_mojom_objects.top_level_enums:
        mod.enums = [self.UserDefinedFromTypeKey(key)
            for key in mojom_file.declared_mojom_objects.top_level_enums]

    return mod

  def PopulateModuleMetadata(self, mod, mojom_file):
    """Populates some fields of a module.Module based on a MojomFile.

    Populates name, path, namespace and attributes of mod.

    Args:
      mod: {module.Module} the module to be populated.
      mojom_file: {MojomFile} the file to be translated.
    """
    mod.name = os.path.basename(mojom_file.file_name)
    # specified_file_name is the file name specified on the command line if one
    # was specified. The mojom parser sets specified_file_name to the empty
    # string if the file was parsed only because the file was imported by
    # another file. While specified_file_name can be None, the mojom parser
    # should not set it to None, so we check for that error here.
    assert mojom_file.specified_file_name is not None
    mod.specified_name = mojom_file.specified_file_name
    mod.path = mojom_file.file_name
    mod.namespace = mojom_file.module_namespace
    # Note that attribute values are typed. That is why we use
    # attr.value.data directly instead of the string representation of it.
    if mojom_file.attributes:
      mod.attributes = {attr.key:
          attr.value.data for attr in mojom_file.attributes}

  def GetTransitiveImports(self, mojom_file):
    """Gets a mojom file's transitive imports.

    Args:
      mojom_file: {mojom_files.MojomFile} the mojom file whose imports have to
        be found.

    Returns:
      {dict} The key is the file_name which is an index into self._graph.files
      and is referenced in the SourceFileInfo.file_name of imported types.
      The value is a dictionary as returned by ImportFromMojom.
    """
    if not mojom_file.imports:
      return {}
    to_be_processed = set(mojom_file.imports)
    processed = set()
    transitive_imports = {}

    while to_be_processed:
      import_name = to_be_processed.pop()
      processed.add(import_name)

      import_dict = self.ImportFromMojom(import_name)

      transitive_imports[import_dict['module'].path] = import_dict

      import_file = self._graph.files[import_name]
      if import_file.imports:
        to_be_processed.update(set(import_file.imports) - processed)

    return transitive_imports

  def ImportFromMojom(self, import_name):
    """Builds a dict representing an import.

    Args:
      import_name: {str} key to the imported file in graph.files.

    Returns:
      {dict} representing the imported file.
    """
    import_file = self._graph.files[import_name]
    import_module = module.Module()
    self.PopulateModuleMetadata(import_module, import_file)

    import_item = {
        'module_name': import_module.name,
        'namespace': import_module.namespace,
        'module': import_module,
        }
    return import_item

  def UnionFromMojom(self, union, mojom_type):
    """Populates a module.Union based on a MojomUnion.

    Args:
      union: {module.Union} to be populated.
      mojom_type: {UserDefinedType} referring to the MojomUnion to be
        translated.
    """
    assert mojom_type.tag == mojom_types_mojom.UserDefinedType.Tags.union_type
    mojom_union = mojom_type.union_type
    self.PopulateUserDefinedType(union, mojom_union)
    union.fields = [self.UnionFieldFromMojom(f) for f in mojom_union.fields]

  def StructFromMojom(self, struct, mojom_type):
    """Populates a module.Struct based on a MojomStruct.

    Args:
      struct: {module.Struct} to be populated.
      mojom_type: {UserDefinedType} referring to the MojomStruct to be
        translated.
    """
    assert mojom_type.tag == mojom_types_mojom.UserDefinedType.Tags.struct_type
    mojom_struct = mojom_type.struct_type
    self.PopulateUserDefinedType(struct, mojom_struct)
    struct.fields = [self.StructFieldFromMojom(f) for f in mojom_struct.fields]
    self.PopulateContainedDeclarationsFromMojom(
        struct, mojom_struct.decl_data.contained_declarations)

  def UnionFieldFromMojom(self, mojom_field):
    """Translates a mojom_types_mojom.UnionField to a module.UnionField.

    Args:
      mojom_field: {mojom_types_mojom.UnionField} to be translated.

    Returns:
      {module.UnionField} translated from mojom_field.
    """
    union_field = module.UnionField()
    self.PopulateCommonFieldValues(union_field, mojom_field)
    union_field.ordinal = self.OrdinalFromMojom(mojom_field)
    return union_field

  def StructFieldFromMojom(self, mojom_field):
    """Translates a mojom_types_mojom.StructField to a module.StructField.

    Args:
      mojom_field: {mojom_types_mojom.StructField} to be translated.

    Returns:
      {module.StructField} translated from mojom_field.
    """
    struct_field = module.StructField()
    self.PopulateCommonFieldValues(struct_field, mojom_field)
    struct_field.ordinal = self.OrdinalFromMojom(mojom_field)
    if mojom_field.default_value:
      if (mojom_field.default_value.tag ==
          mojom_types_mojom.DefaultFieldValue.Tags.default_keyword):
        struct_field.default = 'default'
      else:
        struct_field.default = self.ValueFromMojom(
            mojom_field.default_value.value)

    return struct_field

  def ParamFromMojom(self, mojom):
    """Translates a mojom_types_mojom.StructField to a module.Parameter.

    The parameters passed to and returned from a method are expressed as a
    struct. The struct fields in the struct are the parameters.

    Args:
      mojom: {mojom_types_mojom.StructField} representing a method parameter.

    Returns:
      {module.Parameter} translated from the mojom.
    """
    param = module.Parameter()
    param.ordinal = self.OrdinalFromMojom(mojom)
    self.PopulateCommonFieldValues(param, mojom)
    return param

  def PopulateCommonFieldValues(self, field, mojom_field):
    """Populates a number of common field values based on a mojom field.

    Args:
      field: {module.Field|module.Parameter} to be populated.
      mojom_field: {StructField|UnionField} to be translated.
    """
    # TODO(rudominer) Some of the code generators check that the type
    # of field.name is a non-unicode string. If we change this we can
    # remove the str() below.
    field.name = str(mojom_field.decl_data.short_name)
    field.kind = self.KindFromMojom(mojom_field.type)
    field.attributes = self.AttributesFromMojom(mojom_field)

  def PopulateContainedDeclarationsFromMojom(
      self, parent_kind, contained_declarations):
    """Populates a module.Struct|module.Interface with contained declarations.

    Args:
      parent_kind: {module.Struct|module.Interface} to be populated.
      contained_declarations: {mojom_types_mojom.ContainedDeclarations} from
        which the contained types need to be extracted.
    """
    if not contained_declarations:
      return

    if contained_declarations.enums:
      for enum_key in contained_declarations.enums:
        enum = self.UserDefinedFromTypeKey(enum_key)
        parent_kind.enums.append(enum)

    if contained_declarations.constants:
      for const_key in contained_declarations.constants:
        const = self.ConstantFromValueKey(const_key)
        parent_kind.constants.append(const)

  def EnumFromMojom(self, enum, mojom_type):
    """Populates a module.Enum based on a MojomEnum.

    Args:
      enum: {module.Enum} to be populated.
      mojom_type: {mojom_types_mojom.Type} referring to the MojomEnum to be
        translated.
    """
    assert mojom_type.tag == mojom_types_mojom.UserDefinedType.Tags.enum_type
    mojom_enum = mojom_type.enum_type
    self.PopulateUserDefinedType(enum, mojom_enum)
    if mojom_enum.decl_data.container_type_key:
      parent_kind = self.UserDefinedFromTypeKey(
          mojom_enum.decl_data.container_type_key)
      enum.parent_kind = parent_kind
    enum.fields = [self.EnumFieldFromMojom(value)
        for value in mojom_enum.values]

  def EnumFieldFromMojom(self, mojom_enum_value):
    """Translates an mojom_types_mojom.EnumValue to a module.EnumField.

    mojom_enum_value: {mojom_types_mojom.EnumValue} to be translated.

    Returns:
      {module.EnumField} translated from mojom_enum_value.
    """
    field = module.EnumField()
    field.name = mojom_enum_value.decl_data.short_name
    field.attributes = self.AttributesFromMojom(mojom_enum_value)
    field.numeric_value = mojom_enum_value.int_value
    if mojom_enum_value.initializer_value is not None:
      field.value = self.ValueFromMojom(mojom_enum_value.initializer_value)

    return field

  def AttributesFromMojom(self, mojom):
    """Extracts the attributes from a Mojom object into a dict.

    Args:
      mojom: A type in mojom_types_mojom containing a decl_data field.

    Returns:
      {dict<str, str>} of the attributes.
    """
    if not mojom.decl_data.attributes:
      return None

    # Note that attribute values are typed. That is why we use
    # attr.value.data directly instead of the string representation of it.
    return {attr.key: attr.value.data for attr in mojom.decl_data.attributes}

  def PopulateUserDefinedType(self, module_type, mojom):
    """Populates fields that are common among user-defined types.

    Args:
      module_type: {module.Struct|Union|Enum} to be populated.
      mojom: {MojomStruct|MojomUnion|MojomEnum} to be translated.
    """
    module_type.attributes = self.AttributesFromMojom(mojom)
    module_type.name = mojom.decl_data.short_name
    module_type.spec = mojom.decl_data.full_identifier
    if module_type.spec == None:
      module_type.spec = mojom.decl_data.short_name
    self.PopulateModuleOrImportedFrom(module_type, mojom)

  def PopulateModuleOrImportedFrom(self, module_type, mojom):
    """Populates either the module field or the imported_from field.

    All user-defined types must have either the module field populated (if
    they are from the currently-processed module) or the imported_from (if
    they are imported from another module).

    Args:
      module_type: {module.Struct|Union|Enum|Interface} to be populated.
      mojom: {MojomStruct|MojomUnion|MojomEnum|MojomInterface} to be translated.
    """
    if mojom.decl_data.source_file_info:
      if mojom.decl_data.source_file_info.file_name == self._file_name:
        module_type.module = self._module
      else:
        imported_from = self._transitive_imports[
            mojom.decl_data.source_file_info.file_name]
        module_type.imported_from = imported_from
        module_type.module = imported_from['module']


  def OrdinalFromMojom(self, mojom):
    """Extracts the declared ordinal from a mojom StructField or UnionField.

    Args:
      mojom: {MojomStruct|MojomUnion} from which the ordinal is to be extracted.

    Returns:
      {int} if an ordinal was present, {NoneType} otherwise.
    """
    ordinal = mojom.decl_data.declared_ordinal
    if ordinal < 0:
      return None
    return ordinal

  def InterfaceFromMojom(self, interface, mojom_type):
    """Populates a module.Interface from a mojom_types_mojom.MojomInterface.

    Args:
      interface: {module.Interface} to be populated.
      mojom_type: {UserDefinedType} referring to the MojomInterface to be
        translated.
    """
    assert (mojom_type.tag
        == mojom_types_mojom.UserDefinedType.Tags.interface_type)
    mojom_interface = mojom_type.interface_type
    interface.attributes = self.AttributesFromMojom(mojom_interface)
    self.PopulateModuleOrImportedFrom(interface, mojom_interface)
    interface.name = mojom_interface.decl_data.short_name
    interface.spec = interface.name
    interface.service_name = mojom_interface.service_name
    if interface.attributes:
      assert interface.service_name == interface.attributes.get(
          'ServiceName', None), interface.service_name
    else:
      assert interface.service_name is None, interface.service_name


    # Translate the dictionary of methods into a list of module.Methods.
    # In order to have a deterministic ordering we sort by method ordinal.
    # TODO(rudominer) Consider ordering by declaration order instead once
    # this field is populated by the front-end.
    interface.methods = [self.MethodFromMojom(mojom_method, interface)
        for ordinal, mojom_method in sorted(mojom_interface.methods.iteritems(),
          key=operator.itemgetter(0))]
    self.PopulateContainedDeclarationsFromMojom(
        interface, mojom_interface.decl_data.contained_declarations)

  def MethodFromMojom(self, mojom_method, interface):
    """Translates a mojom_types_mojom.MojomMethod to a module.Method.

    Args:
      mojom_method: {mojom_types_mojom.MojomMethod} to be translated.
      interface: {module.Interface} the method is a member of.

    Returns:
      {module.Method} translated from mojom_method.
    """
    method = module.Method(interface, mojom_method.decl_data.short_name)
    method.ordinal = mojom_method.ordinal
    method.parameters = [self.ParamFromMojom(param)
        for param in mojom_method.parameters.fields]
    if mojom_method.response_params is not None:
      method.response_parameters = [self.ParamFromMojom(param)
          for param in mojom_method.response_params.fields]
    return method

  def ConstantFromValueKey(self, value_key):
    """Takes a value key into a graph.resolved_values referring to a constant
    and returns the module equivalent.

    Args:
      value_key: {str} the value key referring to the value to be returned.

    Returns:
      {module.Constant} translated.
    """
    if value_key in self._constant_cache:
      return self._constant_cache[value_key]

    mojom_const = self._graph.resolved_values[value_key].declared_constant
    const = module.Constant()
    self._constant_cache[value_key] = const

    self.ConstantFromMojom(const, mojom_const)
    return const

  def ConstantFromMojom(self, const, mojom_const):
    """Populates a module.Constant based on a DeclaredConstant.

    Args:
      const: {module.Constant} to be populated.
      mojom_const: {mojom_types_mojom.DeclaredConstant} to be translated.

    Returns:
      {module.Constant} translated from mojom_const.
    """
    const.name = mojom_const.decl_data.short_name
    const.kind = self.KindFromMojom(mojom_const.type)
    const.value = self.ValueFromMojom(mojom_const.value)
    const.parent_kind = None
    if mojom_const.decl_data.container_type_key:
      const.parent_kind = self.UserDefinedFromTypeKey(
          mojom_const.decl_data.container_type_key)

  def ValueFromMojom(self, value):
    """Translates a mojom_types_mojom.Value.

    Args:
      value: {mojom_types_mojom.Value} to be translated.

    Returns:
      {str|module.BuiltinValue|module.NamedValue} translated from the passed in
      mojom_value.
      If value is a literal value, a string is returned. If the literal value is
        a string literal value, the returned string is enclosed in double
        quotes. If the literal value is a boolean literal value then one of the
        strings 'true' or 'false' is returned. Otherwise the literal value is a
        numeric literal value and in this case the returned value is a Python
        string representation of the numeric value.
      If value is a built-in value, a module.BuiltinValue is returned.
      If value is a user defined reference, a module.NamedValue is returned.
    """
    if value.tag == mojom_types_mojom.Value.Tags.literal_value:
      if (value.literal_value.tag
          == mojom_types_mojom.LiteralValue.Tags.string_value):
        return '"%s"' % value.literal_value.data
      if (value.literal_value.tag
          == mojom_types_mojom.LiteralValue.Tags.bool_value):
        # The strings 'true' and 'false' are used to represent bool literals.
        return ('%s' % value.literal_value.data).lower()
      elif (value.literal_value.tag
          == mojom_types_mojom.LiteralValue.Tags.float_value or
          value.literal_value.tag
          == mojom_types_mojom.LiteralValue.Tags.double_value):
        # Use the Python repr() function to get a string that accurately
        # represents the value of the floating point number.
        return repr(value.literal_value.data)
      return str(value.literal_value.data)
    elif value.tag == mojom_types_mojom.Value.Tags.builtin_value:
      mojom_to_builtin = {
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_INFINITY:
          'double.INFINITY',
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_NEGATIVE_INFINITY:
          'double.NEGATIVE_INFINITY',
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_NAN:
          'double.NAN',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_INFINITY:
          'float.INFINITY',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_NEGATIVE_INFINITY:
          'float.NEGATIVE_INFINITY',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_NAN: 'float.NAN',
          }
      return module.BuiltinValue(mojom_to_builtin[value.builtin_value])

    assert value.tag == mojom_types_mojom.Value.Tags.user_value_reference
    return self.UserDefinedFromValueKey(value.user_value_reference.value_key)

  def UserDefinedFromValueKey(self, value_key):
    """Takes a value key into graph.resolved_values and returns the module
    equivalent.

    Args:
      value_key: {str} the value key referring to the value to be returned.

    Returns:
      {module.EnumValue|module.ConstantValue} translated.
    """
    if value_key in self._value_cache:
      return self._value_cache[value_key]

    value = self._graph.resolved_values[value_key]
    if value.tag == mojom_types_mojom.UserDefinedValue.Tags.enum_value:
      return self.EnumValueFromMojom(value.enum_value)
    return self.ConstantValueFromValueKey(value_key)

  def ConstantValueFromValueKey(self, value_key):
    """Takes a value key into graph.resolved_values referring to a declared
    constant and returns the module equivalent.

    Args:
      value_key: {str} the value key referring to the value to be returned.

    Returns:
      {module.ConstantValue} translated.
    """
    const_value = module.ConstantValue()
    self._value_cache[value_key] = const_value

    const = self.ConstantFromValueKey(value_key)
    const_value.constant = const
    const_value.name = const.name
    const_value.parent_kind = const.parent_kind
    self.PopulateModuleOrImportedFrom(const_value,
        self._graph.resolved_values[value_key].declared_constant)
    const_value.namespace = const_value.module.namespace
    return const_value

  def EnumValueFromMojom(self, mojom_enum_value):
    """Translates an mojom_types_mojom.EnumValue to a module.EnumValue.

    mojom_enum_value: {mojom_types_mojom.EnumValue} to be translated.

    Returns:
      {module.EnumValue} translated from mojom_enum_value.
    """
    enum_type_key = mojom_enum_value.enum_type_key
    name = mojom_enum_value.decl_data.short_name
    value_key = (enum_type_key, name)
    if value_key in self._value_cache:
      return self._value_cache[value_key]

    # We need to create and cache the EnumValue object just in case later calls
    # require the creation of that same EnumValue object.
    enum_value = module.EnumValue()
    self._value_cache[value_key] = enum_value

    enum = self.UserDefinedFromTypeKey(enum_type_key)
    enum_value.enum = enum
    self.PopulateModuleOrImportedFrom(enum_value, mojom_enum_value)
    enum_value.namespace = enum_value.module.namespace
    enum_value.parent_kind = enum.parent_kind
    enum_value.name = name

    return enum_value

  def KindFromMojom(self, mojom_type):
    """Translates a mojom_types_mojom.Type to its equivalent module type.

    It is guaranteed that two calls to KindFromMojom with the same input yield
    the same object.

    Args:
      mojom_type: {mojom_types_mojom.Type} to be translated.

    Returns:
      {module.Kind} translated from mojom_type.
    """
    mappers = {
        mojom_types_mojom.Type.Tags.simple_type: self.SimpleKindFromMojom,
        mojom_types_mojom.Type.Tags.string_type: self.StringFromMojom,
        mojom_types_mojom.Type.Tags.handle_type: self.HandleFromMojom,
        mojom_types_mojom.Type.Tags.array_type: self.ArrayFromMojom,
        mojom_types_mojom.Type.Tags.map_type: self.MapFromMojom,
        mojom_types_mojom.Type.Tags.type_reference: self.UserDefinedFromTypeRef,
    }
    return mappers[mojom_type.tag](mojom_type)

  def SimpleKindFromMojom(self, mojom_type):
    """Translates a simple type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its simple_type field set to be
        translated.

    Returns:
      {module.Kind} translated from mojom_type.
    """
    simple_mojom_types = {
        mojom_types_mojom.SimpleType.BOOL: module.BOOL,
        mojom_types_mojom.SimpleType.INT8: module.INT8,
        mojom_types_mojom.SimpleType.INT16: module.INT16,
        mojom_types_mojom.SimpleType.INT32: module.INT32,
        mojom_types_mojom.SimpleType.INT64: module.INT64,
        mojom_types_mojom.SimpleType.UINT8: module.UINT8,
        mojom_types_mojom.SimpleType.UINT16: module.UINT16,
        mojom_types_mojom.SimpleType.UINT32: module.UINT32,
        mojom_types_mojom.SimpleType.UINT64: module.UINT64,
        mojom_types_mojom.SimpleType.FLOAT: module.FLOAT,
        mojom_types_mojom.SimpleType.DOUBLE: module.DOUBLE,
    }
    return simple_mojom_types[mojom_type.simple_type]

  def HandleFromMojom(self, mojom_type):
    """Translates a handle type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its handle_type field set to be
        translated.

    Returns:
      {module.ReferenceKind} translated from mojom_type.
    """
    handle_mojom_types = {
        mojom_types_mojom.HandleType.Kind.UNSPECIFIED: module.HANDLE,
        mojom_types_mojom.HandleType.Kind.MESSAGE_PIPE: module.MSGPIPE,
        mojom_types_mojom.HandleType.Kind.DATA_PIPE_CONSUMER: module.DCPIPE,
        mojom_types_mojom.HandleType.Kind.DATA_PIPE_PRODUCER: module.DPPIPE,
        mojom_types_mojom.HandleType.Kind.SHARED_BUFFER: module.SHAREDBUFFER,
    }

    nullable_handle_mojom_types = {
        mojom_types_mojom.HandleType.Kind.UNSPECIFIED: module.NULLABLE_HANDLE,
        mojom_types_mojom.HandleType.Kind.MESSAGE_PIPE: module.NULLABLE_MSGPIPE,
        mojom_types_mojom.HandleType.Kind.DATA_PIPE_CONSUMER:
        module.NULLABLE_DCPIPE,
        mojom_types_mojom.HandleType.Kind.DATA_PIPE_PRODUCER:
        module.NULLABLE_DPPIPE,
        mojom_types_mojom.HandleType.Kind.SHARED_BUFFER:
        module.NULLABLE_SHAREDBUFFER,
    }

    if mojom_type.handle_type.nullable:
      return nullable_handle_mojom_types[mojom_type.handle_type.kind]
    return handle_mojom_types[mojom_type.handle_type.kind]

  def StringFromMojom(self, mojom_type):
    """Translates a string type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its string_type field set to be
        translated.

    Returns:
      {module.ReferenceKind} translated from mojom_type. Either module.STRING or
      module.NULLABLE_STRING.
    """
    if mojom_type.string_type.nullable:
      return module.NULLABLE_STRING
    return module.STRING

  def ArrayFromMojom(self, mojom_type):
    """Translates an array type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its array_type field set to be
        translated.

    Returns:
      {module.Array} translated from mojom_type.
    """
    array = module.Array(
        kind=self.KindFromMojom(mojom_type.array_type.element_type))
    if mojom_type.array_type.fixed_length > 0:
      array.length = mojom_type.array_type.fixed_length
    if mojom_type.array_type.nullable:
      return array.MakeNullableKind()
    return array

  def MapFromMojom(self, mojom_type):
    """Translates a map type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its map_type field set to be
        translated.

    Returns:
      {module.Map} translated from mojom_type.
    """
    key_kind = self.KindFromMojom(mojom_type.map_type.key_type)
    value_kind = self.KindFromMojom(mojom_type.map_type.value_type)
    module_map = module.Map(key_kind=key_kind, value_kind=value_kind)
    if mojom_type.map_type.nullable:
      return module_map.MakeNullableKind()
    return module_map

  def UserDefinedFromTypeRef(self, mojom_type):
    """Translates a type reference to the module equivalent of the
       UserDefinedType that the reference refers to.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its type_reference field set to
        be translated.

    Returns:
      {module.Enum|Struct|Union|Interface} translated from mojom_type.
    """
    type_key = mojom_type.type_reference.type_key
    module_type = self.UserDefinedFromTypeKey(type_key)
    if mojom_type.type_reference.is_interface_request:
      module_type = module.InterfaceRequest(module_type)
    if mojom_type.type_reference.nullable:
      return module_type.MakeNullableKind()
    return module_type

  def UserDefinedFromTypeKey(self, type_key):
    """Takes a type key into graph.resolved_types and returns the module
    equivalent.

    Args:
      type_key: {str} the type key referring to the type to be returned.

    Returns:
      {module.Enum|Struct|Union|Interface} translated.
    """
    if type_key in self._type_cache:
      return self._type_cache[type_key]
    else:
      mojom_type = self._graph.resolved_types[type_key]
      return self.UserDefinedFromMojom(type_key, mojom_type)

  def UserDefinedFromMojom(self, type_key, mojom_type):
    """Translates a user defined type to its module equivalent.

    Args:
      type_key: {str} the type key referring to the type in graph.resolved_types
        used to cache the type object.
      mojom_type: {mojom_types_mojom.UserDefinedType} to be translated.

    Returns:
      {module.Enum|Struct|Union|Interface} translated from mojom_type.
    """
    user_defined_types = {
        mojom_types_mojom.UserDefinedType.Tags.struct_type:
        (module.Struct, self.StructFromMojom),
        mojom_types_mojom.UserDefinedType.Tags.enum_type:
        (module.Enum, self.EnumFromMojom),
        mojom_types_mojom.UserDefinedType.Tags.union_type:
        (module.Union, self.UnionFromMojom),
        mojom_types_mojom.UserDefinedType.Tags.interface_type:
        (module.Interface, self.InterfaceFromMojom),
        }
    module_type_class, from_mojom = user_defined_types[mojom_type.tag]
    module_type = module_type_class()

    if module_type.spec == None:
      # module.py expects the spec of user defined types to be set when
      # constructing map, array, and interface request types, but the value
      # appears to be only used for error messages.
      module_type.spec = 'dummyspec'

    # It is necessary to cache the type object before populating it since in
    # the course of populating it, it may be necessary to resolve that same
    # type (say, a struct with a field of its own type).
    self._type_cache[type_key] = module_type
    from_mojom(module_type, mojom_type)

    return module_type


def TranslateFileGraph(graph):
  """Translates a mojom_types_mojom.MojomFileGraph to module.Module(s).

  The input is the output of the parser. The output is the input to the
  various bindings generators.

  Args:
    graph: {mojom_types_mojom.MojomFileGraph} to be translated.

  Return:
    {dict<str, module.Module>} mapping the file's name to its module.Module
    translation for all files in graph.files.
  """
  return {file_name: FileTranslator(graph, file_name).Translate()
      for file_name in graph.files}
