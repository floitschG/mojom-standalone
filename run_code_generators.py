#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script accepts the output of version 2 of the mojom parser and uses that
# data to invoke the code generators.

import argparse
import imp
import os
import sys


def _ParseCLIArgs():
  """Parses the command line arguments.

  Returns:
    tuple<Namespace, list<str>> The first value of the tuple is a Namespace
    holding the value of the optional args. The second value of the tuple is
    a list of the remaining arguments.
  """
  parser = argparse.ArgumentParser(
      description='Generate bindings from mojom parser output.')
  parser.add_argument('-f', '--file-graph', dest='file_graph',
                      help='Location of the parser output. "-" for stdin. '
                      '(default "-")', default='-')
  parser.add_argument('-p', '--python-sdk-dir', dest='python_sdk_dir',
                      default=None,
                      help='Location of the compiled python bindings')
  parser.add_argument("-o", "--output-dir", dest="output_dir", default=".",
                      help="output directory for generated files")
  parser.add_argument("-g", "--generators", dest="generators_string",
                      metavar="GENERATORS",
                      default="c++,dart,go,javascript,java,python",
                      help="comma-separated list of generators")
  parser.add_argument("-d", "--depth", dest="depth", default=".",
                      help="relative path to the root of the source tree.")

  return parser.parse_known_args()

# We assume this script is located in the Mojo SDK in tools/bindings.
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
SDK_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir))
PYTHON_SDK_DIR = os.path.abspath(os.path.join(SDK_ROOT, "python"))

def _FixPath():
  # We parse command line args before imports in case the caller wishes to
  # specify an alternative location for the Mojo Python SDK.
  # TODO(rudominer) Consider removing this flexibility as I can think of
  # no good reason for it.
  args, _ = _ParseCLIArgs()
  python_sdk_dir = args.python_sdk_dir
  if not python_sdk_dir:
    python_sdk_dir = PYTHON_SDK_DIR
  sys.path.insert(0, python_sdk_dir)
  # In order to use mojom_files_mojom we need to make sure the dummy mojo_system
  # can be found on the python path.
  sys.path.insert(0, os.path.join(python_sdk_dir, "dummy_mojo_system"))

  sys.path.insert(0, os.path.join(THIS_DIR, "pylib"))


_FixPath()


from mojom.generate.generated import mojom_files_mojom
from mojom.generate import mojom_translator
from mojo_bindings import serialization


def LoadGenerators(generators_string):
  if not generators_string:
    return []  # No generators.

  script_dir = os.path.dirname(os.path.abspath(__file__))
  generators = []
  for generator_name in [s.strip() for s in generators_string.split(",")]:
    # "Built-in" generators:
    if generator_name.lower() == "c++":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_cpp_generator.py")
    elif generator_name.lower() == "dart":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_dart_generator.py")
    elif generator_name.lower() == "go":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_go_generator.py")
    elif generator_name.lower() == "javascript":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_js_generator.py")
    elif generator_name.lower() == "java":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_java_generator.py")
    elif generator_name.lower() == "python":
      generator_name = os.path.join(script_dir, "generators",
                                    "mojom_python_generator.py")
    # Specified generator python module:
    elif generator_name.endswith(".py"):
      pass
    else:
      print "Unknown generator name %s" % generator_name
      sys.exit(1)
    generator_module = imp.load_source(os.path.basename(generator_name)[:-3],
                                       generator_name)
    generators.append(generator_module)
  return generators


def ReadMojomFileGraphFromFile(fp):
  """Reads a mojom_files_mojom.MojomFileGraph from a file.

  Args:
    fp: A file pointer from which a serialized mojom_fileS_mojom.MojomFileGraph
        can be read.

  Returns:
    The mojom_files_mojom.MojomFileGraph that was deserialized from the file.
  """
  data = bytearray(fp.read())
  context = serialization.RootDeserializationContext(data, [])
  return mojom_files_mojom.MojomFileGraph.Deserialize(context)


def FixModulePath(module, src_root_path):
  """Fix the path attribute of the provided module and its imports.

  The path provided for the various modules is the absolute path to the mojom
  file which the module represents. But the generators expect the path to be
  relative to the root of the source tree.

  Args:
    module: {module.Module} whose path is to be updated.
    abs_root: {str} absolute path to the root of the source tree.
  """
  module.path = os.path.relpath(module.path, src_root_path)
  if not hasattr(module, 'imports'):
    return
  for import_dict in module.imports:
    FixModulePath(import_dict['module'], src_root_path)


def main():
  args, remaining_args = _ParseCLIArgs()

  if args.file_graph == '-':
    fp = sys.stdin
  else:
    fp = open(args.file_graph)

  mojom_file_graph = ReadMojomFileGraphFromFile(fp)
  modules = mojom_translator.TranslateFileGraph(mojom_file_graph)

  generator_modules = LoadGenerators(args.generators_string)

  for _, module in modules.iteritems():
    FixModulePath(module, os.path.abspath(args.depth))
    for generator_module in generator_modules:
      generator = generator_module.Generator(module, args.output_dir)

      # Look at unparsed args for generator-specific args.
      filtered_args = []
      if hasattr(generator_module, 'GENERATOR_PREFIX'):
        prefix = '--' + generator_module.GENERATOR_PREFIX + '_'
        filtered_args = [arg for arg in remaining_args
                         if arg.startswith(prefix)]

      generator.GenerateFiles(filtered_args)


if __name__ == "__main__":
  sys.exit(main())
