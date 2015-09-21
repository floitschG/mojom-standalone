#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def _FixPath():
  import os
  import sys

  root_path = os.path.abspath(__file__)
  # bindings directory
  root_path = os.path.dirname(root_path)
  # tools directory
  root_path = os.path.dirname(root_path)
  # public directory
  root_path = os.path.dirname(root_path)

  sys.path.insert(0, os.path.join(root_path, 'tools/bindings/pylib'))
  sys.path.insert(0, os.path.join(root_path, 'tools/bindings/generators'))
  sys.path.insert(0, os.path.join(root_path, 'tools/bindings/third_party'))
  sys.path.insert(0, os.path.join(root_path, 'python'))


_FixPath()


import mojom_file_mojom
import mojom_cpp_generator
