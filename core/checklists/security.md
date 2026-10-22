# Security

Load for any change that touches authentication, authorization, tenant data, untrusted input, secrets, outbound calls, dependencies or infrastructure.

## Authentication and authorization
- [ ] Every new or changed endpoint, handler and job requires authentication unless public by decision.
- [ ] Authorization is checked on the server for every action, not only hidden in the UI.
- [ ] Checks are deny-by-default; a missing role or permission fails closed.
- [ ] Object-level access is checked (no access by guessing or changing an ID).

## Tenant isolation
- [ ] Every query on tenant data is scoped by tenant from the authenticated context, not from request input.
- [ ] Caches, queues, files and search indexes keep tenant data separate.
- [ ] A test proves tenant A cannot read or change tenant B's data.

## Input validation and injection
- [ ] Untrusted input is validated at the boundary with the project's schema or parser.
- [ ] Database access is parameterized; no string-built queries.
- [ ] No untrusted input reaches a shell, template, eval, path join or regex without escaping.
- [ ] Output is encoded for its context (HTML, attribute, URL, header).

## Outbound requests (SSRF)
- [ ] User-supplied URLs are checked against an allow-list of hosts and schemes.
- [ ] Internal, loopback, link-local and metadata addresses are blocked after DNS resolution.
- [ ] Outbound calls have timeouts and size limits; redirects are re-checked.

## Secrets
- [ ] No secret, token or key in code, config defaults, fixtures, logs or commit history.
- [ ] Secrets come from the platform secret mechanism; least privilege for each credential and CI token.
- [ ] Error messages and stack traces shown to clients reveal no internals.

## Dependencies and supply chain
- [ ] New dependencies are maintained, licence-compatible and free of known critical advisories.
- [ ] Versions are pinned through the lockfile; no install scripts from unknown sources.

## Sensitive data in logs and telemetry
- [ ] Logs, spans and metrics contain no passwords, tokens, payment data or unmasked personal data.

## Abuse and rate limits
- [ ] Expensive or enumerable endpoints (login, search, export, invite) have rate limits.
- [ ] Request size, page size and batch size are bounded.
- [ ] Replayed or duplicated requests cannot cause double effects.

## Auditability
- [ ] Security-relevant actions (login, permission change, export, deletion) are recorded with actor, tenant, time and outcome, in a store the actor cannot change.
