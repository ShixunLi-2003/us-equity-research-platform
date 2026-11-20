# Research protocol

## Time contract

For signal close t, features may use observations available by that close. The demo label is open(t+2)/open(t+1)-1. A training row is admitted only if its label-end date is strictly before the next prediction date. This purges unfinished outcome intervals. Training is limited to the most recent 80 prior sessions. Model hyperparameters, feature columns and portfolio size are fixed in the example.

The native account executes the rank list at the following session open. Same-day closing prices enter only end-of-session marking. The final two dates are not signal dates, because their future labels would be incomplete.

## Real-data acceptance criteria

1. Use an exchange calendar with half days and DST. Normalize minute start/end conventions explicitly.
2. Maintain immutable raw observations, provider/feed metadata and coverage reports. Empty responses cannot count as valid coverage.
3. Use filing availability timestamps, including publication lags and amendments. Never join current financial values backward over history.
4. Align split-adjusted feature returns with raw executable prices and share adjustments. Flag unsupported held events.
5. Define historical security identity and universe membership. A current 500-stock list is not a survivorship-free historical universe.
6. Select features, model and top-N/holding policy on development periods only; freeze the entire decision rule before forward monitoring.
7. Report net returns, drawdown, turnover, exposure, concentration, benchmark beta, fill rates and parameter sensitivity together.

## Comparisons worth reproducing

Compare momentum/linear baselines, Random Forest, Extra Trees, gradient boosting and neural models under identical timestamps, universes and costs. Keep ETF regime variables in a separately evaluated risk overlay if that is the declared research design. Compare raw scores with neutralized scores, sector/beta controls, equal-weight selected-name returns and matched benchmarks. Apply feature-group ablation using development data; do not pick exclusions from the final period.

Historical 2025+ periods were repeatedly inspected in the source project. They are historical comparison periods, not new independent tests. A high cumulative return with a large drawdown does not establish stable alpha. The synthetic example here makes no financial claim.
