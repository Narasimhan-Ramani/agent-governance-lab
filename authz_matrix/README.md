# Authority Matrix: Tool Permission Is Not Transaction Authority

Permission to call a tool like `issue_refund` says nothing about which customer,
which order, how much, or under whose approval. The gateway decides whether a
tool can be called. The business service decides whether a specific transaction
can happen.

This folder makes that boundary testable without any model.

## The matrix

| Case | Acts for | Order owner | Amount | Approval | Expected |
|---|---|---|---|---|---|
| Own order, small | alice | alice | £50 | none | allow |
| Someone else's order | alice | bob | £50 | none | deny |
| Over limit, no approval | alice | alice | £800 | none | deny |
| Over limit, full approval | alice | alice | £800 | £800 | allow |
| Approval too small | alice | alice | £800 | £300 | deny |
| Exceeds order total | alice | alice | £60 (£50 already refunded on £100) | none | deny |
| No on-behalf-of context | none | alice | £50 | none | deny |
| Split refunds | alice | alice | £60 then £60 (limit £100) | none | allow, then deny |

Every row is a permitted tool call. Only some are permitted transactions.

## Run

```bash
py -m unittest discover -s tests -v
```

(Use `python` instead of `py` on macOS/Linux.)

## Layout

- `models.py` – Order, RefundRequest, Decision
- `policy.py` – deterministic rules, including a cumulative limit
- `ledger.py` – amounts already refunded per order
- `service.py` – the enforcement point; records evidence for every decision

## Limitations

Synthetic data, one service, no real identity provider, whole-pound amounts,
and the cumulative check is per order rather than per customer.

## Contribute

Add a row: write a test in `tests/test_authz_matrix.py` for an edge case the
matrix misses.
