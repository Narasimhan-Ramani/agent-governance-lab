# Agent Governance Lab

A practical, open-source lab for testing governance controls around AI agents.

The repository starts with **MCP Catalogue Diff**, a small Python command-line tool that compares an approved Model Context Protocol (MCP) tool catalogue with a live or newly exported catalogue. It identifies structural drift before that drift is silently accepted by an agent, CI/CD pipeline, gateway, or operating team.

The project is intentionally narrow. It detects **configuration change**. It does not claim that every change is harmful, that model behaviour changed, or that a security incident occurred. Those questions require separate behavioural and security tests.

## Why this repository exists

MCP makes it easier to expose tools and data to AI agents. That convenience also creates a governance problem: an MCP server can change independently of the agent that consumes it.

Examples include:

- A new write-capable tool appears in a server that previously exposed only read operations.
- A tool description is reworded and the model begins interpreting the tool differently.
- A required input parameter becomes optional.
- A numeric field loses its minimum or maximum constraint.
- A tool disappears but the agent still expects it.
- The server returns the same tools in a different order.
- Metadata changes without a corresponding review or deployment record.

A normal availability check will not detect most of these conditions. The server can remain healthy, the MCP connection can succeed, and the agent can continue responding while its effective operating environment has changed.

MCP Catalogue Diff provides a small control point:

```text
Approved catalogue ──┐
                     ├── Compare ──> Human report
Live catalogue ──────┘              JSON report
                                    CI exit code
```

The output can support a review, a CI gate, a scheduled drift check, or the first stage of a broader agent-governance workflow.

## Governance model

This lab separates three questions that are often blended together.

### 1. What changed?

MCP Catalogue Diff answers this question. It compares tool names, descriptions, input schemas, metadata and ordering.

### 2. Does the change matter?

A structural difference does not prove behavioural impact. A changed description could be harmless, or it could alter tool selection. A schema change could be compatible, or it could break an agent.

Answer this question with tool-selection tests, contract tests and policy review.

### 3. Is the changed behaviour acceptable?

Even when behaviour changes as expected, the resulting authority might exceed the approved boundary. Answer this with authorization tests, approval rules, state-change checks and business-owned policy.

The intended control chain is:

```text
Detect catalogue drift
        ↓
Classify the change
        ↓
Run affected regression tests
        ↓
Review authority or policy impact
        ↓
Approve, reject, or update the baseline
```

## Current experiment: MCP Catalogue Diff

### Checks performed

The comparator detects:

- Added tools
- Removed tools
- Description changes
- Input-schema changes
- Other metadata changes
- Tool-order changes, reported separately
- Duplicate tool names
- Invalid JSON
- Missing or empty tool names

The comparator also produces:

- A SHA-256 hash for the approved catalogue
- A SHA-256 hash for the live catalogue
- Before and after hashes for each changed tool
- A deterministic JSON report
- An optional non-zero exit code for CI

### Checks deliberately not performed

Version 0.1 does not:

- Connect directly to a remote MCP server
- Authenticate to an MCP server
- Decide whether a schema change is backward compatible
- Reproduce a provider's prompt-cache key
- Prove that tool selection changed
- Prove that a security boundary was crossed
- Inspect tool implementation code
- Execute any tool
- Send data to an external service

These boundaries are deliberate. A small tool that makes one defensible claim is more useful than a broad tool that overstates what its results mean.

## Repository structure

```text
agent-governance-lab/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── pyproject.toml
├── .gitignore
├── .github/
│   ├── workflows/
│   │   └── test.yml
│   └── ISSUE_TEMPLATE/
│       └── bug_report.yml
├── mcp_catalogue_diff/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   └── core.py
├── fixtures/
│   ├── approved.json
│   └── changed.json
└── tests/
    └── test_core.py
```

## Requirements

- Python 3.10 or later
- No runtime third-party dependencies
- Git, if you want to contribute or use the GitHub Actions workflow

The included workflow tests Python 3.10, 3.11, 3.12 and 3.13.

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/<YOUR-GITHUB-USERNAME>/agent-governance-lab.git
cd agent-governance-lab
```

### 2. Run the unit tests

```bash
python -m unittest discover -s tests -v
```

Expected result:

```text
Ran 5 tests

OK
```

### 3. Compare the sample catalogues

```bash
python -m mcp_catalogue_diff \
  fixtures/approved.json \
  fixtures/changed.json
```

Expected output:

```text
MCP catalogue drift detected
Approved catalogue SHA-256: b9119960ed68452243babeaca4272d1af3a4b172f531cabd8ec4bd0805b18b6e
Live catalogue SHA-256:     211105f9e750b5b58ae9338be52216fb398c84ef32325a7d3f2d40f097d398c9
Order changed: yes
Added tools: issue_refund
Removed tools: none
Changed tools:
  - get_invoice: description, inputSchema
Unchanged tools: search_policy
```

The exact hashes are deterministic for the provided fixtures.

## Command-line usage

```text
python -m mcp_catalogue_diff APPROVED LIVE [options]
```

### Positional arguments

| Argument | Description |
|---|---|
| `APPROVED` | Path to the reviewed or approved catalogue JSON file |
| `LIVE` | Path to the live, proposed or newly exported catalogue JSON file |

### Options

| Option | Purpose |
|---|---|
| `--json-out PATH` | Writes the structured report to a JSON file |
| `--fail-on-drift` | Returns exit code `1` when any supported drift is detected |
| `--quiet` | Suppresses the human-readable console report |
| `-h`, `--help` | Displays command help |

### Example: generate a report

```bash
python -m mcp_catalogue_diff \
  fixtures/approved.json \
  fixtures/changed.json \
  --json-out report.json
```

### Example: use as a CI gate

```bash
python -m mcp_catalogue_diff \
  approved/catalogue.json \
  generated/catalogue.json \
  --json-out artefacts/mcp-drift-report.json \
  --fail-on-drift
```

### Example: produce JSON without console output

```bash
python -m mcp_catalogue_diff \
  approved.json \
  live.json \
  --json-out report.json \
  --quiet
```

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Comparison completed. Either no drift was found, or drift was found without `--fail-on-drift` |
| `1` | Drift was found and `--fail-on-drift` was supplied |
| `2` | Invalid input, missing file, malformed JSON or another execution error |

This makes the tool straightforward to use in GitHub Actions, Azure Pipelines, GitLab CI, Jenkins or another build system.

## Input format

The comparator accepts either an MCP-style object with a `tools` array:

```json
{
  "tools": [
    {
      "name": "get_invoice",
      "description": "Read an invoice by invoice ID.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "invoice_id": {
            "type": "string"
          }
        },
        "required": ["invoice_id"],
        "additionalProperties": false
      }
    }
  ]
}
```

or a top-level array:

```json
[
  {
    "name": "get_invoice",
    "description": "Read an invoice by invoice ID.",
    "inputSchema": {}
  }
]
```

### Validation rules

- The catalogue must be valid JSON.
- The tool collection must be an array.
- Every tool must be an object.
- Every tool must have a non-empty string `name`.
- Tool names must be unique within a catalogue.

Unknown tool fields are allowed and compared as metadata.

## How comparison works

### Canonical JSON

JSON objects are serialized with keys sorted. This avoids reporting drift when only object-key order changes.

For example, these are treated as equivalent:

```json
{"type": "object", "properties": {}}
```

```json
{"properties": {}, "type": "object"}
```

### Arrays remain ordered

Array order is preserved because it can carry meaning. For example, reordering an `enum` or a list of examples is reported as a schema change.

### Tool order is separate

The comparator reports catalogue ordering independently from tool-definition changes.

This distinction matters because:

- A reordered catalogue may change its serialized prefix.
- A reordered catalogue does not mean the individual tools changed.
- The project does not claim that reordering necessarily causes a prompt-cache miss or behavioural change.

### Added and removed tools

Tool identity is based on the unique `name` field.

A renamed tool therefore appears as:

- One removed tool
- One added tool

This is intentional because a rename can affect clients and prompts that refer to the original name.

### Changed tools

For a tool present in both catalogues, the report classifies changes into:

- `description`
- `inputSchema`
- `metadata`

The report includes before and after hashes to support review and audit records.

## JSON report example

```json
{
  "approved_file": "fixtures/approved.json",
  "live_file": "fixtures/changed.json",
  "approved_catalogue_hash": "...",
  "live_catalogue_hash": "...",
  "exact_representation_changed": true,
  "order_changed": true,
  "added": ["issue_refund"],
  "removed": [],
  "unchanged": ["search_policy"],
  "changed": [
    {
      "name": "get_invoice",
      "description_changed": true,
      "input_schema_changed": true,
      "metadata_changed": false,
      "before_hash": "...",
      "after_hash": "..."
    }
  ],
  "has_drift": true
}
```

## Suggested governance workflow

### Baseline creation

1. Export the catalogue from the environment you intend to approve.
2. Review the tool names, descriptions, schemas and metadata.
3. Store the approved file in a protected location.
4. Record the catalogue hash, owner, approval reference and date.

### Proposed-change review

1. Export the proposed or newly generated catalogue.
2. Run MCP Catalogue Diff.
3. Review added, removed and changed tools.
4. Run behavioural tests for affected tools.
5. Review changes that add write capability, remove constraints or broaden inputs.
6. Approve the new catalogue or reject the change.
7. Replace the approved baseline only after approval.

### Scheduled drift detection

A scheduled job can export the live catalogue and compare it with the approved baseline. If drift is found, the job should create a review item rather than automatically approving the new state.

The comparator does not currently perform the export step. Keep authentication and secret handling in a separate, reviewed adapter or pipeline stage.

## Risk-based review guidance

The tool does not assign a formal risk score. The following review order is a practical starting point:

### Review immediately

- A new write, delete, payment, refund, deployment or access-management tool
- A removed authorization-related parameter
- A schema change that makes a constrained field free-form
- A change from required approval input to optional input
- A tool description that broadens the stated action

### Review before the next release

- New read-only tools
- New optional parameters
- Description clarifications
- Metadata or annotation changes

### Investigate but do not infer impact

- Tool ordering changes
- Formatting-only changes
- Hash changes caused by newly added non-functional metadata

Always pair catalogue review with the business system's authorization controls. Permission to call a tool is not automatically permission to perform every business action behind it.

## CI integration

The repository includes `.github/workflows/test.yml`, which:

- Runs on pushes and pull requests
- Tests Python 3.10 through 3.13
- Runs all unit tests
- Runs the sample comparison
- Confirms that a JSON report was generated

To use the comparator as a blocking control, add a workflow step like this:

```yaml
- name: Detect MCP catalogue drift
  run: |
    python -m mcp_catalogue_diff \
      approved/catalogue.json \
      generated/catalogue.json \
      --json-out artefacts/mcp-drift-report.json \
      --fail-on-drift
```

Store reports as build artefacts if the report content is safe to retain. Tool descriptions and schemas may expose internal capabilities, so do not publish reports blindly from private environments.

## Testing strategy

The initial test suite covers:

1. Equivalent JSON objects with different key order
2. Added, removed and changed tools
3. Catalogue-order drift
4. Duplicate tool-name rejection
5. Ordered arrays inside schemas

Run tests with:

```bash
python -m unittest discover -s tests -v
```

Useful future tests include:

- Nested schema changes
- Removed required parameters
- Constraint widening, such as a removed `maximum`
- Formatting-only description changes
- Renamed tools
- Metadata additions
- Empty catalogues
- Large catalogues
- Non-ASCII names and descriptions

## Security and privacy

Catalogue files can reveal sensitive information even when they contain no credentials.

Potentially sensitive content includes:

- Internal system names
- Private API paths
- Privileged actions
- Field names that reveal customer or financial data
- Tool descriptions containing operational procedures
- Schemas describing identity, payment or administrative functions

Before committing or sharing a catalogue:

1. Confirm that publication is authorized.
2. Replace organization, client and environment identifiers with synthetic values.
3. Remove credentials, tokens, keys and connection strings.
4. Remove tenant IDs, subscription IDs, private host names and internal endpoints.
5. Review generated reports before uploading them as CI artefacts.
6. Use GitHub secret scanning and push protection.
7. Follow employer and client intellectual-property and publication policies.

Do not assume that anonymizing a real internal catalogue makes it safe to publish.

## Threat model

This project helps detect accidental, unauthorized or undocumented catalogue change.

It can support detection of:

- Unreviewed tools
- Removed constraints
- Description drift
- Schema drift
- Catalogue reordering
- Unexpected metadata changes

It does not protect against:

- A malicious tool implementation that keeps the same catalogue
- A compromised baseline
- A reviewer approving a harmful change
- Incorrect runtime authorization
- Prompt injection
- Tool-output poisoning
- Credential theft
- Missing or altered audit records
- A server returning one catalogue during review and another at runtime

Use defense in depth: protected baselines, signed build artefacts, runtime authorization, gateway controls, downstream business validation, logging and behavioural evaluation.

## Operational recommendations

For enterprise use, store the following beside an approved catalogue:

- Catalogue hash
- Application or agent name
- Environment
- Owner
- Approver
- Approval date
- Review or expiry date
- MCP endpoint identifier
- Deployment or build version
- Linked regression-suite result
- Linked policy or change record

This repository does not prescribe a storage system. A version-controlled repository, approved artefact store or governance registry can work if access and change control are appropriate.

## Troubleshooting

### `file not found`

Confirm the path is relative to the current directory or use an absolute path.

```bash
pwd
ls fixtures
```

### `invalid JSON`

Validate the file with Python:

```bash
python -m json.tool catalogue.json
```

### `duplicate tool name`

Every catalogue entry needs a unique `name`. Remove the duplicate or determine whether two implementations were incorrectly published under the same identity.

### Drift reported only because order changed

The report sets `order_changed` independently. Review whether order is operationally relevant in your system. Do not automatically infer a behavioural or caching impact.

### CI returns exit code 1

That is expected when `--fail-on-drift` is supplied and drift is found. Review the generated report and decide whether to approve the change.

### CI returns exit code 2

The input was invalid or an execution error occurred. Check file paths and JSON validity first.

## Roadmap

Potential future experiments include:

### v0.2: Schema-impact classification

- Identify added and removed required properties
- Detect constraint widening and narrowing
- Classify likely breaking versus non-breaking changes

### v0.3: Behaviour regression fixtures

- Define tool-selection test cases
- Assert expected tool names and arguments
- Include cases where the correct outcome is no action
- Run repeated trials for stochastic agents

### v0.4: MCP endpoint adapter

- Export a tool catalogue through a separately configured client
- Keep credentials outside the comparison package
- Support scheduled comparisons

### Future lab modules

- Caller identity versus backend identity tests
- Approval-bound action tests
- No-state-change regression tests
- Policy and tool-catalogue version stamping
- Model replacement manifests
- Retrieval-source version recall
- Cost and quality evaluation per model route

Roadmap items are intentions, not committed release dates.

## Contributing

Contributions are welcome when they are focused, reproducible and safe to share.

Good contributions include:

- A sanitized fixture reproducing an edge case
- A failing unit test with expected behaviour
- Better input validation
- Clearer report output
- Security and privacy improvements
- Documentation corrections

Before opening a pull request:

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Use synthetic data.
3. Run the complete test suite.
4. Explain the expected and actual behaviour.
5. Keep the change focused.

Suggested first contributions:

- Add a nested-schema change fixture.
- Add a removed-required-parameter fixture.
- Improve reporting for removed schema properties.
- Add tests for empty catalogues.
- Propose a safe report-redaction option.

## Responsible disclosure

Do not open a public issue containing credentials, private catalogues or a vulnerability that could expose sensitive data. See [SECURITY.md](SECURITY.md).

## Design principles

This repository follows five principles:

1. **Detect before interpreting.** Report what changed before claiming impact.
2. **Keep evidence reproducible.** The same inputs should produce the same report.
3. **Separate configuration from behaviour.** Catalogue drift and agent behaviour are different tests.
4. **Fail explicitly.** Invalid inputs and detected drift have distinct exit codes.
5. **Protect source data.** Public examples must remain synthetic.

## Author

Created by **Narasimhan Bharatham Ramani**, a Senior Cloud Architect working across Azure governance, agent identity, drift detection, FinOps, observability and application engineering.

This is an independent open-source project. It is not an official Microsoft, MCP vendor, employer or client project, and it does not imply endorsement by those organizations.

## License

MIT. See [LICENSE](LICENSE).
