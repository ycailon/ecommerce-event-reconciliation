# Deployment boundary and security considerations

**This repository is a local reference demonstration. It has not been deployed to GCP, has not been penetration-tested, and does not claim HIPAA compliance.**

## Proven locally

- Shopify-compatible HMAC SHA-256 verification against original request bytes.
- Strict payload allowlist; reject unexpected identifiers and PII fields.
- Consent-gating of browser analytics events before persistence.
- Idempotent inserts and collision detection for reused event identifiers.
- Minimal SQLite persistence, with synthetic, non-personal order references.
- Distinct signed-event validation and reporting layers.

## Required changes for a real Shopify + GCP deployment

1. Verify actual Shopify webhook topic/schema and use Shopify's official per-request signature header. The demo's simplified canonical event shape is **not** a Shopify native payload. Verify authenticity at a trusted Cloud Run ingress and enforce request limits.
2. Add proper anti-replay policy appropriate to the real event source, source-specific delivery IDs, backoff, retries, bounded queues, and dead-letter recovery workflows. Persisted event IDs alone are not complete replay protection.
3. Use Secret Manager for signing secrets, rotate keys, and restrict Cloud Run service identities and BigQuery write/read roles by least privilege. Never commit credentials.
4. Put event intake behind authenticated infrastructure where appropriate, configure monitoring, request tracing, quota alerts, error budgets, SLOs, access logging, and retention rules.
5. Define consent requirements with privacy counsel before selecting the event schema. Do not assume operational orders may be joined to behavioral analytics for every purpose.
6. Decide whether order updates are immutable revisions or mutable state, preserve delivery-time/source-time distinctions, and verify historical backfills against source-of-truth operational orders.
7. Document dataset region, ownership, deletion, retention, attribution design, disaster recovery, data-subject requests, and secure access review.
8. Run dbt/BigQuery models with a real GCP project, service account and dataset; the samples have intentionally not been run against BigQuery.

## A minimal suggested path

```text
Shopify signed webhook / consented browser event
             |
         Cloud Run ingress (verification, schema checks)
             |
       Pub/Sub (+ retry / dead-letter path)
             |
        Cloud Run worker (idempotency)
             |
           BigQuery raw + dbt staging
             |
      Reporting / reconciliation alerts
```

**Non-goal:** claiming a deployed production environment, actual Shopify API integration, or audited compliance.
