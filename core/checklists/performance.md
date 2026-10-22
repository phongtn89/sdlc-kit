# Performance

Load when a change touches a hot path, a query over growing data, a loop over external calls, a batch or a list endpoint. Do not add speculative micro-optimizations.

## Expected scale
- [ ] Expected volume is written down: rows, requests per second, payload size, concurrency, growth.
- [ ] The latency or throughput target comes from the spec or an existing SLO, not a guess.

## Data access
- [ ] No N+1: queries or calls inside loops are batched, joined or prefetched.
- [ ] New query filters and sorts are backed by an index, or the plan was checked.
- [ ] Queries select only needed columns and rows.
- [ ] No redundant I/O or serialization of the same data within one request.

## Bounds
- [ ] Every list, query and export is paginated or capped; page size has a maximum.
- [ ] Memory use is bounded: large results are streamed, not loaded whole.
- [ ] Concurrency is bounded (pool, semaphore, worker count); no unbounded `Promise.all` or thread fan-out.
- [ ] Queues and buffers have a size limit and a defined behaviour when full.

## Backpressure and timeouts
- [ ] Producers slow down, shed or reject when consumers fall behind.
- [ ] Outbound calls have timeouts; retries use backoff with jitter and a cap.
- [ ] A slow dependency cannot exhaust shared pools for unrelated work.

## Caching
- [ ] Any cache has a key that includes tenant and scope, a TTL or invalidation rule, and a size limit.
- [ ] Stale reads are acceptable for the data cached, by decision.

## Measurement
- [ ] Where a regression is plausible, a before and after measurement exists (benchmark, query plan, profile, load test) with the command used.
- [ ] Measurements ran on representative data size, not an empty table.
- [ ] Client-facing changes stay within the project's bundle or payload budget.
