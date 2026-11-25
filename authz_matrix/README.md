# Authority Matrix: Tool Permission Is Not Transaction Authority

> An agent being permitted to call `issue_refund` does not mean every refund the agent requests is authorized.

This experiment demonstrates a simple but important boundary in agentic systems:

**Tool access is a capability decision. Transaction authorization is a business decision.**

A gateway, agent runtime, or MCP tool registry can decide whether an agent is permitted to invoke `issue_refund`.

That decision alone cannot determine whether a particular refund should happen.

The business service still needs to answer questions such as:

- Is the agent acting on behalf of the correct customer?
- Does the order belong to that customer?
- Is the requested amount valid?
- Has part of the order already been refunded?
- Does the cumulative refund exceed the self-service limit?
- Does the approval cover the complete amount being authorized?
- Has the underlying transaction state changed since approval?

This lab turns that distinction into executable Python tests.

---

## Why this matters

Consider an agent with access to:

```text
issue_refund(order_id, amount)
```

The following controls may all succeed:

```text
Authenticated agent
        ↓
Authorized to call issue_refund
        ↓
Tool is on approved allowlist
        ↓
Input matches schema
        ↓
Audit logging enabled
```

And the requested transaction can still be wrong.

For example:

```text
Alice asks for a refund
        ↓
Agent selects issue_refund
        ↓
Agent mistakenly supplies Bob's order ID
        ↓
Gateway allows issue_refund
        ↓
Schema validation succeeds
        ↓
?
```

At `?`, the payments/refund service still has to determine:

> Is Alice authorized to receive a refund for this specific order and this specific amount?

This project places that decision in deterministic business logic rather than asking the model to reason about it correctly.

---

## Architecture

```text
┌─────────────────────────────────────┐
│             User / Caller           │
│                 Alice               │
└──────────────────┬──────────────────┘
                   │
                   │ request
                   ▼
┌─────────────────────────────────────┐
│               AI Agent              │
│                                     │
│ chooses: issue_refund               │
│ order: A1                           │
│ amount: £50                         │
└──────────────────┬──────────────────┘
                   │
                   │ tool invocation
                   ▼
┌─────────────────────────────────────┐
│        Gateway / Tool Boundary      │
│                                     │
│ Can this agent call issue_refund?   │
│                                     │
│ ALLOW                               │
└──────────────────┬──────────────────┘
                   │
                   │ permitted call
                   ▼
┌─────────────────────────────────────┐
│           Refund Service            │
│                                     │
│ authorize_refund()                  │
│                                     │
│ • whose authority?                  │
│ • whose order?                      │
│ • amount valid?                     │
│ • already refunded?                 │
│ • approval sufficient?              │
│ • cumulative limit exceeded?        │
└─────────────┬───────────────┬───────┘
              │               │
           ALLOW             DENY
              │               │
              ▼               ▼
┌────────────────────┐   ┌─────────────────────┐
│   Refund Ledger    │   │   No state change   │
│                    │   │                     │
│ record refund      │   │ explicit reason     │
└─────────┬──────────┘   └──────────┬──────────┘
          │                         │
          └───────────┬─────────────┘
                      ▼
          ┌────────────────────────┐
          │    Evidence Record     │
          │                        │
          │ caller                 │
          │ order                  │
          │ amount                 │
          │ approval reference     │
          │ allow / deny           │
          │ decision reason        │
          │ policy version         │
          └────────────────────────┘
```

The architecture deliberately separates:

### Capability authorization

```text
Can the agent invoke issue_refund?
```

from:

### Transaction authorization

```text
May this refund occur for this customer,
this order, this amount and this approval?
```

Those are different decisions.

---

## Design principle

### Gateway decision

A gateway, MCP server, API gateway, or tool registry can control:

- Which agent identities may invoke a tool
- Which tools are exposed
- Authentication
- Scope
- Rate limits
- Tool schemas
- Request validation
- Audit telemetry

### Business-service decision

The service owning the transaction should enforce invariants such as:

- Resource ownership
- Transaction limits
- Approval requirements
- Current state
- Cumulative values
- Idempotency
- Business-specific restrictions

The agent should not be the final enforcement point for those rules.

---

## Authority matrix

The experiment currently implements these scenarios.

| Case | Acting for | Order owner | Amount | Approval | Expected |
|---|---|---|---:|---:|---|
| Own order, small refund | Alice | Alice | £50 | None | **Allow** |
| Someone else's order | Alice | Bob | £50 | None | **Deny** |
| Over self-service limit | Alice | Alice | £800 | None | **Deny** |
| Full approval covers transaction | Alice | Alice | £800 | £800 | **Allow** |
| Approval doesn't cover transaction | Alice | Alice | £800 | £300 | **Deny** |
| Cumulative refund exceeds order total | Alice | Alice | £60 after £50 already refunded from £100 | None | **Deny** |
| Missing on-behalf-of context | None | Alice | £50 | None | **Deny** |
| Unknown order | Alice | Unknown | £50 | None | **Deny** |
| Invalid amount | Alice | Alice | £0 | None | **Deny** |
| Split refunds cross self-service threshold | Alice | Alice | £60 + £60 | None | **First allow, second deny** |

The important property is this:

> Every row may arrive through an otherwise permitted `issue_refund` tool call. Only some rows represent authorized transactions.

---

## The split-refund test

Assume the self-service limit is:

```text
£100
```

The agent requests:

```text
Refund 1 = £60
```

The service allows it.

Later, the same workflow requests:

```text
Refund 2 = £60
```

Looking only at each call:

```text
£60 < £100
```

Both appear valid.

Looking at the business transaction:

```text
£60 + £60 = £120
```

The cumulative value exceeds the £100 limit.

The implementation therefore checks the cumulative amount rather than authorizing each call independently.

Conceptually:

```python
cumulative = already_refunded + requested_amount

if cumulative > SELF_SERVICE_LIMIT:
    require_approval_for(cumulative)
```

This prevents an agent from unintentionally routing around a transaction limit by splitting an action into smaller calls.

---

## Repository structure

```text
authz_matrix/
├── __init__.py
├── ledger.py
├── models.py
├── policy.py
├── service.py
└── README.md

tests/
└── test_authz_matrix.py
```

### `models.py`

Defines the core domain objects:

- `Order`
- `RefundRequest`
- `Decision`

The models deliberately contain no LLM-specific concepts.

### `policy.py`

Contains deterministic authorization rules.

The core entry point is:

```python
authorize_refund(...)
```

This code decides whether the requested transaction is allowed.

No model is used for the decision.

### `ledger.py`

Maintains the amount already refunded against an order.

This allows authorization to evaluate cumulative state rather than treating every tool invocation independently.

### `service.py`

Acts as the business enforcement point.

The service:

1. Loads the current order.
2. Reads previously refunded value.
3. Evaluates the authorization rule.
4. Changes state only when authorized.
5. Records evidence for both allowed and denied decisions.

### `test_authz_matrix.py`

Turns the authority matrix into executable tests.

The current project contains **11 transaction-authorization tests**.

---

## Decision flow

```text
Refund request
      │
      ▼
On-behalf-of identity present?
      │
      ├── No → DENY
      │
      ▼
Order exists?
      │
      ├── No → DENY
      │
      ▼
Requester owns order?
      │
      ├── No → DENY
      │
      ▼
Amount > 0?
      │
      ├── No → DENY
      │
      ▼
Current + requested refund <= order total?
      │
      ├── No → DENY
      │
      ▼
Cumulative amount <= self-service limit?
      │
      ├── Yes → ALLOW
      │
      ▼
Approval covers full cumulative amount?
      │
      ├── No → DENY
      │
      ▼
     ALLOW
```

The sequence matters because authorization uses the current business state, not merely the model's intention.

---

## Evidence records

The service records every decision.

For example:

```json
{
  "order_id": "A1",
  "on_behalf_of": "alice",
  "amount": 800,
  "approval_ref": "APR-2",
  "decision": "deny",
  "reason": "cumulative amount needs approval covering the full value",
  "rule_version": "refund-policy-v1"
}
```

The evidence record distinguishes:

```text
Who requested the operation?
What transaction was requested?
What approval was presented?
What decision was made?
Why?
Under which rule version?
```

A tool-call name alone does not explain why the transaction was permitted or denied.

---

## Running the tests

From the root of `agent-governance-lab`:

```powershell
python -m unittest discover -s tests -v
```

On Windows systems using the Python launcher:

```powershell
py -m unittest discover -s tests -v
```

The authority-matrix tests include:

```text
test_approval_does_not_cover_amount
test_every_decision_is_recorded_with_reason
test_exceeds_order_total
test_invalid_amount
test_missing_on_behalf_of
test_over_limit_with_full_approval
test_over_limit_without_approval
test_own_order_small_amount
test_someone_elses_order
test_split_refunds_cannot_bypass_limit
test_unknown_order
```

The project requires:

- No Azure subscription
- No model endpoint
- No API key
- No LLM tokens
- No external service

The authorization boundary can therefore be tested independently of agent behavior.

---

## Why no LLM is involved in authorization

An LLM could be asked:

> Is this refund permitted?

That is deliberately not what this lab does.

For business invariants such as:

```text
order.owner == requester

already_refunded + requested <= order.total

approval >= cumulative_refund
```

deterministic rules are:

- Easier to test
- Easier to audit
- Easier to version
- Easier to reproduce
- Independent of model changes
- Independent of prompt changes

The agent can recommend or initiate the transaction.

The service owns the final authorization decision.

---

## What this lab does not claim

This repository is intentionally narrow.

The example does **not** prove that an agent is secure.

It does not implement:

- A production payment system
- Microsoft Entra ID authentication
- OAuth token exchange
- MCP authorization
- Real customer identities
- Database transactions
- Distributed locking
- Currency-safe decimal handling
- Real approval workflows
- Fraud detection
- Refund settlement
- Production audit storage

The implementation uses:

- Synthetic users
- Synthetic orders
- An in-memory ledger
- Integer pound values
- A single process
- A simple rule set

It is an architecture experiment, not a payment library.

---

## Important production gaps

### Idempotency

A retry after a timeout must not create a second refund.

A production service should accept a stable idempotency key and return the original result when the same operation is retried.

### Atomic authorization and state change

This lab evaluates and records state in one process.

A real implementation must prevent this race:

```text
Request A reads refundable balance
Request B reads refundable balance
Request A refunds
Request B refunds using stale state
```

The authorization check and reservation/update need transaction-safe semantics.

### Stale approvals

An approval can be correct when granted and wrong when executed.

For example:

```text
10:02 approval issued for £800
10:04 another channel refunds £300
10:06 queued agent resumes
```

A stronger design should bind approval to the transaction state or version against which the approval was given.

If that state changes, the approval becomes stale and needs re-evaluation.

### Currency handling

Money should not generally be represented as floating-point values.

This lab uses whole integer pounds only to keep the example readable.

Production systems should use the currency representation and rounding rules appropriate to their payment domain.

### Identity and delegation

`on_behalf_of` is a string in this experiment.

Production systems need cryptographically verifiable identity and delegation rather than accepting a caller-supplied value at face value.

---

## Security boundary

```text
Agent
  │
  │ proposes an action
  ▼
Tool boundary
  │
  │ authorizes access to capability
  ▼
Business-service boundary
  │
  │ authorizes the actual transaction
  ▼
State change
```

Each boundary answers a different question.

### Agent

```text
What should I try to do?
```

### Tool boundary

```text
May this caller reach this capability?
```

### Business service

```text
May this exact state transition occur now?
```

Combining those questions into one "agent permission" is the mistake this lab is intended to expose.

---

## Threats the matrix currently exercises

The test suite currently demonstrates protection against:

- Cross-customer access
- Missing delegation context
- Invalid transaction values
- Transaction limits
- Under-scoped approval
- Cumulative-limit bypass
- Refunds exceeding the original order value
- Unknown resources
- Missing evidence

Future versions could add:

- Approval expiry
- Stale approval state
- Duplicate requests
- Idempotency keys
- Concurrent refund races
- Per-customer daily limits
- Risk-tiered approval
- Delegation depth
- Revoked authorization
- Order lifecycle state
- Currency and regional policy
- Compensating actions

---

## Suggested next experiments

### Experiment 1: Stale approval

Store:

```text
approval transaction version = 7
```

Then change the order to:

```text
current transaction version = 8
```

Expected:

```text
DENY / RE-APPROVE
```

even though the customer and amount still match.

### Experiment 2: Idempotent retry

Send the same refund twice with:

```text
idempotency_key = refund-A1-001
```

Expected:

```text
first request  → refund executed
second request → original result returned
```

not:

```text
two refunds
```

### Experiment 3: Concurrent channels

Submit the same refund simultaneously from:

```text
Human support application
AI agent
```

Both should hit the same business-authorization boundary.

Only one valid state transition should succeed.

---

## Design takeaway

The central lesson is not specific to refunds.

The same distinction applies to tools such as:

```text
delete_record
approve_invoice
send_payment
grant_access
deploy_release
change_firewall_rule
send_email
cancel_order
```

Allowing access to the tool answers:

> Can the actor use this capability?

The business system still has to answer:

> Is this particular state change authorized, for this subject, on this resource, under these conditions, right now?

Those are different questions.

For agentic systems, both matter.

---

## Contributing

A useful contribution is one new row in the authority matrix.

For example:

```text
Given:
  order belongs to Alice
  refund amount = £80
  approval exists

But:
  approval has expired

Expected:
  deny
```

Add the case as a test in:

```text
tests/test_authz_matrix.py
```

Keep contributions:

- Deterministic
- Synthetic
- Independently testable
- Free of real customer information
- Free of employer/client data
- Explicit about expected allow/deny behavior

---

## Repository

This experiment is part of [Agent Governance Lab](https://github.com/Narasimhan-Ramani/agent-governance-lab).

The repository explores small, reproducible controls for governable AI-agent systems.

The broader principle behind the lab is:

> **Agents can reason about what to do. Deterministic controls still decide what they are allowed to change.**
## Cases added from reader suggestions

These two cases were suggested in the comments on the original post.

### Stale approval (suggested by Rakshitha G)

An approval can be valid when given and wrong by the time the agent executes.
The request carries `approved_at_refunded`, the refunded total on the order when
the approval was given. If the order has changed since, the service returns
`reapprove` instead of `deny`, and changes nothing.

| Approved when refunded total was | Refunded total at execution | Result |
|---|---|---|
| 0 | 0 | allow |
| 0 | 300 | **reapprove** (approval is stale) |
| 300 (new approval, covers 300 + 500) | 300 | allow |

### Idempotent retry (suggested by Dishant Sharma)

If the agent times out and retries the same refund, a cumulative limit alone does
not stop it while the total stays under the limit. With an `idempotency_key`, the
service returns the original result and refunds once.

| Request | Result |
|---|---|
| Same key, same request, sent twice | allow, then **replay** (one refund) |
| Same key, different request | deny |
| No key, same ₹50 sent twice | both allowed (the gap the key closes) |

### Outcomes

`Decision.outcome` is one of `allow`, `deny`, `reapprove` or `replay`. A test that
only asserts "denied" cannot tell these apart.

### Still not covered

Concurrent requests (two callers passing against the same remaining balance) and
persistence of idempotency keys. This lab keeps both in memory, in one process.
