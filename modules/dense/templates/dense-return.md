Reply in exactly this shape (DAP return v1), with nothing before the first line or after the last:

```
#ret 1 <done|partial|blocked>
f <path>:<line> <one-sentence claim>
k <key>: <value>
? <open question or gap>
```

- `f`: one finding per line, at least one unless `blocked`. A finding without `path:line` goes under `?` instead.
- `k`: optional summary facts. `<key>` is any key in the dense key list (`keys.json` in the `sdlc-dense-index` skill folder).
- `?`: optional.
- Keep `UNVERIFIED` and `INFERRED` markers verbatim.
