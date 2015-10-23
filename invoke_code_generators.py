#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script accepts the output of version 2 of the mojom parser and uses that
# data to invoke the code generators.
#
# This script is not related mojom_bindings_generator.py (which is part of v1
# of the mojom parser pipeline).

def _ProcessArgs():
  import argparse

  parser = argparse.ArgumentParser(
      description='Generate bindings from mojom parser output.')
  parser.add_argument('-f', '--file-graph', dest='file_graph',
                      help='Location of the parser output. "-" for stdin. '
                      '(default "-")', default='-')
  parser.add_argument('-p', '--python-bindings-dir', dest='py_bindings_dir',
                      default='out/Debug/python',
                      help='Location of the compiled python bindings')
  parser.add_argument("-o", "--output-dir", dest="output_dir", default=".",
                      help="output directory for generated files")
  parser.add_argument("-g", "--generators", dest="generators_string",
                      metavar="GENERATORS",
                      default="c++,dart,go,javascript,java,python",
                      help="comma-separated list of generators")

  args, remaining_args = parser.parse_known_args()

  if remaining_args:
    raise Exception('Unexpected positional arguments: %s' %
        ', '.join(remaining_args))

  return args


def _FixPath(args):
  import sys
  import os
  sys.path.insert(0, args.py_bindings_dir)
  sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "pylib"))


# We need to parse command line args before imports so we can find out where
# the python bindings are located and add them to sys.path.
args = _ProcessArgs()
_FixPath(args)


import imp
import os
import sys
import mojom_files_mojom
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


def main(args):
  if args.file_graph == '-':
    fp = sys.stdin
  else:
    fp = open(args.file_graph)

  mojom_file_graph = ReadMojomFileGraphFromFile(fp)
  modules = mojom_translator.TranslateFileGraph(mojom_file_graph)

  generator_modules = LoadGenerators(args.generators_string)

  for _, module in modules.iteritems():
    # TODO(azani): Fix module path
    for generator_module in generator_modules:
      generator = generator_module.Generator(module, args.output_dir)
      # TODO(azani): Handle language-specific args
      generator.GenerateFiles([])



if __name__ == "__main__":
  sys.exit(main(args))
