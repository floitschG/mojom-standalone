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
import mojom_files_mojom
import mojom_types_mojom
import module


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
    self._graph = graph
    self._file_name = file_name
    self._types = {}
    self._module = module.Module()
    self._imports = {}

  def Translate(self):
    """Translates the file specified in the constructor.

    Returns:
      {module.Module} representing the translated file.
    """
    mojom_file = self._graph.files[self._file_name]

    mod = self._module
    self.PopulateModuleMetadata(mod, mojom_file)
    mod.imports = [self.ImportFromMojom(imp) for imp in mojom_file.imports]
    # TODO(azani): The key should be equal to SourceFileInfo.file_name of
    # imported types.
    self._imports = {imp['module'].path: imp for imp in mod.imports}

    if mojom_file.declared_mojom_objects:
      if mojom_file.declared_mojom_objects.top_level_constants:
        mod.constants = [
            self.ConstFromMojom(self._graph.resolved_constants[key], None)
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
    # TODO(azani): Fix the path here!
    mod.path = mojom_file.file_name
    mod.namespace = mojom_file.module_namespace
    if mojom_file.attributes:
      mod.attributes = {attr.key: attr.value for attr in mojom_file.attributes}

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
    # TODO(azani): Handle mojom_struct.decl_data.contained_declarations.

  def UnionFieldFromMojom(self, mojom_field):
    """Translates a mojom_types_mojom.UnionField to a module.UnionField.

    Args:
      mojom_field: {mojom_types_mojom.UnionField} to be translated.

    Returns:
      {module.UnionField} translated from mojom_field.
    """
    union_field = module.UnionField()
    self.PopulateCommonFieldValues(union_field, mojom_field)
    union_field.ordinal = mojom_field.tag
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
      struct_field.default = self.EvalConst(mojom_field.default_value)

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
    if mojom.default_value:
      param.default = self.EvalConst(mojom.default_value)
    self.PopulateCommonFieldValues(param, mojom)
    return param

  def PopulateCommonFieldValues(self, field, mojom_field):
    """Populates a number of common field values based on a mojom field.

    Args:
      field: {module.Field|module.Parameter} to be populated.
      mojom_field: {StructField|UnionField} to be translated.
    """
    field.name = mojom_field.decl_data.short_name
    field.kind = self.KindFromMojom(mojom_field.type)
    field.attributes = self.AttributesFromMojom(mojom_field)

  def EnumFromMojom(self, enum, mojom_type, parent_kind=None):
    """Populates a module.Enum based on a MojomEnum.

    Args:
      enum: {module.Enum} to be populated.
      mojom_type: {mojom_types_mojom.Type} referring to the MojomEnum to be
        translated.
      parent_kind: {MojomStruct|MojomInterface} in which the enum is nested.
    """
    assert mojom_type.tag == mojom_types_mojom.UserDefinedType.Tags.enum_type
    mojom_enum = mojom_type.enum_type
    enum.parent_kind = parent_kind
    self.PopulateUserDefinedType(enum, mojom_enum)
    enum.fields = [self.EnumFieldFromMojom(value)
        for value in mojom_enum.values]

  def EnumFieldFromMojom(self, mojom_field):
    """Translates an mojom_types_mojom.EnumValue to a module.EnumField.

    mojom_field: {mojom_types_mojom.EnumValue} to be translated.

    Returns:
      {module.EnumField} translated from mojom_field.
    """
    field = module.EnumField()
    field.name = mojom_field.decl_data.short_name
    field.attributes = self.AttributesFromMojom(mojom_field)
    field.value = self.EvalConst(mojom_field.value)
    field.numeric_value = self.EvalConst(mojom_field.value)
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

    return {attr.key: attr.value for attr in mojom.decl_data.attributes}

  def PopulateUserDefinedType(self, module_type, mojom):
    """Populates fields that are common among user-defined types.

    Args:
      module_type: {module.Struct|Union|Enum} to be populated.
      mojom: {MojomStruct|MojomUnion|MojomEnum} to be translated.
    """
    module_type.attributes = self.AttributesFromMojom(mojom)
    module_type.name = mojom.decl_data.short_name
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
        module_type.imported_from = self._imports[
            mojom.decl_data.source_file_info.file_name]

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
    interface.name = mojom_interface.interface_name
    interface.methods = [self.MethodFromMojom(mojom_method, interface)
        for mojom_method in mojom_interface.methods.itervalues()]

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

  def ConstFromMojom(self, mojom_const, parent_kind):
    """Translates a mojom_types_mojom.DeclaredConstant to a module.Constant.

    Args:
      mojom_const: {mojom_types_mojom.DeclaredConstant} to be translated.
      parent_kind: {module.Struct|Interface} if the constant is nested in a
        struct or interface.

    Returns:
      {module.Constant} translated from mojom_const.
    """
    const = module.Constant()
    const.name = mojom_const.decl_data.short_name
    const.kind = self.KindFromMojom(mojom_const.type)
    const.value = self.EvalConst(mojom_const.value)
    const.parent_kind = parent_kind
    return const

  def EvalConst(self, const):
    """Evaluates a mojom_types_mojom.ConstantValue.

    Args:
      const: {mojom_types_mojom.ConstantValue} to be evaluated.

    Returns:
      {int|float|str|bool} either the value of the constant or a string
      referencing a built-in constant value.
    """
    if const.value.tag == mojom_types_mojom.ConstantValue.Tags.builtin_value:
      mojom_to_builtin = {
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_INFINITY:
          'double.INFINITY',
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_NEGATIVE_INFINITY:
          'double.NEGATIVE_INFINITY',
        mojom_types_mojom.BuiltinConstantValue.DOUBLE_NAN:
          'double.DOUBLE_NAN',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_INFINITY:
          'float.INFINITY',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_NEGATIVE_INFINITY:
          'float.NEGATIVE_INFINITY',
        mojom_types_mojom.BuiltinConstantValue.FLOAT_NAN: 'float.NAN',
          }
      return module.BuiltinValue(mojom_to_builtin[const.value.builtin_value])

    return const.value.data

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
    """Translates a user defined type to its module equivalent.

    Args:
      mojom_type: {mojom_types_mojom.Type} with its type_reference field set to
        be translated.

    Returns:
      {module.Enum|Struct|Union|Interface} translated from mojom_type.
    """
    type_key = mojom_type.type_reference.type_key
    module_type = self.UserDefinedFromTypeKey(type_key)
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
