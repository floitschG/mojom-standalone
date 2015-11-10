#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script drives the mojom bindings generation."""


import argparse
import os
import platform
import subprocess
import sys

def RunParser(args):
  """Runs the mojom parser.

  Args:
    args: {Namespace} The parsed arguments passed to the script.

  Returns:
    {str} The serialized mojom_files.MojomFileGraph returned by mojom parser.
  """
  if platform.system() != "Linux" or platform.architecture()[0] != "64bit":
    raise Exception("The mojom parser currently only works on Linux 64 bits.")

  mojom_parser = os.path.join(
      args.depth, "mojom", "mojom_parser", "bin", "linux64", "mojom_parser")
  # TODO(azani): Automatically detect the OS and select the right binary.

  if args.mojom_parser:
    mojom_parser = args.mojom_parser
  if not os.path.exists(mojom_parser):
    raise Exception(
        "The mojom parser could not be found at %s. "
        "You may need to run gclient sync."
        % mojom_parser)

  cmd = [mojom_parser]
  if args.import_directories:
    cmd.extend(["-I", ",".join(args.import_directories)])

  cmd.extend(args.filename)

  return subprocess.check_output(cmd)


def RunGenerators(serialized_file_graph, args, remaining_args):
  """Runs the code generators.

  As a side-effect, this function will create the generated bindings
  corresponding to the serialized_file_graph passed in.

  Args:
    serialized_file_graph: {str} A serialized mojom_files.MojomFileGraph.
    args: {Namespace} The parsed arguments passed to the script.
    remaining_args: {list<str>} The unparsed arguments pass to the script.

  Returns:
    The exit code of the generators.
  """
  cmd = [os.path.join(os.path.dirname(__file__), "run_code_generators.py")]

  cmd_args = {
      "--file-graph": "-",
      "--output-dir": args.output_dir,
      "--generators": args.generators_string,
      "--depth": args.depth,
      }

  if args.py_bindings_dir:
    cmd_args["--python-bindings-dir"] = args.py_bindings_dir
  else:
    # By default the python bindings are expected to be under the output
    # directory.
    cmd_args["--python-bindings-dir"] = os.path.join(
        os.path.dirname(args.output_dir), "python")

  for name, value in cmd_args.iteritems():
    cmd.extend([name, value])

  # Some language-specific args may be found in remaining_args. See
  # run_code_generators.py and look for GENERATOR_PREFIX for more information.
  cmd.extend(remaining_args)

  process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
  process.communicate(serialized_file_graph)
  return process.wait()


def main(argv):
  parser = argparse.ArgumentParser(
      description="Generate bindings from mojom files.")
  parser.add_argument("filename", nargs="+",
                      help="mojom input file")
  parser.add_argument("-d", "--depth", dest="depth", default=".",
                      help="Relative path from the current directory to the "
                      "source root.")
  parser.add_argument("-o", "--output_dir", dest="output_dir", default=".",
                      help="output directory for generated files")
  parser.add_argument("-g", "--generators", dest="generators_string",
                      metavar="GENERATORS",
                      default="c++,dart,go,javascript,java,python",
                      help="comma-separated list of generators")
  parser.add_argument("--debug_print_intermediate", action="store_true",
                      help="print the intermediate representation")
  parser.add_argument("-I", dest="import_directories", action="append",
                      metavar="directory", default=[],
                      help="add a directory to be searched for import files")
  parser.add_argument("-mojom-parser", dest="mojom_parser",
                      help="Location of the mojom parser.")
  parser.add_argument("--use_bundled_pylibs", action="store_true",
                      help="use Python modules bundled in the SDK")
  parser.add_argument("-p", "--python-bindings-dir", dest="py_bindings_dir",
                      help="Location of the compiled python bindings",
                      default="")
  (args, remaining_args) = parser.parse_known_args(argv)

  serialized_file_graph = RunParser(args)

  return RunGenerators(serialized_file_graph, args, remaining_args)


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
