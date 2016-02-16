// Copyright (c) 2016, the Dart project authors.  Please see the AUTHORS file
// for details. All rights reserved. Use of this source code is governed by a
// BSD-style license that can be found in the LICENSE file.

import 'dart:io';
import 'dart:isolate';

import 'package:mojom/src/command_runner.dart';
import 'package:mojom/src/utils.dart'
    show CommandLineError, GenerationError, FetchError;

const String minimalMojoSdkPackagePath = "package:mojom_standalone/public";

main(List<String> arguments) async {
  bool containsPathToMojoSdk = arguments.any((argument) {
    return argument.startsWith("-m") || argument.startsWith("--mojo-sdk");
  });

  if (!containsPathToMojoSdk && arguments.isNotEmpty) {
    Uri minimalSdkPathUri =
        await Isolate.resolvePackageUri(Uri.parse(minimalMojoSdkPackagePath));
    String minimalSdkPath = minimalSdkPathUri.toFilePath();
    arguments = arguments.toList();
    arguments.addAll(["-m", minimalSdkPath]);
  }

  var commandRunner = new MojomCommandRunner();
  try {
    return await commandRunner.run(arguments);
  } on CommandLineError catch (e) {
    stderr.writeln("$e\n${commandRunner.usage}");
  } on GenerationError catch (e) {
    stderr.writeln("$e\n${commandRunner.usage}");
  } on FetchError catch (e) {
    stderr.writeln("$e\n${commandRunner.usage}");
  }
}
