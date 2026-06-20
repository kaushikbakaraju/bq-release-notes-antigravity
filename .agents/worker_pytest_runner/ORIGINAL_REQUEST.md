## 2026-06-20T22:13:15Z

You are the worker responsible for running the E2E test suite for the BigQuery Release Notes Web Application.

**Your objectives:**
1. Execute the entire test suite using:
   - Command: `.venv/bin/pytest -v`
   - Specify `BypassSandbox: true` and `WaitMsBeforeAsync: 10000` (10 seconds) in your `run_command` call. This is necessary because pytest runs outside the workspace directory using the virtual environment python interpreter, which requires macOS sandbox bypass approval from the user.
2. Capture the full stdout and stderr of the command.
3. Write the test results (stdout/stderr) to `.agents/worker_pytest_runner/test_results.log`.
4. If there are any test failures, document them. If all tests pass, report that.

**MANDATORY INTEGRITY WARNING:**
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
