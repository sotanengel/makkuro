# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via a GitHub Security
Advisory (`Security` tab → `Report a vulnerability`). We aim to acknowledge
reports within 3 business days.

Do **not** open a public issue for security matters.

## Supply-chain assurance

This project takes supply-chain security seriously — we handle plaintext
secrets in transit and are therefore a high-value target. See the full
threat model in `docs/SPEC.md` §5.7 / §8. Key commitments:

- Runtime dependencies are kept ≤ 15 and hash-pinned.
- CI routes all `pip install` traffic through the
  [Takumi Guard PyPI proxy](https://shisho.dev/docs/ja/t/guard/quickstart/pypi/)
  (`https://pypi.flatt.tech/simple/`) so known-malicious releases are blocked
  before they execute. Contributors can opt in locally — see
  [README.md](README.md#takumi-guard-サプライチェーン保護).
- Releases are published via PyPI Trusted Publishing (OIDC); no long-lived
  API tokens are stored.
- Wheels and sdists are signed with Sigstore and carry SLSA build provenance.
- Every release produces a CycloneDX SBOM.
- `makkuro verify` allows end users to validate the installed package hashes
  against the published release manifest.

## Scope of this policy

In-scope: code and release artifacts under `sotanengel/makkuro`.
Out-of-scope: vulnerabilities in direct dependencies (report upstream) or in
deployments of makkuro that modify source or skip release verification.
