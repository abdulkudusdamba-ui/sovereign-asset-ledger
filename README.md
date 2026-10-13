# Sovereign Asset Ledger

SAL's blockchain provenance module complements the existing asset registry,
Asset Passports, and immutable audit events. It does not replace SAL's database,
make a blockchain the asset registry, or prove legal ownership.

## Architecture and current implementation

SAL currently uses an authenticated SQL database as its operational registry.
The provenance module commits selected, already-accepted immutable audit events.
The provider interface (`app/blockchain/provider.py`) separates commitment and
anchor processing from the registry. The only configured provider is the
deterministic `MockLedgerProvider` on `sal-mocknet-v1`. It performs no network
calls, stores no external ledger data, and incurs no transaction fees; its
references simulate confirmations for local development and tests only.

The deployment options have different trade-offs:

| Option | Benefits | Trade-offs |
| --- | --- | --- |
| Permissioned institutional ledger | Controlled membership, governance, and potentially predictable fees and throughput | Requires participating institutions, shared governance, resilient operators, and long-term protocol maintenance; outages or a small validator set affect availability and independence |
| Public-chain anchors | Broad independent availability and externally checkable transaction references | Fees and throughput vary; public data is permanent, privacy-sensitive, and subject to network and contract lifecycle risk |
| Hybrid (future direction) | Keep operational/private data in SAL or a governed network while selectively anchoring commitments publicly | More operational complexity and cross-system availability/governance work; public anchors still require privacy review and fees |

The practical development choice is the provider-neutral mock ledger. No live
network, institutional consortium, or transaction-cost-bearing deployment is
configured. A future deployment can select a governed permissioned network or
selectively anchor commitments on a public network after authorization, privacy
review, and provider implementation.

## Commitment format and privacy

`SAL-PROVENANCE-COMMITMENT-v1` uses compact UTF-8 JSON with sorted keys,
consistent separators, Unicode preserved, and non-finite numbers rejected. The
versioned allow-list includes the SAL asset identifier, passport/event
references, record version (from the event snapshot when present), action,
entity identity, event time/result, and before/after event snapshots. It
excludes actor IDs, IP addresses, user agents, device IDs, reasons, and arbitrary
audit metadata. SHA-256 hashes a domain separator, a fresh 256-bit random nonce,
and the canonical document. Each accepted audit event has one idempotent,
immutable commitment row; later events link to the previous commitment rather
than replacing it.

The nonce, hash, optional signature, and anchor metadata are stored in SAL.
Sensitive event content stays in the existing protected audit record and is
never returned by provenance APIs or sent to a ledger. Authorized users can
retrieve the nonce with the commitment metadata and independently recompute
the digest against an authorized copy of the event. A hash is not anonymity:
nonce disclosure allows guessing candidate event contents, so proof material
must only be shared with authorized verifiers. SAL's access controls and audit
logging remain essential.

An optional HMAC-SHA-256 institutional signature covers the commitment
identifier and digest. Its key is supplied via
`SAL_PROVENANCE_SIGNING_KEY`, must be at least 32 bytes, and is never stored in
the database. The key ID is recorded for rotation metadata. Development may
omit a key, in which case commitments are unsigned. Production configuration
requires a key. Production deployments should inject it from a managed secret
store and replace/configure the signing implementation for managed asymmetric
keys or an HSM; this local HMAC implementation is not a public-key signature
service. Plan key rotation by assigning a new key ID and retaining a
controlled verification path for prior keys. On suspected compromise, revoke
the affected key, preserve existing evidence, record the incident in SAL's
audit history, and issue new commitments for corrected/current versions rather
than rewriting historical commitments.

Individual events are anchored independently. Merkle batching and inclusion
proofs are not implemented. The mock provider marks an anchor confirmed only
after its local `anchor()` method returns a receipt; this is simulated
confirmation, not a real blockchain transaction or independent external
consensus.

## APIs and status semantics

All provenance routes require an authenticated `admin`, `registrar`, or
`government` user. Retrying failed anchors requires `admin`.

- `POST /provenance/events/{event_id}/commitment` commits an existing accepted
  audit event and is idempotent per event.
- `GET /provenance/passports/{passport_id}/commitments` lists the commitments
  associated with that Passport's lifecycle events.
- `GET /provenance/commitments/{commitment_id}` returns commitment and permitted
  anchor metadata, including the nonce needed for authorized independent
  verification. It does not return the underlying event snapshots.
- `GET /provenance/commitments/{commitment_id}/verify` checks the stored event
  against the digest, verifies a configured signature when possible, and
  checks the provider reference.
- `POST /provenance/commitments/{commitment_id}/retry` retries a non-confirmed
  anchor; each attempt is recorded.
- `GET /provenance/commitments/{commitment_id}/attempts` lists anchor outcomes
  and sanitized failure codes.

`PENDING`, `FAILED`, and `CONFIRMED` refer only to anchoring state. A committed
SAL event is not described as anchored until the provider returns confirmation.
The mock provider's confirmation is a local simulation. This repository does
not currently implement a field-device offline synchronization workflow;
provenance creation therefore accepts only events already present in SAL's
server-side audit history. An offline registration must not appear as
blockchain-verified before its authenticated synchronization and acceptance.

A valid digest shows that the committed event representation matches the
evidence being checked. It does not prove that the original information was
truthful, that a workflow was legally valid, or that a person holds legal
ownership. Applicable law, authoritative records, and authorized institutions
remain decisive.

## Local setup, migration, and tests

Use Python 3.10+ and install the existing requirements:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest==9.1.1 httpx2==2.13.1
cp .env.example .env
```

`pytest` and `httpx2` are test-only tools needed by the existing test suite;
they are not runtime dependencies.

In development, the mock ledger needs no signing key. To exercise commitment
signatures, provide a randomly generated value of at least 32 bytes through
`SAL_PROVENANCE_SIGNING_KEY` in the local environment; do not commit that value.

Apply the existing Alembic migration chain to the configured database:

```sh
alembic upgrade head
```

The existing migration history includes PostgreSQL-specific trigger SQL, so a
fresh full-chain migration on SQLite is not supported. Existing test fixtures
create their schema directly; the provenance migration was separately tested
from the current Alembic head on SQLite. Use the normal PostgreSQL migration
chain for deployments.

Run the application and tests:

```sh
uvicorn app.main:app --reload
pytest
```

The provenance-focused tests can be run with:

```sh
pytest tests/test_provenance.py tests/test_config.py
```

No new package dependencies are required. The Alembic revision adds
`provenance_commitments` and `provenance_anchor_attempts`; SAL's existing asset
registry, passports, audit trail, and database remain in place.

## Not yet implemented

Live public or permissioned network adapters, production transaction signing,
managed/HSM key integration and historical key registry, Merkle batches,
offline synchronization integration, anchoring workers/backoff, public
verification endpoints, and integration with SAL Guard or GIS are not
implemented. Do not report this module as live blockchain integration.
