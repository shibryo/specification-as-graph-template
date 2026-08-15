# Symphony Specification

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

- The Configuration Specification lists every operator-settable field.
- Concept field lists give the data contract.
- The Test and Validation Matrix lists the checks an implementation must pass.
- The Implementation Checklist is the definition of done.
- Examples and reference algorithms show one concrete shape. They are informative, not normative.

To implement by reconstruction, read in order:

- The Problem Statement and Design Intent say why the subject exists.
- The System Overview and Core Domain Model define the participants and who owns each decision.
- The chapters walk through behavior end to end.
- Invariants and failures state what must survive your design choices.

Both paths are projections of the same records. They cannot disagree.

## 1. Problem Statement

Teams keep their work on a tracker board. Coding agents can now carry a work item a long way without step-by-step supervision. Each agent run still needs a checkout to work in, a task description, credentials, and someone watching whether it is still making progress.

Turning a board of work into autonomous agent runs is unmanaged. Nothing decides which items deserve an agent right now. Nothing gives each run an isolated place to work. Nothing keeps a run going until the item leaves the active set. Nothing notices that a run has stopped making progress or is waiting for a human. Done by hand this does not scale past one agent. Done naively, runs collide in a shared checkout, two runs pick up the same item, operator credentials reach agent processes, and a silently stalled run holds capacity forever.

The valuable knowledge here is scheduling and containment policy, not the tracker API or the agent protocol that a given deployment happens to use. Without a specification that knowledge stays welded to one tracker, one agent runtime, and one process model. This document states what an orchestrator must decide, what it must isolate, and what it must expose, so the same subject can be rebuilt against a different board, a different agent, and a different execution topology.

## 2. Goals and Non-Goals

### 2.1 Goals

- Let operators manage work instead of supervising individual agent runs.
- Keep at most one agent working on a work item at a time.
- Give every run an isolated workspace so concurrent runs never interfere.
- Keep a run going while its work item stays active.
- Recover from failure automatically without operator action.
- Distinguish a run that failed from a run that is waiting for a human.
- Make progress, cost, and blockage of every run externally observable.
- Keep the subject portable across trackers and coding agents.

### 2.2 Non-Goals

- Define how a coding agent reasons about or edits code.
- Define the tracker's own workflow, state names, or permission model.
- Guarantee that work is completed. The subject schedules work.
- Replace human review of the agent's output.
- Prescribe a process, threading, or deployment topology.

## 3. System Overview

A Work Source holds Work Items. The scheduler polls it, picks the items that currently qualify, and takes a Claim on each one. A Claim funds one Agent Run: an isolated Workspace on a Worker Host, and an Agent Session inside it that advances the item across one or more Turns. A Workflow Definition supplies the policy, the prompt, and the operator's tunable settings for all of this. While runs proceed, the subject re-reads the Work Source and releases claims for items that stopped qualifying, retries runs that failed, and holds runs that are waiting for a human. Runtime State exposes all of that to operators.

### 3.1 Main Components

One line per component, then its ownership. Generated from the same records as the rest of this document.

- **Work Scheduler** — Own every decision about which Work Items are claimed, dispatched, retried, blocked, or released.
- **Agent Run Supervisor** — Own the execution of one claimed Work Item from workspace preparation through the last Turn of its Agent Session.
- **Workspace Manager** — Own the isolation, identity, and containment of the directory each Work Item's runs execute in.
- **Configuration Store** — Own loading, validating, and re-reading the Workflow Definition, and own which version of it is currently effective.
- **Work Source Adapter** — Own everything provider-specific.
- **Agent Session Client** — Own the conversation with the agent runtime.
- **Runtime State Publisher** — Own the externally observable projection of orchestration.

#### 3.1.1 Work Scheduler

Own every decision about which Work Items are claimed, dispatched, retried, blocked, or released. It is the single authority over claims.

Work Scheduler owns:

- Deciding which Work Items qualify for an Agent Run right now.
- Holding and releasing Claims.
- Enforcing every concurrency limit.
- Ordering candidates for dispatch.
- Scheduling retries and their delays.
- Deciding that a run has stalled.
- Deciding that an item is blocked on operator input.
- Reconciling live Claims against the Work Source.

Work Scheduler does not own:

- Executing the agent or talking its protocol.
- Creating or removing workspace content.
- Provider-specific query, identity, or capability details.
- Rendering the operator-facing view of runtime state.

Requirements:

- Exactly one scheduler authority MUST own the claim set.
- The scheduler MUST NOT dispatch a Work Item it already claims.
- The scheduler MUST re-read a Work Item before dispatching it.
- The scheduler MUST release a Claim when its item stops qualifying.
- The scheduler MUST NOT retry an item that is waiting for operator input.

#### 3.1.2 Agent Run Supervisor

Own the execution of one claimed Work Item from workspace preparation through the last Turn of its Agent Session.

Agent Run Supervisor owns:

- Requesting the Workspace for the run.
- Running the configured lifecycle hooks around the run.
- Starting and ending the Agent Session.
- Rendering the prompt for each Turn.
- Deciding whether another Turn is warranted.
- Reporting run progress to the scheduler.

Agent Run Supervisor does not own:

- Claim decisions or concurrency limits.
- Choosing which Work Item to run.
- Choosing the execution location for its own retry.

Requirements:

- A supervisor MUST run exactly one Work Item at a time.
- A supervisor MUST end its Agent Session when its run ends.
- A supervisor MUST report a failed run to the scheduler rather than retry it.
- A supervisor MUST stop starting Turns once the item leaves the active set.

#### 3.1.3 Workspace Manager

Own the isolation, identity, and containment of the directory each Work Item's runs execute in.

Workspace Manager owns:

- Deriving the deterministic workspace identity of a Work Item.
- Verifying that a workspace path resolves inside the configured root.
- Creating, reusing, and removing workspaces.
- Executing the configured workspace hooks.

Workspace Manager does not own:

- Any decision about which items are worked on.
- The content the agent produces inside a workspace.

Requirements:

- A workspace path that resolves outside the configured root MUST be refused.
- The configured workspace root itself MUST NOT be used as a workspace.
- The same Work Item identifier MUST always yield the same workspace identity.
- Distinct identifiers MUST NOT collapse onto one workspace identity.

#### 3.1.4 Configuration Store

Own loading, validating, and re-reading the Workflow Definition, and own which version of it is currently effective.

Configuration Store owns:

- Reading the Workflow Definition.
- Validating it, including work-source-specific requirements.
- Deciding when a changed definition becomes effective.
- Retaining the last version that validated.

Configuration Store does not own:

- Interpreting settings as scheduling decisions.
- Deciding what to do when a setting changes mid-run.

Requirements:

- An invalid Workflow Definition MUST NOT become effective.
- The subject MUST NOT start when no valid definition is available.
- A failed re-read MUST leave the last valid definition effective.
- A reload failure MUST be reported to the operator.

#### 3.1.5 Work Source Adapter

Own everything provider-specific: how work is read, how it is normalized into Work Items, and which native capabilities the agent is offered.

Work Source Adapter owns:

- Reading Work Items by state and by identity within the configured scope.
- Normalizing provider records into Work Items.
- Rejecting provider records that cannot yield a valid Work Item.
- Declaring which credential-bearing environment names it uses.
- Validating its own configuration.
- Advertising and executing provider-native agent tools.

Work Source Adapter does not own:

- Claim, concurrency, retry, or ordering policy.
- Writing back to the Work Source on the scheduler's behalf.

Requirements:

- The adapter MUST expose reads by state and reads by item identity.
- The adapter MUST drop provider records that lack a required Work Item field.
- The adapter MUST report a read failure rather than return partial results.
- Provider readiness signals MUST NOT bypass scheduler policy.

#### 3.1.6 Agent Session Client

Own the conversation with the agent runtime: starting a session in a workspace, running turns, applying the configured approval policy, and reporting updates.

Agent Session Client owns:

- Launching the agent runtime in the workspace.
- Removing credential-bearing variables from the agent's environment.
- Applying the configured approval and sandbox policy.
- Translating agent messages into timestamped updates.
- Detecting that the agent is asking for operator input.
- Executing tool calls the agent makes and returning results.

Agent Session Client does not own:

- Retry, backoff, or claim decisions.
- Deciding whether another Turn should follow.

Requirements:

- The session MUST start with the run's Workspace as its working directory.
- The client MUST NOT pass configured credential variables to the agent process.
- A request for operator input MUST end the turn as a distinguishable outcome.
- The client MUST report an unanswered agent request rather than guess an answer.

#### 3.1.7 Runtime State Publisher

Own the externally observable projection of orchestration: what is running, retrying, or blocked, and what each has consumed.

Runtime State Publisher owns:

- Projecting scheduler state into Runtime State.
- Accounting the agent resource usage reported for each run.
- Serving the operator's request to poll sooner.

Runtime State Publisher does not own:

- Any scheduling decision.
- Being the durable record of what happened.

Requirements:

- Runtime State MUST distinguish running, retrying, and blocked items.
- A blocked or retrying item MUST be reported with the reason.
- Publishing MUST NOT block or slow the scheduler.
- Usage totals MUST NOT decrease within a run.

### 3.2 External Dependencies

A conforming deployment requires this environment.

- A work source that can be read by state and by item identity.
- A coding agent runtime that accepts a prompt and reports progress.
- Credentials for the work source, held by the operator, not by the agent.
- Storage for isolated per-item workspaces.

## 4. Core Domain Model

### 4.1 Entities

One line per entity, then its full definition. Generated from the same records as the rest of this document.

- **Work Item** — A unit of work on the board that the subject may hand to an agent.
- **Work Source** — The system of record for Work Items.
- **Workflow Definition** — The operator's declaration of how work is orchestrated.
- **Claim** — The subject's exclusive hold on a Work Item.
- **Agent Run** — One supervised attempt to advance a claimed Work Item.
- **Workspace** — An isolated working directory that belongs to one Work Item.
- **Agent Session** — A live conversation with the coding agent, bound to one Workspace and one Work Item.
- **Turn** — One prompt-to-completion exchange inside an Agent Session.
- **Worker Host** — An execution location where a Workspace lives and an Agent Session runs.
- **Runtime State** — The externally observable picture of orchestration right now.
- **Provider-Native Agent Tool** (Optional Extension) — A capability the Work Source adapter offers to the agent so the agent can act on the board without holding its own credential.

#### 4.1.1 Work Item

A unit of work on the board that the subject may hand to an agent. It is the unit of claiming, of workspace identity, and of reporting.

Fields:

- `id` (string) — REQUIRED. Stable dispatch identity within the configured work source scope.
- `identifier` (string) — REQUIRED. Human-readable key. Unique in scope. Derives the workspace identity.
- `title` (string) — REQUIRED. Short description of the work. Supplied to the agent.
- `description` (string) — Long-form statement of the work. Supplied to the agent.
- `state` (string) — REQUIRED. Current board state. Compared against configured active and terminal states.
- `labels` (list of string) — Routing labels. Compared case-insensitively after trimming.
- `priority` (integer) — Dispatch precedence. Lower values are dispatched first.
- `created_at` (timestamp) — Creation time. Breaks ties between items of equal priority. Oldest first.
- `blocked_by` (list of reference) — Other items that must reach a terminal state first.
- `assignee` (string) — Routing target. Used when the deployment routes work to a specific worker.
- `dispatchable` (boolean) — REQUIRED. Adapter's verdict on provider-level readiness. Never the whole decision.
- `url` (string) — Location of the item for an operator. Informational only.

- A Work Item missing any required field MUST NOT be dispatched.
- The identifier MUST be stable for the life of the item.
- Item state is read from the Work Source. The subject never writes it.

#### 4.1.2 Work Source

The system of record for Work Items. It is read by state and by item identity. It is never written by the scheduler.

- The Work Source is authoritative about whether an item still qualifies.
- Reads are scoped to one configured collection of work.
- A read failure is a transient condition, not a signal that work ended.

#### 4.1.3 Workflow Definition

The operator's declaration of how work is orchestrated. It carries the configuration and the prompt template given to the agent.

- It is the single operator-facing contract for runtime behavior.
- It is re-read while the subject runs.
- A version that fails validation never becomes effective.

#### 4.1.4 Claim

The subject's exclusive hold on a Work Item. A Claim exists from the moment an item is selected until the item stops qualifying for orchestration.

- At most one Claim exists per Work Item.
- A Claim survives run failure, retry waiting, and blocking.
- Releasing a Claim makes the item selectable again on a later cycle.

#### 4.1.5 Agent Run

One supervised attempt to advance a claimed Work Item. It owns a Workspace and an Agent Session for its lifetime.

Fields:

- `attempt` (integer) — Position in the retry sequence for this Claim. Absent on a first attempt.
- `worker_host` (reference) — Execution location chosen for this run. Fixed for the run's lifetime.

- A run ends when the agent stops, the item stops qualifying, or the run is preempted.
- A run's outcome selects the next lifecycle state of the Claim.

#### 4.1.6 Workspace

An isolated working directory that belongs to one Work Item. The agent's working directory for the whole run.

- Its identity is derived deterministically from the Work Item identifier.
- It MUST resolve inside the configured workspace root.
- It MUST NOT be the workspace root itself.
- Existing content is reused across runs for the same item unless removed.

#### 4.1.7 Agent Session

A live conversation with the coding agent, bound to one Workspace and one Work Item. It carries the agent's policy settings and its stream of updates.

- A session belongs to exactly one Agent Run.
- A session ends when its run ends.
- Session updates are the only evidence the subject has of agent progress.

#### 4.1.8 Turn

One prompt-to-completion exchange inside an Agent Session. A run may need more than one turn to carry an item to a non-active state.

- The first turn carries the rendered work prompt.
- A later turn tells the agent to resume rather than restart.
- The number of turns in one run is bounded by configuration.

#### 4.1.9 Worker Host

An execution location where a Workspace lives and an Agent Session runs. A deployment always has at least the local location.

- A run stays on the host chosen for it.
- Workspaces on different hosts are independent.

#### 4.1.10 Runtime State

The externally observable picture of orchestration right now: which items are running, retrying, or blocked, what each has consumed, and when the next poll is due.

- It is derived from the scheduler's live state.
- It reports the reason an item is retrying or blocked.
- It is read-only except for an explicit request to poll sooner.

#### 4.1.11 Provider-Native Agent Tool (Optional Extension)

A capability the Work Source adapter offers to the agent so the agent can act on the board without holding its own credential.

- The tool is executed by the subject, not by the agent process.
- The tool is bound to the settings in effect when the session started.
- Tool reach is limited by the configured credential, not by scheduler scope.

### 4.2 Relationships

**Work Source** supplies **Work Item**. The Work Source is read by state and by identity. Everything the scheduler knows about an item comes from that read.

**Claim** holds **Work Item**. A Claim marks an item as owned by this subject. No second run may start for a claimed item.

**Agent Run** advances **Work Item**. A run exists to move the item out of the active set. The item's state after the run decides whether another run follows.

**Agent Run** occupies **Workspace**. A run works inside exactly one Workspace, which persists between runs for the same item unless the item is released.

**Agent Run** drives **Agent Session**. A run starts one session, runs turns in it, and ends the session when the run ends.

**Agent Session** is composed of **Turn**. A session carries one or more turns. Later turns continue the same context rather than starting over.

**Workspace** resides on **Worker Host**. A Workspace exists at one execution location. Containment rules apply at that location.

**Workflow Definition** configures **Agent Run**. The definition supplies the prompt, the agent policy, the hooks, and the limits that shape every run.

**Workflow Definition** selects **Work Source**. The definition names which work source is read and which states, labels, and scope qualify an item.

**Runtime State** reports **Agent Run**. Runtime State projects each run's location, session, progress, cost, and last known event.

**Agent Session** may invoke **Provider-Native Agent Tool**. A session may call a provider-native tool. The subject executes the call and returns the result to the agent.

## 5. Design Intent

### 5.1 The work source is authoritative

The tracker decides whether a work item still deserves an agent. The subject re-reads the item before acting instead of trusting its own memory.

Board state changes while a run is in flight. Humans close items, reassign them, and strip labels. An orchestrator that trusts its own cache keeps burning agent time on work nobody wants any more.

Implications:

- Dispatch decisions are revalidated against a fresh read immediately before dispatch.
- Claimed items are re-read every cycle and released when they stop qualifying.
- Local runtime state is a cache of tracker state, never a substitute for it.

Notes:

- The subject reads the work source more often than a cache-first design would.

### 5.2 One claim, one workspace, one run

A work item under orchestration is owned by exactly one claim. That claim owns one workspace and at most one active agent run.

Two agents on one item duplicate work and fight over the same branch. Two runs in one directory corrupt each other's checkout.

Implications:

- Claim, workspace identity, and run are all keyed by the same work item.
- A second dispatch of a claimed item is refused rather than queued.

### 5.3 Blocked is not failed

A run that stops because it needs operator input is held and surfaced. It is not retried and not released.

Retrying a run that is waiting for a human wastes capacity and hides the request. The operator never learns that a decision is pending.

Implications:

- Requests for input, approval, or elicitation move the item to a blocked state.
- A blocked item keeps its claim so nothing else picks the item up.
- Blocked items are visible in the runtime state with the reason they blocked.

### 5.4 Fail into a retry, not into a stop

Every failure that is not a request for human input results in a scheduled retry with growing delay, until the work item stops qualifying.

Trackers, networks, and agent runtimes fail transiently. An orchestrator that stops on first failure needs an operator to restart it.

Implications:

- Failure paths schedule a retry rather than releasing the claim.
- Repeated failure backs off instead of hammering the failing dependency.
- The claim is released only when the work item itself stops qualifying.

### 5.5 Contain the agent

The agent runs inside a workspace that belongs to its work item and receives no credential that the orchestrator uses to read the board.

An autonomous agent with a writable path outside its workspace can damage the source repository. An agent holding the orchestrator's tracker token can act on the board outside the orchestrator's policy.

Implications:

- The workspace path is verified to resolve inside the configured root.
- Credential-bearing environment variables are removed before the agent starts.

Notes:

- Agents that legitimately need tracker access must be granted it explicitly.

### 5.6 Providers are adapters, not policy

Scheduling policy is expressed over a normalized work item. Provider-specific reads, identifiers, and capabilities stay behind an adapter boundary.

Scheduling rules that are written against one tracker's fields cannot be reused, and every new provider reopens the scheduler.

Implications:

- The scheduler depends only on normalized read operations.
- Provider-native capabilities are offered to the agent, not to the scheduler.

## 6. Configuration Specification

Each field below must exist and be operator-settable. Keys are reference names used by this document, not required spellings. Concrete names, formats, and defaults are implementation-defined unless fixed elsewhere. The stated semantics are normative. One entry per field; sub-bullets give its semantics, reload behavior, and the behaviors it governs.

### 6.1 Core Fields

- `work-source.selection` — Which Work Source is read and which collection of work is in scope.
  - Exactly one work source is effective at a time.
  - Its scope bounds every read the scheduler makes.
  - The subject does not start when the selection is absent or unsupported.
  - Provider-specific settings belong to the selected source, not to the scheduler.
  - Reload: A change takes effect from the next poll cycle. Runs already started are unaffected until they are reconciled.
  - Used by **Poll and Dispatch**, **Reconcile Claimed Work Items**, **Work Source Adapter Interface**.
- `work-source.credential` — The secret the subject presents when reading the Work Source and executing provider-native tools.
  - The credential may be supplied indirectly through the environment.
  - Every environment name that carries it is declared so it can be withheld from the agent.
  - An absent credential is a configuration failure, not a read failure.
  - Reload: A change takes effect on the next read. Sessions keep the credential bound when they started.
  - Used by **Poll and Dispatch**, **Run the Agent Session**, **The Agent Never Receives the Subject's Credentials**.
- `scheduling.active-states` — Which board states make a Work Item eligible for an Agent Run.
  - Only items in an active state are selected for dispatch.
  - A claimed item that leaves the active states is released.
  - A run whose item leaves the active states stops starting further turns.
  - Matching ignores case and surrounding whitespace.
  - Reload: A change takes effect from the next poll cycle and applies to existing claims at the next reconciliation.
  - Used by **Poll and Dispatch**, **Reconcile Claimed Work Items**, **Continue or Conclude the Run**.
- `scheduling.terminal-states` — Which board states mean the work is over and its workspace may be reclaimed.
  - An item in a terminal state is never dispatched.
  - A claimed item reaching a terminal state has its run stopped and workspace removed.
  - Terminal is stronger than non-active: only terminal removes the workspace.
  - Items already terminal at startup have their workspaces reclaimed.
  - Reload: A change takes effect from the next poll cycle.
  - Used by **Reconcile Claimed Work Items**, **Release the Claim and Clean Up**, **Poll and Dispatch**.
- `scheduling.required-labels` — Which labels a Work Item must carry before this deployment will work on it.
  - An item must carry every configured label to be dispatched.
  - An item that loses a required label has its run stopped and its claim released.
  - Matching ignores case and surrounding whitespace.
  - An empty list imposes no label requirement.
  - A blank configured label matches no item.
  - Reload: A change takes effect from the next poll cycle and applies to existing claims at the next reconciliation.
  - Used by **Poll and Dispatch**, **Reconcile Claimed Work Items**, **A Claim Lives Only While Its Item Qualifies**.
- `scheduling.poll-interval` — How long the scheduler waits between poll cycles.
  - It bounds how quickly new work is noticed.
  - It bounds how quickly a claim reacts to a board change.
  - An operator may request an earlier cycle without changing the interval.
  - The value must be positive.
  - Reload: A change takes effect when the next cycle is scheduled.
  - Used by **Poll and Dispatch**, **Reconcile Claimed Work Items**.
- `capacity.max-concurrent-runs` — How many Agent Runs may be active at once across the whole deployment.
  - Dispatch stops when the limit is reached and resumes when a run ends.
  - Items deferred by the limit stay eligible for a later cycle.
  - A retry is subject to the same limit as a first dispatch.
  - The value must be positive.
  - Reload: A change takes effect from the next dispatch decision. Runs already active are not stopped to satisfy a lowered limit.
  - Used by **Poll and Dispatch**, **Concurrency Limits Are Never Exceeded**.
- `capacity.max-concurrent-runs-by-state` — How many Agent Runs may be active at once for Work Items in a given board state.
  - A state without an entry falls back to the global limit.
  - Both the per-state limit and the global limit must permit a dispatch.
  - State names are matched case-insensitively after trimming.
  - Each configured limit must be a positive integer.
  - Reload: A change takes effect from the next dispatch decision.
  - Used by **Poll and Dispatch**, **Concurrency Limits Are Never Exceeded**.
- `capacity.max-turns-per-run` — How many Turns one Agent Run may start while its Work Item stays active.
  - The run ends when the budget is exhausted, even if the item is still active.
  - Ending on an exhausted budget returns control to the scheduler with the claim held.
  - The value must be positive.
  - Reload: A change takes effect for runs that start afterwards.
  - Used by **Continue or Conclude the Run**, **One Run's Turns Are Bounded**.
- `recovery.max-retry-delay` — The ceiling on the growing delay between attempts for one Claim.
  - The delay grows with consecutive failures and never exceeds this ceiling.
  - The ceiling bounds how long recovery can take after a transient failure.
  - The value must be positive.
  - Reload: A change takes effect when the next retry is scheduled.
  - Used by **Retry After Failure**, **Retry Delay Grows and Is Capped**.
- `recovery.stall-timeout` — How long a run may go without observable agent activity before it is restarted.
  - Silence is measured from the last observed agent activity.
  - A run with no activity yet is measured from when it started.
  - A run awaiting operator input is blocked rather than restarted.
  - A value of zero disables stall detection entirely.
  - Reload: A change takes effect at the next poll cycle.
  - Used by **Detect and Recover a Stalled Run**, **Run Stalled**.
- `workspace.root` — The directory beneath which every Workspace must live.
  - Every workspace path is verified to resolve inside this root.
  - The root itself is never used as a workspace and never removed.
  - A relative value resolves against the Workflow Definition's own location.
  - The value may be supplied indirectly through the environment.
  - Reload: A change takes effect for workspaces prepared afterwards. Existing workspaces are not moved.
  - Used by **Prepare the Isolated Workspace**, **Workspaces Stay Inside the Configured Root**.
- `workspace.hooks` — Operator-supplied commands run at workspace creation, before a run, after a run, and before removal.
  - Each hook runs with the Workspace as its working directory.
  - The creation hook runs only on the run that created the directory.
  - Creation and pre-run hook failures fail the run.
  - Post-run and removal hook failures are advisory.
  - Every hook is bounded by the hook timeout.
  - Reload: A change takes effect at the next hook invocation.
  - Used by **Prepare the Isolated Workspace**, **Release the Claim and Clean Up**, **Workspace Hook Interface**.
- `workspace.hook-timeout` — How long any single hook may run before it is abandoned.
  - A hook exceeding the timeout is abandoned and treated as failed.
  - The timeout applies to every hook, local or remote.
  - The value must be positive.
  - Reload: A change takes effect at the next hook invocation.
  - Used by **Workspace Hook Interface**, **Workspace Hook Failed**.
- `agent.command` — Which agent runtime is launched for an Agent Session and how it is invoked.
  - The runtime is launched with the run's Workspace as its working directory.
  - The value must be present and non-blank.
  - The launched runtime must speak the session protocol the subject expects.
  - Reload: A change takes effect for sessions started afterwards.
  - Used by **Run the Agent Session**, **Agent Session Interface**.
- `agent.prompt-template` — What the agent is told about the Work Item at the start of a run.
  - The template may reference Work Item fields and the attempt number.
  - An empty template selects a built-in default.
  - A template that cannot be parsed fails the run.
  - A continuation turn's instruction is not drawn from this template.
  - Reload: A change takes effect for prompts rendered afterwards.
  - Used by **Work Prompt Interface**, **Run the Agent Session**.
- `agent.approval-policy` — Which agent requests the subject may answer on the operator's behalf.
  - A restrictive policy causes an unanswerable request to block the item.
  - A permissive policy lets the subject answer approvals and continue the turn.
  - The default is restrictive, so unattended approval is opt-in.
  - Reload: A change takes effect for sessions started afterwards.
  - Used by **Run the Agent Session**, **Hold a Work Item Blocked on Operator Input**.
- `agent.sandbox-policy` — What the agent may read, write, and reach while a Turn runs.
  - The default confines writes to the run's Workspace.
  - Network access is off by default and enabled deliberately.
  - An explicitly configured policy is passed to the runtime unchanged.
  - A policy that permits writes outside the Workspace violates containment.
  - Reload: A change takes effect for sessions started afterwards.
  - Used by **Run the Agent Session**, **Workspaces Stay Inside the Configured Root**.
- `agent.turn-silence-timeout` — How long one Turn may go without any agent message before it is abandoned.
  - Each agent message resets the interval.
  - The timeout is not a cap on the total length of a Turn.
  - The value must be positive.
  - Reload: A change takes effect for turns started afterwards.
  - Used by **Agent Session Interface**, **Turn Failed**.
- `agent.startup-response-timeout` — How long the subject waits for the agent runtime to answer a startup exchange.
  - Exceeding it fails the session start rather than the whole subject.
  - It is distinct from the timeout that governs turn silence.
  - The value must be positive.
  - Reload: A change takes effect for sessions started afterwards.
  - Used by **Run the Agent Session**, **Agent Session Could Not Start**.
- `observability.exposure` — Whether and how the Runtime State is presented to operators.
  - Runtime State is always derivable, whatever presentation is configured.
  - Presentation cadence is operator-settable.
  - Presentation must not delay scheduling.
  - Reload: A change takes effect at the next presentation cycle.
  - Used by **Publish Runtime State**, **Runtime State Interface**.

### 6.2 Extension Fields

These fields exist only when their extension is implemented.

- `workers.hosts` — Which remote execution locations may carry Agent Runs.
  - An empty list means every run executes locally.
  - A configured list makes every run execute on one of those locations.
  - A run stays on the location chosen for it.
  - The workspace root is interpreted on the chosen location.
  - Reload: A change takes effect for runs dispatched afterwards. Running runs stay where they are.
  - Used by **Run on a Remote Worker Host**, **A Run Stays on One Execution Location**.
- `workers.max-runs-per-host` — How many Agent Runs one execution location may carry at once.
  - Dispatch is deferred when every configured location is at its share.
  - The global limit still applies on top of the per-location share.
  - An absent value imposes no per-location share.
  - A configured value must be positive.
  - Reload: A change takes effect from the next dispatch decision.
  - Used by **Run on a Remote Worker Host**, **Concurrency Limits Are Never Exceeded**.
- `observability.service-endpoint` — Whether the Runtime State is served over a network, and where it listens.
  - The service does not run unless an endpoint is configured.
  - The bind address defaults to a loopback address.
  - Enabling the service changes no scheduling behavior.
  - Reload: A change takes effect when the service is next started.
  - Used by **Observability Service Interface**, **Publish Runtime State**.

## 7. Work Intake and Dispatch

How the board becomes running agents. This chapter defines what makes a Work Item a candidate, in what order candidates are taken, what stops a dispatch, and the read boundary every one of those decisions goes through.

### 7.1 Poll and Dispatch

Turn the current contents of the Work Source into new Agent Runs, without exceeding any limit and without ever starting a second run for one item.

Participants: **Work Scheduler**, **Work Source Adapter**, **Work Source**, **Work Item**, **Claim**, **Agent Run**.

Trigger: The poll interval elapses, or an operator requests an immediate cycle.

Preconditions:

- A valid Workflow Definition is effective.
- Claims and blocked items have been reconciled against the Work Source.

Sequence:

1. **Work Scheduler** Read the Work Items currently in the configured active states.
2. **Work Source Adapter** Return normalized Work Items, dropping records that cannot be normalized.
3. **Work Scheduler** Discard items that are already claimed, running, or blocked.
4. **Work Scheduler** Discard items that lack a required label or are not routed to this deployment.
5. **Work Scheduler** Order the remaining candidates deterministically.
6. **Work Scheduler** For each candidate in order, stop when any applicable concurrency limit is reached.
7. **Work Scheduler** Re-read the candidate immediately and abandon it if it no longer qualifies.
8. **Work Scheduler** Take a Claim on the candidate and start an Agent Run for it.
9. **Work Scheduler** Schedule the next poll and publish the updated state.

Postconditions:

- Every started run corresponds to exactly one new Claim.
- No concurrency limit is exceeded.
- The next poll is scheduled.

Requirements:

- **MUST** — Select only Work Items that are in a configured active state.
- **MUST NOT** — Select a Work Item that is in a configured terminal state.
- **MUST** — Require every configured label before an item may be dispatched.
- **MUST** — Re-read a candidate immediately before dispatching it.
- **MUST NOT** — Start a run for a Work Item that is already claimed.
- **SHOULD** — Treat a provider readiness signal as necessary, never as sufficient.
- **MUST** — Continue polling after a read failure rather than stopping.

Constrained by **One Claim Per Work Item**, **Dispatch Order Is Deterministic**, **Concurrency Limits Are Never Exceeded**, **Dispatch Decisions Are Revalidated**.

Failures: **Work Source Unavailable**.

Reference algorithm (non-normative):

```text
candidates = work_source.read(active_states)
candidates = [i for i in candidates if valid(i) and routed(i) and has_required_labels(i)]
candidates = [i for i in candidates if not claimed(i) and not running(i) and not blocked(i)]
sort candidates by (priority, created_at, identifier)
for item in candidates:
    if not global_slot_free() or not state_slot_free(item) or not location_slot_free():
        break
    fresh = work_source.read_by_id(item.id)
    if fresh is missing or not qualifies(fresh):
        continue
    claim(fresh); start_run(fresh)
```

Validation checks:

- Offer more qualifying items than the configured limit and verify no run exceeds the limit.
- Present a claimed item again in the same cycle and verify no second run starts.
- Move an item to a terminal state between read and dispatch, then verify no run starts.
- Remove a required label between read and dispatch, then verify no run starts.
- Present items with mixed priority and creation time, then verify dispatch order.

### 7.2 Work Source Adapter Interface

The only boundary through which the scheduler learns about work. It hides every provider-specific query, identifier, and capability.

Input semantics:

- A read by state names returns every item currently in any of those states.
- A read by item identities returns the current form of those items.
- An empty state list or empty identity list is a no-op that returns nothing.
- Reads are scoped to the one collection of work named in the configuration.

Output semantics:

- Every returned record is a fully normalized Work Item.
- A record missing a required Work Item field is dropped, never returned partially formed.
- An item absent from a read by identity means it is no longer visible in scope.
- The dispatchable flag carries the provider's readiness verdict only.
- Labels are compared case-insensitively after trimming.
- Unparsable priorities and timestamps become absent rather than wrong values.

Failure semantics:

- A read failure is reported as a failure, never as an empty result.
- Configuration, authentication, transport, and response failures are distinguishable.
- A rate-limit response is distinguishable from other response failures.
- A pagination failure is distinguishable from a payload failure.

Implementation-defined mechanisms:

- The provider and its query language.
- How scope is expressed for that provider.
- Which native identifier becomes the Work Item identity.
- Whether reads are paginated and how.

Example: Normalized Work Item returned by a read:

```yaml
id: "9f1c1e40-1b0a-4b0f-9b1e-2f2a6d0a1c33"
identifier: "SYM-142"
title: "Recover the scheduler contract"
state: "In Progress"
labels: ["agent-ready"]
priority: 2
created_at: "2026-08-01T09:14:00Z"
blocked_by: []
dispatchable: true
url: "https://tracker.example/issue/SYM-142"
```

Validation checks:

- Read with an empty state list and verify no provider request is made.
- Return a record without an identifier and verify it is dropped, not dispatched.
- Fail a read and verify a failure, not an empty list, reaches the scheduler.
- Rename a state's letter case and verify matching still succeeds.

### 7.3 One Claim Per Work Item

At most one Claim exists for a Work Item at any time, and a claimed item has at most one active Agent Run.

Two agents on one item duplicate effort and contend for the same branch.

This prevents:

- Two concurrent runs advancing the same Work Item.
- A retry starting while the earlier run is still active.
- A restarted deployment redispatching work it is already running.

Validation checks:

- Offer a claimed item as a candidate again and verify no second run starts.
- Trigger a retry while the run is active and verify the run is not duplicated.
- Verify a blocked item is never selected while its claim is held.

### 7.4 Dispatch Order Is Deterministic

Candidates are dispatched in a total order derived from priority, then age, then identifier, so equal capacity always yields the same selection.

Operators must be able to predict which work an agent picks up next.

This prevents:

- Starvation of an older item by a newer one of equal priority.
- Selection that varies between runs for the same board state.

Validation checks:

- Offer items of differing priority and verify higher priority dispatches first.
- Offer items of equal priority and verify the older one dispatches first.
- Offer items with equal priority and age and verify identifier order decides.
- Offer an item with no priority and verify it sorts after every prioritized item.

### 7.5 Concurrency Limits Are Never Exceeded

The number of active Agent Runs never exceeds the configured limit overall, the configured limit for the item's board state, or the configured limit per execution location.

Capacity limits exist because agents consume real machines, quota, and money.

This prevents:

- Exhausting a worker host by admitting more runs than it can carry.
- A single crowded board state consuming all global capacity.
- A retry bypassing the limit that blocked the original dispatch.

Validation checks:

- Fill global capacity and verify further qualifying items are not dispatched.
- Fill one state's capacity and verify items in other states still dispatch.
- Fill one host's share and verify dispatch moves to another host or defers.
- Reach capacity at retry time and verify a further retry is scheduled instead.

### 7.6 Dispatch Decisions Are Revalidated

A Work Item is re-read from the Work Source immediately before an Agent Run starts, and the run does not start if it no longer qualifies.

Board state changes between the poll and the dispatch, and an agent run is expensive to start and to undo.

This prevents:

- Starting a run for an item a human just closed.
- Starting a run for an item whose required label was just removed.
- Starting a run for an item that was just reassigned elsewhere.

Validation checks:

- Move an item to a terminal state between poll and dispatch, then verify no run starts.
- Remove a required label between poll and dispatch, then verify no run starts.
- Hide the item between poll and dispatch, then verify the claim is released.

### 7.7 Work Source Unavailable

A read of the Work Source did not produce an answer. The subject learns nothing new about which items qualify.

Occurs during **Poll and Dispatch**, **Reconcile Claimed Work Items**, **Retry After Failure**, **Publish Runtime State**.

Retryable: True.

Requirements:

- Treat the read as unknown, never as an empty board.
- Keep every existing Claim, run, and blocked record.
- Dispatch nothing new in this cycle.
- Report the failure with enough detail to identify the cause.
- Continue polling on the normal schedule.

Recovery: The next successful read reconciles all claims and resumes dispatch. A read failure during a retry schedules a further retry with a longer delay.

Validation checks:

- Fail the candidate read and verify no run is started or stopped.
- Fail the reconciling read and verify every claim survives.
- Fail the read during a retry and verify a further retry is scheduled.

## 8. Isolated Execution Environment

Where a run happens and what keeps it contained. This chapter defines workspace identity, the containment rule the whole subject depends on, and the operator's hooks into the workspace lifecycle.

### 8.1 Prepare the Isolated Workspace

Give an Agent Run a working directory that belongs to its Work Item, is proven to be inside the configured root, and is bootstrapped on first creation.

Participants: **Agent Run Supervisor**, **Workspace Manager**, **Work Item**, **Workspace**, **Worker Host**, **Agent Run**.

Trigger: An Agent Run is starting for a claimed Work Item.

Preconditions:

- The Work Item has a non-empty identifier.
- A workspace root is configured for the execution location.

Sequence:

1. **Agent Run Supervisor** Request the Workspace for this Work Item at the run's execution location.
2. **Workspace Manager** Derive the workspace identity deterministically from the item identifier.
3. **Workspace Manager** Resolve the workspace path and verify it lies inside the configured root.
4. **Workspace Manager** Reuse the directory when it already exists, otherwise create it.
5. **Workspace Manager** Run the creation hook only when the directory was newly created.
6. **Workspace Manager** Discard a newly created workspace whose creation hook failed.
7. **Agent Run Supervisor** Run the pre-run hook and abandon the run if it fails.
8. **Agent Run Supervisor** Report the resolved workspace location to the scheduler.

Postconditions:

- The run has a workspace inside the configured root, or the run has failed.
- A newly created workspace that failed bootstrap no longer exists.
- Existing work from an earlier run for the same item is preserved.

Requirements:

- **MUST** — Verify containment after resolving links, not before.
- **MUST NOT** — Use the configured workspace root itself as a workspace.
- **MUST** — Run the creation hook only on the run that created the directory.
- **MUST** — Treat a creation-hook failure as a failure of the whole run.
- **MUST** — Preserve existing workspace content across runs for the same item.
- **MUST** — Bound every hook by the configured hook timeout.
- **SHOULD** — Truncate hook output before logging it.

Constrained by **Workspaces Stay Inside the Configured Root**, **Workspace Identity Is Deterministic and Collision-Free**.

Failures: **Workspace Preparation Failed**, **Workspace Hook Failed**.

Validation checks:

- Point the workspace path at a link that escapes the root and verify the run is refused.
- Request the workspace for the same identifier twice and verify one identity results.
- Request workspaces for two identifiers that sanitize alike and verify they stay distinct.
- Fail the creation hook and verify the new workspace is removed and the run fails.
- Leave a file in an existing workspace, run again, and verify the file survives.
- Hang a hook past the configured timeout and verify the hook is abandoned.

### 8.2 Workspace Hook Interface

The operator's opportunity to bootstrap, prepare, tidy, and drain a Workspace at fixed points in a run's life.

Input semantics:

- Every hook runs with the Workspace as its working directory.
- The creation hook runs only on the run that created the directory.
- The pre-run hook runs before each run's Agent Session starts.
- The post-run hook runs after each run's Agent Session ends.
- The removal hook runs before workspace content is deleted.
- Every hook is bounded by the configured hook timeout.

Output semantics:

- A hook that ends successfully allows the run to proceed.
- A successful removal hook allows deletion to proceed.

Failure semantics:

- A failing creation hook fails the run and discards the new workspace.
- A failing pre-run hook fails the run and keeps the workspace.
- A failing post-run hook does not change the run's outcome.
- A failing or timed-out removal hook does not prevent removal.
- A hook that exceeds the timeout is abandoned and treated as failed.

Implementation-defined mechanisms:

- The interpreter used to run hook commands.
- Which environment the hook inherits.
- How hook output is captured and truncated.

Example: Bootstrapping a fresh workspace:

```yaml
hooks:
  after_create: |
    git clone --depth 1 "$SOURCE_REPO_URL" .
  before_remove: |
    ./scripts/drain-workspace.sh
  timeout_ms: 60000
```

Validation checks:

- Fail the creation hook and verify the new workspace is discarded and the run fails.
- Fail the post-run hook and verify the run's outcome is unchanged.
- Fail the removal hook and verify removal still completes.
- Exceed the hook timeout and verify the hook is abandoned.

### 8.3 Workspaces Stay Inside the Configured Root

Every path the subject creates, runs an agent in, or deletes resolves, after links are followed, to a location strictly inside the configured workspace root.

An autonomous agent with a writable path outside its workspace can damage the operator's own source tree, and a delete outside the root is unrecoverable.

This prevents:

- Running an agent turn inside the operator's source repository.
- Escaping the workspace root through a symbolic link.
- Deleting the workspace root itself.
- Deleting a path that a recorded value pointed outside the root.

Validation checks:

- Link a workspace path outside the root and verify creation is refused.
- Link a workspace path outside the root and verify removal is refused.
- Ask for the workspace root itself and verify it is refused with a distinct reason.
- Verify the agent's working directory is the workspace and not its parent.

### 8.4 Workspace Identity Is Deterministic and Collision-Free

One Work Item identifier always maps to the same workspace identity, and two different identifiers never map to the same one.

A run must find the work its predecessor left behind, and unrelated items must never share a checkout.

This prevents:

- A retry starting from an empty workspace and losing prior work.
- Two items whose identifiers differ only in unusable characters colliding.
- Cleanup deleting the workspace of a different item.

Validation checks:

- Derive the identity twice for one identifier and verify the results match.
- Derive identities for two identifiers that sanitize alike and verify they differ.
- Leave a file in a workspace, retry the item, and verify the file is still present.

### 8.5 Workspace Preparation Failed

The run's Workspace could not be established: the path failed containment, the location was unusable, or the bootstrap did not complete.

Occurs during **Prepare the Isolated Workspace**.

Retryable: True.

Requirements:

- Do not start an Agent Session.
- Remove a workspace that this run had just created.
- Leave a pre-existing workspace untouched.
- Report the failure to the scheduler as a failed run.

Recovery: The scheduler schedules a retry with backoff. A later attempt re-runs the creation hook because the directory no longer exists.

Validation checks:

- Fail the creation hook and verify the new workspace is gone and no session starts.
- Fail the creation hook on an existing workspace and verify its content survives.
- Verify a later attempt re-runs the creation hook after a discarded workspace.

### 8.6 Workspace Hook Failed

An operator-supplied hook ended unsuccessfully or exceeded the hook timeout.

Occurs during **Prepare the Isolated Workspace**, **Release the Claim and Clean Up**.

Retryable: implementation-defined.

Requirements:

- Treat a creation-hook or pre-run-hook failure as a failure of the run.
- Treat a post-run-hook failure as advisory and leave the run's outcome unchanged.
- Treat a removal-hook failure as advisory and continue removing the workspace.
- Abandon a hook that exceeds the configured timeout.
- Report which hook failed and why.

Recovery: Run-failing hooks recover through the normal retry path. Advisory hooks do not recover; their failure is reported and the surrounding operation proceeds.

Validation checks:

- Fail the pre-run hook and verify the run fails before a session starts.
- Fail the post-run hook and verify the run's outcome is unchanged.
- Fail the removal hook and verify the workspace is still removed.
- Hang a hook past the timeout and verify it is abandoned and reported.

## 9. Agent Session and Turn Continuation

What the agent is told, what it is allowed to do, and how the subject decides whether one more Turn is worth starting. This chapter also carries the rule that keeps the subject's credentials out of the agent.

### 9.1 Run the Agent Session

Start a contained agent session inside the run's Workspace, deliver the work as a prompt, and observe the agent until the turn ends.

Participants: **Agent Run Supervisor**, **Agent Session Client**, **Agent Run**, **Agent Session**, **Workspace**, **Work Item**.

Trigger: The run's Workspace is ready and the pre-run hook has succeeded.

Preconditions:

- The Workspace path has been verified as contained.
- An agent runtime command is configured.

Sequence:

1. **Agent Run Supervisor** Ask the session client to start a session in the run's Workspace.
2. **Agent Session Client** Remove every configured credential-bearing variable from the agent environment.
3. **Agent Session Client** Start the agent runtime with the Workspace as its working directory.
4. **Agent Session Client** Apply the configured approval policy and sandbox policy to the session.
5. **Agent Session Client** Offer the configured provider-native tools to the session.
6. **Agent Run Supervisor** Render the prompt for this Turn and start the Turn.
7. **Agent Session Client** Forward each agent update to the scheduler with a timestamp.
8. **Agent Session Client** Answer approval requests when policy allows, otherwise end the turn as input-required.
9. **Agent Session Client** Execute agent tool calls and return their results to the agent.
10. **Agent Run Supervisor** End the session when the run ends, whatever the outcome.

Postconditions:

- The agent process is no longer running when the run ends.
- Every observed agent update has reached the scheduler.
- The turn ended as completed, failed, or input-required.

Requirements:

- **MUST** — Use the run's Workspace as the agent working directory.
- **MUST NOT** — Expose configured credential variables to the agent process.
- **MUST** — Confine the agent's write access to its own Workspace by default.
- **MUST** — End the agent session when the run ends.
- **MUST** — Distinguish a turn that needs operator input from a turn that failed.
- **MUST** — Abandon a turn that produces no agent activity within the silence timeout.
- **SHOULD** — Report agent activity as it happens rather than only at turn end.

Constrained by **Workspaces Stay Inside the Configured Root**, **The Agent Never Receives the Subject's Credentials**.

Failures: **Agent Session Could Not Start**, **Turn Failed**.

Validation checks:

- Start a session and verify the agent's working directory is the run workspace.
- Configure a credential variable and verify it is absent from the agent process.
- Point the session at a path outside the workspace root and verify it is refused.
- Stop producing agent updates and verify the turn ends at the silence timeout.
- Send an approval request under a restrictive policy and verify the turn ends as input-required.

### 9.2 Continue or Conclude the Run

Decide, after each completed Turn, whether the Work Item still warrants more agent effort inside the same run.

Participants: **Agent Run Supervisor**, **Work Scheduler**, **Turn**, **Agent Session**, **Work Item**.

Trigger: A Turn completes normally.

Preconditions:

- The Agent Session is still open.
- The Work Item's identity is known.

Sequence:

1. **Agent Run Supervisor** Re-read the Work Item from the Work Source.
2. **Agent Run Supervisor** Conclude the run when the item is gone, non-active, or no longer routed.
3. **Agent Run Supervisor** Conclude the run when the configured turn budget for this run is exhausted.
4. **Agent Run Supervisor** Otherwise start another Turn that instructs the agent to resume, not restart.
5. **Work Scheduler** Schedule a short follow-up check when the run concludes with the item still active.

Postconditions:

- The run either continues with a further Turn or ends.
- A run that ends with the item still active leaves the Claim in place.

Requirements:

- **MUST** — Re-read the Work Item before starting another Turn.
- **MUST NOT** — Start another Turn once the configured turn budget is exhausted.
- **MUST** — Return control to the scheduler when the turn budget is exhausted.
- **MUST** — Tell a continuation Turn to resume from the existing workspace state.
- **MUST NOT** — Repeat the original task instructions in a continuation Turn.

Constrained by **One Run's Turns Are Bounded**.

Failures: **Turn Failed**.

Validation checks:

- Keep an item active across turns and verify a further turn starts.
- Exhaust the configured turn budget and verify control returns to the scheduler.
- Remove a required label between turns and verify the run concludes.
- Move the item out of the active states between turns and verify the run concludes.

### 9.3 Agent Session Interface

The boundary between the subject and the coding agent runtime: how a session begins, how a Turn is run, and what the subject learns while it runs.

Input semantics:

- A session is started with a working directory, an approval policy, and a sandbox policy.
- A session is offered the provider-native tools available for it.
- A Turn is started with the rendered prompt and the item's identifying title.
- The subject answers approval requests only as the configured policy allows.

Output semantics:

- Each agent message becomes a timestamped update carrying its event kind.
- Updates identify the session so concurrent runs stay distinguishable.
- Updates may carry cumulative resource usage for the session.
- A Turn ends as completed, failed, cancelled, or awaiting operator input.

Failure semantics:

- A silent Turn is abandoned once the configured silence timeout elapses.
- The silence timeout is reset by each update, so it does not cap total Turn length.
- A protocol response that does not arrive within the read timeout fails the session start.
- An agent process that exits ends the Turn as a failure.
- Unparsable agent output is reported but does not end the Turn.

Implementation-defined mechanisms:

- The agent runtime and its wire protocol.
- How the agent process is launched and stopped.
- The names and shapes of approval and sandbox policies.
- Which policy value means "answer approvals automatically".

Validation checks:

- Start a session and verify the declared working directory is used.
- Withhold updates past the silence timeout and verify the turn is abandoned.
- Emit updates steadily past the silence timeout and verify the turn continues.
- Exit the agent process mid-turn and verify the turn fails.

### 9.4 Work Prompt Interface

How a Work Item becomes the instruction the agent acts on, and how a continuation Turn differs from the first one.

Input semantics:

- The template may reference any field of the Work Item.
- The template may reference the current attempt number.
- An unknown reference is an error, not an empty substitution.
- Structured field values are rendered in a stable textual form.

Output semantics:

- The first Turn of a run receives the rendered template.
- A continuation Turn receives instructions to resume, not to restart.
- A continuation Turn states its position within the run's turn budget.

Failure semantics:

- A template that cannot be parsed fails the run with the offending template reported.
- An unavailable Workflow Definition is reported separately from a parse failure.

Implementation-defined mechanisms:

- The templating syntax.
- The exact wording of the default and continuation prompts.
- The textual form chosen for structured values.

Example: A template referencing the work item and the attempt:

```text
You are working on {{ issue.identifier }}.

Title: {{ issue.title }}
Current state: {{ issue.state }}

{% if attempt %}
This is follow-up attempt #{{ attempt }}. Resume from the workspace as it stands.
{% endif %}
```

Validation checks:

- Reference an unknown field and verify rendering fails rather than substituting nothing.
- Render with an absent description and verify the default template still produces a prompt.
- Start a continuation turn and verify the prompt tells the agent to resume.

### 9.5 The Agent Never Receives the Subject's Credentials

Every environment variable the configuration declares as credential-bearing for the Work Source is absent from the agent process.

The subject's credential is the operator's authority over the board. An agent holding it can act outside the orchestrator's policy and outside its audit.

This prevents:

- The agent reading or writing the board outside the offered tools.
- A credential leaking into agent-visible logs or a committed file.
- A workspace-readable configuration file becoming a credential store.

Validation checks:

- Declare a credential variable and verify it is unset in the agent process.
- Verify the agent can still act on the board through an offered tool.
- Verify the subject itself still reads the board successfully.

### 9.6 One Run's Turns Are Bounded

A single Agent Run starts no more than the configured number of Turns, even while its Work Item stays active.

An unbounded turn loop lets one run hold capacity forever and hides the fact that the agent is not converging.

This prevents:

- One item consuming a slot indefinitely.
- An agent looping on the same work without the scheduler ever regaining control.

Validation checks:

- Keep an item active and verify no more than the configured number of turns run.
- Exhaust the budget and verify control returns to the scheduler with the claim held.

### 9.7 Agent Session Could Not Start

The agent runtime could not be launched, did not answer the startup exchange in time, or rejected the session's policies.

Occurs during **Run the Agent Session**.

Retryable: True.

Requirements:

- Stop any agent process that was started.
- Leave the workspace in place.
- Report the failure to the scheduler as a failed run.
- Distinguish a missing runtime from a runtime that answered with an error.

Recovery: The scheduler schedules a retry with backoff. Repeated failures back off toward the configured ceiling so a misconfigured runtime does not spin.

Validation checks:

- Point the agent command at a missing executable and verify the run fails and retries.
- Withhold the startup response past the read timeout and verify the session start fails.
- Verify no orphaned agent process survives a failed session start.

### 9.8 Turn Failed

A Turn ended without completing: the agent reported failure, the turn was cancelled, the agent process exited, or the turn went silent past its timeout.

Occurs during **Run the Agent Session**, **Continue or Conclude the Run**.

Retryable: True.

Requirements:

- End the Agent Session.
- Leave the workspace in place so a later attempt can resume.
- Report the failure to the scheduler as a failed run.
- Do not confuse a failed turn with a turn awaiting operator input.

Recovery: The scheduler schedules a retry with backoff. The later attempt resumes from the workspace as the failed turn left it.

Validation checks:

- Fail a turn and verify the session ends and the workspace survives.
- Exit the agent process mid-turn and verify the run fails and retries.
- Withhold updates past the silence timeout and verify the turn is abandoned.
- Verify an input-required turn is not reported as a plain failure.

## 10. Claim Lifecycle, Interruption, and Recovery

What happens between runs. This chapter defines the states a Claim moves through, how the subject re-aligns with the board, how failure becomes another attempt, how a silent run is reclaimed, and how a run waiting on a human is held rather than retried.

### 10.1 Lifecycle and State

The lifecycle begins in **Eligible**.

- **Eligible** — The Work Item qualifies for orchestration but the subject holds no Claim on it.
- **Running** — The subject holds a Claim and an Agent Run is active for the item.
- **Retry Waiting** — The subject holds a Claim, no run is active, and a further attempt is scheduled.
- **Blocked** — The subject holds a Claim, no run is active, and the item awaits an operator decision.
- **Released** — The subject holds no Claim. The item may become Eligible again as a fresh Claim. This is terminal.

#### 10.1.1 Transitions

- **Eligible** → **Running** when the item is selected, revalidated, and an agent run starts for it.
- **Running** → **Retry Waiting** when the run ends without carrying the item out of the active states.
- **Running** → **Blocked** when the run ends or stalls while the agent awaits an operator decision.
- **Running** → **Released** when the item reaches a terminal state, leaves the active states, stops being routed here, or stops being visible.
- **Retry Waiting** → **Running** when the delay expires, the item still qualifies, and capacity is available.
- **Retry Waiting** → **Retry Waiting** when the delay expires but capacity is unavailable or the revalidating read fails.
- **Retry Waiting** → **Released** when the item stops qualifying while the delay is pending.
- **Blocked** → **Released** when the item stops qualifying, or the subject restarts and forgets the block.

#### 10.1.2 Lifecycle Constraints

- A Work Item MUST NOT be in more than one of these states at a time.
- Running, Retry Waiting, and Blocked all hold the Claim.
- Only the Released state permits a new Claim on the same item.
- Every transition out of Running MUST first stop the active run.
- A Blocked item MUST NOT transition directly to Retry Waiting.
- Losing the Claim record MUST make the item Eligible, never leave it orphaned.

### 10.2 Reconcile Claimed Work Items

Re-align every Claim with what the Work Source now says, so nothing keeps working on an item that no longer qualifies.

Participants: **Work Scheduler**, **Work Source Adapter**, **Work Source**, **Work Item**, **Claim**, **Agent Run**.

Trigger: A poll cycle begins.

Preconditions:

- At least one Work Item is claimed, running, or blocked.

Sequence:

1. **Work Scheduler** Read the current form of every claimed, running, and blocked Work Item.
2. **Work Source Adapter** Return the requested items, omitting any that are no longer visible.
3. **Work Scheduler** Stop the run and clean up the workspace for an item in a terminal state.
4. **Work Scheduler** Stop the run and keep the workspace for an item that is no longer routed here.
5. **Work Scheduler** Stop the run and keep the workspace for an item that left the active states.
6. **Work Scheduler** Stop the run and keep the workspace for an item that is no longer visible.
7. **Work Scheduler** Refresh the recorded form of items that still qualify.
8. **Work Scheduler** Keep every Claim unchanged when the read itself failed.

Postconditions:

- Every remaining Claim corresponds to an item that still qualifies.
- Workspaces of items that reached a terminal state have been removed.
- Workspaces of items that merely left the active set are preserved.

Requirements:

- **MUST** — Release the Claim of an item that stopped qualifying.
- **MUST** — Stop the active run before releasing its Claim.
- **MUST** — Remove the workspace when the item reached a terminal state.
- **MUST NOT** — Remove the workspace when the item merely left the active states.
- **MUST** — Apply the same reconciliation rules to blocked items.
- **MUST NOT** — Release any Claim when the reconciling read failed.

Constrained by **A Claim Lives Only While Its Item Qualifies**.

Failures: **Work Source Unavailable**, **Work Item No Longer Visible**.

Validation checks:

- Move a running item to a terminal state and verify the run stops and the workspace is removed.
- Move a running item to a non-active state and verify the run stops and the workspace survives.
- Remove a required label from a running item and verify the run stops.
- Remove a required label from a blocked item and verify its claim is released.
- Hide a running item from the work source and verify the run stops and the workspace survives.
- Fail the reconciling read and verify every claim and run is retained.

### 10.3 Retry After Failure

Turn any non-blocking failure into another attempt at a later time, with a delay that grows while failures repeat.

Participants: **Work Scheduler**, **Claim**, **Work Item**, **Agent Run**.

Trigger: An Agent Run ends without carrying its Work Item out of the active set.

Preconditions:

- The Work Item is still claimed.
- The run did not end because operator input is required.

Sequence:

1. **Work Scheduler** Record the reason the run ended and the attempt number it reached.
2. **Work Scheduler** Choose a short delay when the run completed normally and the item stays active.
3. **Work Scheduler** Choose a growing, capped delay when the run ended abnormally.
4. **Work Scheduler** Replace any pending retry for the item so only the newest one survives.
5. **Work Scheduler** Wait for the delay while keeping the Claim.
6. **Work Scheduler** Re-read the Work Item when the delay expires.
7. **Work Scheduler** Release the Claim if the item no longer qualifies.
8. **Work Scheduler** Start a new Agent Run if capacity allows, otherwise schedule a further retry.

Postconditions:

- The item is running again, waiting for a further retry, or released.
- At most one pending retry exists for the item.

Requirements:

- **MUST** — Keep the Claim while a retry is pending.
- **MUST** — Grow the delay as consecutive failures accumulate.
- **MUST** — Cap the delay at the configured ceiling.
- **MUST** — Re-read the Work Item before retrying it.
- **MUST** — Ignore a retry signal that a newer retry has superseded.
- **SHOULD** — Retry a normal completion sooner than a failure.
- **MUST** — Report the failure reason with the pending retry.

Constrained by **Retry Delay Grows and Is Capped**.

Failures: **Work Source Unavailable**.

Validation checks:

- Fail a run repeatedly and verify each delay is at least as long as the previous one.
- Fail a run many times and verify the delay never exceeds the configured ceiling.
- Move the item to a terminal state during the delay and verify the claim is released.
- Deliver a superseded retry signal and verify it does not start a run.
- Fill all capacity at retry time and verify a further retry is scheduled.

### 10.4 Detect and Recover a Stalled Run

Reclaim capacity from a run whose agent has stopped reporting activity, without mistaking a run waiting for a human for a stalled one.

Participants: **Work Scheduler**, **Agent Run**, **Work Item**, **Agent Session**.

Trigger: A poll cycle begins and at least one run is active.

Preconditions:

- A stall timeout is configured and enabled.
- The run has a known time of last activity.

Sequence:

1. **Work Scheduler** Compute how long each run has gone without agent activity.
2. **Work Scheduler** Leave runs within the stall timeout untouched.
3. **Work Scheduler** Block the item instead of restarting when the run is waiting for operator input.
4. **Work Scheduler** Stop the run and schedule a retry with backoff otherwise.

Postconditions:

- No run remains silent for longer than the configured timeout.
- A stalled run has become either a pending retry or a blocked item.

Requirements:

- **MUST** — Measure silence from the last observed agent activity.
- **MUST** — Fall back to the run's start time when no activity was ever observed.
- **MUST NOT** — Restart a run that is waiting for operator input.
- **MUST** — Allow the operator to disable stall detection.
- **MUST** — Count a restarted stalled run as a further retry attempt.

Constrained by **Retry Delay Grows and Is Capped**.

Failures: **Run Stalled**, **Operator Input Required**.

Validation checks:

- Silence a run past the configured timeout and verify it is stopped and retried.
- Silence a run that already requested operator input and verify it becomes blocked.
- Disable stall detection and verify a silent run is left alone.

### 10.5 Hold a Work Item Blocked on Operator Input

Keep a Work Item and its Claim held, and make the pending human decision visible, instead of retrying work that cannot proceed.

Participants: **Work Scheduler**, **Runtime State Publisher**, **Work Item**, **Claim**, **Runtime State**.

Trigger: A run ends or stalls while the agent is awaiting operator input, approval, or elicitation.

Preconditions:

- The Work Item is claimed.

Sequence:

1. **Work Scheduler** Stop the agent run without scheduling a retry.
2. **Work Scheduler** Retain the Claim so nothing else picks the item up.
3. **Work Scheduler** Record what the agent asked for and when it blocked.
4. **Runtime State Publisher** Expose the item as blocked with that reason.
5. **Work Scheduler** Release the block only when the item stops qualifying.

Postconditions:

- The item holds a Claim, has no active run, and has no pending retry.
- The reason for blocking is externally visible.

Requirements:

- **MUST NOT** — Schedule a retry for a blocked Work Item.
- **MUST** — Retain the Claim for a blocked Work Item.
- **MUST** — Expose the reason the item blocked.
- **MUST** — Reconcile blocked items against the Work Source every cycle.
- **MUST** — Release a blocked item that reaches a terminal state and remove its workspace.
- **SHOULD** — Distinguish an approval request from a request for information.

Constrained by **A Blocked Item Is Held, Not Retried**.

Failures: **Operator Input Required**.

Validation checks:

- Make the agent request input and verify the item becomes blocked with no pending retry.
- Verify a blocked item is not selected for dispatch while it stays blocked.
- Move a blocked item to a terminal state and verify its claim and workspace are released.

### 10.6 Release the Claim and Clean Up

End the subject's involvement with a Work Item and reclaim the resources its Claim was holding.

Participants: **Work Scheduler**, **Workspace Manager**, **Claim**, **Work Item**, **Workspace**.

Trigger: A claimed Work Item reaches a terminal state, leaves the active states, or stops being visible.

Preconditions:

- The Work Item is claimed.

Sequence:

1. **Work Scheduler** Stop any active run for the item.
2. **Work Scheduler** Cancel any pending retry for the item.
3. **Work Scheduler** Clear any blocked record for the item.
4. **Workspace Manager** Remove the item's workspace when the item reached a terminal state.
5. **Workspace Manager** Run the removal hook before deleting a workspace, ignoring its failure.
6. **Work Scheduler** Drop the Claim.

Postconditions:

- The item holds no Claim, run, retry, or blocked record.
- A terminal item's workspace no longer exists.

Requirements:

- **MUST** — Remove a workspace only through a path proven inside the configured root.
- **MUST** — Run the removal hook before deleting workspace content.
- **MUST** — Continue removal when the removal hook fails or times out.
- **MUST** — Reclaim workspaces of items already terminal when the subject starts.
- **MUST** — Prefer the workspace recorded for the run over a re-derived path.

Constrained by **Workspaces Stay Inside the Configured Root**, **A Claim Lives Only While Its Item Qualifies**.

Failures: **Workspace Hook Failed**.

Validation checks:

- Close an item with a running agent and verify the run stops and the workspace is removed.
- Fail the removal hook and verify the workspace is still removed.
- Point a recorded workspace path at an escaping link and verify removal is refused.
- Start the subject with terminal items present and verify their workspaces are reclaimed.

### 10.7 A Claim Lives Only While Its Item Qualifies

A Claim is released as soon as its Work Item reaches a terminal state, leaves the active states, stops being routed to this deployment, or stops being visible.

Board state is authoritative. A claim that outlives eligibility is capacity spent on work nobody wants.

This prevents:

- An agent continuing to work on a closed item.
- Capacity held by items that were reassigned away.
- Workspaces accumulating for work that ended.

Validation checks:

- Close a running item and verify the run stops and the claim is released.
- Move a running item out of the active states and verify the claim is released.
- Remove a required label from a running item and verify the claim is released.
- Fail the reconciling read and verify no claim is released.

### 10.8 Retry Delay Grows and Is Capped

Consecutive failures for one Claim produce non-decreasing delays that never exceed the configured ceiling, and at most one retry is pending per item.

Immediate retries turn a failing dependency into a denial of service, and an uncapped curve turns a transient failure into an outage.

This prevents:

- Hammering an unavailable work source or worker host.
- A retry delay growing without bound and stalling recovery.
- Stale retry signals starting duplicate runs.

Validation checks:

- Fail a run repeatedly and verify each delay is at least the previous one.
- Fail a run many times and verify no delay exceeds the configured ceiling.
- Schedule a new retry over a pending one and verify only the newer one fires.
- Deliver a superseded retry signal and verify it starts no run.

### 10.9 A Blocked Item Is Held, Not Retried

A Work Item whose agent is awaiting an operator decision holds its Claim, has no active run, and has no pending retry until it stops qualifying.

Retrying work that cannot proceed without a human wastes capacity and hides the pending decision from the operator.

This prevents:

- A retry loop on an approval the agent cannot grant itself.
- Another run picking up an item that is already waiting on a human.
- The pending request being invisible to the operator.

Validation checks:

- Make the agent request input and verify the item blocks with no pending retry.
- Verify the blocked item is not dispatched while it stays blocked.
- Verify the reason for blocking is present in the runtime state.

### 10.10 Run Stalled

An Agent Run has produced no observable agent activity for longer than the configured stall timeout, without reporting either success or failure.

Occurs during **Detect and Recover a Stalled Run**.

Retryable: True.

Requirements:

- Stop the run rather than let it hold capacity indefinitely.
- Count the restart as a further retry attempt so backoff applies.
- Leave the workspace in place.
- Report how long the run was silent.
- Do not restart a run that is silent because it awaits operator input.

Recovery: The item returns to the retry path and a later attempt resumes in the same workspace. Operators may disable stall detection entirely.

Validation checks:

- Silence a run past the timeout and verify it is stopped and retried with backoff.
- Verify the stalled run's workspace survives the restart.
- Disable stall detection and verify a silent run is not restarted.

### 10.11 Operator Input Required

The agent cannot proceed without a human decision: an approval, an answer, or a choice the configured policy does not permit the subject to make.

Occurs during **Hold a Work Item Blocked on Operator Input**, **Detect and Recover a Stalled Run**.

Retryable: False.

Requirements:

- End the run without scheduling a retry.
- Retain the Claim so nothing else picks the item up.
- Record what was asked and when the item blocked.
- Expose the item as blocked with that reason.
- Keep reconciling the item against the Work Source.

Recovery: The block ends only when the item stops qualifying, or when the operator acts on the board so that the item is released and later selected afresh.

Validation checks:

- Request an approval the policy forbids and verify the item blocks, not retries.
- Verify a blocked item keeps its claim and stays out of dispatch.
- Close a blocked item and verify its claim is released and its workspace removed.

### 10.12 Work Item No Longer Visible

A claimed Work Item is absent from a read that requested it by identity. It was deleted, moved out of scope, or hidden from the configured credential.

Occurs during **Reconcile Claimed Work Items**, **Poll and Dispatch**.

Retryable: False.

Requirements:

- Stop any active run for the item.
- Release the Claim.
- Preserve the workspace, because disappearance is not completion.
- Distinguish an absent item from a failed read.

Recovery: If the item becomes visible again it is selected afresh, and its preserved workspace lets the new run resume from the earlier state.

Validation checks:

- Hide a running item and verify the run stops and the claim is released.
- Hide a running item and verify its workspace is preserved.
- Fail the read entirely and verify the claim is retained instead of released.

## 11. Configuration and Reload

The one document an operator edits, and the guarantee that editing it badly cannot take a working deployment down.

### 11.1 Load and Reload the Workflow Definition

Make the operator's declaration effective, keep it current while running, and never let an invalid edit degrade a healthy deployment.

Participants: **Configuration Store**, **Work Scheduler**, **Workflow Definition**, **Work Source**.

Trigger: The subject starts, or the Workflow Definition changes while it runs.

Preconditions:

- A Workflow Definition location is known.

Sequence:

1. **Configuration Store** Read the Workflow Definition and separate its settings from its prompt.
2. **Configuration Store** Apply defaults for every omitted setting.
3. **Configuration Store** Validate the settings, including the selected work source's own requirements.
4. **Configuration Store** Refuse to start when the first load is invalid.
5. **Configuration Store** Make a valid definition effective and remember it as last known good.
6. **Configuration Store** Keep the last known good definition and report the error when a reload is invalid.
7. **Work Scheduler** Apply the effective settings from the start of the next decision.

Postconditions:

- Exactly one valid Workflow Definition is effective.
- An invalid edit has changed no behavior.

Requirements:

- **MUST** — Refuse to start when no valid Workflow Definition is available.
- **MUST NOT** — Make an invalid Workflow Definition effective.
- **MUST** — Keep running on the last valid definition after a failed reload.
- **MUST** — Report every reload failure to the operator.
- **MUST** — Detect changes without requiring a restart.
- **MUST** — Resolve credential references from the environment rather than storing secrets inline.
- **SHOULD** — Apply a changed limit from the next decision, not retroactively.

Constrained by **Only a Valid Configuration Is Ever Effective**.

Failures: **Invalid Workflow Definition**.

Validation checks:

- Start with an invalid definition and verify the subject does not start.
- Make a valid definition invalid while running and verify prior settings stay effective.
- Make a valid definition invalid while running and verify the failure is reported.
- Change a limit while running and verify later decisions use the new value.

### 11.2 Workflow Definition Interface

The single document an operator edits to declare which work is orchestrated, how runs behave, and what the agent is told.

Input semantics:

- The document carries a settings section and a prompt template section.
- Every omitted setting takes its default.
- A credential-valued setting may name an environment variable instead of a literal.
- A path-valued setting may name an environment variable instead of a literal.
- A relative workspace root resolves against the document's own location.
- An empty prompt template selects a built-in default template.

Output semantics:

- A document that validates becomes the effective configuration.
- The effective configuration is observable through the behavior it governs.
- The document is re-read while the subject runs.

Failure semantics:

- An unreadable or invalid document at startup prevents the subject from starting.
- An invalid document at reload leaves the previous configuration effective.
- A reload failure is reported and repeated until the document is fixed.

Implementation-defined mechanisms:

- The document's file name, format, and location.
- The spelling of each setting.
- The templating language of the prompt.
- How the document's changes are detected.

Example: A minimal definition, with the settings section first:

```yaml
tracker:
  kind: <work-source>
  active_states: ["Todo", "In Progress"]
  terminal_states: ["Done", "Cancelled"]
  required_labels: ["agent-ready"]
polling:
  interval_ms: 30000
workspace:
  root: ~/work/agent-workspaces
hooks:
  after_create: |
    git clone --depth 1 "$SOURCE_REPO_URL" .
agent:
  max_concurrent_agents: 10
  max_turns: 20
# prompt template follows the settings section
```

Validation checks:

- Omit every optional setting and verify documented defaults apply.
- Reference a credential through an environment variable and verify it resolves.
- Give a relative workspace root and verify it resolves against the document's location.
- Leave the prompt template empty and verify the default template is used.

### 11.3 Only a Valid Configuration Is Ever Effective

The effective configuration is always a version that passed validation. An invalid version neither starts the subject nor replaces a running one.

Configuration is edited while agents are mid-run. A typo must not take down a working deployment or silently change scheduling policy.

This prevents:

- A half-parsed document producing undefined scheduling behavior.
- A running deployment losing its settings because of an editing mistake.
- A subject starting with settings it could not validate.

Validation checks:

- Start with an invalid document and verify the subject does not start.
- Invalidate the document while running and verify prior settings stay effective.
- Invalidate the document while running and verify the failure is reported.
- Repair the document and verify the new settings become effective without restart.

### 11.4 Invalid Workflow Definition

The Workflow Definition is missing, unparsable, or fails validation for the selected Work Source.

Occurs during **Load and Reload the Workflow Definition**.

Retryable: True.

Requirements:

- Refuse to start when this is the first load.
- Keep the last valid configuration effective when the subject is already running.
- Report the failure with the reason and the document's location.
- Keep re-reading so a repaired document takes effect without a restart.
- Never apply a partially valid configuration.

Recovery: A repaired document validates on a later read and becomes effective. Nothing that ran under the previous configuration is disturbed.

Validation checks:

- Start with a missing document and verify the subject does not start.
- Invalidate the document while running and verify behavior is unchanged.
- Repair the document and verify the new settings become effective without restart.

## 12. Observability

What an operator can see and how they can ask the subject to look again. This chapter also states how resource usage is accounted so that cost figures stay trustworthy.

### 12.1 Publish Runtime State

Give operators a current, self-explaining picture of what the subject is doing and what each run has consumed.

Participants: **Runtime State Publisher**, **Work Scheduler**, **Runtime State**, **Agent Run**, **Work Item**.

Trigger: Orchestration state changes, or a reader requests the current state.

Preconditions:

- The scheduler is reachable.

Sequence:

1. **Work Scheduler** Expose a consistent snapshot of running, retrying, and blocked items.
2. **Runtime State Publisher** Fold each reported usage figure into the run's totals without double counting.
3. **Runtime State Publisher** Project the snapshot with the reason for every retry and every block.
4. **Runtime State Publisher** Report when the next poll is due and whether a poll is in progress.
5. **Runtime State Publisher** Report that state is unavailable rather than block when the scheduler does not answer.
6. **Work Scheduler** Honor an operator request to poll sooner, coalescing repeats.

Postconditions:

- A reader can tell running, retrying, and blocked items apart.
- A reader can see why each retrying or blocked item is in that state.

Requirements:

- **MUST** — Distinguish running, retrying, and blocked items.
- **MUST** — Report the reason for every retry and every block.
- **MUST NOT** — Delay or block scheduling in order to publish state.
- **MUST** — Report unavailability instead of waiting indefinitely for a snapshot.
- **MUST** — Coalesce repeated immediate-poll requests into one cycle.
- **SHOULD** — Report the workspace and execution location of every run.

Constrained by **Reported Usage Never Decreases Within a Run**.

Failures: **Work Source Unavailable**.

Validation checks:

- Run, retry, and block one item each, then verify all three are distinguishable.
- Stop answering snapshot requests and verify the reader is told state is unavailable.
- Request an immediate poll twice in quick succession and verify one cycle results.
- Report a smaller cumulative usage figure and verify the run's totals do not decrease.

### 12.2 Runtime State Interface

The read model an operator or tool uses to see what is happening now, and the one control it may exercise over timing.

Input semantics:

- A reader may request the whole current state.
- A reader may request the state of one Work Item by its identifier.
- A reader may request that the next poll happen sooner.

Output semantics:

- The state separates running, retrying, and blocked items.
- Each running entry reports its location, workspace, session, and progress.
- Each retrying entry reports its attempt number, due time, and failure reason.
- Each blocked entry reports when and why it blocked.
- The state reports whether a poll is in progress and when the next is due.
- Cumulative resource usage is reported per run and in total.
- An immediate-poll request reports whether it was coalesced into a pending cycle.

Failure semantics:

- An unknown Work Item identifier is reported as not found.
- A scheduler that does not answer in time is reported as a timeout.
- An absent scheduler is reported as unavailable.

Implementation-defined mechanisms:

- The transport and encoding of the read model.
- Field naming and the shape of each entry.
- The retention, if any, of past state.

Validation checks:

- Query an item that is not orchestrated and verify a not-found result.
- Make the scheduler unresponsive and verify a timeout result rather than a hang.
- Request an immediate poll during a running cycle and verify coalescing is reported.

### 12.3 Observability Service Interface (Optional Extension)

Serve the Runtime State over a network to operators and tools, when a deployment chooses to expose it.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Input semantics:

- The service is off unless the operator configures a listening port.
- The service exposes reading the whole state, reading one item, and requesting a poll.
- The bind address is operator-settable and defaults to a loopback address.

Output semantics:

- Read requests answer with the same information as the Runtime State Interface.
- A poll request is acknowledged as accepted rather than as completed.
- A live view of the state may be offered in addition to the read model.

Failure semantics:

- An unknown route is reported as not found.
- An unsupported method on a known route is reported as method not allowed.
- An unavailable scheduler is reported as a service-unavailable condition.

Implementation-defined mechanisms:

- The protocol, routes, and encoding.
- Whether a human-facing view is offered.
- Authentication, if any.

Validation checks:

- Leave the port unset and verify no service listens.
- Request an unknown route and verify a not-found response.
- Use an unsupported method on a known route and verify a method-not-allowed response.

### 12.4 Reported Usage Never Decreases Within a Run

Cumulative usage reported for an Agent Run is non-decreasing, and an incremental report is never added on top of a cumulative one for the same usage.

Usage is the operator's only measure of what a run costs. A total that drops or double counts makes cost impossible to reason about.

This prevents:

- A per-turn figure being mistaken for a session total and stalling the count.
- The same usage being counted once as a total and again as an increment.
- Totals resetting when a new turn starts on the same session.

Validation checks:

- Report a cumulative total, then a smaller one, and verify the total does not drop.
- Report a cumulative total and its increment and verify the increment is not added.
- Start a further turn on the same session and verify totals continue rather than reset.

## 13. Distributed Execution (Optional Extension)

Spreading runs across several execution locations. A conforming implementation may run everything locally and omit this chapter entirely.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

### 13.1 Run on a Remote Worker Host (Optional Extension)

Spread Agent Runs across several execution locations while keeping each run whole on the location it started on.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Participants: **Work Scheduler**, **Agent Run Supervisor**, **Worker Host**, **Agent Run**, **Workspace**, **Work Item**.

Trigger: A run is about to start and more than one execution location is configured.

Preconditions:

- At least one remote worker host is configured.
- The workspace root is meaningful on the selected host.

Sequence:

1. **Work Scheduler** Exclude hosts that already carry their configured share of runs.
2. **Work Scheduler** Defer the dispatch when no host has capacity.
3. **Work Scheduler** Prefer the host a retrying run previously used, when it still has capacity.
4. **Work Scheduler** Otherwise choose the least loaded host, breaking ties deterministically.
5. **Agent Run Supervisor** Prepare the workspace and run the session on the chosen host.
6. **Agent Run Supervisor** Report the failure to the scheduler rather than move the run to another host.

Postconditions:

- The run's workspace and session are on the same host.
- No host exceeds its configured share of concurrent runs.

Requirements:

- **MUST** — Keep one run's workspace and session on the same host.
- **MUST NOT** — Move a running run to a different host after a failure.
- **MUST** — Defer dispatch when every host is at its configured share.
- **SHOULD** — Return a retrying run to the host that already holds its workspace.
- **MUST** — Apply the workspace containment rules on the remote host too.

Constrained by **A Run Stays on One Execution Location**, **Concurrency Limits Are Never Exceeded**.

Failures: **Worker Host Unreachable**.

Validation checks:

- Fill every host to its configured share and verify dispatch is deferred.
- Fail a run on one host and verify the retry does not start on another host.
- Retry a run whose host still has capacity and verify the same host is chosen.
- Make one host unreachable and verify the failure surfaces as a normal run failure.

### 13.2 A Run Stays on One Execution Location

One Agent Run prepares its workspace and runs its session on a single execution location, and a failure never moves the same run to another location.

Work in progress lives in the workspace. Moving a run to another host abandons that work and hides the failure of the original host.

This prevents:

- A retry starting from an empty workspace on a different machine.
- A host failure being masked by silent migration.
- Two hosts holding divergent workspaces for one item.

Validation checks:

- Fail a run on one host and verify the retry does not start on another host.
- Verify a run's workspace and session report the same execution location.
- Retry an item whose host still has capacity and verify the same host is chosen.

### 13.3 Worker Host Unreachable (Optional Extension)

The chosen execution location could not be reached, or a command on it could not be run.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Occurs during **Run on a Remote Worker Host**.

Retryable: True.

Requirements:

- Report the failure as a failure of the run.
- Do not move the run to a different execution location.
- Do not treat the host's workspaces as removed.
- Make the failing location identifiable in the report.

Recovery: The scheduler retries the item with backoff, preferring the same location while it retains capacity, so the run resumes on its own workspace.

Validation checks:

- Make a host unreachable and verify the run fails and retries.
- Verify the retry does not start on a different host.
- Verify the unreachable host is named in the failure report.

## 14. Provider-Native Agent Tools (Optional Extension)

Letting the agent act on the board through the subject's credential instead of its own. A conforming implementation may omit this chapter; the agent then needs its own access, or none.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

### 14.1 Execute a Provider-Native Agent Tool (Optional Extension)

Let the agent act on the board through the subject's credential, instead of giving the agent that credential.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Participants: **Agent Session Client**, **Work Source Adapter**, **Agent Session**, **Provider-Native Agent Tool**, **Work Item**.

Trigger: The agent calls a tool the adapter advertised for this session.

Preconditions:

- The session was started with the adapter's tool advertisement.
- A credential for the work source is configured.

Sequence:

1. **Agent Session Client** Receive the tool call and its arguments from the agent.
2. **Work Source Adapter** Reject arguments that do not satisfy the tool's declared shape.
3. **Work Source Adapter** Execute the call with the credential and settings bound when the session started.
4. **Agent Session Client** Return a structured result stating success or failure to the agent.
5. **Agent Session Client** Return a failure result naming the supported tools when the tool is unknown.

Postconditions:

- The agent has a structured result for every call it made.
- The agent never received the credential itself.

Requirements:

- **MUST** — Execute tool calls outside the agent process.
- **MUST** — Bind tool settings when the session starts, not when the call arrives.
- **MUST** — Return a structured failure rather than raising on a bad call.
- **MUST NOT** — Add retry, deduplication, or rate-limit policy on the agent's behalf.
- **MUST** — State that tool reach follows the credential, not the scheduler's scope.

Constrained by **The Agent Never Receives the Subject's Credentials**.

Failures: **Agent Tool Call Failed**.

Validation checks:

- Call an advertised tool and verify it runs with the session-bound settings.
- Change the effective settings mid-session and verify the bound settings are still used.
- Call an unknown tool and verify a failure result naming supported tools is returned.
- Call a tool with malformed arguments and verify a structured failure is returned.

### 14.2 Provider-Native Agent Tool Interface (Optional Extension)

Let the agent operate on the board through the subject's credential, with a declared argument shape and a structured result.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Input semantics:

- Each tool declares a name, a purpose, and the shape of its arguments.
- Arguments that do not satisfy the declared shape are rejected before execution.
- The credential and scope are bound when the session starts.

Output semantics:

- Every call returns a structured result stating success or failure.
- The result carries the provider's response or the reason it failed.
- Reach is limited by the configured credential, not by the scheduler's scope.

Failure semantics:

- An unknown tool returns a failure naming the supported tools.
- Malformed arguments return a failure explaining the expected shape.
- A missing credential returns a failure that names the missing setting.
- Provider errors are returned verbatim enough for the agent to react.
- No retry, deduplication, or rate-limit policy is applied on the agent's behalf.

Implementation-defined mechanisms:

- Which tools a given adapter offers.
- The argument schema of each tool.
- The encoding of the structured result.

Validation checks:

- Call an unknown tool and verify a failure naming the supported tools.
- Call with malformed arguments and verify a structured failure result.
- Remove the credential and verify a failure that names the missing setting.

### 14.3 Agent Tool Call Failed (Optional Extension)

A provider-native tool call could not be executed or the provider rejected it.

This is an optional extension. A conforming implementation may omit it entirely. When implemented, its semantics are normative in full.

Occurs during **Execute a Provider-Native Agent Tool**.

Retryable: implementation-defined.

Requirements:

- Return a structured failure result to the agent rather than ending the turn.
- State the reason in terms the agent can act on.
- Name the supported tools when the requested tool is unknown.
- Name the missing setting when the credential is absent.
- Apply no retry or deduplication policy on the agent's behalf.

Recovery: The agent decides what to do next. Idempotency and repetition of provider mutations are the workflow author's responsibility, not the subject's.

Validation checks:

- Call an unknown tool and verify a failure result naming supported tools.
- Remove the credential and verify a failure naming the missing setting.
- Fail the provider call and verify the turn continues with a failure result.

## 15. Implementation-Defined Areas

### 15.1 Work source and its protocol

Any system that can be read by state and by item identity may serve as the Work Source, over any protocol.

Fixed semantics:

- Reads are scoped to one configured collection of work.
- Records that cannot be normalized are dropped, not returned partially formed.
- A read failure is distinguishable from an empty result.
- Provider readiness never bypasses scheduler policy.

A conforming implementation must document:

- Which system is supported and how its scope is expressed.
- Which native field becomes the Work Item identity and which becomes the identifier.
- Which native states are expected to be configured as active and terminal.
- How the provider's readiness signal is derived.
- Which failures map to configuration, authentication, transport, and rate limiting.

### 15.2 Agent runtime and its protocol

Any coding agent that accepts a prompt, works in a directory, and reports progress may be driven.

Fixed semantics:

- The agent runs with the run's Workspace as its working directory.
- The agent does not receive the subject's work source credentials.
- A turn ends as completed, failed, or awaiting operator input.
- Silence past the configured timeout ends the turn.

A conforming implementation must document:

- Which agent runtime is supported and how it is launched.
- How approval and sandbox policies are expressed for that runtime.
- Which policy setting permits the subject to answer approvals.
- Which runtime signals are read as a request for operator input.

### 15.3 Runtime state durability

Claims, retries, and blocked records may be held in memory, persisted, or replicated.

Fixed semantics:

- The Work Source stays authoritative regardless of what is retained.
- Losing runtime state must not leave a Work Item permanently unclaimable.
- A restart must not produce two concurrent runs for one item.

A conforming implementation must document:

- What survives a restart and what does not.
- What happens to a blocked item when the subject restarts.
- Whether an interrupted run's workspace is reused, reset, or removed on restart.

### 15.4 Retry delay curve

The exact growth curve, jitter, and starting delay of the retry sequence are unconstrained.

Fixed semantics:

- Consecutive failures produce non-decreasing delays.
- No delay exceeds the configured ceiling.
- A normal completion with the item still active may be retried sooner than a failure.

A conforming implementation must document:

- The chosen curve and its starting delay.
- Whether jitter is applied.

### 15.5 Workspace storage and naming

The layout, naming scheme, and storage medium of workspaces are unconstrained.

Fixed semantics:

- Identity is a deterministic function of the Work Item identifier.
- Distinct identifiers never collapse onto one workspace.
- Every path resolves inside the configured root after links are followed.

A conforming implementation must document:

- How a workspace name is derived from an identifier.
- How identifiers that contain unusable characters are disambiguated.
- Whether workspaces are ever reclaimed for reasons other than a terminal item.

### 15.6 Execution and concurrency model

Runs may execute as processes, threads, containers, or remote jobs, in one or many execution units.

Fixed semantics:

- Exactly one authority owns the claim set.
- Stopping a run stops its agent process.
- Concurrency limits are enforced against actually active runs.

A conforming implementation must document:

- How runs are isolated from one another.
- How a stopped run's agent process is guaranteed to end.
- Whether the scheduler authority is replicated and how that stays consistent.

### 15.7 Observability presentation and transport

Runtime State may be presented on a terminal, over a network, through logs, or not at all beyond the required derivation.

Fixed semantics:

- Running, retrying, and blocked items remain distinguishable.
- Reasons for retrying and blocking remain visible.
- Presentation never delays scheduling.

A conforming implementation must document:

- Which presentations are offered and how they are enabled.
- The shape of the read model, if one is served.
- Whether any history is retained.

### 15.8 Logging and diagnostics

Log format, level, destination, and rotation are unconstrained.

Fixed semantics:

- Failures that trigger a retry or a block are reported.
- Reload failures are reported until the configuration is repaired.

A conforming implementation must document:

- Which context identifies a log entry with a Work Item and a session.
- Where logs are written and how they are rotated.
- How sensitive values are kept out of logs.

## 16. Reference Implementation

The reference implementation is an Elixir/OTP service that polls an issue tracker, creates a workspace per issue, launches a Codex app-server session inside it, and keeps that session working until the issue leaves the active set. It is one realization of this specification and adds no normative requirements.

The reference implementation is **not normative**; it is one realization of this specification.

## 17. Test and Validation Matrix

Checks assembled from the verification clauses of this specification. A conforming implementation should be able to demonstrate each of them. Checks under an optional extension apply only when that extension is implemented.

### 17.1 Work Intake and Dispatch

- **Poll and Dispatch** — Offer more qualifying items than the configured limit and verify no run exceeds the limit.
- **Poll and Dispatch** — Present a claimed item again in the same cycle and verify no second run starts.
- **Poll and Dispatch** — Move an item to a terminal state between read and dispatch, then verify no run starts.
- **Poll and Dispatch** — Remove a required label between read and dispatch, then verify no run starts.
- **Poll and Dispatch** — Present items with mixed priority and creation time, then verify dispatch order.
- **Work Source Adapter Interface** — Read with an empty state list and verify no provider request is made.
- **Work Source Adapter Interface** — Return a record without an identifier and verify it is dropped, not dispatched.
- **Work Source Adapter Interface** — Fail a read and verify a failure, not an empty list, reaches the scheduler.
- **Work Source Adapter Interface** — Rename a state's letter case and verify matching still succeeds.
- **One Claim Per Work Item** — Offer a claimed item as a candidate again and verify no second run starts.
- **One Claim Per Work Item** — Trigger a retry while the run is active and verify the run is not duplicated.
- **One Claim Per Work Item** — Verify a blocked item is never selected while its claim is held.
- **Dispatch Order Is Deterministic** — Offer items of differing priority and verify higher priority dispatches first.
- **Dispatch Order Is Deterministic** — Offer items of equal priority and verify the older one dispatches first.
- **Dispatch Order Is Deterministic** — Offer items with equal priority and age and verify identifier order decides.
- **Dispatch Order Is Deterministic** — Offer an item with no priority and verify it sorts after every prioritized item.
- **Concurrency Limits Are Never Exceeded** — Fill global capacity and verify further qualifying items are not dispatched.
- **Concurrency Limits Are Never Exceeded** — Fill one state's capacity and verify items in other states still dispatch.
- **Concurrency Limits Are Never Exceeded** — Fill one host's share and verify dispatch moves to another host or defers.
- **Concurrency Limits Are Never Exceeded** — Reach capacity at retry time and verify a further retry is scheduled instead.
- **Dispatch Decisions Are Revalidated** — Move an item to a terminal state between poll and dispatch, then verify no run starts.
- **Dispatch Decisions Are Revalidated** — Remove a required label between poll and dispatch, then verify no run starts.
- **Dispatch Decisions Are Revalidated** — Hide the item between poll and dispatch, then verify the claim is released.
- **Work Source Unavailable** — Fail the candidate read and verify no run is started or stopped.
- **Work Source Unavailable** — Fail the reconciling read and verify every claim survives.
- **Work Source Unavailable** — Fail the read during a retry and verify a further retry is scheduled.

### 17.2 Isolated Execution Environment

- **Prepare the Isolated Workspace** — Point the workspace path at a link that escapes the root and verify the run is refused.
- **Prepare the Isolated Workspace** — Request the workspace for the same identifier twice and verify one identity results.
- **Prepare the Isolated Workspace** — Request workspaces for two identifiers that sanitize alike and verify they stay distinct.
- **Prepare the Isolated Workspace** — Fail the creation hook and verify the new workspace is removed and the run fails.
- **Prepare the Isolated Workspace** — Leave a file in an existing workspace, run again, and verify the file survives.
- **Prepare the Isolated Workspace** — Hang a hook past the configured timeout and verify the hook is abandoned.
- **Workspace Hook Interface** — Fail the creation hook and verify the new workspace is discarded and the run fails.
- **Workspace Hook Interface** — Fail the post-run hook and verify the run's outcome is unchanged.
- **Workspace Hook Interface** — Fail the removal hook and verify removal still completes.
- **Workspace Hook Interface** — Exceed the hook timeout and verify the hook is abandoned.
- **Workspaces Stay Inside the Configured Root** — Link a workspace path outside the root and verify creation is refused.
- **Workspaces Stay Inside the Configured Root** — Link a workspace path outside the root and verify removal is refused.
- **Workspaces Stay Inside the Configured Root** — Ask for the workspace root itself and verify it is refused with a distinct reason.
- **Workspaces Stay Inside the Configured Root** — Verify the agent's working directory is the workspace and not its parent.
- **Workspace Identity Is Deterministic and Collision-Free** — Derive the identity twice for one identifier and verify the results match.
- **Workspace Identity Is Deterministic and Collision-Free** — Derive identities for two identifiers that sanitize alike and verify they differ.
- **Workspace Identity Is Deterministic and Collision-Free** — Leave a file in a workspace, retry the item, and verify the file is still present.
- **Workspace Preparation Failed** — Fail the creation hook and verify the new workspace is gone and no session starts.
- **Workspace Preparation Failed** — Fail the creation hook on an existing workspace and verify its content survives.
- **Workspace Preparation Failed** — Verify a later attempt re-runs the creation hook after a discarded workspace.
- **Workspace Hook Failed** — Fail the pre-run hook and verify the run fails before a session starts.
- **Workspace Hook Failed** — Fail the post-run hook and verify the run's outcome is unchanged.
- **Workspace Hook Failed** — Fail the removal hook and verify the workspace is still removed.
- **Workspace Hook Failed** — Hang a hook past the timeout and verify it is abandoned and reported.

### 17.3 Agent Session and Turn Continuation

- **Run the Agent Session** — Start a session and verify the agent's working directory is the run workspace.
- **Run the Agent Session** — Configure a credential variable and verify it is absent from the agent process.
- **Run the Agent Session** — Point the session at a path outside the workspace root and verify it is refused.
- **Run the Agent Session** — Stop producing agent updates and verify the turn ends at the silence timeout.
- **Run the Agent Session** — Send an approval request under a restrictive policy and verify the turn ends as input-required.
- **Continue or Conclude the Run** — Keep an item active across turns and verify a further turn starts.
- **Continue or Conclude the Run** — Exhaust the configured turn budget and verify control returns to the scheduler.
- **Continue or Conclude the Run** — Remove a required label between turns and verify the run concludes.
- **Continue or Conclude the Run** — Move the item out of the active states between turns and verify the run concludes.
- **Agent Session Interface** — Start a session and verify the declared working directory is used.
- **Agent Session Interface** — Withhold updates past the silence timeout and verify the turn is abandoned.
- **Agent Session Interface** — Emit updates steadily past the silence timeout and verify the turn continues.
- **Agent Session Interface** — Exit the agent process mid-turn and verify the turn fails.
- **Work Prompt Interface** — Reference an unknown field and verify rendering fails rather than substituting nothing.
- **Work Prompt Interface** — Render with an absent description and verify the default template still produces a prompt.
- **Work Prompt Interface** — Start a continuation turn and verify the prompt tells the agent to resume.
- **The Agent Never Receives the Subject's Credentials** — Declare a credential variable and verify it is unset in the agent process.
- **The Agent Never Receives the Subject's Credentials** — Verify the agent can still act on the board through an offered tool.
- **The Agent Never Receives the Subject's Credentials** — Verify the subject itself still reads the board successfully.
- **One Run's Turns Are Bounded** — Keep an item active and verify no more than the configured number of turns run.
- **One Run's Turns Are Bounded** — Exhaust the budget and verify control returns to the scheduler with the claim held.
- **Agent Session Could Not Start** — Point the agent command at a missing executable and verify the run fails and retries.
- **Agent Session Could Not Start** — Withhold the startup response past the read timeout and verify the session start fails.
- **Agent Session Could Not Start** — Verify no orphaned agent process survives a failed session start.
- **Turn Failed** — Fail a turn and verify the session ends and the workspace survives.
- **Turn Failed** — Exit the agent process mid-turn and verify the run fails and retries.
- **Turn Failed** — Withhold updates past the silence timeout and verify the turn is abandoned.
- **Turn Failed** — Verify an input-required turn is not reported as a plain failure.

### 17.4 Claim Lifecycle, Interruption, and Recovery

- **Reconcile Claimed Work Items** — Move a running item to a terminal state and verify the run stops and the workspace is removed.
- **Reconcile Claimed Work Items** — Move a running item to a non-active state and verify the run stops and the workspace survives.
- **Reconcile Claimed Work Items** — Remove a required label from a running item and verify the run stops.
- **Reconcile Claimed Work Items** — Remove a required label from a blocked item and verify its claim is released.
- **Reconcile Claimed Work Items** — Hide a running item from the work source and verify the run stops and the workspace survives.
- **Reconcile Claimed Work Items** — Fail the reconciling read and verify every claim and run is retained.
- **Retry After Failure** — Fail a run repeatedly and verify each delay is at least as long as the previous one.
- **Retry After Failure** — Fail a run many times and verify the delay never exceeds the configured ceiling.
- **Retry After Failure** — Move the item to a terminal state during the delay and verify the claim is released.
- **Retry After Failure** — Deliver a superseded retry signal and verify it does not start a run.
- **Retry After Failure** — Fill all capacity at retry time and verify a further retry is scheduled.
- **Detect and Recover a Stalled Run** — Silence a run past the configured timeout and verify it is stopped and retried.
- **Detect and Recover a Stalled Run** — Silence a run that already requested operator input and verify it becomes blocked.
- **Detect and Recover a Stalled Run** — Disable stall detection and verify a silent run is left alone.
- **Hold a Work Item Blocked on Operator Input** — Make the agent request input and verify the item becomes blocked with no pending retry.
- **Hold a Work Item Blocked on Operator Input** — Verify a blocked item is not selected for dispatch while it stays blocked.
- **Hold a Work Item Blocked on Operator Input** — Move a blocked item to a terminal state and verify its claim and workspace are released.
- **Release the Claim and Clean Up** — Close an item with a running agent and verify the run stops and the workspace is removed.
- **Release the Claim and Clean Up** — Fail the removal hook and verify the workspace is still removed.
- **Release the Claim and Clean Up** — Point a recorded workspace path at an escaping link and verify removal is refused.
- **Release the Claim and Clean Up** — Start the subject with terminal items present and verify their workspaces are reclaimed.
- **A Claim Lives Only While Its Item Qualifies** — Close a running item and verify the run stops and the claim is released.
- **A Claim Lives Only While Its Item Qualifies** — Move a running item out of the active states and verify the claim is released.
- **A Claim Lives Only While Its Item Qualifies** — Remove a required label from a running item and verify the claim is released.
- **A Claim Lives Only While Its Item Qualifies** — Fail the reconciling read and verify no claim is released.
- **Retry Delay Grows and Is Capped** — Fail a run repeatedly and verify each delay is at least the previous one.
- **Retry Delay Grows and Is Capped** — Fail a run many times and verify no delay exceeds the configured ceiling.
- **Retry Delay Grows and Is Capped** — Schedule a new retry over a pending one and verify only the newer one fires.
- **Retry Delay Grows and Is Capped** — Deliver a superseded retry signal and verify it starts no run.
- **A Blocked Item Is Held, Not Retried** — Make the agent request input and verify the item blocks with no pending retry.
- **A Blocked Item Is Held, Not Retried** — Verify the blocked item is not dispatched while it stays blocked.
- **A Blocked Item Is Held, Not Retried** — Verify the reason for blocking is present in the runtime state.
- **Run Stalled** — Silence a run past the timeout and verify it is stopped and retried with backoff.
- **Run Stalled** — Verify the stalled run's workspace survives the restart.
- **Run Stalled** — Disable stall detection and verify a silent run is not restarted.
- **Operator Input Required** — Request an approval the policy forbids and verify the item blocks, not retries.
- **Operator Input Required** — Verify a blocked item keeps its claim and stays out of dispatch.
- **Operator Input Required** — Close a blocked item and verify its claim is released and its workspace removed.
- **Work Item No Longer Visible** — Hide a running item and verify the run stops and the claim is released.
- **Work Item No Longer Visible** — Hide a running item and verify its workspace is preserved.
- **Work Item No Longer Visible** — Fail the read entirely and verify the claim is retained instead of released.

### 17.5 Configuration and Reload

- **Load and Reload the Workflow Definition** — Start with an invalid definition and verify the subject does not start.
- **Load and Reload the Workflow Definition** — Make a valid definition invalid while running and verify prior settings stay effective.
- **Load and Reload the Workflow Definition** — Make a valid definition invalid while running and verify the failure is reported.
- **Load and Reload the Workflow Definition** — Change a limit while running and verify later decisions use the new value.
- **Workflow Definition Interface** — Omit every optional setting and verify documented defaults apply.
- **Workflow Definition Interface** — Reference a credential through an environment variable and verify it resolves.
- **Workflow Definition Interface** — Give a relative workspace root and verify it resolves against the document's location.
- **Workflow Definition Interface** — Leave the prompt template empty and verify the default template is used.
- **Only a Valid Configuration Is Ever Effective** — Start with an invalid document and verify the subject does not start.
- **Only a Valid Configuration Is Ever Effective** — Invalidate the document while running and verify prior settings stay effective.
- **Only a Valid Configuration Is Ever Effective** — Invalidate the document while running and verify the failure is reported.
- **Only a Valid Configuration Is Ever Effective** — Repair the document and verify the new settings become effective without restart.
- **Invalid Workflow Definition** — Start with a missing document and verify the subject does not start.
- **Invalid Workflow Definition** — Invalidate the document while running and verify behavior is unchanged.
- **Invalid Workflow Definition** — Repair the document and verify the new settings become effective without restart.

### 17.6 Observability

- **Publish Runtime State** — Run, retry, and block one item each, then verify all three are distinguishable.
- **Publish Runtime State** — Stop answering snapshot requests and verify the reader is told state is unavailable.
- **Publish Runtime State** — Request an immediate poll twice in quick succession and verify one cycle results.
- **Publish Runtime State** — Report a smaller cumulative usage figure and verify the run's totals do not decrease.
- **Runtime State Interface** — Query an item that is not orchestrated and verify a not-found result.
- **Runtime State Interface** — Make the scheduler unresponsive and verify a timeout result rather than a hang.
- **Runtime State Interface** — Request an immediate poll during a running cycle and verify coalescing is reported.
- **Observability Service Interface** — Leave the port unset and verify no service listens.
- **Observability Service Interface** — Request an unknown route and verify a not-found response.
- **Observability Service Interface** — Use an unsupported method on a known route and verify a method-not-allowed response.
- **Reported Usage Never Decreases Within a Run** — Report a cumulative total, then a smaller one, and verify the total does not drop.
- **Reported Usage Never Decreases Within a Run** — Report a cumulative total and its increment and verify the increment is not added.
- **Reported Usage Never Decreases Within a Run** — Start a further turn on the same session and verify totals continue rather than reset.

### 17.7 Distributed Execution (Optional Extension)

- **Run on a Remote Worker Host** — Fill every host to its configured share and verify dispatch is deferred.
- **Run on a Remote Worker Host** — Fail a run on one host and verify the retry does not start on another host.
- **Run on a Remote Worker Host** — Retry a run whose host still has capacity and verify the same host is chosen.
- **Run on a Remote Worker Host** — Make one host unreachable and verify the failure surfaces as a normal run failure.
- **A Run Stays on One Execution Location** — Fail a run on one host and verify the retry does not start on another host.
- **A Run Stays on One Execution Location** — Verify a run's workspace and session report the same execution location.
- **A Run Stays on One Execution Location** — Retry an item whose host still has capacity and verify the same host is chosen.
- **Worker Host Unreachable** — Make a host unreachable and verify the run fails and retries.
- **Worker Host Unreachable** — Verify the retry does not start on a different host.
- **Worker Host Unreachable** — Verify the unreachable host is named in the failure report.

### 17.8 Provider-Native Agent Tools (Optional Extension)

- **Execute a Provider-Native Agent Tool** — Call an advertised tool and verify it runs with the session-bound settings.
- **Execute a Provider-Native Agent Tool** — Change the effective settings mid-session and verify the bound settings are still used.
- **Execute a Provider-Native Agent Tool** — Call an unknown tool and verify a failure result naming supported tools is returned.
- **Execute a Provider-Native Agent Tool** — Call a tool with malformed arguments and verify a structured failure is returned.
- **Provider-Native Agent Tool Interface** — Call an unknown tool and verify a failure naming the supported tools.
- **Provider-Native Agent Tool Interface** — Call with malformed arguments and verify a structured failure result.
- **Provider-Native Agent Tool Interface** — Remove the credential and verify a failure that names the missing setting.
- **Agent Tool Call Failed** — Call an unknown tool and verify a failure result naming supported tools.
- **Agent Tool Call Failed** — Remove the credential and verify a failure naming the missing setting.
- **Agent Tool Call Failed** — Fail the provider call and verify the turn continues with a failure result.

## 18. Implementation Checklist (Definition of Done)

Generated from the specification graph. Intentionally redundant with the body.

### 18.1 Core

- Interactions: **Poll and Dispatch**, **Prepare the Isolated Workspace**, **Run the Agent Session**, **Continue or Conclude the Run**, **Reconcile Claimed Work Items**, **Retry After Failure**, **Detect and Recover a Stalled Run**, **Hold a Work Item Blocked on Operator Input**, **Release the Claim and Clean Up**, **Load and Reload the Workflow Definition**, **Publish Runtime State**.
- Lifecycle: implement every state and transition of the lifecycle.
- Interfaces: **Work Source Adapter Interface**, **Workflow Definition Interface**, **Workspace Hook Interface**, **Work Prompt Interface**, **Agent Session Interface**, **Runtime State Interface**.
- Invariants: **One Claim Per Work Item**, **Dispatch Order Is Deterministic**, **Concurrency Limits Are Never Exceeded**, **Dispatch Decisions Are Revalidated**, **Workspaces Stay Inside the Configured Root**, **Workspace Identity Is Deterministic and Collision-Free**, **The Agent Never Receives the Subject's Credentials**, **One Run's Turns Are Bounded**, **A Claim Lives Only While Its Item Qualifies**, **Retry Delay Grows and Is Capped**, **A Blocked Item Is Held, Not Retried**, **Only a Valid Configuration Is Ever Effective**, **Reported Usage Never Decreases Within a Run**.
- Failure semantics: **Work Source Unavailable**, **Workspace Preparation Failed**, **Workspace Hook Failed**, **Agent Session Could Not Start**, **Turn Failed**, **Run Stalled**, **Operator Input Required**, **Work Item No Longer Visible**, **Invalid Workflow Definition**.
- Configuration fields: `work-source.selection`, `work-source.credential`, `scheduling.active-states`, `scheduling.terminal-states`, `scheduling.required-labels`, `scheduling.poll-interval`, `capacity.max-concurrent-runs`, `capacity.max-concurrent-runs-by-state`, `capacity.max-turns-per-run`, `recovery.max-retry-delay`, `recovery.stall-timeout`, `workspace.root`, `workspace.hooks`, `workspace.hook-timeout`, `agent.command`, `agent.prompt-template`, `agent.approval-policy`, `agent.sandbox-policy`, `agent.turn-silence-timeout`, `agent.startup-response-timeout`, `observability.exposure`.
- Documentation: record the selected behavior for every implementation-defined area.

### 18.2 Optional extensions (normative in full when implemented)

- **Run on a Remote Worker Host**
- **Execute a Provider-Native Agent Tool**
- **Observability Service Interface**
- **Provider-Native Agent Tool Interface**
- **A Run Stays on One Execution Location**
- **Worker Host Unreachable**
- **Agent Tool Call Failed**
- `workers.hosts`
- `workers.max-runs-per-host`
- `observability.service-endpoint`

## 19. Conformance

Implement a conforming realization of this specification. Preserve the normative semantics and the design intent. Do not infer additional constraints from the reference implementation. Where behavior is implementation-defined, choose a reasonable mechanism that preserves all stated invariants.

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
