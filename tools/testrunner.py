#!/usr/bin/env python

# Copyright 2017-present Samsung Electronics Co., Ltd. and other contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import argparse
import json
import signal
import subprocess
import os
import sys

from common_py import path
from common_py.system.filesystem import FileSystem as fs
from common_py.system.executor import Executor as ex
from common_py.system.platform import Platform

platform = Platform()


class Reporter(object):
    @staticmethod
    def message(msg="", color=ex._TERM_EMPTY):
        print("%s%s%s" % (color, msg, ex._TERM_EMPTY))

    @staticmethod
    def report_testset(testset):
        Reporter.message()
        Reporter.message("Testset: %s" % testset, ex._TERM_BLUE)

    @staticmethod
    def report_pass(test):
        Reporter.message("  PASS: %s" % test, ex._TERM_GREEN)

    @staticmethod
    def report_fail(test):
        Reporter.message("  FAIL: %s" % test, ex._TERM_RED)

    @staticmethod
    def report_timeout(test):
        Reporter.message("  TIMEOUT: %s" % test, ex._TERM_RED)

    @staticmethod
    def report_skip(test, reason):
        skip_message = "  SKIP: %s" % test

        if reason:
            skip_message += "   (Reason: %s)" % reason

        Reporter.message(skip_message, ex._TERM_YELLOW)

    @staticmethod
    def report_configuration(testrunner):
        Reporter.message()
        Reporter.message("Test configuration:")
        Reporter.message("  cmd-prefix:   %s" % testrunner.cmd_prefix)
        Reporter.message("  iotjs:        %s" % testrunner.iotjs)
        Reporter.message("  show-output:  %s" % testrunner.show_output)
        Reporter.message("  skip-modules: %s" % testrunner.skip_modules)
        Reporter.message("  timeout:      %d sec" % testrunner.timeout)

    @staticmethod
    def report_final(results):
        Reporter.message()
        Reporter.message("Finished with all tests:", ex._TERM_BLUE)
        Reporter.message("  PASS:    %d" % results["pass"], ex._TERM_GREEN)
        Reporter.message("  FAIL:    %d" % results["fail"], ex._TERM_RED)
        Reporter.message("  TIMEOUT: %d" % results["timeout"], ex._TERM_RED)
        Reporter.message("  SKIP:    %d" % results["skip"], ex._TERM_YELLOW)


class TimeoutException(Exception):
    pass


def alarm_handler(signum, frame):
    raise TimeoutException


class TestRunner(object):
    def __init__(self, arguments):
        self.iotjs = fs.abspath(arguments.iotjs)
        self.show_output = arguments.show_output
        self.builtins = arguments.builtins
        self.timeout = arguments.timeout
        self.cmd_prefix = []
        self.skip_modules = []
        self.results = {}

        if arguments.experimental:
            self.stability = "experimental"
        else:
            self.stability = "stable"

        if arguments.cmd_prefix:
            self.cmd_prefix = arguments.cmd_prefix.split()

        if arguments.skip_modules:
            self.skip_modules = arguments.skip_modules.split(",")

        signal.signal(signal.SIGALRM, alarm_handler)

    def run(self):
        Reporter.report_configuration(self)

        self.results = { "pass": 0, "fail": 0, "skip": 0, "timeout": 0 }

        with open(fs.join(path.TEST_ROOT, "testsets.json")) as testsets_file:
            testsets = json.load(testsets_file)

        for testset, tests in testsets.items():
            self.run_testset(testset, tests)

        Reporter.report_final(self.results)

    def run_testset(self, testset, tests):
        Reporter.report_testset(testset)

        for test in tests:
            if self.skip_test(test):
                Reporter.report_skip(test["name"], test.get("reason"))
                self.results["skip"] += 1
                continue

            exitcode = self.run_test(testset, test)
            expected_failure = test.get("expected-failure", False)

            if exitcode == "TIMEOUT":
                Reporter.report_timeout(test["name"])
                self.results["timeout"] += 1

            elif (bool(exitcode) == expected_failure):
                Reporter.report_pass(test["name"])
                self.results["pass"] += 1

            else:
                Reporter.report_fail(test["name"])
                self.results["fail"] += 1

    def run_test(self, testset, test):
            workdir = fs.join(path.TEST_ROOT)
            command = [self.iotjs, testset + '/' + test["name"]]

            process = subprocess.Popen(self.cmd_prefix + command, cwd=workdir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            signal.alarm(test.get("timeout", self.timeout))

            try:
                output = process.communicate()[0]
                exitcode = process.returncode
                signal.alarm(0)

            except TimeoutException:
                process.kill()
                return "TIMEOUT"

            if self.show_output:
                print(output, end="")

            return exitcode

    def skip_test(self, test):
        skip_list = test.get("skip", [])

        # Skip by the `skip` attribute in testsets.json file.
        for i in ['all', Platform().os(), self.stability]:
            if i in skip_list:
                return True

        # Skip by the `--skip-modules` flag.
        for module in self.skip_modules:
            if module in test["name"]:
                return True

        # Skip test if the required module is not enabled.
        name = test["name"][0:-3]
        parts = name.split('_')

        # Test filename does not start with 'test_' so we'll just
        # assume we support it.
        if parts[0] != 'test':
            return False

        # The second part of the array contains the module
        # which is under test.
        tested_module = parts[1]
        for module in self.builtins:
            if module == tested_module:
                return False

        return True


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("iotjs", action="store",
            help="IoT.js binary to run tests with")
    parser.add_argument("--cmd-prefix", action="store",
            help="Add a prefix to the command running the tests")
    parser.add_argument("--show-output", action="store_true", default=False,
            help="Print output of the tests (default: %(default)s)")
    parser.add_argument("--skip-modules", action="store",
            help="Skip the tests that uses the given modules")
    parser.add_argument("--timeout", action="store", default=300, type=int,
            help="Timeout for the tests in seconds (default: %(default)s)")

    return parser.parse_args()


def main():
    arguments = get_args()

    testrunner = TestRunner(arguments)
    testrunner.run()


if __name__ == "__main__":
    main()
