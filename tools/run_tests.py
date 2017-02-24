#!/usr/bin/env python

# Copyright 2016-present Samsung Electronics Co., Ltd. and other contributors
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
import subprocess
import os

from common_py import path
from common_py.system.filesystem import FileSystem as fs
from common_py.system.platform import Platform

platform = Platform()


class Reporter(object):
    _TERM_PASS = "\033[1;32m"
    _TERM_FAIL = "\033[1;31m"
    _TERM_SKIP = "\033[1;33m"
    _TERM_INFO = "\033[1;34m"
    _TERM_BASE = "\033[0m"

    @staticmethod
    def report_testset(testset):
        print()
        print("%sRunning: %s%s" % (_TERM_INFO, testset, _TERM_BASE))

    @staticmethod
    def report_skip(test, reason):
        print("%sSKIP : %s (%s)%s" % (_TERM_SKIP, test, reason, _TERM_BASE))

    @staticmethod
    def report_pass(test):
        print("%sPASS : %s%s" % (_TERM_PASS, test, _TERM_BASE))

    @staticmethod
    def report_fail(test):
        print("%sFAIL : %s%s" % (_TERM_FAIL, test, _TERM_BASE))

    @staticmethod
    def report_final(results):
        print("")
        print("%sFinished with all tests%s" % (_TERM_INFO, test, _TERM_BASE))
        print("%sPASS : %d%s" % (_TERM_PASS, results["pass"], _TERM_BASE))
        print("%sFAIL : %d%s" % (_TERM_FAIL, results["fail"], _TERM_BASE))
        print("%sSKIP : %d%s" % (_TERM_SKIP, results["skip"], _TERM_BASE))


class TestRunner(object):
    def __init__(self, arguments):
        self.iotjs = fs.abspath(arguments.iotjs)
        self.timeout = arguments.timeout
        self.cmd_prefix = arguments.cmd_prefix
        self.show_output = arguments.show_output
        self.skip_expected = arguments.skip_expected

        self.results = { "pass": 0, "fail": 0, "skip": 0 }

    def run(self):
        with open(fs.join(path.TEST_ROOT, 'testsets.json')) as testsets_file:
            testsets = json.load(testsets_file)

        for testset, tests in testsets.items():
            run_testset(testset, tests, results)

    def run_testset(self, testset, tests):
        Reporter.report_testset(testset)

        for test in tests:
            test_name = test.get("name")
            skip_list = test.get("skip", [])

            if "all" in skip or platform.os() in skip_list:
                Reporter.report_skip(test_name, test.get("reason", ""))
                self.results["skip"] += 1
                continue

            timeout = test.get("timeout", self.timeout)
            command = ["timeout", "-k", "30", timeout, self.iotjs, test_name]

            if self.cmd_prefix:
                command.insert(1, self.cmd_prefix.split())

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = process.communicate()[0]
            exitcode = process.returncode

            if self.show_output:
                print(output, end='')

            should_fail = test.get("fail", False)
            
            if (exitcode and should_fail) and (skip_expected or check_expected(test, output)):
                self.results["pass"] += 1
                Reporter.report_pass(test_name)
            else:
                self.results["fail"] += 1
                Reporter.report_fail(test_name)

    def check_expected(test, output):
        expected_file = test.get("expected")
        if expected_file:
            file_path = fs.join("expected", expected_file)
            try:
                with open(file_path) as input:
                    if output != input.read():
                        return False
            except IOError:
                print("Expected file not found: %s" % (file_path))
                return False

        return True

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('iotjs', action='store', help='IoT.js binary to run tests with')
    parser.add_argument('--timeout', action='store', default=300, type=int, help='Timeout for the tests in seconds (default: %(default)s)')
    parser.add_argument('--cmd-prefix', action='store', default="", help='Add a prefix to the command running the tests')
    parser.add_argument('--show-output', action='store_true', default=False, help='Print output of the tests (default: %(default)s)')
    parser.add_argument('--skip-expected', action='store_true', default=False, help='Do not check the output of the tests (default: %(default)s)')
    return parser.parse_args()


def main():
    arguments = get_args()

    testrunner = TestRunner(arguments)
    testrunner.run()

if __name__ == "__main__":
    main()
