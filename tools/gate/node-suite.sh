#!/usr/bin/env bash
# One of the frontend suites under Node's test runner, with two limits a runaway test cannot pass.
#
#   tools/gate/node-suite.sh verify/team_analytics_page.cjs              one or more runner files
#   tools/gate/node-suite.sh --may-start-browser verify/task_progress.cjs
#
# - Every process of the run may map at most NODE_SUITE_MEMORY_KB of address space (default 8 GiB;
#   the page suite, the largest, peaks below 1 GiB of resident memory). A test that allocates
#   without bound then dies at that size with an allocation failure, and the suite fails.
# - Every test has NODE_SUITE_TEST_TIMEOUT_MS to finish (default one minute; a test of these
#   suites takes milliseconds to a few seconds).
#
# --may-start-browser is for the one suite that can start a real browser, the task progress suite
# with BROWSER_BIN set. A browser does not start inside such an address-space limit (it reserves
# far more than it uses), so for that suite, and only while BROWSER_BIN is set, the memory limit is
# left off, with a line saying so; the time limit stays. Without the option BROWSER_BIN changes
# nothing: the other suites keep their memory limit whatever the environment holds.
#
# Why: Node's test runner has neither limit by default, and the limit of the JavaScript heap does
# not bound a process. On 2026-11-16 one failing assertion that compared a mounted DOM element
# (which Node then tried to print, walking React's internal graph) took 49.5 GB in two minutes and
# stopped the machine it ran on. The page suite's helper now refuses such a comparison; these two
# limits are the net under whatever else can run away.
set -euo pipefail

may_start_browser=0
if [ "${1:-}" = "--may-start-browser" ]; then
    may_start_browser=1
    shift
fi
if [ "$#" -eq 0 ]; then
    echo "usage: tools/gate/node-suite.sh [--may-start-browser] RUNNER.cjs [RUNNER.cjs...]" >&2
    exit 2
fi

if [ "$may_start_browser" = 1 ] && [ -n "${BROWSER_BIN:-}" ]; then
    echo "tools/gate/node-suite.sh: BROWSER_BIN is set, so the memory limit is off for this run" >&2
else
    ulimit -v "${NODE_SUITE_MEMORY_KB:-8388608}"
fi
exec node --test --test-timeout="${NODE_SUITE_TEST_TIMEOUT_MS:-60000}" "$@"
