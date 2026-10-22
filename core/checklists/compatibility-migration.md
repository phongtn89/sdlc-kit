# Compatibility and migration

Load for any change to an API, event, SDK, schema, database, config format or stored data, or anything other code consumes.

## Backward compatibility
- [ ] Existing consumers are listed (services, clients, SDKs, jobs, reports) and checked.
- [ ] No field, endpoint, event or column is removed or renamed in the same release that stops writing it.
- [ ] New fields are optional or defaulted; old clients keep working unchanged.
- [ ] Enum additions are tolerated by consumers; unknown values do not crash them.
- [ ] Any breaking change is approved, documented and versioned.

## Expand and contract
- [ ] Schema changes are split: expand (add, dual-write), migrate data, then contract (remove) in a later release.
- [ ] Each migration step is deployable and reversible on its own.
- [ ] Long-running data migrations are batched, resumable and do not lock hot tables.
- [ ] Migrations are files under version control, not runtime schema changes.

## Rollout order
- [ ] Deployment order across services, database and clients is written down.
- [ ] Old and new versions can run side by side during the rollout.
- [ ] Feature flags guard new behaviour where rollout needs to be gradual or reversible; each flag has an owner and removal plan.

## Rollback and forward fix
- [ ] Rollback steps are stated, including what happens to data written by the new version.
- [ ] If rollback is impossible (destructive migration), a forward-fix plan and backup exist.
- [ ] The rollback path was tested or its risk is explicitly accepted.

## Versions
- [ ] Event and message schemas carry a version; consumers handle old and new.
- [ ] API and SDK versions follow semver or the project's versioning rule; changelog updated.
- [ ] Contract artifacts (schemas, generated clients) are updated in the owning repository first.

## Idempotency and replay
- [ ] Handlers for events, webhooks and retried requests are idempotent (dedup key or natural idempotency).
- [ ] Replaying a backlog after an outage produces the same end state.
- [ ] Ordering assumptions are stated; out-of-order delivery is handled or impossible by design.

## Verification
- [ ] A test exercises old-client against new-server (or old-event against new-consumer).
- [ ] The migration ran against a copy of representative data, with the command recorded.
