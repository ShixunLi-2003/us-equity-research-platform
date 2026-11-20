# Operational lessons from the source Paper system

These are observed failure classes, not claims that all remedies have been implemented in this extracted repository.

| Failure | Observed consequence | Engineering acceptance criterion |
|---|---|---|
| Wrapper/function signature mismatch | Passed preparation, failed before submission | Exercise the actual execution call with a fake broker in CI |
| Stale single-venue quotes and wide spreads | Repeated zero-submission sessions | Persist quote age, bid/ask, feed and rejection reason; measure fill feasibility |
| Interactive Windows process interruption | Execution and watchdog stopped while waiting | Durable service ownership, independent watchdog, restart reconciliation |
| Account snapshot read before lengthy activity replay | Equity-only reconciliation failure | Collect timestamped near-synchronous snapshots; bounded retry; preserve strict cash/quantity checks |
| Inactive symbol or new corporate action | Missing features / blocked panel | Versioned universe exclusions, identity tracking, explicit event support |
| Cancel request not yet terminal | Local session stayed unresolved | Reconcile broker terminal state before completing a session |

The equity mismatch was observed; non-atomic snapshots are a hypothesis supported by read order, not a proven root cause. Increasing tolerance without measuring the discrepancy would hide potentially material errors.

Paper fills are simulated outcomes. Submission, acceptance, partial fill, completion and cancellation must be separate states. Restart logic must reconcile persisted intent with broker order identifiers before any retry. Duplicate order prevention is a persistent-state concern, not merely an in-memory flag.

Two strategy ledgers in one account require explicit allocation of shared-symbol fills and fees, plus aggregate reconciliation to broker cash and quantities. A full broker adapter and its operational state are outside this offline release; do not deploy this demo as an unattended trading service.
