# Scope and provenance

This package is extracted from an existing private research workspace. The C++ core, Python native wrapper and native/data-audit tests originate from its `hybrid_quant` component. `feature_adjustments.py` and the pure planning/replay portion of `ledger.py` originate from its Alpaca bridge. The broker launch CLI was excluded. The portable source build, synthetic rolling integration example, temporal and ledger tests, CI and public documentation were added for this release.

The original workspace also contains extensive date-specific research, model sweeps, frozen contracts, cloud tasks and broker ledger code. Those remain in the private source project. This repository is a curated engineering release, not a byte-for-byte archive of that workspace. It does not yet reproduce every historical experiment or the original 12-model sweep from raw data.

No account records, credentials, weights, raw data or third-party factor-library copies are included. No third-party code license is inferred from availability in the private workspace. NumPy, pandas, scikit-learn and the compiler are dependencies with their own licenses.

Before publication: review the generated source tree and tests; select a source license after confirming rights; add the author's name/contact through GitHub profile rather than private operational metadata. Hosted CI results must be confirmed after the first push.
