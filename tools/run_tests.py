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


def report_skip(test, results):
    results["skip"] += 1
    reason = test.get("reason", "")
    print("\033[1;33mSKIP : %s    (reason: %s)\033[0m" % (test["name"], reason))


def report_pass(test, results):
    results["pass"] += 1
    print("\033[1;32mPASS : %s\033[0m" % (test["name"]))


def report_fail(test, results):
    results["fail"] += 1
    print("\033[1;31mFAIL : %s\033[0m" % (test["name"]))


def report_final(results):
    print("")
    print("\033[1;34mFinished with all tests\033[0m")
    print("\033[1;32mPASS : %d\033[0m" % (results["pass"]))
    print("\033[1;31mFAIL : %d\033[0m" % (results["fail"]))
    print("\033[1;33mSKIP : %d\033[0m" % (results["skip"]))


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


def run_testset(testset, iotjs, timeout, prefix, skip_expected, show_output, results):
    print("")
    print("\033[1;34mRunning: %s\033[0m" % (testset["path"]))

    owd = fs.getcwd()
    fs.chdir(fs.join(path.TEST_ROOT, testset["path"]))

    for test in testset["tests"]:
        skip = test.get("skip", [])
        if "all" in skip or platform.os() in skip:
            report_skip(test, results)
            continue

        tout = test.get("timeout", timeout)
        cmd = ["timeout", "-k", "30", "%d" % (tout * 60), iotjs, test["name"]]

        if prefix:
            cmd[-2:-2:] = prefix.split()[::]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = proc.communicate()[0]

        if show_output:
            print(output, end='')

        should_fail = test.get("fail", False)
        if bool(proc.returncode) == bool(should_fail) and (skip_expected or check_expected(test, output)):
            report_pass(test, results)
        else:
            report_fail(test, results)

    fs.chdir(owd)


def run_tests(iotjs, timeout=5, prefix="", skip_expected=False, show_output=False):
    iotjs = fs.abspath(iotjs)

    with open(fs.join(path.TEST_ROOT, 'tests.json')) as data_file:
        testsets = json.load(data_file)["testsets"]

    results = {"pass":0, "fail":0, "skip":0}
    for testset in testsets:
        run_testset(testset, iotjs, timeout, prefix, skip_expected, show_output, results)

    report_final(results)
    return results["fail"]


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('iotjs', action='store', help='IoT.js binary to run tests with')
    parser.add_argument('--timeout', type=int, action='store', default=5, help='Timeout for the tests in minutes (default: %(default)s)')
    parser.add_argument('--prefix', action='store', default="", help='Add a prefix to the command running the tests')
    parser.add_argument('--show-output', action='store_true', default=False, help='Print output of the tests (default: %(default)s)')
    parser.add_argument('--skip-expected', action='store_true', default=False, help='Do not check the output of the tests (default: %(default)s)')
    return parser.parse_args()


def main():
    args = get_args()

    exit(run_tests(args.iotjs, args.timeout, args.prefix, args.skip_expected, args.show_output))


if __name__ == "__main__":
    main()
