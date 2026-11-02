# Independent backtest archive scope

Read README.md, 研究规则.md and 准备状态.md before work in this directory.
This is an independent historical test of the existing major-event module.

- Write research inputs, caches, predictions and reports ONLY inside this directory.
- Do not change gold-event-atlas-2023-present, its instructions, its live-update
  workflow, project-wide instructions, baseline-1 or shared strategy inputs.
- The live module may change concurrently. Read it only; identify any evaluated
  version or copy with a timestamp/hash inside this backtest directory.
- engine.py is a simplified comparator, NOT the original event module. Do not
  report comparator performance as the original module's performance.
- Establish a faithful, reproducible mapping of the original analysis framework
  before reporting any reconstructed-original-module results.
- Separate scheduled releases from unscheduled events and warning status.
- Never use retrospective outcomes, later article versions or future prices as
  historical prediction inputs. Preserve frozen predictions.
- Consult status.json before claiming completion. Passing synthetic unit tests
  is not evidence of predictive skill or a completed historical backtest.
- Experimental code was removed on 2026-11-02. Preserve the remaining reports, inputs and frozen results; do not claim they are reproducible from active code.
- Do not message other chats or schedule monitoring without explicit authorization.
