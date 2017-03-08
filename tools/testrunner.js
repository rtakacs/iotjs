/* Copyright 2016-present Samsung Electronics Co., Ltd. and other contributors
 *
 * Licensed under the Apache License, Version 2.0 (the 'License');
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var fs = require('fs');
var util = require('common_js/util');
var Logger = require('common_js/logger').Logger;
var OptionParser = require('common_js/option_parser').OptionParser;
var consoleWrapper = require('common_js/module/console');

// Helper functions
function readSource(filename) {
  return fs.readFileSync(filename).toString();
}

function initFile(file) {
  fs.writeFileSync(file, new Buffer(''));
}


function TestEnvironment(options) {
  this.os = process.platform;
  this.root = util.absolutePath('test');

  this.logger = new Logger();
  this.skipModules = null;
  this.startFrom = null;

  if (file = options['output-file'])
    this.logger.path = util.join(this.root, file);

  if (startFrom = options['start-from'])
    this.startFrom = startFrom;

  if (skipModules = options['skip-module'])
    this.skipModules = skipModules.split(',');
}


function TestRunner(environment) {
  this.results = {
    pass: 0,
    fail: 0,
    skip: 0,
    timeout: 0
  };

  this.environment = environment;
  this.currentTest = null;
  this.timer = null;
}


TestRunner.prototype.run = function() {
  var testfile = util.join(this.environment.root, 'testsets.json');
  var testsets = JSON.parse(readSource(testfile));

  for (testset in testsets) {
    // Step into the current testset directory.
    process.chdir(util.join(this.environment.root, testset));

    testsets[testset].forEach(this.runTest, this);
  }

  // Step back into the test directory.
  process.chdir(this.environment.root);

  this.reportStatistics();
  this.saveCoverage();

  process.doExit(this.results.fail || this.results.timeout);
}


TestRunner.prototype.runTest = function(test, index, array) {
  this.currentTest = test;
  this.currentTest.finished = false;

  if (this.shouldSkip()) {
    this.reportResult('skip');
    return;
  }

  var source = readSource(test['name'])
  var timeout = test['timeout'];

  if (timeout) {
    testrunner = this;

    this.timer = setTimeout(function() {
      testrunner.reportResult('timeout');
    }, timeout * 1000);
  }

  try {
    eval(source);
  } catch(exception) {
    // Testing uncaught exceptions.
    if (test['uncaught'])
      throw exception;

    this.reportPassOrFail(exception);
  } finally {
    // Waiting for async tests.
    if (!this.currentTest.finished)
      this.waitingForFinish();
  }
}


TestRunner.prototype.shouldSkip = function() {
  var testname = this.currentTest['name']

  // Skip tests that are behind the 'start-from' parameter.
  if (this.environment.startFrom) {
    if (testname == this.environment.startFrom) {
      // Disable startFrom checking because the test is reached.
      this.environment.startFrom = null;
      return false;
    }

    return true;
  }

  // Skip tests by the 'skip-modules' parameter.
  if (this.environment.skipModules) {
    for (module in this.environment.skipModules) {
      if (testname.indexOf(this.environment.skipModules[module]) >= 0) {
        return true;
      }
    }
  }

  // Skip tests by their 'skip' attribute.
  if (skip = this.currentTest['skip']) {
    if ((skip.indexOf('all') || skip.indexOf(this.environment.os)) >= 0) {
      return true;
    }
  }

  return false;
}


TestRunner.prototype.waitingForFinish = function() {
  var testrunner = this;

  process.nextTick(function() {
    var timerOnlyAlive = !testdriver.isAliveExceptFor(testrunner.timer);

    if (timerOnlyAlive)
      timerOnlyAlive = !process._onNextTick();

    if (timerOnlyAlive)
      testrunner.finishTest(0);

    if (!testrunner.currentTest.finished)
      testrunner.waitingForFinish();
  });
}


TestRunner.prototype.finishTest = function(exitcode) {
  try {
    process.emitExit(exitcode);
  } catch(exception) {
    // process.on('exit', function { ... }) failure.
    this.reportPassOrFail(exception);
  } finally {
    // Finish normally.
    if (!this.currentTest.finished)
      this.reportPassOrFail(exitcode);
  }
};


TestRunner.prototype.reportPassOrFail = function(result) {
  // Note: 'result' is an exception or an exitcode.
  var shouldFail = this.currentTest['expected-fail']

  if (result && shouldFail)
    status = 'pass'
  else
    status = 'fail'

  this.reportResult(status)
}


TestRunner.prototype.reportResult = function(status) {
  if (this.timer) {
    clearTimeout(this.timer);
    this.timer = null;
  }

  this.currentTest.finished = true;
  this.results[status]++;

  var message = status.toUpperCase() + ': ' + this.currentTest['name']

  if (status == 'skip')
    message = message.concat('  Reason:' + this.currentTest['reason'])

  this.environment.logger.message(message, status);
}


TestRunner.prototype.reportStatistics = function() {
  this.environment.logger.message('Finish all tests', 'summary');

  this.environment.logger.message('PASS :    ' + this.results.pass, 'pass');
  this.environment.logger.message('FAIL :    ' + this.results.fail, 'fail');
  this.environment.logger.message('TIMEOUT : ' + this.results.timeout, 'timeout');
  this.environment.logger.message('SKIP :    ' + this.results.skip, 'skip');
}


TestRunner.prototype.saveCoverage = function() {
  var saveCoverage = this.options['output-coverage'] == 'yes';
  var hasCoverage = typeof __coverage__ !== 'undefined';

  if (saveCoverage && hasCoverage) {
    var data = JSON.stringify(__coverage__);

    if (!fs.existsSync('.coverage_output'))
        fs.mkdirSync('.coverage_output');

    fs.writeFileSync(".coverage_output/js_coverage.data", Buffer(data));
  }
};


function parseOptions() {
  var parser = new OptionParser();

  parser.addOption('start-from', '', '',
    'a test case file name where the testrunner starts');
  parser.addOption('skip-module', '', '',
    'a module list to skip test of specific modules');
  parser.addOption('quiet', 'yes|no', 'yes',
    'a flag that indicates if the testrunner suppresses ' +
    'console outputs of test case');
  parser.addOption('output-file', '', '',
    'a file name where the testrunner leaves output');
  parser.addOption('output-coverage', 'yes|no', 'no',
    'output coverage information');

  return parser.parse();
}


options = parseOptions()

if (options) {
  environment = new TestEnvironment(options)

  // TestRunner should bound to the process module to indicate
  // for IoT.js that tests are runned by a testsystem.
  process.testrunner = new TestRunner(environment)
  process.testrunner.run()
}
