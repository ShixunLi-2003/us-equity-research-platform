# Research record and evidence boundaries

The source project explored US equity cross-sectional prediction with minute/daily market data and SEC fundamentals, including tree ensembles and neural predictors. It developed ETF risk separation, model-specific holding-policy searches and chronological evaluation. Frozen MLP and Extra Trees models were subsequently connected to a Paper account through separate virtual ledgers.

Observed work included correcting minute timestamp alignment between providers, testing whole-share feasibility, investigating turnover and holding horizons, auditing company actions and excluding inactive securities. Paper operations exposed sparse IEX quote coverage, scheduler interruptions, integration mismatches and equity reconciliation issues.

This repository includes the extracted execution implementation and a new reproducible integration example. It does not include an independently audited empirical performance table. Historical headline returns are deliberately not used as a hiring claim: the periods were repeatedly inspected, some early runs had data/execution defects, and the complete research selection history is not independently validated.

For a credible future empirical report, publish a signed/hash-addressed experiment manifest with universe vintage, provider/feed, time convention, adjustment policy, feature availability, train/selection/evaluation boundaries, hyperparameters, execution assumptions, costs, benchmark and all selection trials. Report failed and zero-fill sessions alongside successful ones.
