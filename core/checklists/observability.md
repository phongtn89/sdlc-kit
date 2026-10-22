# Observability

Load for any change to production behaviour: new endpoints, jobs, integrations, or changed failure handling. Use the project's existing logger and telemetry stack; do not add a parallel one.

## Logs
- [ ] Logs are structured (key/value or JSON), not free-text concatenation.
- [ ] Each log line carries the request or correlation ID and the trace/span ID where supported.
- [ ] Errors log the cause, the operation and the identifiers needed to find the record, once, at the boundary that handles them.
- [ ] Levels are deliberate: expected client errors are not logged as `error`.
- [ ] No per-item logging inside loops or hot paths.
- [ ] No secrets, tokens, passwords or unmasked personal data in any field.

## Metrics
- [ ] Request-driven work exposes RED: rate, errors, duration.
- [ ] Resources and queues expose USE: utilization, saturation (queue depth, pool usage), errors.
- [ ] Labels are low-cardinality (route template, status class, operation); never user IDs, tenant IDs, raw URLs or error messages.
- [ ] Metric names and units follow the project's existing convention.

## Traces
- [ ] New outbound calls (HTTP, database, queue, cache) appear as spans with operation name and outcome.
- [ ] Trace context propagates across service and queue boundaries.
- [ ] Span attributes follow the same no-secrets, low-cardinality rules as logs and metrics where indexed.

## Alerts and ownership
- [ ] Failure modes that need a human have an alert on a symptom (error rate, latency, backlog), not on every error.
- [ ] Each alert names an owner and links to a runbook or the doc that explains the fix.
- [ ] Thresholds are stated and derived from expected scale, not guessed.

## Verification
- [ ] A test or local run shows the new logs, metrics and spans are emitted with the expected fields.
- [ ] A failure path was exercised and is diagnosable from telemetry alone.
- [ ] If the project owns no telemetry stack, the gap is recorded instead of adding one.
