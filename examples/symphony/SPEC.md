# Symphony Issue-Driven Agent Orchestrator Specification

> GENERATED FROM `spec/`. DO NOT EDIT DIRECTLY.

Status: draft  
Version: 0.1.0

Provenance: recovered from an existing implementation. Where the evidence was behavior alone, mechanisms default to implementation-defined.

---

## Normative Language

The key words below carry the stated meaning wherever they appear in this specification.

- **MUST** — required for conformance.
- **MUST NOT** — prohibited for conformance.
- **SHOULD** — expected unless there is a justified reason to deviate.
- **SHOULD NOT** — normally avoided unless justified.
- **MAY** — optional.
- **Implementation-defined** — variable within constraints stated by this specification.
- **Unspecified** — consumers must not rely on the behavior.

## How to Read This Specification

This specification serves two implementation styles.

To implement by transcription, use the scan path:

- The Configuration Specification and its cheat sheet name every required field.
- Concept field lists give the data contract.
- The Test and Validation Matrix lists the checks an implementation must pass.
- The Implementation Checklist is the definition of done.
- Examples and reference algorithms show one concrete shape. They are informative, not normative.

To implement by reconstruction, read in order:

- The Problem Statement and Design Intent say why the subject exists.
- The System Model defines the concepts and who owns each decision.
- The chapters walk through behavior end to end.
- Invariants and failures state what must survive your design choices.

Both paths are projections of the same records. They cannot disagree.

## Problem Statement

Teams track software work in an issue tracker (Linear, GitHub, GitLab, Jira, Asana, or similar). Autonomous coding agents can execute much of that work, but an agent session is a fragile, finite process: it can crash, stall, run out of turns, or hit a question only a human can answer. Someone has to watch the tracker, hand each eligible item to an agent in a safe workspace, keep the agent honest about the item's current tracker state, and clean up when the item is finished. Doing this by hand does not scale past a handful of items, and doing it naively risks duplicate agents on one item, agents working on closed items, or agents escaping their workspace.

Continuously convert active tracker work items into supervised coding-agent runs, in parallel and unattended, while the tracker remains the single source of truth for what is in scope, without ever running two agents on the same item, without letting an agent touch anything outside its assigned workspace, and while surfacing progress and blockage to a human operator.

### Why This Specification Exists

The subject's essential guarantees - single ownership of an item, tracker supremacy over local state, revalidation before every dispatch, workspace containment, blocked-versus-retry classification, and last-known-good configuration - are scattered across one implementation's process tree. Without a specification, a reimplementation would likely reproduce the easy parts (poll, spawn) and silently lose the safety and reconciliation semantics that make unattended operation acceptable.

## Goals and Non-Goals

### Goals

- Keep the issue tracker authoritative; local scheduling state always yields to fresh tracker state.
- Run at most one agent per work item at any time, across restarts and retries.
- Confine every agent run to an isolated, deterministic per-issue workspace.
- Recover from agent failure by bounded, backed-off retry rather than by dropping the item.
- Distinguish items that need operator input from items that merely failed, and hold rather than retry them.
- Let operators tune scheduling, safety, and agent behavior at runtime through one configuration artifact.
- Make orchestrator and agent activity observable to a human operator.

### Non-Goals

- Specifying the coding agent itself or the quality of its work.
- Prescribing tracker-side workflow policy; that lives in the operator's prompt and tracker configuration.
- Coordinating multiple orchestrator instances beyond per-item routing hints (assignee and labels).
- Guaranteeing exactly-once effects inside the tracker or the repository; the agent owns its own idempotence.

## Design Intent

### Tracker supremacy

The tracker is the only durable authority on an item's state. The orchestrator holds claims, retry timers, and blocked entries as caches of intent, and every consequential decision re-reads the tracker first.

Humans and other tools move items concurrently. An orchestrator that trusts its own memory will work on closed items or fight reassignment.

Implications:

- Running and blocked items are re-checked against the tracker every poll cycle.
- An item is re-fetched and re-validated immediately before every agent spawn.
- Tracker unavailability yields inaction, never guesses.

### Fail toward retry, never toward duplication

When an agent run ends for any reason other than operator input, the item stays claimed and re-enters through a backed-off retry that re-checks eligibility. The claim is the duplication guard.

Unattended operation makes duplicate agents the most expensive failure: two agents on one item corrupt each other's workspace and tracker notes.

Implications:

- A claim persists across agent crashes, stalls, and capacity waits.
- Retry delays grow and are capped by an operator parameter.
- Only observed tracker-state change releases a claim.

### Bounded blast radius for unattended agents

Every mechanism that lets the agent act - workspace, sandbox policy, shell hooks, provider tools - is scoped to the single item being worked and denied ambient credentials.

The service runs without a human in the loop; the only acceptable failure mode of a misbehaving agent is damage inside one workspace.

Implications:

- Workspace paths are canonicalized and must resolve inside the configured root.
- Tracker credentials are withheld from the agent process environment.
- Starting the service requires an explicit operator acknowledgement of unattended execution.

### Last-known-good configuration

Configuration is validated strictly at startup, then hot-reloaded; a reload that fails validation never replaces the running configuration.

An operator edit must not be able to take down agents that are mid-run.

Implications:

- The service refuses to start on an invalid configuration.
- A failed reload logs the error and keeps serving the previous settings.

Notes:

- A broken edit can go unnoticed while the stale configuration keeps working.

### Provider capabilities stay behind the adapter

The scheduler depends only on normalized read operations. Everything provider-specific - authentication, write operations, native agent tools - stays behind the tracker adapter boundary.

Scheduling policy must not accrete per-provider special cases, and new trackers must be addable without touching the scheduler.

Implications:

- Adapters normalize items into one issue shape before the scheduler sees them.
- Agent-side tracker mutations are optional provider-native tools, not scheduler features.

## System Model

### Core Concepts

#### Workflow Document

The single operator-editable artifact that configures one orchestrator: structured settings plus the prompt template handed to every agent run. It is read at startup and re-read while the service runs.

Fields:

- `settings` (structured map) — REQUIRED. Operator settings grouped by area (tracker, polling, workspace, worker, agent, codex, hooks, observability, server).
- `prompt_template` (template text) — Template rendered per run with issue fields and attempt number; a built-in default applies when blank.

- One document configures one orchestrator instance.
- Values may reference environment variables for secrets and paths.

#### Issue

The normalized work item the scheduler operates on, produced by a tracker adapter from provider data. It is the unit of claiming, workspace assignment, and agent execution.

Fields:

- `id` (string) — REQUIRED. Stable dispatch identity within the configured tracker scope; the claim key.
- `identifier` (string) — REQUIRED. Human-readable identity, unique in scope; derives the workspace key.
- `title` (string) — REQUIRED. Short human summary; part of dispatch eligibility (must be present).
- `description` (string) — Full body text made available to the prompt template.
- `state` (string) — REQUIRED. Provider workflow state name; compared case-insensitively against the configured active and terminal state sets.
- `priority` (integer) — Provider priority; ranks 1 (highest) through 4; absent or out-of-range sorts last.
- `created_at` (timestamp) — Creation time; older items dispatch first within a priority rank.
- `labels` (string list) — Provider labels, matched case-insensitively against required routing labels.
- `dispatchable` (boolean) — REQUIRED. Adapter's verdict that this item is routed to this orchestrator (assignment, blockers, provider policy).
- `blocked_by` (list) — Provider-side blocking relations the adapter folds into the dispatchable verdict.
- `url` (string) — Human link surfaced in observability output.
- `assignee_id` (string) — Provider assignee used for routing diagnostics.
- `native_ref` (map) — Non-secret provider identifiers needed by provider-native agent tools.
- `branch_name` (string) — Provider-suggested branch name exposed to the prompt template.
- `updated_at` (timestamp) — Last provider update time, informational.


#### Claim

The orchestrator's exclusive, in-memory ownership of one issue. A claim is held while an agent runs, while a retry is pending, and while the issue is blocked on operator input. It is the guard against duplicate dispatch and it carries continuity data across attempts.

- At most one claim exists per issue id.
- A claim records attempt count, last error, worker host, and workspace path.
- A claim is released only when the tracker shows the issue terminal, inactive, unrouted, or gone.

#### Workspace

An isolated directory dedicated to one issue, in which every agent run for that issue executes. Its location is derived deterministically from the issue identifier under an operator-configured root.

- The same issue always maps to the same workspace path.
- The workspace persists across turns and retries so agents resume work in place.
- It is removed when the issue reaches a terminal tracker state.

#### Agent Session

One live connection to a coding-agent runtime, bound to a workspace and an issue. A session hosts one or more turns; each turn takes a prompt and runs until completion, failure, cancellation, or timeout.

- A session is created per agent run and always torn down with it.
- Session policies (approval, sandbox) are fixed at session start.

#### Session Event

A timestamped notification emitted during a session: lifecycle events, approval and input requests, tool calls, streamed output, and token usage. Events drive stall detection, blocked classification, and observability.

- Every event carries an event kind and a timestamp.
- Events may carry a session id, token usage, and rate-limit data.

#### Worker Host

A remote execution target on which workspaces are provisioned and agent sessions launched, addressed over an operator-configured transport. Present only when the remote-execution extension is configured.

- Each host has a bounded number of concurrent agent slots.
- An agent run is pinned to one host for its whole lifetime.

### Concept Relationships

**Workflow Document** governs **Claim**. Operator settings decide which issues may be claimed, how many run concurrently, and how retries and blocking behave.

**Claim** owns **Issue**. A claim asserts exclusive local ownership of one issue for the duration of running, retrying, or blocked handling.

**Issue** maps to **Workspace**. Each issue deterministically maps to exactly one workspace per execution target.

**Agent Session** executes in **Workspace**. Every session runs with the issue's workspace as its working directory and writable scope.

**Agent Session** works on **Issue**. A session receives the issue's content in its prompt and continues only while the issue remains active and routed here.

**Agent Session** emits **Session Event**. Sessions stream events that the scheduler folds into claim telemetry and blocked/stall decisions.

**Worker Host** hosts **Workspace**. Under the remote-execution extension, a workspace is provisioned on the worker host selected for the run.

### Responsibilities and Ownership

#### Configuration Authority

Own the loading, validation, hot reload, and serving of the workflow document so every other responsibility reads one consistent, always-valid view of operator intent.

It owns:

- Parsing the workflow document into settings and prompt template.
- Structural and semantic validation, including tracker-adapter validation.
- Detecting document changes and swapping in reloaded settings atomically.
- Retaining the last known good configuration when a reload fails.

It does not own:

- Scheduling decisions made with the settings it serves.

Requirements:

- Settings served to readers MUST always come from a fully validated document.

#### Scheduler

Own the claim ledger and the polling loop; decide when each issue is dispatched, retried, blocked, reconciled, or released.

It owns:

- The periodic poll cycle and immediate refresh requests.
- Claim admission, including all eligibility and capacity checks.
- Retry timers, backoff progression, and attempt accounting.
- Blocked-entry bookkeeping for issues awaiting operator input.
- Reconciling running and blocked claims against fresh tracker state.
- Selecting the execution target for each run.

It does not own:

- Provider-specific issue interpretation; the adapter normalizes first.
- The content or conduct of an agent turn.

Requirements:

- The scheduler MUST NOT dispatch an issue it already holds a claim for.
- The scheduler MUST re-read runtime-tunable settings at least once per poll cycle.

#### Agent Run Supervisor

Own one agent run end to end: workspace readiness, lifecycle hooks, the turn loop against a single session, and continuation decisions based on fresh issue state.

It owns:

- Ordering of workspace provisioning, hooks, session start, and teardown.
- The per-run turn loop and its turn budget.
- Re-checking issue state and routing between turns.

It does not own:

- Retry scheduling and host selection; the scheduler decides both.

Requirements:

- A run MUST release its session and run teardown hooks on every exit path.

#### Agent Session Protocol Client

Own the wire conversation with the coding-agent runtime: session and turn setup, event streaming, approval and input-request handling, and tool-call brokering.

It owns:

- Encoding session policies (approval, sandbox, working directory) at session start.
- Classifying mid-turn requests as auto-approvable, tool calls, or operator-input blockers.
- Enforcing response and turn timeouts on the stream.
- Withholding tracker secrets from the agent process environment.

It does not own:

- Deciding whether a blocked issue is later released; the scheduler owns claims.

Requirements:

- A turn that requires operator input MUST end as a distinguishable blocker, not as a generic failure.

#### Tracker Adapter

Own the boundary to the issue provider: normalize provider data into issues, validate provider configuration, and expose optional provider-native agent tools with their credentials.

It owns:

- Fetching issues by state names and by ids as normalized issues.
- The dispatchable verdict folded from assignment, blockers, and provider policy.
- Provider credential resolution and the list of secret environment names.
- Optional provider-native tool advertisement and execution.

It does not own:

- Scheduling policy; capability differences stay behind the boundary.

Requirements:

- Reads MUST be side-effect free on the provider.
- Malformed provider items MUST be rejected at the boundary, not passed to the scheduler.

#### Workspace Manager

Own the safety and lifecycle of per-issue workspaces: derivation, containment validation, bootstrap and teardown hooks, reuse, and removal.

It owns:

- Deriving the deterministic, collision-safe workspace key.
- Canonicalizing paths and enforcing containment under the configured root.
- Running lifecycle hooks with the workspace as working directory.
- Removing workspaces for terminal issues, including the startup sweep.

It does not own:

- Deciding when an issue is terminal; the scheduler interprets tracker state.

Requirements:

- No create or remove operation may act on a path outside the configured root.

#### Observability Surface

Own the operator-facing view: fold session events into telemetry and expose orchestrator status through a live dashboard and a query API.

It owns:

- Aggregating running, retrying, and blocked claims into status snapshots.
- Token and rate-limit accounting across sessions.
- Serving the dashboard and status API and pushing updates to viewers.

It does not own:

- Any influence on scheduling decisions beyond triggering an immediate poll.

Requirements:

- Observability MUST degrade gracefully when the scheduler is slow or absent.

## Configuration Specification

Each field below must exist and be operator-settable. Keys are reference names used by this document, not required spellings. Concrete names, formats, and defaults are implementation-defined unless fixed elsewhere. The stated semantics are normative.

### `polling.interval_ms` — Poll interval

How often the scheduler runs a poll cycle (reconcile plus dispatch).

- Must be a positive duration.
- Each completed cycle schedules the next one after this interval.
- Changes apply when the next cycle schedules its successor, without restart.

Used by **Poll Cycle**.

### `tracker.kind` — Tracker kind

Which tracker adapter the orchestrator uses.

- Must name an adapter in the implementation's registry.
- Absent or unknown kinds fail configuration validation.

Used by **Tracker Adapter Contract**, **Load Configuration at Startup**.

### `tracker.provider` — Tracker provider settings

Provider-specific connection settings - endpoint, project scope, credentials, assignee identity - owned by the selected adapter.

- Contents are adapter-defined; the adapter validates them at load time.
- Credential values may be environment references and resolve at load.
- Resolved credentials feed the adapter and its tools, never the agent environment.

Used by **Tracker Adapter Contract**, **Tracker Secrets Never Reach the Agent**.

### `tracker.active_states` — Active tracker states

The tracker state names that make an issue eligible for dispatch and for turn continuation.

- Matched case-insensitively after trimming.
- Adapters may supply provider-appropriate defaults.
- An issue outside these states is never dispatched and stops continuing.

Used by **Poll Cycle**, **Dispatch Issue**, **Agent Run**.

### `tracker.terminal_states` — Terminal tracker states

The tracker state names that mean an issue is finished and its workspace reclaimable.

- Matched case-insensitively after trimming.
- A terminal issue's agent stops, its claim releases, and its workspace is removed.
- Adapters may supply provider-appropriate defaults.

Used by **Reconcile Claims Against Tracker**, **Remove Workspace for Finished Issue**.

### `tracker.required_labels` — Required routing labels

Labels an issue must carry (all of them) to be routed to this orchestrator.

- Matched case-insensitively after trimming.
- An empty list requires nothing.
- Losing a required label mid-run stops the agent and releases the claim.

Used by **Dispatch Issue**, **Reconcile Claims Against Tracker**.

### `workspace.root` — Workspace root

The directory under which every per-issue workspace lives; the local blast radius granted to agents.

- Relative values resolve against the workflow document's directory.
- May be an environment reference.
- All workspace creation and removal is contained under this root.

Used by **Provision Workspace**, **Workspace Operations Stay Inside the Root**.

### `agent.max_concurrent_agents` — Global concurrency cap

The maximum number of agent runs executing concurrently.

- Must be a positive integer.
- Admission never exceeds it; deferred issues stay eligible.
- Re-read every poll cycle; new admissions honor the new value.

Used by **Dispatch Issue**, **Concurrency Never Exceeds Configured Caps**.

### `agent.max_concurrent_agents_by_state` — Per-state concurrency caps

Optional per-tracker-state overrides of the concurrency cap.

- Keys are state names, matched case-insensitively; values are positive integers.
- A state without an override uses the global cap.

Used by **Dispatch Issue**, **Concurrency Never Exceeds Configured Caps**.

### `agent.max_turns` — Turn budget per run

How many turns one agent run may execute before returning control to the scheduler.

- Must be a positive integer.
- Reaching the budget with the issue still active ends the run normally.

Used by **Agent Run**, **Turn Budget Bounds Every Run**.

### `agent.max_retry_backoff_ms` — Maximum retry backoff

The upper bound on the delay between consecutive failure retries of one issue.

- Must be a positive duration.
- Failure retry delays grow up to and never beyond this value.

Used by **Retry a Claimed Issue**, **Failure Retries Back Off Within a Cap**.

### `codex.command` — Agent runtime command

The command line that launches the coding-agent runtime for each session.

- Must be non-blank.
- Runs with the workspace as working directory on the run's execution target.
- Operator-supplied arguments pass through to the runtime.

Used by **Agent Session Protocol**.

### `codex.approval_policy` — Approval policy

How mid-turn approval requests are answered.

- A dedicated auto-approve value grants approvals for the session automatically.
- Any other policy turns approval requests into blocking outcomes.
- Structured policy values pass through to the runtime unchanged.

Used by **Handle Mid-Turn Requests**.

### `codex.thread_sandbox` — Session sandbox mode

The sandbox mode declared for the whole agent session.

- Passed to the runtime at session start.

Used by **Agent Session Protocol**.

### `codex.turn_sandbox_policy` — Turn sandbox policy

The filesystem and network policy applied to each turn.

- When set, the operator's structured policy passes through unchanged.
- When unset, a default policy grants write access to the workspace only.
- The default's workspace path is canonicalized for local runs.

Used by **Agent Session Protocol**, **Agent Run**.

### `codex.turn_timeout_ms` — Turn inactivity timeout

How long a turn may stay silent before it is failed.

- Must be a positive duration.
- Resets on every received stream event.

Used by **Agent Run**, **Turn Inactivity Timeout**.

### `codex.read_timeout_ms` — Control response timeout

How long the client waits for a direct protocol response during session setup.

- Must be a positive duration.
- Expiry fails the pending control operation.

Used by **Agent Session Protocol**.

### `codex.stall_timeout_ms` — Stall timeout

How long a running agent may go without observable session activity before stall recovery acts.

- Zero or negative disables stall detection.
- Expiry triggers restart-with-backoff, or blocking when input was requested.

Used by **Detect and Recover Stalled Runs**.

### `hooks.after_create` — Bootstrap hook

The shell command that initializes a newly created workspace (for example, cloning the repository).

- Runs only when the workspace directory was newly created.
- Failure or timeout removes the fresh workspace and fails provisioning.

Used by **Provision Workspace**.

### `hooks.before_run` — Pre-run hook

The shell command run in the workspace before each agent session starts.

- Failure aborts the run before any session starts.

Used by **Agent Run**.

### `hooks.after_run` — Post-run hook

The shell command run in the workspace after each agent run, on every exit path.

- Failures are logged and ignored.

Used by **Agent Run**.

### `hooks.before_remove` — Pre-removal hook

The shell command run in the workspace before it is removed (for example, salvaging artifacts).

- Failure or timeout never prevents the removal.

Used by **Remove Workspace for Finished Issue**.

### `hooks.timeout_ms` — Hook timeout

The shared execution timeout for every workspace hook.

- Must be a positive duration.
- A timed-out hook is terminated and treated as failed per its hook point.

Used by **Workspace Lifecycle Hooks**.

### `workflow.prompt_template` — Prompt template

The template rendered into each run's first-turn prompt; the operator's entire tracker-workflow policy for the agent lives here.

- Receives every issue field and the attempt number.
- Rendering is strict; unknown variables fail the run.
- Blank templates fall back to a documented built-in default.

Used by **Agent Run**, **Workflow Document**.

### `worker.ssh_hosts` — Worker hosts

The remote worker hosts on which workspaces and agent sessions run.

- An empty list means local execution.
- Each entry names one reachable execution target.

Used by **Run Agents on Remote Worker Hosts**.

### `worker.max_concurrent_agents_per_host` — Per-host concurrency cap

The maximum concurrent agent runs on any single worker host.

- Must be a positive integer when set; unset means unlimited per host.
- Host selection skips hosts at their cap; all-full defers dispatch.

Used by **Run Agents on Remote Worker Hosts**, **Concurrency Never Exceeds Configured Caps**.

### `observability.dashboard_enabled` — Terminal dashboard toggle

Whether the terminal status dashboard renders.

- Disabling stops rendering without affecting scheduling or the API.

Used by **Observe Orchestrator Status**.

### `observability.refresh_ms` — Dashboard refresh cadence

The periodic re-render cadence of the terminal dashboard.

- Must be a positive duration.

Used by **Observe Orchestrator Status**.

### `observability.render_interval_ms` — Render coalescing interval

The minimum spacing between dashboard renders when updates arrive rapidly.

- Must be a positive duration.
- Bursts of updates coalesce into one render per interval.

Used by **Observe Orchestrator Status**.

### `server.port` — Observability server port

The TCP port for the HTTP observability surface.

- Unset disables the HTTP surface entirely.
- Zero requests an ephemeral port; the bound port is discoverable.
- An invocation-time override takes precedence over the document value.

Used by **Observability API and Dashboards**.

### `server.host` — Observability bind host

The address the HTTP observability surface binds to.

- Defaults to a loopback-only bind.

Used by **Observability API and Dashboards**.

### Config Fields Summary (Cheat Sheet)

One line per field. Generated from the same records as the full entries above.

- `polling.interval_ms` — How often the scheduler runs a poll cycle (reconcile plus dispatch).
- `tracker.kind` — Which tracker adapter the orchestrator uses.
- `tracker.provider` — Provider-specific connection settings - endpoint, project scope, credentials, assignee identity - owned by the selected adapter.
- `tracker.active_states` — The tracker state names that make an issue eligible for dispatch and for turn continuation.
- `tracker.terminal_states` — The tracker state names that mean an issue is finished and its workspace reclaimable.
- `tracker.required_labels` — Labels an issue must carry (all of them) to be routed to this orchestrator.
- `workspace.root` — The directory under which every per-issue workspace lives; the local blast radius granted to agents.
- `agent.max_concurrent_agents` — The maximum number of agent runs executing concurrently.
- `agent.max_concurrent_agents_by_state` — Optional per-tracker-state overrides of the concurrency cap.
- `agent.max_turns` — How many turns one agent run may execute before returning control to the scheduler.
- `agent.max_retry_backoff_ms` — The upper bound on the delay between consecutive failure retries of one issue.
- `codex.command` — The command line that launches the coding-agent runtime for each session.
- `codex.approval_policy` — How mid-turn approval requests are answered.
- `codex.thread_sandbox` — The sandbox mode declared for the whole agent session.
- `codex.turn_sandbox_policy` — The filesystem and network policy applied to each turn.
- `codex.turn_timeout_ms` — How long a turn may stay silent before it is failed.
- `codex.read_timeout_ms` — How long the client waits for a direct protocol response during session setup.
- `codex.stall_timeout_ms` — How long a running agent may go without observable session activity before stall recovery acts.
- `hooks.after_create` — The shell command that initializes a newly created workspace (for example, cloning the repository).
- `hooks.before_run` — The shell command run in the workspace before each agent session starts.
- `hooks.after_run` — The shell command run in the workspace after each agent run, on every exit path.
- `hooks.before_remove` — The shell command run in the workspace before it is removed (for example, salvaging artifacts).
- `hooks.timeout_ms` — The shared execution timeout for every workspace hook.
- `workflow.prompt_template` — The template rendered into each run's first-turn prompt; the operator's entire tracker-workflow policy for the agent lives here.
- `worker.ssh_hosts` — The remote worker hosts on which workspaces and agent sessions run.
- `worker.max_concurrent_agents_per_host` — The maximum concurrent agent runs on any single worker host.
- `observability.dashboard_enabled` — Whether the terminal status dashboard renders.
- `observability.refresh_ms` — The periodic re-render cadence of the terminal dashboard.
- `observability.render_interval_ms` — The minimum spacing between dashboard renders when updates arrive rapidly.
- `server.port` — The TCP port for the HTTP observability surface.
- `server.host` — The address the HTTP observability surface binds to.

## 1. Configuration and Reload

How operator intent enters the system: one workflow document, strict validation at startup, hot reload while running, and the last-known-good guarantee that protects mid-run agents from bad edits.

### Workflow Document

The single operator artifact carrying both the structured settings and the prompt template for one orchestrator instance.

Input semantics:

- One document combines structured settings and a prompt-template body.
- Settings group by area; unknown areas and absent optional fields take documented defaults.
- String values may reference environment variables; references resolve at load time.
- Secret values resolve from provider-conventional environment fallbacks when unset.
- The prompt template receives every issue field plus the attempt number.
- Template rendering is strict; referencing an unknown variable is an error.

Output semantics:

- Loading yields validated settings plus the effective prompt template.
- A blank template yields a documented built-in default prompt.

Failure semantics:

- A missing document, a parse failure, or an invalid field is a load failure with a reason.
- Settings that decode to a non-map structure are rejected.
- A template parse or render failure fails the agent run that needed the prompt.

Implementation-defined mechanisms:

- The document's concrete syntax (the reference uses Markdown with YAML front matter).
- Concrete setting names and nesting (this specification fixes semantics via parameter keys).
- The template language (the reference uses Liquid-style templates).

Example: Minimal front matter plus prompt (reference syntax):

```markdown
---
tracker:
  kind: linear
  provider:
    project_slug: "my-project"
polling:
  interval_ms: 5000
workspace:
  root: ~/code/agent-workspaces
hooks:
  after_create: |
    git clone --depth 1 https://example.com/repo .
agent:
  max_concurrent_agents: 10
  max_turns: 20
codex:
  approval_policy: never
---

You are working on ticket {{ issue.identifier }}: {{ issue.title }}
{% if attempt %}This is follow-up attempt #{{ attempt }}.{% endif %}
```

**Verification**

- Load a document exercising defaults, environment references, and a template, and verify the resolved settings and rendered prompt.

### Service Invocation

How an operator starts one orchestrator instance against one workflow document.

Input semantics:

- An optional workflow document path argument; absent, a documented default location applies.
- A mandatory explicit acknowledgement that agents run unattended without guardrails.
- Optional overrides for the log destination root and the observability server port.

Output semantics:

- On success the process runs until its supervision tree stops, then exits with a matching status.

Failure semantics:

- Missing acknowledgement prints a prominent warning banner and exits nonzero.
- A missing workflow file or invalid arguments print usage or the error and exit nonzero.

Implementation-defined mechanisms:

- The exact flag spellings and banner wording.
- The packaging (escript, release binary, or container entrypoint).

**Verification**

- Invoke without the acknowledgement and verify the banner and nonzero exit.
- Invoke with an explicit workflow path and verify that document is loaded.

### Load Configuration at Startup

Turn the operator's workflow document into a validated running configuration, or refuse to run.

Participants: **Configuration Authority**, **Workflow Document**.

Trigger: The service starts with a workflow document path (explicit or defaulted).

Preconditions:

- The operator has acknowledged unattended execution at invocation.

Sequence:

1. **Configuration Authority** Read the workflow document and split it into structured settings and the prompt template.
2. **Configuration Authority** Parse the settings, apply defaults, and resolve environment references for secrets and paths.
3. **Configuration Authority** Validate structure, then run the selected tracker adapter's semantic validation.
4. **Configuration Authority** On success, publish the settings; on any failure, stop startup with the reason.

Postconditions:

- Either the service runs with fully validated settings, or it did not start.

- **MUST** — Refuse startup when the document is missing, unparsable, or invalid.
- **MUST** — Refuse startup when no supported tracker kind is configured.

Constrained by **Only Validated Configuration Is Ever Effective**.

Failures: **Invalid Configuration at Startup**.

Validation checks:

- Start with a missing document and verify the service exits with a missing-file error.
- Start with structurally invalid settings and verify startup is refused with the validation message.
- Start without a tracker kind and verify startup is refused.
- Start without the unattended-execution acknowledgement and verify the service prints the warning and exits nonzero.

### Hot-Reload Configuration

Apply operator edits to the workflow document while the service runs, without ever serving a partially valid configuration.

Participants: **Configuration Authority**, **Workflow Document**.

Trigger: The workflow document's content changes while the service is running.

Sequence:

1. **Configuration Authority** Detect that the document changed since the last successful load.
2. **Configuration Authority** Re-run the full load and validation pipeline on the new content.
3. **Configuration Authority** On success, atomically replace the served settings and prompt template.
4. **Configuration Authority** On failure, log the reason and continue serving the last known good configuration.

Postconditions:

- Subsequent scheduling, agent, and observability decisions read the newest valid settings.

- **MUST** — Apply valid edits without a service restart.
- **MUST NOT** — Replace running settings with any configuration that failed validation.

Constrained by **Only Validated Configuration Is Ever Effective**.

Failures: **Invalid Configuration on Reload**.

Validation checks:

- Change the poll interval in the document and verify the next cycles use the new interval without restart.
- Write an invalid document and verify the previous settings keep being served and the error is logged.
- Restore a valid document and verify it takes effect on the next read.

### Only Validated Configuration Is Ever Effective

Every setting the service acts on comes from a workflow document that passed full structural and semantic validation. An invalid document prevents startup; an invalid edit never replaces the running configuration.

Operators must be able to edit configuration live without risking the agents currently running.

This prevents:

- Running with partially applied or defaulted-over broken settings.
- A bad edit taking down mid-run agents.

Validation checks:

- Attempt startup with each class of invalid document and verify refusal with a reason.
- Break the document mid-run and verify all subsequent reads still serve the prior settings.

### Invalid Configuration at Startup

The workflow document is missing, unparsable, structurally invalid, or fails the tracker adapter's semantic validation when the service starts.

Occurs during **Load Configuration at Startup**.

Retryable: no (requires operator correction).

Requirements:

- Refuse to start; no partial runtime comes up.
- Report the failure class and detail to the operator.

Recovery: The operator fixes the document and starts the service again.

Validation checks:

- For each failure class (missing file, parse error, invalid field, missing tracker kind) verify refusal with a distinguishable reason.

### Invalid Configuration on Reload

A running service detects a document change whose content fails any stage of the load and validation pipeline.

Occurs during **Hot-Reload Configuration**.

Retryable: yes (next detected change retries automatically).

Requirements:

- Keep serving the last known good configuration unchanged.
- Log the reload failure with its reason.
- Leave running agents and claims untouched.

Recovery: A subsequent valid edit is picked up and applied normally.

Validation checks:

- Break the document mid-run and verify settings reads, agents, and claims are unaffected.
- Fix the document and verify the new settings apply without restart.

## 2. Scheduling and Dispatch

The poll cycle that turns active tracker issues into supervised agent runs: candidate ordering, eligibility, the claim as duplication guard, capacity limits, and last-moment revalidation before every spawn.

### Poll Cycle

Periodically synchronize the claim ledger with the tracker and fill free capacity with the most deserving active issues.

Participants: **Scheduler**, **Tracker Adapter**, **Issue**, **Claim**.

Trigger: The poll interval elapses, or an operator requests an immediate refresh.

Sequence:

1. **Scheduler** Refresh runtime-tunable settings (poll interval, concurrency caps).
2. **Scheduler** Reconcile running and blocked claims against fresh tracker state.
3. **Tracker Adapter** Fetch all issues currently in the configured active states.
4. **Scheduler** Order candidates by priority, then age, then identifier.
5. **Scheduler** Dispatch eligible candidates while capacity remains.
6. **Scheduler** Schedule the next cycle after the configured interval.

Postconditions:

- Every claim reflects tracker state as of this cycle, and free capacity was offered to eligible issues.

- **MUST** — Coalesce refresh requests when a cycle is already due or in progress.
- **SHOULD** — Run the first cycle promptly after startup rather than waiting a full interval.

Constrained by **Deterministic Dispatch Order**.

Failures: **Tracker Fetch Failure**.

Validation checks:

- Observe that a cycle runs shortly after startup and then at the configured interval.
- Issue several refresh requests during one cycle and verify only one additional cycle results.
- Present candidates with mixed priorities and ages and verify dispatch order is priority, then oldest creation time, then identifier.

### Dispatch Issue

Admit one eligible issue into execution: verify eligibility against the freshest possible state, take the claim, and start a supervised agent run.

Participants: **Scheduler**, **Tracker Adapter**, **Agent Run Supervisor**, **Issue**, **Claim**.

Trigger: A poll cycle or a due retry selects a candidate issue while capacity is free.

Preconditions:

- The issue has non-empty id, identifier, title, and state.
- The issue is in an active state, not a terminal state, and routed to this orchestrator.
- No claim (running, retrying-consumed, or blocked) exists for the issue id.
- Global, per-state, and per-host concurrency limits all have a free slot.

Sequence:

1. **Tracker Adapter** Re-fetch the issue by id immediately before spawning.
2. **Scheduler** Skip the dispatch when the refreshed issue is missing, terminal, unrouted, or otherwise ineligible.
3. **Scheduler** Select the execution target for the run.
4. **Scheduler** Record the claim with attempt metadata, then start and monitor the agent run.
5. **Agent Run Supervisor** Begin the run for the refreshed issue on the selected target.

Postconditions:

- Exactly one running claim exists for the issue, or the issue was skipped with its claim state unchanged.

- **MUST** — Skip dispatch silently when refresh shows the issue no longer eligible.
- **MUST** — Schedule a retry when spawning the run fails.

Constrained by **One Claim per Issue**, **Concurrency Never Exceeds Configured Caps**, **Fresh State Precedes Every Spawn**.

Failures: **Agent Spawn Failure**.

Validation checks:

- Verify a claimed, running, or blocked issue is never dispatched again while the claim holds.
- Move an issue to a terminal state between listing and dispatch and verify the dispatch is skipped.
- Fill the global cap and verify further candidates wait; repeat for a per-state cap.
- Kill the run spawn and verify a retry is scheduled instead of losing the issue.

### Deterministic Dispatch Order

Dispatch candidates are ordered by provider priority rank (1 highest through 4, absent or invalid last), then oldest creation time, then identifier.

Operators can predict which issues get slots first when capacity is scarce.

This prevents:

- Starvation of old high-priority items by arrival order accidents.

Validation checks:

- Offer candidates with mixed priority, age, and identifier and verify the exact order.
- Verify issues without priority or creation time sort after those with them.

### One Claim per Issue

At any moment, at most one claim exists per issue id, and an issue with a claim in any lifecycle state is never dispatched again until that claim is released.

The claim is the sole guard against two agents working the same issue.

This prevents:

- Duplicate concurrent agents corrupting one workspace or tracker thread.
- Retry timers and live runs coexisting for one issue.

Validation checks:

- Drive poll cycles while an issue runs, retries, and blocks, and verify no second dispatch occurs.
- Restart the orchestrator mid-run and verify redispatched work does not overlap a surviving agent.

### Concurrency Never Exceeds Configured Caps

The number of concurrently running agent runs never exceeds the global cap, the per-tracker-state cap for any state, or the per-host cap on any execution target.

Operators bound resource usage and tracker churn with hard limits.

This prevents:

- Resource exhaustion on the orchestrator or a worker host.
- One tracker state monopolizing all execution slots.

Validation checks:

- Offer more eligible issues than each cap allows and verify running counts stay at the cap.
- Lower a cap at runtime and verify subsequent admission respects the new value.

### Fresh State Precedes Every Spawn

Immediately before an agent run is spawned - on first dispatch and on every retry - the issue is re-fetched by id and the dispatch is skipped unless the fresh issue is still an eligible candidate.

Listing results and retry decisions are stale by the time they act; only a just-fetched issue may justify spending an agent on it.

This prevents:

- Starting agents on issues closed, reassigned, or blocked since listing.

Validation checks:

- Change an issue's state between listing and spawn and verify the spawn is skipped.
- Verify a retry whose refetch shows lost routing releases instead of spawning.

### Tracker Fetch Failure

A tracker read (listing active issues, reconciling claim ids, or refetching for retry) fails or returns an error.

Occurs during **Poll Cycle**, **Reconcile Claims Against Tracker**, **Retry a Claimed Issue**.

Retryable: yes (next cycle or next backoff step).

Requirements:

- Treat the failure as absence of information, never as issue absence.
- Keep running agents and held claims unchanged.
- Log the failure and proceed to the next scheduled attempt.
- Reschedule an affected retry with an increased delay.

Recovery: Normal operation resumes on the first successful fetch; reconciliation then applies whatever changed in the meantime.

Validation checks:

- Fail listing during a poll cycle and verify no claim changes and the next cycle is scheduled.
- Fail the reconciliation fetch and verify agents keep running.
- Fail a retry refetch and verify the retry reschedules with a larger delay.

### Agent Spawn Failure

The supervised agent run cannot be started for an admitted issue.

Occurs during **Dispatch Issue**.

Retryable: yes.

Requirements:

- Do not lose the issue; schedule a backed-off retry carrying the error.
- Record the failure reason on the retry entry for the operator.

Recovery: The retry path re-validates and re-dispatches when the cause clears.

Validation checks:

- Force spawn failure and verify a retry entry exists with the error and an increased attempt.

## 3. Claim Lifecycle, Retry, and Blocking

What happens to an issue after it is claimed: the lifecycle of a claim, reconciliation that lets tracker state override local state, backed-off retries that never duplicate, stall recovery, and the blocked handling that holds issues waiting on a human.

### Lifecycle and State

The lifecycle begins in **Unclaimed**.

- **Unclaimed** — The issue is visible in an active tracker state but this orchestrator holds no claim on it. It competes for dispatch every poll cycle.
- **Running** — A claim is held and an agent run is executing in the issue's workspace. The claim carries live telemetry from the session.
- **Awaiting Retry** — A claim is held with no live agent; a timer will re-validate and re-dispatch the issue. Covers failure backoff, capacity waits, and the continuation check after a normal run completion.
- **Blocked** — A claim is held because the agent needs operator input or approval. No timer exists; only an observed tracker-state change releases it.
- **Released** — The claim is gone. The issue may re-enter as Unclaimed later if the tracker makes it eligible again. This is terminal.

#### Transitions

- **Unclaimed** → **Running** when dispatch admits the issue after revalidation and takes the claim.
- **Running** → **Awaiting Retry** when the agent run exits abnormally, stalls without an input signal, or completes normally (continuation check).
- **Running** → **Blocked** when the run exits or stalls while the last session signal indicates required operator input or approval.
- **Running** → **Released** when reconciliation observes the issue terminal, inactive, unrouted, or missing.
- **Awaiting Retry** → **Running** when the retry timer fires, revalidation passes, and capacity is free.
- **Awaiting Retry** → **Awaiting Retry** when the retry timer fires but capacity is exhausted or the refetch failed; a longer retry is scheduled.
- **Awaiting Retry** → **Released** when the retry-time refetch shows the issue terminal, inactive, unrouted, or missing.
- **Blocked** → **Released** when reconciliation observes the blocked issue terminal, inactive, unrouted, or missing.

#### Lifecycle Constraints

- An issue holds at most one claim, in exactly one lifecycle state, at any time.
- Only fresh tracker state moves a claim into Released.
- Blocked never transitions directly back to Running; release and re-dispatch are required.
- Workspace removal accompanies release only when the observed tracker state is terminal.

### Reconcile Claims Against Tracker

Make fresh tracker state override every locally held claim, stopping agents and releasing claims the tracker no longer justifies.

Participants: **Scheduler**, **Tracker Adapter**, **Workspace Manager**, **Issue**, **Claim**, **Workspace**.

Trigger: Each poll cycle begins, before any new dispatch.

Sequence:

1. **Tracker Adapter** Fetch fresh issues for every running and every blocked claim id.
2. **Scheduler** For a now-terminal issue, stop its agent, request workspace removal, and release the claim.
3. **Workspace Manager** Remove the workspace recorded for each terminal issue.
4. **Scheduler** For an issue no longer routed here or no longer active, stop its agent and release the claim, keeping the workspace.
5. **Scheduler** For an issue absent from the fetch result, stop its agent or release its block, keeping the workspace.
6. **Scheduler** For a still-active issue, refresh the cached issue snapshot on the claim.

Postconditions:

- No agent is running for an issue the tracker shows terminal, inactive, unrouted, or missing.

- **MUST NOT** — Stop agents or release claims when the reconciliation fetch itself fails.
- **MUST** — Remove the workspace only for issues observed in a terminal state.

Constrained by **Tracker State Supersedes Local Claims**.

Failures: **Tracker Fetch Failure**.

Validation checks:

- Move a running issue to a terminal state and verify the agent stops and the workspace is removed.
- Remove a required label from a running issue and verify the agent stops and the workspace is kept.
- Make the tracker fetch fail during reconciliation and verify all agents keep running.
- Move a blocked issue to a terminal state and verify the block is released and the workspace removed.

### Retry a Claimed Issue

Re-admit a claimed issue after a failure, a stall, a capacity wait, or a normal completion check, with backoff and full re-validation.

Participants: **Scheduler**, **Tracker Adapter**, **Issue**, **Claim**.

Trigger: A retry timer fires for a claimed issue.

Sequence:

1. **Scheduler** Ignore the timer when it does not match the currently scheduled retry for that issue.
2. **Tracker Adapter** Re-fetch the issue by id.
3. **Scheduler** Release the claim (removing the workspace when terminal) if the issue is terminal, inactive, unrouted, or missing.
4. **Scheduler** When still eligible and capacity is free, redispatch, preserving the attempt count and preferred execution target.
5. **Scheduler** When capacity is exhausted or the refetch fails, reschedule with the next backoff step.

Postconditions:

- The issue is running again, rescheduled with a larger delay, or fully released - never silently dropped.

- **MUST** — Preserve attempt count and prior execution target across rescheduled retries.
- **MUST** — Increase the delay between consecutive failure retries up to the configured cap.

Constrained by **Failure Retries Back Off Within a Cap**.

Failures: **Tracker Fetch Failure**.

Validation checks:

- Fail an agent repeatedly and verify each retry waits longer, up to the configured maximum.
- Fire a stale (superseded) retry timer and verify it consumes nothing.
- Fill capacity when a retry fires and verify the retry reschedules instead of dropping the claim.
- Move the issue out of active states before the retry fires and verify the claim is released.

### Detect and Recover Stalled Runs

Notice agent runs that have stopped making observable progress and route them to retry or to blocked handling.

Participants: **Scheduler**, **Claim**, **Agent Session**, **Session Event**.

Trigger: A poll cycle inspects running claims while a stall timeout is configured.

Sequence:

1. **Scheduler** Compute each run's idle time from its last session event, falling back to its start time.
2. **Scheduler** Leave runs alone while idle time is within the stall timeout, or when the timeout is disabled.
3. **Scheduler** For a stalled run whose last signal indicates operator input, stop the session and block the issue.
4. **Scheduler** For any other stalled run, stop the session and schedule a backed-off retry.

Postconditions:

- No run stays silently idle beyond the stall timeout.

- **MUST** — Treat a zero or negative stall timeout as disabling stall detection.
- **MUST NOT** — Remove the workspace when recovering a stalled run.

Constrained by **Blocked Issues Are Held, Not Retried**.

Failures: **Agent Run Stalled**.

Validation checks:

- Let a run go idle past the stall timeout and verify it is stopped and retried with backoff.
- Stall a run after an elicitation request and verify it is blocked instead of retried.
- Set the stall timeout to zero and verify idle runs are left alone.

### Block an Issue on Operator Input

Convert an agent run that is waiting on a human decision into a held, non-retrying blocked claim that a human can discover and resolve.

Participants: **Scheduler**, **Claim**, **Issue**, **Agent Session**.

Trigger: An agent run exits, or stalls past the stall timeout, while its last observed signal indicates required operator input or approval.

Sequence:

1. **Scheduler** Stop the agent session if it is still running.
2. **Scheduler** Record a blocked entry carrying the reason, session id, workspace path, execution target, and last session signal.
3. **Scheduler** Drop any pending retry state and keep the claim held.
4. **Scheduler** Exclude the issue from dispatch and retry until reconciliation observes a tracker-state change.

Postconditions:

- The issue is visible as blocked with its reason, and no agent or retry timer exists for it.

- **MUST NOT** — Automatically restart or retry a blocked issue while its tracker state is unchanged.
- **MUST** — Expose the blocking reason to the operator-facing status surface.

Constrained by **Blocked Issues Are Held, Not Retried**.

Failures: **Operator Input Required**.

Validation checks:

- End a run with an input-required signal and verify the issue becomes blocked, not retried.
- Verify a normal exit whose last signal was input-required also blocks.
- Verify blocked issues are skipped by dispatch until the tracker state changes.
- Change the blocked issue's tracker state and verify reconciliation releases the block.

### Tracker State Supersedes Local Claims

When fresh tracker state contradicts a local claim - the issue became terminal, left the active states, lost routing, or disappeared - the claim yields: agents stop and the claim is released. Absence of fresh state (a failed fetch) changes nothing.

Humans and other tools own the tracker; the orchestrator must follow, not fight, their changes.

This prevents:

- Agents continuing work on closed or reassigned issues.
- Tracker outages mass-stopping healthy agents.

Validation checks:

- For each contradiction class (terminal, inactive, unrouted, missing) verify agent stop and claim release.
- Fail the fetch and verify no claim changes.

### Failure Retries Back Off Within a Cap

Consecutive failure retries for one issue wait progressively longer, never exceed the operator-configured maximum backoff, and the first failure retry already waits a non-trivial delay.

A persistently failing issue must not hammer the tracker or the agent runtime, yet must keep being retried.

This prevents:

- Tight crash loops consuming agent budget and provider rate limits.
- Unbounded delays that effectively abandon an issue.

Validation checks:

- Fail a run repeatedly and verify each scheduled delay is at least the previous one until the cap.
- Verify no scheduled failure-retry delay exceeds the configured maximum.

### Blocked Issues Are Held, Not Retried

An issue blocked on operator input or approval is never automatically restarted or retried; it stays held and visible until reconciliation observes its tracker state change.

Re-running an agent that is waiting for a human wastes budget and can repeat the action that needed approval.

This prevents:

- Retry loops against a question only a human can answer.
- Silent disappearance of issues that need human attention.

Validation checks:

- Block an issue and run many poll cycles, verifying no dispatch or retry occurs.
- Verify stall detection routes input-waiting runs to blocked, not to backoff retry.

### Agent Run Abnormal Exit

An agent run terminates with an error: session startup failed, a turn failed or was cancelled, the process crashed, or the run raised.

Occurs during **Agent Run**.

Retryable: yes.

Requirements:

- Keep the claim and schedule a backed-off retry preserving attempt count and execution target.
- Keep the workspace so the retry resumes prior work.
- Record the exit reason for observability.
- Route the exit to blocked handling instead when the last session signal was input-required.

Recovery: The retry re-validates the issue and starts a fresh run in the same workspace.

Validation checks:

- Crash a run and verify claim retention, workspace retention, and a backed-off retry.
- Crash a run after an input-required event and verify blocking instead of retry.

### Agent Run Stalled

A running agent produced no observable session activity for longer than the configured stall timeout.

Occurs during **Detect and Recover Stalled Runs**.

Retryable: yes, unless the last signal was input-required.

Requirements:

- Stop the stalled session.
- Schedule a backed-off retry preserving the claim and workspace.
- Block instead of retrying when the last signal indicated required input.

Recovery: The retried run resumes from the intact workspace.

Validation checks:

- Stall a run and verify stop plus backed-off retry with the workspace intact.
- Stall a run on an elicitation and verify blocking.

### Operator Input Required

The agent runtime asks for something only a human can provide - an approval under a non-auto-approving policy, freeform input, or an elicitation - and the turn cannot proceed.

Occurs during **Agent Run**, **Handle Mid-Turn Requests**, **Block an Issue on Operator Input**.

Retryable: no (automatic retry is prohibited; human action releases it).

Requirements:

- End the turn promptly with a classified input-required or approval-required outcome.
- Move the claim to blocked, carrying the human-readable reason.
- Hold the block until the tracker state changes.

Recovery: A human answers via the tracker or agent-side channel and moves the issue's tracker state; reconciliation releases the block and normal dispatch resumes.

Validation checks:

- Trigger each blocker class (approval, freeform input, elicitation) and verify a blocked claim with a reason.
- Verify no automatic retry occurs while blocked.

## 4. Agent Session Execution

One agent run from the inside: the session protocol, the prompt built from the operator's template, the bounded turn loop that re-checks the tracker between turns, mid-turn approval and input handling, and the secrecy line between orchestrator credentials and agent commands.

### Agent Run

Execute one supervised attempt at an issue: a prepared workspace, one agent session, and a bounded loop of turns that continues only while the tracker still wants the work done here.

Participants: **Agent Run Supervisor**, **Workspace Manager**, **Agent Session Protocol Client**, **Tracker Adapter**, **Issue**, **Workspace**, **Agent Session**.

Trigger: Dispatch starts a run for a claimed issue.

Sequence:

1. **Workspace Manager** Provision the issue's workspace on the selected execution target.
2. **Agent Run Supervisor** Report the resolved workspace path and execution target back to the scheduler.
3. **Workspace Manager** Run the before_run hook; a failure aborts the run.
4. **Agent Session Protocol Client** Start one agent session with the workspace as working directory and the configured policies.
5. **Agent Run Supervisor** Render the first-turn prompt from the operator template with the issue fields and attempt number.
6. **Agent Session Protocol Client** Run the turn, streaming session events to the scheduler.
7. **Tracker Adapter** Re-fetch the issue after each completed turn.
8. **Agent Run Supervisor** Start a continuation turn while the issue stays active and routed here and the turn budget remains.
9. **Agent Run Supervisor** End the run when the issue is done, routing is lost, or the turn budget is exhausted.
10. **Workspace Manager** Run the after_run hook on every exit path, ignoring its failures.
11. **Agent Session Protocol Client** Tear down the session on every exit path.

Postconditions:

- The session is closed, teardown hooks ran, and the scheduler observed the run's outcome.
- After a normal completion, the scheduler schedules a prompt continuation check for the issue.

- **MUST NOT** — Start a continuation turn after the issue leaves active states or loses routing.
- **MUST** — Return control to the scheduler when the turn budget is exhausted with the issue still active.
- **MUST** — Keep the workspace intact after the run ends.

Constrained by **Turn Budget Bounds Every Run**, **Tracker Secrets Never Reach the Agent**.

Failures: **Agent Run Abnormal Exit**, **Turn Inactivity Timeout**, **Operator Input Required**.

Validation checks:

- Keep an issue active and verify the run continues with follow-up turns until the turn budget.
- Verify a run at the turn budget returns to the scheduler and a later run resumes the same workspace.
- Remove a required label mid-run and verify no further continuation turn starts.
- Verify the after_run hook and session teardown execute on both success and failure paths.
- Verify a normal completion is followed by a scheduled continuation check for the issue.

### Handle Mid-Turn Requests

Answer the agent runtime's mid-turn requests - approvals, tool calls, and input requests - according to the operator's approval policy, without ever leaving the turn waiting silently.

Participants: **Agent Session Protocol Client**, **Agent Session**, **Session Event**.

Trigger: The agent session emits a request during a running turn.

Sequence:

1. **Agent Session Protocol Client** Execute advertised dynamic tool calls and reply with a structured result, continuing the turn.
2. **Agent Session Protocol Client** Answer unsupported tool calls with a structured failure naming the supported tools, continuing the turn.
3. **Agent Session Protocol Client** Under an auto-approving policy, grant approval requests for the session and continue the turn.
4. **Agent Session Protocol Client** Under any other policy, end the turn as an approval-required blocker.
5. **Agent Session Protocol Client** End the turn as an input-required blocker for freeform input and elicitation requests that cannot be auto-answered.

Postconditions:

- Every mid-turn request received a reply or ended the turn with a classified blocker.

- **MUST NOT** — Leave a mid-turn request unanswered while the turn keeps waiting.
- **MUST** — Distinguish approval-required and input-required outcomes from generic turn failure.

Constrained by **Tracker Secrets Never Reach the Agent**.

Failures: **Operator Input Required**.

Validation checks:

- Under the auto-approving policy, verify command and patch approval requests are granted for the session.
- Under a safer policy, verify an approval request ends the turn as approval-required.
- Send a freeform input request and verify the turn ends as input-required.
- Call an unsupported tool and verify a failure reply arrives and the turn does not stall.

### Agent Session Protocol

The conversation between the orchestrator and the coding-agent runtime that hosts sessions and turns.

Input semantics:

- The runtime is launched with the workspace as working directory, using the operator-configured command.
- Session setup declares client identity, approval policy, sandbox mode, working directory, and the advertised dynamic tools.
- Each turn submits the prompt, a human-readable title, the approval policy, and the turn sandbox policy.
- The default turn sandbox policy grants write access to the workspace only; an explicit operator policy passes through unchanged.

Output semantics:

- The runtime streams line-delimited protocol messages; events carry method names and payloads.
- Turn completion, failure, and cancellation are distinct terminal turn events.
- Partial lines are buffered until terminated; non-protocol output is logged, never fatal.

Failure semantics:

- Control responses not received within the read timeout fail the operation.
- Turn inactivity past the turn timeout fails the turn.
- Runtime process exit mid-turn fails the turn with the exit status.

Implementation-defined mechanisms:

- The concrete protocol dialect and method names (the reference speaks the Codex app-server JSON-RPC dialect).
- The launch mechanism and stream transport.

**Verification**

- Verify session setup carries policy, sandbox, working directory, and tools, and each turn carries prompt and sandbox policy.
- Split a protocol message across stream chunks and verify correct reassembly.
- Verify malformed protocol-like lines are surfaced as malformed events without ending the turn.

### Turn Budget Bounds Every Run

One agent run executes at most the configured number of turns; when the budget is exhausted with the issue still active, the run ends normally and control returns to the scheduler, which may start a fresh run.

A run that cannot finish must yield so scheduling policy, fresh configuration, and fairness re-apply between runs.

This prevents:

- A single run monopolizing a slot indefinitely.
- Continuation decisions escaping scheduler policy.

Validation checks:

- Keep an issue active past the budget and verify the run ends and a continuation check is scheduled.
- Verify no run ever executes more turns than the configured budget.

### Tracker Secrets Never Reach the Agent

Credential environment variables declared secret by the tracker adapter are removed from the agent process environment on every execution target; agents access the tracker only through brokered provider-native tools.

The agent executes untrusted, model-generated commands; ambient credentials would let those commands act as the orchestrator.

This prevents:

- Exfiltration or misuse of tracker credentials by agent-run commands.

Validation checks:

- Inspect the agent child environment locally and verify declared secret names are absent.
- Verify the remote launch command strips the same names before starting the agent.

### Turn Inactivity Timeout

A running turn produces no stream activity for the configured turn timeout; the turn is abandoned as failed.

Occurs during **Agent Run**.

Retryable: yes (as an abnormal run exit).

Requirements:

- Reset the timeout on every received stream event, so only true silence fires it.
- End the run with a timeout error that enters the normal retry path.

Recovery: The scheduler retries the issue with backoff.

Validation checks:

- Stream periodic events longer than the timeout and verify no firing.
- Go silent past the timeout and verify the turn fails with a timeout error.

## 5. Tracker Adapter Boundary

The contract every issue provider implements: normalized read operations the scheduler relies on, and the optional provider-native agent tools whose bindings are frozen per session.

### Tracker Adapter Contract

The boundary every issue provider implements so the scheduler can stay provider-agnostic.

Input semantics:

- Required read - fetch issues by a list of state names, normalized case-insensitively.
- Required read - fetch issues by a list of issue ids.
- Required - the list of secret environment variable names for the current settings.
- Optional - semantic validation of tracker settings at load time.
- Optional - provider-native agent tool specifications and execution (extension).

Output semantics:

- Reads return normalized Issues; malformed provider items are rejected, not passed through.
- The dispatchable verdict folds provider assignment, blocking relations, and readiness policy.
- An adapter is selected by the configured tracker kind from a documented registry.
- Adapters may supply provider-appropriate default active and terminal state sets.

Failure semantics:

- Reads return an error value on transport or provider failure; they never return partial guesses.
- An unsupported tracker kind is a configuration validation failure.

Implementation-defined mechanisms:

- The provider protocol, pagination, and rate handling behind each adapter.
- Which providers ship in the registry (the reference ships Linear, GitHub, GitLab, Jira, Asana, and an in-memory test adapter).

**Verification**

- Drive the scheduler against the in-memory adapter and verify identical scheduling behavior to a provider adapter.
- Feed a malformed provider item and verify it never reaches the scheduler.

### Execute Provider-Native Agent Tool (Optional Extension)

Let the agent act on the tracker through tools the adapter advertises, using a credential and settings snapshot fixed at session start.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Participants: **Agent Session Protocol Client**, **Tracker Adapter**, **Agent Session**, **Issue**.

Trigger: The agent session calls a dynamic tool during a turn.

Preconditions:

- The adapter advertised at least one tool at session start.

Sequence:

1. **Tracker Adapter** At session start, bind the adapter, tracker settings, tool specifications, and secret names into one snapshot.
2. **Agent Session Protocol Client** Advertise the bound tool specifications to the session.
3. **Tracker Adapter** On a call, validate the arguments against the tool's declared contract before contacting the provider.
4. **Tracker Adapter** Execute the call with the bound settings and return a structured success or failure payload.
5. **Agent Session Protocol Client** Reply the payload to the session so the turn continues.

Postconditions:

- The tool result reached the session, and no live configuration read occurred during execution.

- **MUST** — Reject invalid tool arguments before any provider request.
- **MUST** — Answer unknown tools with a failure payload naming supported tools.

Constrained by **Session-Start Tool Binding Is Immutable**.

Failures: **Provider Tool Call Failure**.

Validation checks:

- Reload the configuration mid-session and verify tool execution still uses the session-start snapshot.
- Call a tool with invalid arguments and verify a validation failure with no provider request.
- Verify provider error responses are returned as structured failures preserving the body.

### Session-Start Tool Binding Is Immutable

The tracker adapter, settings, tool specifications, and secret names used for provider-native tool execution are captured once at session start; a configuration reload never changes what an in-flight session's tools do or authenticate as.

Tool advertisement and tool execution must not drift apart within one session when the operator edits configuration.

This prevents:

- A mid-session reload re-pointing advertised tools at a different tracker or credential.

Validation checks:

- Reload the configuration with different tracker settings mid-session and verify tool calls still use the snapshot.

### Provider Tool Call Failure (Optional Extension)

A provider-native tool call fails: unknown tool, invalid arguments, provider error response, or transport failure.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Occurs during **Execute Provider-Native Agent Tool**.

Retryable: at the agent's discretion (the turn continues).

Requirements:

- Reply a structured failure payload to the session; never leave the call unanswered.
- Name the supported tools when the tool is unknown.
- Preserve provider error bodies in the failure payload.

Recovery: The agent reads the failure and adapts within the same turn.

Validation checks:

- Trigger each failure class and verify a structured failure reply with the turn continuing.

## 6. Workspace Provisioning and Safety

The per-issue directory every run executes in: deterministic identity, containment under the operator's root, lifecycle hooks for bootstrap and salvage, reuse across attempts, and removal when the tracker says the work is done.

### Provision Workspace

Give an agent run a deterministic, contained, bootstrapped directory for its issue, reusing prior work when it exists.

Participants: **Workspace Manager**, **Issue**, **Workspace**.

Trigger: An agent run needs its issue's workspace.

Sequence:

1. **Workspace Manager** Derive the deterministic, collision-safe workspace key from the issue identifier.
2. **Workspace Manager** Resolve the path under the configured root, canonicalize it, and verify containment.
3. **Workspace Manager** Reuse an existing directory unchanged; replace a non-directory; create the directory when absent.
4. **Workspace Manager** Run the after_create bootstrap hook only when the directory was newly created.
5. **Workspace Manager** On bootstrap failure or timeout, remove the newly created directory and fail the provisioning.

Postconditions:

- The workspace exists, is contained under the root, and is bootstrapped exactly once.

- **MUST** — Reuse an existing workspace without deleting its contents.
- **MUST** — Guarantee a failed bootstrap leaves no half-initialized workspace behind.

Constrained by **Workspace Operations Stay Inside the Root**, **Deterministic Workspace Identity**.

Failures: **Workspace Bootstrap Failure**, **Unsafe Workspace Path**.

Validation checks:

- Provision the same issue twice and verify the same path with contents preserved.
- Provision two identifiers that sanitize identically and verify distinct paths.
- Point the workspace at a symlink escaping the root and verify provisioning is refused.
- Fail the bootstrap hook and verify the fresh directory is removed and the next attempt bootstraps again.

### Remove Workspace for Finished Issue

Reclaim workspaces once the tracker shows their issues terminal, giving the operator's teardown hook a chance to salvage state first.

Participants: **Scheduler**, **Workspace Manager**, **Issue**, **Workspace**.

Trigger: Reconciliation or a retry check observes a terminal issue, or the service starts and sweeps issues already terminal.

Sequence:

1. **Scheduler** Identify the workspace by its recorded path when known, otherwise derive it from the issue identifier per execution target.
2. **Workspace Manager** Run the before_remove hook in the workspace; its failure or timeout never prevents removal.
3. **Workspace Manager** Validate containment of the target path, then remove the directory.

Postconditions:

- Workspaces for terminal issues no longer exist on any configured execution target.

- **MUST** — Sweep and remove workspaces of already-terminal issues at startup.
- **MUST NOT** — Remove the configured workspace root itself or any path outside it.

Constrained by **Workspace Operations Stay Inside the Root**.

Failures: **Non-Blocking Hook Failure**, **Unsafe Workspace Path**.

Validation checks:

- Move an issue to a terminal state and verify its workspace is removed after the before_remove hook runs.
- Make the before_remove hook fail and verify removal still completes.
- Record a workspace path that escapes containment and verify removal is refused.
- Restart the service with terminal issues present and verify their workspaces are swept.

### Workspace Lifecycle Hooks

Operator-supplied shell commands that run at workspace lifecycle boundaries, giving the operator control over bootstrap and salvage.

Input semantics:

- Four hook points: after_create (bootstrap), before_run, after_run, and before_remove.
- Every hook runs with the workspace as working directory, through a shell, on the run's execution target.
- Hooks may be multi-line scripts.
- One shared operator-configured timeout bounds each hook execution.

Output semantics:

- Exit status zero is success; anything else is hook failure.
- Hook output is captured for logging, truncated to a bounded size.

Failure semantics:

- after_create failure aborts provisioning and removes the fresh workspace.
- before_run failure aborts the agent run before any session starts.
- after_run and before_remove failures are logged and ignored.
- A timed-out hook is terminated and treated as failed.

Implementation-defined mechanisms:

- The shell and invocation details.
- How remote hook execution transports the script (extension).

**Verification**

- Verify each hook runs at its boundary with the workspace as working directory.
- Verify blocking hooks abort their operation on failure and non-blocking hooks do not.
- Verify a hook exceeding the timeout is terminated and handled per its blocking class.

### Workspace Operations Stay Inside the Root

Every local workspace create and remove operation acts on a canonicalized path strictly inside the configured workspace root; the root itself, symlink escapes, and outside paths are refused with the operation unperformed.

The workspace root is the entire local blast radius the operator granted; nothing may widen it, including hostile symlinks.

This prevents:

- An agent or a crafted identifier causing writes or deletion outside the root.
- Recursive removal of the root or of linked-in directories.

Validation checks:

- Attempt creation and removal through symlinks escaping the root and verify refusal.
- Attempt removal of the root itself and verify a distinct refusal.
- Verify a recorded workspace path is re-validated before removal.

### Deterministic Workspace Identity

The workspace key is a pure function of the issue identifier: the same identifier always yields the same key, distinct identifiers always yield distinct keys, and any party knowing only the identifier can derive the key.

Retries, continuation runs, and cleanup must all find the same directory without shared state.

This prevents:

- Retries losing prior work by landing in a new directory.
- Sanitization collisions merging two issues into one workspace.

Validation checks:

- Derive the key twice for one identifier and verify equality.
- Derive keys for identifiers that sanitize identically and verify inequality.

### Workspace Bootstrap Failure

The after_create bootstrap hook fails or exceeds the hook timeout while initializing a newly created workspace.

Occurs during **Provision Workspace**.

Retryable: yes.

Requirements:

- Remove the newly created partial workspace before failing.
- Fail the provisioning so the run fails into the retry path.
- Never delete a pre-existing (reused) workspace on bootstrap failure.

Recovery: The next attempt creates the directory fresh and bootstraps again.

Validation checks:

- Fail the bootstrap hook and verify no directory remains and the run fails.
- Time the hook out and verify identical handling.
- Verify the following attempt runs the bootstrap hook again.

### Unsafe Workspace Path

A workspace path fails containment validation: it equals the root, escapes it through symlinks, resolves outside it, or cannot be canonicalized.

Occurs during **Provision Workspace**, **Remove Workspace for Finished Issue**.

Retryable: no (indicates hostile or broken filesystem state).

Requirements:

- Refuse the create or remove operation entirely.
- Report a reason that distinguishes the containment violation class.
- Leave the filesystem untouched by the refused operation.

Recovery: An operator inspects and repairs the workspace root; the issue retries through normal scheduling afterward.

Validation checks:

- Exercise each violation class and verify refusal with a distinct error and no filesystem change.

### Non-Blocking Hook Failure

A teardown-side hook (after_run or before_remove) fails or times out. These hooks are best-effort; their failure must not change control flow.

Occurs during **Remove Workspace for Finished Issue**, **Agent Run**.

Retryable: not applicable (outcome is ignored).

Requirements:

- Log the hook failure with its output.
- Proceed with the surrounding operation (run completion or workspace removal) unchanged.

Recovery: None required; the operator reads the log if the hook mattered.

Validation checks:

- Fail and time out before_remove and verify removal still completes.
- Fail after_run and verify the run's outcome is unchanged.

## 7. Remote Execution (Optional Extension)

Running workspaces and agent sessions on remote worker hosts: host selection with per-host caps, one-host-per-run affinity, and remote failure handling that surfaces to the normal retry path.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

### Run Agents on Remote Worker Hosts (Optional Extension)

Spread agent runs across configured remote worker hosts while keeping each run pinned to one host and each host under its concurrency cap.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Participants: **Scheduler**, **Workspace Manager**, **Agent Session Protocol Client**, **Worker Host**, **Workspace**, **Agent Session**.

Trigger: Worker hosts are configured and an issue is dispatched or retried.

Sequence:

1. **Scheduler** Prefer the run's previously recorded host when it has capacity; otherwise pick the least-loaded host with capacity.
2. **Scheduler** Defer the dispatch entirely when every host is at its per-host cap.
3. **Workspace Manager** Provision the workspace on the chosen host with the same reuse, replace, and bootstrap semantics as locally.
4. **Agent Session Protocol Client** Launch the agent session on the chosen host in the workspace, with tracker secrets withheld.
5. **Workspace Manager** Run lifecycle hooks on the chosen host in the workspace.
6. **Scheduler** Surface remote failures into the normal retry path, preserving the host preference.

Postconditions:

- The whole run - workspace, hooks, session - executed on exactly one host.

- **MUST NOT** — Move a run to a different host within one run lifetime.
- **MUST** — Enforce the per-host concurrency cap during host selection.

Constrained by **One Run, One Host**, **Concurrency Never Exceeds Configured Caps**.

Failures: **Remote Execution Failure**.

Validation checks:

- Fill one host to its cap and verify new runs land on another host.
- Fill every host and verify dispatch defers with the claim intact.
- Fail the remote session launch and verify the failure surfaces to retry with the same preferred host.
- Verify remote workspaces are removed on the host when their issues become terminal.

### One Run, One Host

An agent run executes its workspace provisioning, hooks, and session on exactly one worker host; host changes happen only between runs, through the scheduler's retry path.

Workspace state lives on the host; hopping mid-run would silently abandon it and split one run's effects across machines.

This prevents:

- Split-brain workspaces for one attempt across hosts.
- Failure handling inside a run masking host problems from the scheduler.

Validation checks:

- Fail the session launch on the selected host and verify the run fails rather than moving hosts.
- Verify a retry after a host failure prefers the recorded host when it has capacity.

### Remote Execution Failure (Optional Extension)

A remote operation - workspace preparation, hook execution, or session launch - fails or times out on the selected worker host.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Occurs during **Run Agents on Remote Worker Hosts**.

Retryable: yes, via the scheduler's retry path.

Requirements:

- Surface the failure to the run instead of silently switching hosts.
- Enter the normal retry path preserving the host preference.
- Bound every remote command with a timeout.

Recovery: The retry re-selects a host through the scheduler; a healthy preferred host is reused, a dead one loses the tie to others.

Validation checks:

- Fail a remote launch and verify the run fails with the reason, without a host hop.
- Verify remote commands cannot hang past their timeout.

## 8. Observability (Optional Extension)

The operator's window: session telemetry folded into claim status, terminal and browser dashboards, a JSON status API, manual refresh, and accounting that stays truthful under noisy runtime reports.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

### Observe Orchestrator Status (Optional Extension)

Give a human operator a live, accurate view of what the orchestrator is doing and a lever to make it look at the tracker right now.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Participants: **Observability Surface**, **Scheduler**, **Claim**, **Session Event**.

Trigger: An operator views the dashboard or queries the status API, or scheduler state changes push an update.

Sequence:

1. **Scheduler** Fold incoming session events into per-claim telemetry (session id, last event, token usage, rate limits).
2. **Scheduler** Serve snapshots exposing running, retrying, and blocked claims plus cumulative totals and the poll countdown.
3. **Observability Surface** Render the snapshot to the terminal dashboard and connected viewers, coalescing updates per render interval.
4. **Observability Surface** Serve the status API - full state, per-issue lookup, and refresh trigger.
5. **Scheduler** On a refresh request, run an immediate poll cycle unless one is already due or in progress.

Postconditions:

- The operator can see every claim's phase, error, and telemetry without affecting scheduling.

- **MUST** — Report scheduler unavailability or slowness explicitly instead of failing the viewer.
- **MUST** — Expose blocked issues with their blocking reasons.

Constrained by **Monotonic Token Accounting**.

Failures: **Status Snapshot Unavailable**.

Validation checks:

- Emit a session event and verify the snapshot reflects the session id and last event.
- Verify a snapshot lists retry entries with attempt and due time, and blocked entries with reasons.
- Query an unknown issue and verify a not-found response; use a wrong method and verify method-not-allowed.
- Make the scheduler unresponsive and verify the surface reports a timeout instead of crashing.

### Observability API and Dashboards (Optional Extension)

The operator-facing HTTP surface and dashboards for orchestrator status.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Input semantics:

- A full-state query returns the current snapshot of running, retrying, and blocked claims plus totals.
- A per-issue query looks up one issue's status by its identifier.
- A refresh request asks the scheduler to poll immediately.
- A browser dashboard renders the same state live, self-contained without external assets.
- A terminal dashboard renders the same state in the service's terminal when enabled.

Output semantics:

- Refresh acknowledges acceptance and reports whether it coalesced with an in-flight cycle.
- Responses expose claim phases, errors, blocking reasons, session telemetry, and poll countdown.

Failure semantics:

- Unknown issue identifiers yield a not-found error.
- Unsupported methods on known routes yield a method-not-allowed error.
- Scheduler unavailability yields an explicit service-unavailable error.

Implementation-defined mechanisms:

- Route shapes, payload field names, and dashboard presentation.
- The bind address and port resolution beyond the operator parameters.

**Verification**

- Exercise state, per-issue, refresh, unknown-issue, and wrong-method requests and verify the stated outcomes.
- Verify the dashboard updates when scheduler state changes without a viewer-driven poll.

### Monotonic Token Accounting

Reported token totals are non-negative and never decrease from out-of-order or repeated cumulative usage reports; deltas are derived against the highest cumulative value seen per session counter.

Operators use totals for budget decisions; double counting or negative dips would make them meaningless.

This prevents:

- Double-counting usage when the runtime repeats cumulative totals.
- Negative or regressing displayed totals.

Validation checks:

- Replay cumulative usage reports out of order and verify totals only grow by true deltas.
- Send delta-only reports without cumulative totals and verify they are ignored.

### Status Snapshot Unavailable (Optional Extension)

The scheduler cannot produce a status snapshot in time, or is not running, when an observability surface asks for one.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Occurs during **Observe Orchestrator Status**.

Retryable: yes (the next render or request tries again).

Requirements:

- Report timeout or unavailability explicitly to the viewer.
- Keep the observability surface itself alive.
- Never block or crash the scheduler on behalf of a viewer.

Recovery: Snapshots resume when the scheduler catches up; no state is lost.

Validation checks:

- Make the scheduler unresponsive and verify an explicit timeout result and a live surface.
- Stop the scheduler and verify an explicit unavailable result.

## Implementation-Defined Areas

### Configuration document syntax

Any concrete syntax may carry the workflow document, provided one artifact combines structured settings and the prompt template.

Fixed semantics:

- Setting semantics follow the parameter keys of this specification.
- Environment references resolve at load time.

A conforming implementation must document:

- The concrete syntax and the mapping from parameter keys to setting names.
- The template language and its strictness behavior.

### Configuration change detection

Any mechanism may detect workflow document changes (polling a content stamp, filesystem events, explicit signal).

Fixed semantics:

- Valid edits become effective without a restart.
- Detection latency is bounded and small relative to the poll interval.

A conforming implementation must document:

- The detection mechanism and its worst-case latency.

### Retry backoff curve

The delay progression between failure retries is free (the reference doubles from a base of ten seconds).

Fixed semantics:

- Delays never decrease across consecutive failures of one issue.
- Delays never exceed the configured maximum backoff.
- The check after a normal run completion uses a much shorter delay than failure retries.

A conforming implementation must document:

- The base delay, the growth rule, and the continuation-check delay.

### Workspace naming scheme

The mapping from issue identifier to workspace directory name is free (the reference sanitizes the identifier and appends a content hash when sanitization changed it).

Fixed semantics:

- The mapping is deterministic and injective per the workspace-determinism invariant.
- Resulting names are safe for the target filesystem.

A conforming implementation must document:

- The exact derivation so external tooling can locate a workspace from an identifier.

### Process and supervision topology

Runs, timers, and the scheduler may be threads, processes, actors, or tasks in any supervision arrangement.

Fixed semantics:

- A crashed run is always observed by the scheduler and enters retry or blocked handling.
- Stopping a run releases its session and its monitoring resources.

A conforming implementation must document:

- The supervision arrangement and how run termination is detected.

### Input-required signal recognition

The concrete protocol signals recognized as "the agent needs a human" depend on the agent runtime dialect (the reference matches specific event kinds, completion outcomes, and an elicitation method name).

Fixed semantics:

- Any signal meaning the session awaits operator input or approval must route to blocked handling, never to automatic retry.

A conforming implementation must document:

- The recognized signal set for the supported runtime dialect.

### Session telemetry extraction

How token usage and rate-limit data are located inside runtime payloads is free; payload shapes vary by runtime version.

Fixed semantics:

- Extracted totals obey the monotonic token accounting invariant.

A conforming implementation must document:

- The payload shapes recognized for usage and rate-limit extraction.

### Remote transport

The remote-execution extension may use any transport that executes commands and streams a session on the worker host (the reference uses the system OpenSSH client, honoring an operator-supplied client configuration and host:port shorthand).

Fixed semantics:

- Remote commands are bounded by timeouts.
- Remote workspace and hook semantics match the local ones.

A conforming implementation must document:

- The transport, its authentication expectations, and host addressing syntax.

### Log persistence

Any durable logging arrangement may be used (the reference rotates a size-bounded on-disk log and silences the console in favor of the terminal dashboard).

Fixed semantics:

- Failures, retries, blocks, releases, and hook failures are logged with issue context.

A conforming implementation must document:

- The log destination, rotation policy, and how to redirect it.

### Dashboard presentation

The layout, styling, and level of detail of the terminal and browser dashboards are free.

Fixed semantics:

- Running, retrying, and blocked claims with their reasons remain visible.

A conforming implementation must document:

- What each dashboard column or field means.

### Adapter default state sets

Each tracker adapter may supply default active and terminal state sets appropriate to its provider.

Fixed semantics:

- Defaults apply only after an adapter is selected; operator-configured sets always win.

A conforming implementation must document:

- Each shipped adapter's default state sets.

## Reference Implementation

The Elixir application under elixir/ in the openai/symphony repository, pinned at commit 8001b52e3062495a16e520e4ceaf8f9de868c4d0 (2026-08-12). All evidence citations in spec/evidence.yaml resolve against this revision, relative to the elixir/ directory. It is one realization of this specification and adds no requirements.

The reference implementation is **not normative**; it is one realization of this specification.

## Test and Validation Matrix

Checks assembled from the verification clauses of this specification. A conforming implementation should be able to demonstrate each of them. Checks under an optional extension apply only when that extension is implemented.

### 1. Configuration and Reload

- **Workflow Document** — Load a document exercising defaults, environment references, and a template, and verify the resolved settings and rendered prompt.
- **Service Invocation** — Invoke without the acknowledgement and verify the banner and nonzero exit.
- **Service Invocation** — Invoke with an explicit workflow path and verify that document is loaded.
- **Load Configuration at Startup** — Start with a missing document and verify the service exits with a missing-file error.
- **Load Configuration at Startup** — Start with structurally invalid settings and verify startup is refused with the validation message.
- **Load Configuration at Startup** — Start without a tracker kind and verify startup is refused.
- **Load Configuration at Startup** — Start without the unattended-execution acknowledgement and verify the service prints the warning and exits nonzero.
- **Hot-Reload Configuration** — Change the poll interval in the document and verify the next cycles use the new interval without restart.
- **Hot-Reload Configuration** — Write an invalid document and verify the previous settings keep being served and the error is logged.
- **Hot-Reload Configuration** — Restore a valid document and verify it takes effect on the next read.
- **Only Validated Configuration Is Ever Effective** — Attempt startup with each class of invalid document and verify refusal with a reason.
- **Only Validated Configuration Is Ever Effective** — Break the document mid-run and verify all subsequent reads still serve the prior settings.
- **Invalid Configuration at Startup** — For each failure class (missing file, parse error, invalid field, missing tracker kind) verify refusal with a distinguishable reason.
- **Invalid Configuration on Reload** — Break the document mid-run and verify settings reads, agents, and claims are unaffected.
- **Invalid Configuration on Reload** — Fix the document and verify the new settings apply without restart.

### 2. Scheduling and Dispatch

- **Poll Cycle** — Observe that a cycle runs shortly after startup and then at the configured interval.
- **Poll Cycle** — Issue several refresh requests during one cycle and verify only one additional cycle results.
- **Poll Cycle** — Present candidates with mixed priorities and ages and verify dispatch order is priority, then oldest creation time, then identifier.
- **Dispatch Issue** — Verify a claimed, running, or blocked issue is never dispatched again while the claim holds.
- **Dispatch Issue** — Move an issue to a terminal state between listing and dispatch and verify the dispatch is skipped.
- **Dispatch Issue** — Fill the global cap and verify further candidates wait; repeat for a per-state cap.
- **Dispatch Issue** — Kill the run spawn and verify a retry is scheduled instead of losing the issue.
- **Deterministic Dispatch Order** — Offer candidates with mixed priority, age, and identifier and verify the exact order.
- **Deterministic Dispatch Order** — Verify issues without priority or creation time sort after those with them.
- **One Claim per Issue** — Drive poll cycles while an issue runs, retries, and blocks, and verify no second dispatch occurs.
- **One Claim per Issue** — Restart the orchestrator mid-run and verify redispatched work does not overlap a surviving agent.
- **Concurrency Never Exceeds Configured Caps** — Offer more eligible issues than each cap allows and verify running counts stay at the cap.
- **Concurrency Never Exceeds Configured Caps** — Lower a cap at runtime and verify subsequent admission respects the new value.
- **Fresh State Precedes Every Spawn** — Change an issue's state between listing and spawn and verify the spawn is skipped.
- **Fresh State Precedes Every Spawn** — Verify a retry whose refetch shows lost routing releases instead of spawning.
- **Tracker Fetch Failure** — Fail listing during a poll cycle and verify no claim changes and the next cycle is scheduled.
- **Tracker Fetch Failure** — Fail the reconciliation fetch and verify agents keep running.
- **Tracker Fetch Failure** — Fail a retry refetch and verify the retry reschedules with a larger delay.
- **Agent Spawn Failure** — Force spawn failure and verify a retry entry exists with the error and an increased attempt.

### 3. Claim Lifecycle, Retry, and Blocking

- **Reconcile Claims Against Tracker** — Move a running issue to a terminal state and verify the agent stops and the workspace is removed.
- **Reconcile Claims Against Tracker** — Remove a required label from a running issue and verify the agent stops and the workspace is kept.
- **Reconcile Claims Against Tracker** — Make the tracker fetch fail during reconciliation and verify all agents keep running.
- **Reconcile Claims Against Tracker** — Move a blocked issue to a terminal state and verify the block is released and the workspace removed.
- **Retry a Claimed Issue** — Fail an agent repeatedly and verify each retry waits longer, up to the configured maximum.
- **Retry a Claimed Issue** — Fire a stale (superseded) retry timer and verify it consumes nothing.
- **Retry a Claimed Issue** — Fill capacity when a retry fires and verify the retry reschedules instead of dropping the claim.
- **Retry a Claimed Issue** — Move the issue out of active states before the retry fires and verify the claim is released.
- **Detect and Recover Stalled Runs** — Let a run go idle past the stall timeout and verify it is stopped and retried with backoff.
- **Detect and Recover Stalled Runs** — Stall a run after an elicitation request and verify it is blocked instead of retried.
- **Detect and Recover Stalled Runs** — Set the stall timeout to zero and verify idle runs are left alone.
- **Block an Issue on Operator Input** — End a run with an input-required signal and verify the issue becomes blocked, not retried.
- **Block an Issue on Operator Input** — Verify a normal exit whose last signal was input-required also blocks.
- **Block an Issue on Operator Input** — Verify blocked issues are skipped by dispatch until the tracker state changes.
- **Block an Issue on Operator Input** — Change the blocked issue's tracker state and verify reconciliation releases the block.
- **Tracker State Supersedes Local Claims** — For each contradiction class (terminal, inactive, unrouted, missing) verify agent stop and claim release.
- **Tracker State Supersedes Local Claims** — Fail the fetch and verify no claim changes.
- **Failure Retries Back Off Within a Cap** — Fail a run repeatedly and verify each scheduled delay is at least the previous one until the cap.
- **Failure Retries Back Off Within a Cap** — Verify no scheduled failure-retry delay exceeds the configured maximum.
- **Blocked Issues Are Held, Not Retried** — Block an issue and run many poll cycles, verifying no dispatch or retry occurs.
- **Blocked Issues Are Held, Not Retried** — Verify stall detection routes input-waiting runs to blocked, not to backoff retry.
- **Agent Run Abnormal Exit** — Crash a run and verify claim retention, workspace retention, and a backed-off retry.
- **Agent Run Abnormal Exit** — Crash a run after an input-required event and verify blocking instead of retry.
- **Agent Run Stalled** — Stall a run and verify stop plus backed-off retry with the workspace intact.
- **Agent Run Stalled** — Stall a run on an elicitation and verify blocking.
- **Operator Input Required** — Trigger each blocker class (approval, freeform input, elicitation) and verify a blocked claim with a reason.
- **Operator Input Required** — Verify no automatic retry occurs while blocked.

### 4. Agent Session Execution

- **Agent Run** — Keep an issue active and verify the run continues with follow-up turns until the turn budget.
- **Agent Run** — Verify a run at the turn budget returns to the scheduler and a later run resumes the same workspace.
- **Agent Run** — Remove a required label mid-run and verify no further continuation turn starts.
- **Agent Run** — Verify the after_run hook and session teardown execute on both success and failure paths.
- **Agent Run** — Verify a normal completion is followed by a scheduled continuation check for the issue.
- **Handle Mid-Turn Requests** — Under the auto-approving policy, verify command and patch approval requests are granted for the session.
- **Handle Mid-Turn Requests** — Under a safer policy, verify an approval request ends the turn as approval-required.
- **Handle Mid-Turn Requests** — Send a freeform input request and verify the turn ends as input-required.
- **Handle Mid-Turn Requests** — Call an unsupported tool and verify a failure reply arrives and the turn does not stall.
- **Agent Session Protocol** — Verify session setup carries policy, sandbox, working directory, and tools, and each turn carries prompt and sandbox policy.
- **Agent Session Protocol** — Split a protocol message across stream chunks and verify correct reassembly.
- **Agent Session Protocol** — Verify malformed protocol-like lines are surfaced as malformed events without ending the turn.
- **Turn Budget Bounds Every Run** — Keep an issue active past the budget and verify the run ends and a continuation check is scheduled.
- **Turn Budget Bounds Every Run** — Verify no run ever executes more turns than the configured budget.
- **Tracker Secrets Never Reach the Agent** — Inspect the agent child environment locally and verify declared secret names are absent.
- **Tracker Secrets Never Reach the Agent** — Verify the remote launch command strips the same names before starting the agent.
- **Turn Inactivity Timeout** — Stream periodic events longer than the timeout and verify no firing.
- **Turn Inactivity Timeout** — Go silent past the timeout and verify the turn fails with a timeout error.

### 5. Tracker Adapter Boundary

- **Tracker Adapter Contract** — Drive the scheduler against the in-memory adapter and verify identical scheduling behavior to a provider adapter.
- **Tracker Adapter Contract** — Feed a malformed provider item and verify it never reaches the scheduler.
- **Execute Provider-Native Agent Tool** — Reload the configuration mid-session and verify tool execution still uses the session-start snapshot.
- **Execute Provider-Native Agent Tool** — Call a tool with invalid arguments and verify a validation failure with no provider request.
- **Execute Provider-Native Agent Tool** — Verify provider error responses are returned as structured failures preserving the body.
- **Session-Start Tool Binding Is Immutable** — Reload the configuration with different tracker settings mid-session and verify tool calls still use the snapshot.
- **Provider Tool Call Failure** — Trigger each failure class and verify a structured failure reply with the turn continuing.

### 6. Workspace Provisioning and Safety

- **Provision Workspace** — Provision the same issue twice and verify the same path with contents preserved.
- **Provision Workspace** — Provision two identifiers that sanitize identically and verify distinct paths.
- **Provision Workspace** — Point the workspace at a symlink escaping the root and verify provisioning is refused.
- **Provision Workspace** — Fail the bootstrap hook and verify the fresh directory is removed and the next attempt bootstraps again.
- **Remove Workspace for Finished Issue** — Move an issue to a terminal state and verify its workspace is removed after the before_remove hook runs.
- **Remove Workspace for Finished Issue** — Make the before_remove hook fail and verify removal still completes.
- **Remove Workspace for Finished Issue** — Record a workspace path that escapes containment and verify removal is refused.
- **Remove Workspace for Finished Issue** — Restart the service with terminal issues present and verify their workspaces are swept.
- **Workspace Lifecycle Hooks** — Verify each hook runs at its boundary with the workspace as working directory.
- **Workspace Lifecycle Hooks** — Verify blocking hooks abort their operation on failure and non-blocking hooks do not.
- **Workspace Lifecycle Hooks** — Verify a hook exceeding the timeout is terminated and handled per its blocking class.
- **Workspace Operations Stay Inside the Root** — Attempt creation and removal through symlinks escaping the root and verify refusal.
- **Workspace Operations Stay Inside the Root** — Attempt removal of the root itself and verify a distinct refusal.
- **Workspace Operations Stay Inside the Root** — Verify a recorded workspace path is re-validated before removal.
- **Deterministic Workspace Identity** — Derive the key twice for one identifier and verify equality.
- **Deterministic Workspace Identity** — Derive keys for identifiers that sanitize identically and verify inequality.
- **Workspace Bootstrap Failure** — Fail the bootstrap hook and verify no directory remains and the run fails.
- **Workspace Bootstrap Failure** — Time the hook out and verify identical handling.
- **Workspace Bootstrap Failure** — Verify the following attempt runs the bootstrap hook again.
- **Unsafe Workspace Path** — Exercise each violation class and verify refusal with a distinct error and no filesystem change.
- **Non-Blocking Hook Failure** — Fail and time out before_remove and verify removal still completes.
- **Non-Blocking Hook Failure** — Fail after_run and verify the run's outcome is unchanged.

### 7. Remote Execution (Optional Extension)

- **Run Agents on Remote Worker Hosts** — Fill one host to its cap and verify new runs land on another host.
- **Run Agents on Remote Worker Hosts** — Fill every host and verify dispatch defers with the claim intact.
- **Run Agents on Remote Worker Hosts** — Fail the remote session launch and verify the failure surfaces to retry with the same preferred host.
- **Run Agents on Remote Worker Hosts** — Verify remote workspaces are removed on the host when their issues become terminal.
- **One Run, One Host** — Fail the session launch on the selected host and verify the run fails rather than moving hosts.
- **One Run, One Host** — Verify a retry after a host failure prefers the recorded host when it has capacity.
- **Remote Execution Failure** — Fail a remote launch and verify the run fails with the reason, without a host hop.
- **Remote Execution Failure** — Verify remote commands cannot hang past their timeout.

### 8. Observability (Optional Extension)

- **Observe Orchestrator Status** — Emit a session event and verify the snapshot reflects the session id and last event.
- **Observe Orchestrator Status** — Verify a snapshot lists retry entries with attempt and due time, and blocked entries with reasons.
- **Observe Orchestrator Status** — Query an unknown issue and verify a not-found response; use a wrong method and verify method-not-allowed.
- **Observe Orchestrator Status** — Make the scheduler unresponsive and verify the surface reports a timeout instead of crashing.
- **Observability API and Dashboards** — Exercise state, per-issue, refresh, unknown-issue, and wrong-method requests and verify the stated outcomes.
- **Observability API and Dashboards** — Verify the dashboard updates when scheduler state changes without a viewer-driven poll.
- **Monotonic Token Accounting** — Replay cumulative usage reports out of order and verify totals only grow by true deltas.
- **Monotonic Token Accounting** — Send delta-only reports without cumulative totals and verify they are ignored.
- **Status Snapshot Unavailable** — Make the scheduler unresponsive and verify an explicit timeout result and a live surface.
- **Status Snapshot Unavailable** — Stop the scheduler and verify an explicit unavailable result.

## Implementation Checklist (Definition of Done)

Generated from the specification graph. Intentionally redundant with the body.

### Core

- Interactions: **Load Configuration at Startup**, **Hot-Reload Configuration**, **Poll Cycle**, **Dispatch Issue**, **Reconcile Claims Against Tracker**, **Retry a Claimed Issue**, **Block an Issue on Operator Input**, **Detect and Recover Stalled Runs**, **Agent Run**, **Handle Mid-Turn Requests**, **Provision Workspace**, **Remove Workspace for Finished Issue**.
- Lifecycle: implement every state and transition of the lifecycle.
- Interfaces: **Workflow Document**, **Service Invocation**, **Tracker Adapter Contract**, **Agent Session Protocol**, **Workspace Lifecycle Hooks**.
- Invariants: **Only Validated Configuration Is Ever Effective**, **One Claim per Issue**, **Concurrency Never Exceeds Configured Caps**, **Fresh State Precedes Every Spawn**, **Deterministic Dispatch Order**, **Tracker State Supersedes Local Claims**, **Blocked Issues Are Held, Not Retried**, **Failure Retries Back Off Within a Cap**, **Turn Budget Bounds Every Run**, **Tracker Secrets Never Reach the Agent**, **Workspace Operations Stay Inside the Root**, **Deterministic Workspace Identity**.
- Failure semantics: **Invalid Configuration at Startup**, **Invalid Configuration on Reload**, **Tracker Fetch Failure**, **Agent Spawn Failure**, **Agent Run Abnormal Exit**, **Turn Inactivity Timeout**, **Operator Input Required**, **Agent Run Stalled**, **Workspace Bootstrap Failure**, **Unsafe Workspace Path**, **Non-Blocking Hook Failure**.
- Configuration fields: `polling.interval_ms`, `tracker.kind`, `tracker.provider`, `tracker.active_states`, `tracker.terminal_states`, `tracker.required_labels`, `workspace.root`, `agent.max_concurrent_agents`, `agent.max_concurrent_agents_by_state`, `agent.max_turns`, `agent.max_retry_backoff_ms`, `codex.command`, `codex.approval_policy`, `codex.thread_sandbox`, `codex.turn_sandbox_policy`, `codex.turn_timeout_ms`, `codex.read_timeout_ms`, `codex.stall_timeout_ms`, `hooks.after_create`, `hooks.before_run`, `hooks.after_run`, `hooks.before_remove`, `hooks.timeout_ms`, `workflow.prompt_template`.
- Documentation: record the selected behavior for every implementation-defined area.

### Optional extensions (normative in full when implemented)

- **Execute Provider-Native Agent Tool**
- **Run Agents on Remote Worker Hosts**
- **Observe Orchestrator Status**
- **Observability API and Dashboards**
- **Session-Start Tool Binding Is Immutable**
- **One Run, One Host**
- **Monotonic Token Accounting**
- **Provider Tool Call Failure**
- **Remote Execution Failure**
- **Status Snapshot Unavailable**
- `worker.ssh_hosts`
- `worker.max_concurrent_agents_per_host`
- `observability.dashboard_enabled`
- `observability.refresh_ms`
- `observability.render_interval_ms`
- `server.port`
- `server.host`

## Conformance

Implement a conforming realization of this specification. Preserve normative semantics and design intent. Do not infer additional constraints from the reference implementation. Where behavior is implementation-defined, choose a reasonable mechanism that preserves all stated invariants, and document it.

A conforming implementation:

- satisfies applicable normative semantics.
- preserves conceptual relationships and responsibility boundaries.
- implements the defined interactions and lifecycle semantics.
- preserves invariants and defined failure behavior.
- exposes every field in the configuration specification with its stated semantics.
- may choose different mechanisms where implementation freedom is declared.
- documents its selected behavior for every implementation-defined area.
- does not treat reference-specific choices as additional requirements.
- may omit optional extensions entirely; every implemented extension is normative in full.
