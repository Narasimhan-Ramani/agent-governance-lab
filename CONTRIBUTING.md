# Contributing

Thank you for improving Agent Governance Lab.

## Good contributions

- A sanitized JSON fixture reproducing an edge case
- A failing unit test that describes expected behaviour
- A focused fix with no unrelated formatting changes
- Improvements to security, validation, output clarity or documentation

## Before opening a pull request

1. Do not include employer, client or customer material.
2. Remove credentials, tenant IDs, subscription IDs, host names and private endpoints.
3. Use synthetic names and data.
4. Run:

```bash
python -m unittest discover -s tests -v
```

5. Explain expected and actual behaviour.

## Scope for v0.1

This version compares exported JSON catalogues. Endpoint discovery, provider cache-key emulation and behavioural impact claims are out of scope.
