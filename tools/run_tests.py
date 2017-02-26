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
import signal
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
        print("%sRunning: %s%s" % (Reporter._TERM_INFO, testset, Reporter._TERM_BASE))


    @staticmethod
    def report_skip(test):
        name = test.get("name")
        reason = test.get("reason")

        print("%sSKIP : %s (%s)%s" % (Reporter._TERM_SKIP, name, reason, Reporter._TERM_BASE))


    @staticmethod
    def report_pass(test):
        print("%sPASS : %s%s" % (Reporter._TERM_PASS, test, Reporter._TERM_BASE))


    @staticmethod
    def report_fail(test):
        print("%sFAIL : %s%s" % (Reporter._TERM_FAIL, test, Reporter._TERM_BASE))


    @staticmethod
    def report_timeout(test):
        print("%sTIMEOUT : %s%s" % (Reporter._TERM_FAIL, test, Reporter._TERM_BASE))


    @staticmethod
    def report_final(results):
        print("")
        print("%sFinished with all tests%s" % (Reporter._TERM_INFO, test, Reporter._TERM_BASE))
        print("%sPASS : %d%s" % (Reporter._TERM_PASS, results["pass"], Reporter._TERM_BASE))
        print("%sFAIL : %d%s" % (Reporter._TERM_FAIL, results["fail"], Reporter._TERM_BASE))
        print("%sSKIP : %d%s" % (Reporter._TERM_SKIP, results["skip"], Reporter._TERM_BASE))


    @staticmethod
    def report_error(message):
        print()
        print("%s%s%s" % (Reporter._TERM_RED, message, Reporter._TERM_BASE))


class TimeoutException(Exception):
    pass


class Timeout:
    def __init__(self, seconds=1):
        self.seconds = seconds


    def handle_timeout(self, signum, frame):
        raise TimeoutException


    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)


    def __exit__(self, type, value, traceback):
        signal.alarm(0)


class TestRunner(object):
    def __init__(self, arguments):
        self.iotjs = fs.abspath(arguments.iotjs)
        self.timeout = arguments.timeout
        self.cmd_prefix = arguments.cmd_prefix
        self.show_output = arguments.show_output
        self.skip_expected = arguments.skip_expected
        self.skip_modules = arguments.skip_modules

        self.results = { "pass": 0, "fail": 0, "skip": 0, "timeout": 0 }


    def run(self):
        with open(fs.join(path.TEST_ROOT, "testsets.json")) as testsets_file_p:
            testsets = json.load(testsets_file_p)

        for testset, tests in testsets.items():
            self.run_testset(testset, tests)


    def run_testset(self, testset, tests):
        Reporter.report_testset(testset)

        for test in tests:
            if self.should_be_skipped(test):
                Reporter.report_skip(test)
                self.results["skip"] += 1
                continue

            self.run_test(testset, test)


    def run_test(self, testset, test):
            test_name = test.get("name")

            timeout = test.get("timeout", self.timeout)
            command = [self.cmd_prefix, self.iotjs, test_name]

            working_directory = fs.join(path.TEST_ROOT, testset)

            try:
                with Timeout(seconds=timeout):
                    process = subprocess.Popen(command,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=working_directory, shell=True)
            except TimeoutException:
                Reporter.report_timeout(test)
                self.results["timeout"] += 1
                return

            output = process.communicate()[0]
            exitcode = process.returncode

            if self.show_output:
                print(output, end='')

            self.validate_results(test, exitcode, output)


    def validate_results(self, test, exitcode, output):
            test_name = test.get("name")

            should_fail = test.get("fail", False)
            expected_file = test.get("expected")

            exitcode_is_ok = not (exitcode and should_fail)
            output_is_ok = self.is_output_as_expected(expected_file)

            if (exitcode_is_ok and output_is_ok):
                Reporter.report_pass(test_name)
                self.results["pass"] += 1
            else:
                Reporter.report_fail(test_name)
                self.results["fail"] += 1


    def is_output_as_expected(self, expected_filename):
        if not expected_filename or self.skip_expected:
            return True

        expected_file = fs.join(paths.TEST_ROOT, testset, expected_filename)

        try:
            with open(expected_file) as expected_file_p:
                expected_output = expected_file_p.read()

                if not output is expected_output:
                    return False

        except IOError as e:
            Reporter.report_error(e.strerror)
            return False

        return True


    def should_be_skipped(self, test):
        test_name = test.get("name")
        skip_list = test.get("skip", [])

        if "all" in skip_list or platform.os() in skip_list:
            return True

        if not self.skip_modules:
            return False

        if any(module in test_name for module in self.skip_modules.split()):
            return True

        return False


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('iotjs', action='store', help='IoT.js binary to run tests with')
    parser.add_argument('--timeout', action='store', default=300, type=int, help='Timeout for the tests in seconds (default: %(default)s)')
    parser.add_argument('--cmd-prefix', action='store', default="", help='Add a prefix to the command running the tests')
    parser.add_argument('--show-output', action='store_true', default=False, help='Print output of the tests (default: %(default)s)')
    parser.add_argument('--skip-expected', action='store_true', default=False, help='Do not check the output of the tests (default: %(default)s)')
    parser.add_argument('--skip-modules', action='store', help='Skip tests that uses the given modules')

    return parser.parse_args()


def main():
    arguments = get_args()

    testrunner = TestRunner(arguments)
    testrunner.run()

if __name__ == "__main__":
    main()
