#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# TODO(azani): Delete when we are done switching over to the v2 compiler.

# This script is temporary. It allows us to switch between v1 and v2 of the
# bindings generation compiler.

import argparse
import os
import sys

import mojom_bindings_generator_v1
import mojom_bindings_generator_v2


def main():
  parser = argparse.ArgumentParser(
      description="Generate bindings from mojom files.", add_help=False)
  parser.add_argument("--compiler-version", type=int, default=2,
                      help="Which compiler version should be used?")
  (args, remaining_args) = parser.parse_known_args()

  if args.compiler_version == 1:
    return mojom_bindings_generator_v1.main(remaining_args)
  elif args.compiler_version == 2:
    return mojom_bindings_generator_v2.main(remaining_args)
  else:
    raise Exception("There are only 2 compiler versions: 1 and 2!")


if __name__ == "__main__":
  sys.exit(main())
