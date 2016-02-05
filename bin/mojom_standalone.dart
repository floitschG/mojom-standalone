// Copyright (c) 2016, the Dart project authors.  Please see the AUTHORS file
// for details. All rights reserved. Use of this source code is governed by a
// BSD-style license that can be found in the LICENSE file.

import 'dart:async';
import 'dart:io';
import 'dart:isolate';

final Uri mojomCompilerUri = Uri.parse("package:mojom_standalone/public/tools/"
    "bindings/mojom_bindings_generator.py");

// A simple script that invokes the mojom-compiler.
//
// By providing a Dart script, users can run the mojom-compiler through
// `pub global active` and `pub run`.
Future main(List<String> arguments) async {
  // Make a copy.
  arguments = arguments.toList();
  Uri resolvedUri = await Isolate.resolvePackageUri(mojomCompilerUri);
  arguments.insert(0, resolvedUri.toFilePath());
  // print("python ${arguments.join(" ")}");
  var process = await Process.start("python", arguments);
  process.stdout.pipe(stdout);
  process.stderr.pipe(stderr);
  int exitCode = await process.exitCode;
  exit(exitCode);
}