# Validation record

Local verification on 2026-11-20:

- Built the native library from source using Visual Studio 2022 MSVC x64.
- Python 3.9 environment: 17 unittest tests passed.
- Synthetic integration completed 98 rolling windows and generated 268 simulated fills.
- Example cost assumptions: 2 bps commission and 5 bps slippage; initial cash USD 10,000.
- Synthetic return was approximately -4.57%, maximum drawdown approximately -10.79%. These numbers describe generated test data, not market performance; the negative outcome is retained unchanged.
- Source package excludes native binaries, datasets, credentials, model files and generated experiment outputs.
- Targeted source scan found no known personal account identifier, email, remote host or private local project path.

The old local GCC was 32-bit and produced an incompatible DLL for 64-bit Python. The build script now prefers MSVC x64 on Windows. GCC/Clang users must match the interpreter architecture.

The installed pandas/NumPy combination emitted a deprecation warning during date membership filtering. It did not fail testing. Dependencies have compatible ranges, not a fully hashed cross-platform lockfile. Linux CI is configured but has not been run on GitHub yet.

No broker endpoint was called and no order was submitted during this extraction. This record does not certify the separate cloud Paper deployment or its unresolved equity-reconciliation problem.
