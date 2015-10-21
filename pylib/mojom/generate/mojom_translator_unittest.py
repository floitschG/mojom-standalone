# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import module

try:
  import mojom_translator
  import mojom_files_mojom
  import mojom_types_mojom
  bindings_imported = True
except ImportError:
  bindings_imported = False


@unittest.skipUnless(bindings_imported, 'Could not import python bindings.')
class TranslateFileGraph(unittest.TestCase):

  def test_basics(self):
    g = mojom_files_mojom.MojomFileGraph()

    # File names need to be set so the file can be translated at all.
    g.files = {
        'a.mojom': mojom_files_mojom.MojomFile(
            file_name='a.mojom',
            imports=[]),
        'b.mojom': mojom_files_mojom.MojomFile(
            file_name='b.mojom',
            imports=[]),
        'root/c.mojom': mojom_files_mojom.MojomFile(
            file_name='root/c.mojom',
            imports=[]),
    }

    modules = mojom_translator.TranslateFileGraph(g)
    self.assertEquals(len(modules), len(g.files))


@unittest.skipUnless(bindings_imported, 'Could not import python bindings.')
class TestTranslateFile(unittest.TestCase):

  def test_basics(self):
    graph = mojom_files_mojom.MojomFileGraph(
        resolved_types={})

    file_name = 'root/f.mojom'
    imported_file_name = 'other/a.mojom'
    mojom_file = mojom_files_mojom.MojomFile(
        file_name=file_name,
        module_namespace='somens',
        imports=[imported_file_name])
    imported_file = mojom_files_mojom.MojomFile(
        file_name=imported_file_name,
        module_namespace='somens')
    graph.files = {
        file_name: mojom_file,
        imported_file_name: imported_file,
        }

    mojom_interface = mojom_types_mojom.MojomInterface(
        methods={},
        decl_data=mojom_types_mojom.DeclarationData(
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)),
        interface_name='AnInterface')
    graph.resolved_types['interface_key'] = mojom_types_mojom.UserDefinedType(
        interface_type=mojom_interface)

    mojom_struct = mojom_types_mojom.MojomStruct(
        fields=[],
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='AStruct',
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)))
    graph.resolved_types['struct_key'] = mojom_types_mojom.UserDefinedType(
        struct_type=mojom_struct)

    mojom_union = mojom_types_mojom.MojomUnion(
        fields=[],
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='AUnion',
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)))
    graph.resolved_types['union_key'] = mojom_types_mojom.UserDefinedType(
        union_type=mojom_union)

    mojom_enum = mojom_types_mojom.MojomEnum(
        values=[],
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='AnEnum',
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)))
    graph.resolved_types['enum_key'] = mojom_types_mojom.UserDefinedType(
        enum_type=mojom_enum)

    mojom_const = mojom_types_mojom.DeclaredConstant(
        decl_data=mojom_types_mojom.DeclarationData(short_name='AConst'),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.INT64),
        value=mojom_types_mojom.Value(
          literal_value=mojom_types_mojom.LiteralValue(
            int64_value=30)))
    user_defined_value = mojom_types_mojom.UserDefinedValue()
    user_defined_value.declared_constant = mojom_const
    graph.resolved_values = {'value_key': user_defined_value}

    mojom_file.declared_mojom_objects = mojom_files_mojom.KeysByType(
        interfaces=['interface_key'],
        structs=['struct_key'],
        unions=['union_key'],
        top_level_enums=['enum_key'],
        top_level_constants=['value_key']
        )

    mod = mojom_translator.FileTranslator(graph, file_name).Translate()

    self.assertEquals('f.mojom', mod.name)
    self.assertEquals(mojom_file.file_name, mod.path)
    self.assertEquals(mojom_file.module_namespace, mod.namespace)

    self.assertEquals('a.mojom', mod.imports[0]['module_name'])
    self.assertEquals(imported_file.module_namespace,
        mod.imports[0]['namespace'])
    self.assertEquals(imported_file.file_name, mod.imports[0]['module'].path)

    self.assertEquals(mojom_interface.interface_name, mod.interfaces[0].name)
    self.assertEquals(mojom_struct.decl_data.short_name, mod.structs[0].name)
    self.assertEquals(mojom_union.decl_data.short_name, mod.unions[0].name)
    self.assertEquals(mojom_enum.decl_data.short_name, mod.enums[0].name)
    self.assertEquals(mojom_const.decl_data.short_name, mod.constants[0].name)


@unittest.skipUnless(bindings_imported, 'Could not import python bindings.')
class TestUserDefinedTypeFromMojom(unittest.TestCase):

  def test_structs(self):
    file_name = 'a.mojom'
    graph = mojom_files_mojom.MojomFileGraph()
    mojom_file = mojom_files_mojom.MojomFile(
        file_name='a.mojom',
        module_namespace='foo.bar')
    graph.files = {mojom_file.file_name: mojom_file}

    mojom_struct = mojom_types_mojom.MojomStruct(
        decl_data=mojom_types_mojom.DeclarationData(short_name='FirstStruct'))
    mojom_struct.fields = [
        mojom_types_mojom.StructField(
          decl_data=mojom_types_mojom.DeclarationData(
            short_name='field01',
            declared_ordinal=5),
          type=mojom_types_mojom.Type(
            simple_type=mojom_types_mojom.SimpleType.BOOL)),
        mojom_types_mojom.StructField(
          decl_data=mojom_types_mojom.DeclarationData(
            short_name='field02'),
          type=mojom_types_mojom.Type(
            simple_type=mojom_types_mojom.SimpleType.DOUBLE),
          default_value=mojom_types_mojom.DefaultFieldValue(
            value=mojom_types_mojom.Value(
              literal_value=mojom_types_mojom.LiteralValue(double_value=15)))),
        ]
    mojom_struct.decl_data.source_file_info = mojom_types_mojom.SourceFileInfo(
        file_name=mojom_file.file_name)

    struct = module.Struct()
    translator = mojom_translator.FileTranslator(graph, file_name)
    translator.StructFromMojom(
        struct, mojom_types_mojom.UserDefinedType(struct_type=mojom_struct))

    self.assertEquals('FirstStruct', struct.name)
    self.assertEquals(translator._module, struct.module)

    self.assertEquals(len(mojom_struct.fields), len(struct.fields))
    for gold, f in zip(mojom_struct.fields, struct.fields):
      self.assertEquals(f.name, gold.decl_data.short_name)

    self.assertEquals(module.BOOL, struct.fields[0].kind)
    self.assertEquals(5, struct.fields[0].ordinal)

    self.assertEquals(module.DOUBLE, struct.fields[1].kind)
    self.assertEquals(None, struct.fields[1].ordinal)
    self.assertEquals(15, struct.fields[1].default)

  def test_constant(self):
    graph = mojom_files_mojom.MojomFileGraph()

    mojom_const = mojom_types_mojom.DeclaredConstant()
    mojom_const.decl_data = mojom_types_mojom.DeclarationData(
        short_name='foo')
    mojom_const.type = mojom_types_mojom.Type(
        simple_type=mojom_types_mojom.SimpleType.INT64)
    mojom_const.value = mojom_types_mojom.Value()
    mojom_const.value.literal_value = mojom_types_mojom.LiteralValue(
        int64_value=20)

    struct = module.Struct()
    const = mojom_translator.FileTranslator(graph, None).ConstFromMojom(
        mojom_const, struct)

    self.assertEquals(mojom_const.decl_data.short_name, const.name)
    self.assertEquals(module.INT64, const.kind)
    self.assertEquals(20, const.value)
    self.assertEquals(struct, const.parent_kind)

  def test_enum(self):
    file_name = 'a.mojom'
    mojom_enum = mojom_types_mojom.MojomEnum()
    mojom_enum.decl_data = mojom_types_mojom.DeclarationData(
        short_name='AnEnum',
        source_file_info=mojom_types_mojom.SourceFileInfo(file_name=file_name))
    value1 = mojom_types_mojom.EnumValue(
        decl_data=mojom_types_mojom.DeclarationData(short_name='val1'),
        enum_type_key='AnEnum',
        int_value=20)
    value2 = mojom_types_mojom.EnumValue(
        decl_data=mojom_types_mojom.DeclarationData(short_name='val2'),
        enum_type_key='AnEnum',
        int_value=70)
    mojom_enum.values = [value1, value2]


    graph = mojom_files_mojom.MojomFileGraph()
    enum = module.Enum()
    translator = mojom_translator.FileTranslator(graph, file_name)
    translator.EnumFromMojom(
        enum, mojom_types_mojom.UserDefinedType(enum_type=mojom_enum), None)

    self.assertEquals(translator._module, enum.module)
    self.assertEquals(mojom_enum.decl_data.short_name, enum.name)
    self.assertEquals(len(mojom_enum.values), len(enum.fields))

    self.assertEquals(value1.decl_data.short_name, enum.fields[0].name)
    self.assertEquals(value2.decl_data.short_name, enum.fields[1].name)

    self.assertEquals(value1.int_value, enum.fields[0].value)
    self.assertEquals(value2.int_value, enum.fields[1].value)

    self.assertEquals(value1.int_value,
        enum.fields[0].numeric_value)
    self.assertEquals(value2.int_value,
        enum.fields[1].numeric_value)

  def test_unions(self):
    file_name = 'a.mojom'
    mojom_union = mojom_types_mojom.MojomUnion()
    mojom_union.decl_data = mojom_types_mojom.DeclarationData(
        short_name='AUnion',
        source_file_info=mojom_types_mojom.SourceFileInfo(file_name=file_name))

    field1 = mojom_types_mojom.UnionField(
        tag = 10,
        decl_data=mojom_types_mojom.DeclarationData(short_name='field1'),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.BOOL))
    field2 = mojom_types_mojom.UnionField(
        tag = 11,
        decl_data=mojom_types_mojom.DeclarationData(short_name='field2'),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.DOUBLE))
    mojom_union.fields = [field1, field2]

    graph = mojom_files_mojom.MojomFileGraph()
    union = module.Union()
    translator = mojom_translator.FileTranslator(graph, file_name)
    translator.UnionFromMojom(
        union, mojom_types_mojom.UserDefinedType(union_type=mojom_union))

    self.assertEquals(translator._module, union.module)
    self.assertEquals('AUnion', union.name)
    self.assertEquals(len(mojom_union.fields), len(union.fields))

    for gold, f in zip(mojom_union.fields, union.fields):
      self.assertEquals(gold.decl_data.short_name, f.name)

    self.assertEquals(module.BOOL, union.fields[0].kind)
    self.assertEquals(10, union.fields[0].ordinal)
    self.assertEquals(module.DOUBLE, union.fields[1].kind)
    self.assertEquals(11, union.fields[1].ordinal)

  def test_attributes(self):
    mojom_enum = mojom_types_mojom.MojomEnum()
    mojom_enum.decl_data = mojom_types_mojom.DeclarationData()
    gold = {
        'foo': 'bar',
        'other': 'thing',
        'hello': 'world',
        }
    mojom_enum.decl_data.attributes = []
    for key, value in gold.iteritems():
      mojom_enum.decl_data.attributes.append(
          mojom_types_mojom.Attribute(key=key, value=value))

    graph = mojom_files_mojom.MojomFileGraph()
    attributes = mojom_translator.FileTranslator(
        graph, None).AttributesFromMojom(mojom_enum)

    self.assertEquals(gold, attributes)

  def test_attributes_none(self):
    mojom_enum = mojom_types_mojom.MojomEnum()
    mojom_enum.decl_data = mojom_types_mojom.DeclarationData()
    graph = mojom_files_mojom.MojomFileGraph()
    attributes = mojom_translator.FileTranslator(
        graph, None).AttributesFromMojom(mojom_enum)
    self.assertFalse(attributes)

  def test_imported_struct(self):
    graph = mojom_files_mojom.MojomFileGraph()

    graph.files = {
        'a.mojom': mojom_files_mojom.MojomFile(
            file_name='a.mojom',
            module_namespace='namespace',
            imports=['root/c.mojom']),
        'root/c.mojom': mojom_files_mojom.MojomFile(
            file_name='root/c.mojom',
            module_namespace='otherns',
            imports=[]),
    }

    mojom_struct = mojom_types_mojom.MojomStruct()
    mojom_struct.decl_data = mojom_types_mojom.DeclarationData(
        short_name='AStruct',
        source_file_info=mojom_types_mojom.SourceFileInfo(
          file_name='root/c.mojom'))
    mojom_struct.fields = []

    type_key = 'some_type_key'
    graph.resolved_types = {
        type_key: mojom_types_mojom.UserDefinedType(struct_type=mojom_struct)}
    struct = module.Struct()

    # Translate should create the imports.
    translator = mojom_translator.FileTranslator(graph, 'a.mojom')
    translator.Translate()

    struct = translator.UserDefinedFromTypeRef(
        mojom_types_mojom.Type(
          type_reference=mojom_types_mojom.TypeReference(
            type_key=type_key)))

    self.assertIsNone(struct.module)
    self.assertEquals(translator._imports['root/c.mojom'], struct.imported_from)

  def test_interface(self):
    file_name = 'a.mojom'
    mojom_interface = mojom_types_mojom.MojomInterface(
        decl_data=mojom_types_mojom.DeclarationData(
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)),
        interface_name='AnInterface')
    mojom_method = mojom_types_mojom.MojomMethod(
        ordinal=10,
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='AMethod',
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)),
        parameters=mojom_types_mojom.MojomStruct(fields=[]))
    mojom_interface.methods = {10: mojom_method}

    interface = module.Interface()
    graph = mojom_files_mojom.MojomFileGraph()
    translator = mojom_translator.FileTranslator(graph, file_name)
    translator.InterfaceFromMojom(interface, mojom_types_mojom.UserDefinedType(
      interface_type=mojom_interface))

    self.assertEquals(translator._module, interface.module)
    self.assertEquals(mojom_interface.interface_name, interface.name)
    self.assertEquals(mojom_method.ordinal, interface.methods[0].ordinal)
    # TODO(azani): Add the contained declarations.

  def test_method(self):
    file_name = 'a.mojom'
    mojom_method = mojom_types_mojom.MojomMethod(
        ordinal=10,
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='AMethod',
          source_file_info=mojom_types_mojom.SourceFileInfo(
            file_name=file_name)))

    param1 = mojom_types_mojom.StructField(
        decl_data=mojom_types_mojom.DeclarationData(short_name='a_param'),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.UINT32))
    param2 = mojom_types_mojom.StructField(
        decl_data=mojom_types_mojom.DeclarationData(short_name='b_param'),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.UINT64))
    mojom_method.parameters = mojom_types_mojom.MojomStruct(
        fields=[param1, param2])

    interface = module.Interface()
    graph = mojom_files_mojom.MojomFileGraph()
    translator = mojom_translator.FileTranslator(graph, file_name)
    method = translator.MethodFromMojom(mojom_method, interface)

    self.assertEquals(mojom_method.decl_data.short_name, method.name)
    self.assertEquals(interface, method.interface)
    self.assertEquals(mojom_method.ordinal, method.ordinal)
    self.assertIsNone(method.response_parameters)
    self.assertEquals(
        len(mojom_method.parameters.fields), len(method.parameters))
    self.assertEquals(param1.decl_data.short_name, method.parameters[0].name)
    self.assertEquals(param2.decl_data.short_name, method.parameters[1].name)

    # Add empty return params.
    mojom_method.response_params = mojom_types_mojom.MojomStruct(fields=[])
    method = translator.MethodFromMojom(mojom_method, interface)
    self.assertEquals([], method.response_parameters)

    # Add non-empty return params.
    mojom_method.response_params.fields = [param1]
    method = translator.MethodFromMojom(mojom_method, interface)
    self.assertEquals(
        param1.decl_data.short_name, method.response_parameters[0].name)

  def test_parameter(self):
    # Parameters are encoded as fields in a struct.
    mojom_param = mojom_types_mojom.StructField(
        decl_data=mojom_types_mojom.DeclarationData(
          short_name='param0',
          declared_ordinal=5),
        type=mojom_types_mojom.Type(
          simple_type=mojom_types_mojom.SimpleType.UINT64),
        default_value=mojom_types_mojom.Value(
          literal_value=mojom_types_mojom.LiteralValue(uint64_value=20)))

    graph = mojom_files_mojom.MojomFileGraph()
    translator = mojom_translator.FileTranslator(graph, '')
    param = translator.ParamFromMojom(mojom_param)

    self.assertEquals(mojom_param.decl_data.short_name, param.name)
    self.assertEquals(module.UINT64, param.kind)
    self.assertEquals(mojom_param.decl_data.declared_ordinal, param.ordinal)


@unittest.skipUnless(bindings_imported, 'Could not import python bindings.')
class TestEvalValue(unittest.TestCase):

  def test_literal_value(self):
    mojom = mojom_types_mojom.Value()
    mojom.literal_value = mojom_types_mojom.LiteralValue(int64_value=20)

    graph = mojom_files_mojom.MojomFileGraph()
    const = mojom_translator.FileTranslator(graph, None).EvalValue(mojom)

    self.assertEquals(20, const)

  def test_resolved_user_defined_values(self):
    # TODO(azani): Write this.
    pass

  def test_builtin_const(self):
    mojom = mojom_types_mojom.Value()

    graph = mojom_files_mojom.MojomFileGraph()

    gold = [
        (mojom_types_mojom.BuiltinConstantValue.DOUBLE_INFINITY,
          'double.INFINITY'),
        (mojom_types_mojom.BuiltinConstantValue.DOUBLE_NEGATIVE_INFINITY,
          'double.NEGATIVE_INFINITY'),
        (mojom_types_mojom.BuiltinConstantValue.DOUBLE_NAN,
          'double.DOUBLE_NAN'),
        (mojom_types_mojom.BuiltinConstantValue.FLOAT_INFINITY,
          'float.INFINITY'),
        (mojom_types_mojom.BuiltinConstantValue.FLOAT_NEGATIVE_INFINITY,
          'float.NEGATIVE_INFINITY'),
        (mojom_types_mojom.BuiltinConstantValue.FLOAT_NAN, 'float.NAN'),
        ]

    for mojom_builtin, string in gold:
      mojom.builtin_value = mojom_builtin
      const = mojom_translator.FileTranslator(graph, None).EvalValue(mojom)
      self.assertIsInstance(const, module.BuiltinValue)
      self.assertEquals(string, const.value)


@unittest.skipUnless(bindings_imported, 'Could not import python bindings.')
class TestKindFromMojom(unittest.TestCase):

  def test_simple_type(self):
    simple_types = [
        (mojom_types_mojom.SimpleType.BOOL, module.BOOL),
        (mojom_types_mojom.SimpleType.INT8, module.INT8),
        (mojom_types_mojom.SimpleType.INT16, module.INT16),
        (mojom_types_mojom.SimpleType.INT32, module.INT32),
        (mojom_types_mojom.SimpleType.INT64, module.INT64),
        (mojom_types_mojom.SimpleType.UINT8, module.UINT8),
        (mojom_types_mojom.SimpleType.UINT16, module.UINT16),
        (mojom_types_mojom.SimpleType.UINT32, module.UINT32),
        (mojom_types_mojom.SimpleType.UINT64, module.UINT64),
        (mojom_types_mojom.SimpleType.FLOAT, module.FLOAT),
        (mojom_types_mojom.SimpleType.DOUBLE, module.DOUBLE),
    ]

    g = mojom_files_mojom.MojomFileGraph()
    t = mojom_translator.FileTranslator(g, None)
    for mojom, golden in simple_types:
      self.assertEquals(
          golden, t.KindFromMojom(mojom_types_mojom.Type(simple_type=mojom)))

  def test_handle_type(self):
    handle_types = [
        (mojom_types_mojom.HandleType.Kind.UNSPECIFIED, False,
          module.HANDLE),
        (mojom_types_mojom.HandleType.Kind.MESSAGE_PIPE, False,
          module.MSGPIPE),
        (mojom_types_mojom.HandleType.Kind.DATA_PIPE_CONSUMER, False,
          module.DCPIPE),
        (mojom_types_mojom.HandleType.Kind.DATA_PIPE_PRODUCER, False,
          module.DPPIPE),
        (mojom_types_mojom.HandleType.Kind.SHARED_BUFFER, False,
          module.SHAREDBUFFER),
        (mojom_types_mojom.HandleType.Kind.UNSPECIFIED, True,
          module.NULLABLE_HANDLE),
        (mojom_types_mojom.HandleType.Kind.MESSAGE_PIPE, True,
          module.NULLABLE_MSGPIPE),
        (mojom_types_mojom.HandleType.Kind.DATA_PIPE_CONSUMER, True,
          module.NULLABLE_DCPIPE),
        (mojom_types_mojom.HandleType.Kind.DATA_PIPE_PRODUCER, True,
          module.NULLABLE_DPPIPE),
        (mojom_types_mojom.HandleType.Kind.SHARED_BUFFER, True,
          module.NULLABLE_SHAREDBUFFER),
    ]
    g = mojom_files_mojom.MojomFileGraph()
    t = mojom_translator.FileTranslator(g, None)
    for mojom, nullable, golden in handle_types:
      h = mojom_types_mojom.Type()
      h.handle_type = mojom_types_mojom.HandleType(
          kind=mojom, nullable=nullable)
      self.assertEquals(golden, t.KindFromMojom(h))

  def test_string_type(self):
    g = mojom_files_mojom.MojomFileGraph()
    t = mojom_translator.FileTranslator(g, None)

    s = mojom_types_mojom.Type(string_type=mojom_types_mojom.StringType())
    self.assertEquals(module.STRING, t.KindFromMojom(s))

    s.string_type.nullable = True
    self.assertEquals(module.NULLABLE_STRING, t.KindFromMojom(s))

  def test_array_type(self):
    array_types = [
        (False, False, -1),
        (False, False, 10),
        (True, False, -1),
        (True, True, -1),
        (False, True, -1),
        (False, True, 10),
        ]
    g = mojom_files_mojom.MojomFileGraph()
    t = mojom_translator.FileTranslator(g, None)

    for array_nullable, element_nullable, size in array_types:
      a = mojom_types_mojom.Type()
      a.array_type = mojom_types_mojom.ArrayType(
          nullable=array_nullable,
          fixed_length=size)
      a.array_type.element_type = mojom_types_mojom.Type(
          string_type=mojom_types_mojom.StringType(nullable=element_nullable))

      result = t.KindFromMojom(a)
      self.assertTrue(module.IsArrayKind(result))
      self.assertTrue(module.IsStringKind(result.kind))
      self.assertEquals(array_nullable, module.IsNullableKind(result))
      self.assertEquals(element_nullable, module.IsNullableKind(result.kind))

      if size < 0:
        self.assertIsNone(result.length)
      else:
        self.assertEquals(size, result.length)

  def test_map_type(self):
    map_types = [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]
    g = mojom_files_mojom.MojomFileGraph()
    t = mojom_translator.FileTranslator(g, None)

    for map_nullable, value_nullable in map_types:
      m = mojom_types_mojom.Type()
      m.map_type = mojom_types_mojom.MapType(
          nullable=map_nullable)
      m.map_type.key_type = mojom_types_mojom.Type(
          string_type=mojom_types_mojom.StringType())
      m.map_type.value_type = mojom_types_mojom.Type(
          handle_type=mojom_types_mojom.HandleType(
            kind=mojom_types_mojom.HandleType.Kind.SHARED_BUFFER,
            nullable=value_nullable))

      result = t.KindFromMojom(m)
      self.assertTrue(module.IsMapKind(result))
      self.assertTrue(module.IsStringKind(result.key_kind))
      self.assertTrue(module.IsSharedBufferKind(result.value_kind))
      self.assertEquals(map_nullable, module.IsNullableKind(result))
      self.assertEquals(value_nullable,
          module.IsNullableKind(result.value_kind))

  def test_user_defined_type_type(self):
    graph = mojom_files_mojom.MojomFileGraph()
    mojom_struct = mojom_types_mojom.MojomStruct(
        decl_data=mojom_types_mojom.DeclarationData(short_name='FirstStruct'))
    type_key = 'some opaque string'
    mojom_struct.fields = [
        # Make sure recursive structs are correctly handled.
        mojom_types_mojom.StructField(
          decl_data=mojom_types_mojom.DeclarationData(short_name='field00'),
          type=mojom_types_mojom.Type(
            type_reference=mojom_types_mojom.TypeReference(type_key=type_key)))
        ]
    graph.resolved_types = {
        type_key: mojom_types_mojom.UserDefinedType(struct_type=mojom_struct)}

    mojom_type = mojom_types_mojom.Type()
    mojom_type.type_reference = mojom_types_mojom.TypeReference(
        type_key=type_key)

    t = mojom_translator.FileTranslator(graph, None)
    result = t.KindFromMojom(mojom_type)
    self.assertTrue(module.IsStructKind(result))
    self.assertEquals(mojom_struct.decl_data.short_name, result.name)
    self.assertEquals(result, result.fields[0].kind)

    # Make sure we create only one module object per type.
    result2 = t.KindFromMojom(mojom_type)
    self.assertIs(result, result2)

    # Nullable type reference
    mojom_type.type_reference.nullable = True
    nullable_result = t.KindFromMojom(mojom_type)
    self.assertTrue(module.IsNullableKind(nullable_result))

if __name__ == '__main__':
  unittest.main()
