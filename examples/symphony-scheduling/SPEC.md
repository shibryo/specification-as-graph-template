# Symphony Issue Orchestration and Scheduling Specification

> GENERATED FROM `spec/`. DO NOT EDIT DIRECTLY.

Status: draft  
Version: 0.1.0

---

## Problem Statement

A team routes software work through an external issue tracker (Linear, GitHub, GitLab, Jira, Asana, or similar). Autonomous coding agents can work those issues without a human driving each step, but agent runs are long, expensive, and unreliable: they crash, stall silently, exceed rate limits, and sometimes reach a point where only a human operator can answer a question or grant an approval. Meanwhile the tracker keeps changing underneath the automation: humans close issues, reassign them, relabel them, or move them between workflow states at any moment. Multiple agent runs may execute in parallel on the local machine or on remote worker hosts, so each run needs an isolated working directory, and the machine's filesystem must be protected from misdirected cleanup.

Continuously decide which tracker issues an autonomous agent should be working on right now, start and supervise one agent run per selected issue without exceeding capacity, recover from run failures and stalls without losing work or looping hot, stop automation the moment the tracker withdraws an issue or a run needs a human, and create and destroy per-issue isolated workspaces without ever damaging unrelated files — all while treating the external tracker, not local memory, as the authority on what each issue's state is.

### Why This Specification Exists

The scheduling semantics — what makes an issue eligible, when exactly a run is started, retried, blocked, or abandoned, which side wins when local state and tracker state disagree, and which filesystem paths cleanup may ever touch — live implicitly in one large orchestration module. Without a specification, a reimplementation would have to rediscover safety-critical decisions (tracker authority, never auto-retrying input-required runs, workspace path containment, bounded backoff) by reverse engineering, and would likely copy incidental mechanisms (process topology, timer tokens, specific backoff constants) as if they were contractual.

## Goals and Non-Goals

### Goals

- Preserve the orchestration semantics independently of process model, timer mechanism, or tracker product.
- Make the issue orchestration lifecycle, capacity rules, retry policy, and reconciliation authority explicit enough that a substantially different implementation can conform.
- State workspace safety guarantees as hard invariants rather than incidental code paths.

### Non-Goals

- Specify how an agent run performs the actual coding work, or the agent's internal protocol.
- Specify tracker-specific APIs, authentication, or data mapping beyond the read contract the orchestrator requires.
- Prescribe internal structure (single process vs. many, timer libraries, supervision trees) unless that structure is itself part of the contract.

## Design Intent

### Tracker is the source of truth

The external issue tracker is authoritative for an issue's workflow state, routing, and existence. The orchestrator holds only a local, revocable claim; whenever local belief and tracker state diverge, the tracker wins.

**Why it matters**

Humans and other tools operate on the tracker concurrently. If local orchestration state could override the tracker, a closed or reassigned issue could keep consuming an agent, or work could be silently dropped.

**Implications**

- Every dispatch is preceded by a fresh revalidation of the issue against the tracker.
- Active and blocked issues are periodically re-read from the tracker, and runs are stopped when the tracker withdraws eligibility.
- Transient tracker read failures must not be treated as withdrawal; existing runs are kept.

**Trade-offs**

- Convergence to tracker truth is eventual (bounded by the reconciliation cadence), not instantaneous.

### Progress by supervised restart, not by trust

Agent runs are assumed unreliable. A normal exit is not proof the issue is finished, a crash is not fatal to the issue, and silence is treated as failure. The orchestrator converges by re-checking the tracker and re-dispatching with bounded backoff.

**Why it matters**

Long-running autonomous work fails in ways the run itself cannot always report; the scheduler must supply the reliability the runs lack.

**Implications**

- Normal completion triggers a prompt continuation check rather than terminal bookkeeping.
- Failures and stalls are retried with growing, bounded delays that preserve attempt history and placement affinity.
- A run that requires operator input is excluded from automatic restart entirely.

**Trade-offs**

- An issue may be dispatched multiple times; agent work must tolerate re-entry into an existing workspace.

### Isolation with strict containment

Each issue gets exactly one deterministic, isolated workspace, and destructive filesystem operations are confined to provable descendants of the configured workspace root.

**Why it matters**

Parallel agents share hosts with each other and with the operator's own files; a single unconfined recursive delete is catastrophic.

**Implications**

- Workspace identity is derived deterministically and collision-safely from the issue identifier.
- Path containment is validated (including symlink escape) before any removal.
- Cleanup failures are surfaced or skipped, never worked around by loosening containment.

**Trade-offs**

- Some stale workspaces may survive until an eligible cleanup opportunity rather than being force-removed.

## System Model

### Core Concepts

#### Issue

A unit of tracked work owned by the external issue tracker. From the orchestrator's perspective an issue is a snapshot with a stable dispatch identity, a human-readable identifier, a workflow state name, routing attributes (dispatchability, labels, assignment), a priority, and a creation time. The snapshot is always potentially stale; only the tracker's current answer is authoritative.

- Has a stable dispatch identity within the configured tracker scope, distinct from its human-readable identifier.
- Its human-readable identifier is unique within the scope and is the basis for workspace identity.
- Carries a workflow state name; state names are compared case-insensitively after trimming surrounding whitespace.
- Is a dispatch candidate only when it is routable to this orchestrator (dispatchable and carrying all configured required labels), its state is in the configured active set, its state is not in the configured terminal set, and its identity, identifier, title, and state are all present and non-empty.

#### Tracker

The external issue-tracking system, accessed through a uniform read boundary. It is the authority for issue existence, workflow state, and routing. The orchestrator only reads from it; agent-side mutations stay outside scheduling policy.

- Answers two read questions, fetch issues currently in a set of workflow states, and fetch issues by identity.
- May be temporarily unreachable; unreachability is a defined transient condition, not evidence about issue state.

#### Agent Run

One supervised execution of an autonomous agent working a single issue. The orchestrator tracks, per run, the issue snapshot it was started from, its placement (worker host and workspace), its retry attempt number, when it started, and the most recent activity observed from the agent (event kind, message, timestamp).

- Belongs to exactly one issue; an issue has at most one live run at a time.
- Its recorded last-activity time is the timestamp of the most recent agent event, or the run start time if no event has arrived yet.
- Certain observed conditions mark the run as requiring operator input (an input-required or approval-required event, an input-required completion outcome, or an elicitation request); such a run is a blocking candidate, never a retry candidate.

#### Retry Schedule

A pending decision to re-evaluate an issue for dispatch after a delay. It records the attempt number, when it is due, the reason (error) that caused it, and affinity hints (previous worker host and workspace path) so a re-dispatch can resume where the prior run worked.

- At most one retry schedule exists per issue; scheduling a new one replaces and cancels the previous one.
- Its delay is derived from the attempt number and is bounded above by a configured maximum, except that the continuation check after a normal run completion uses a short fixed delay.
- Firing does not imply dispatch; the issue is re-validated against the tracker and against capacity first.

#### Blocked Issue

A record that an issue's run reached a point requiring a human operator (input, approval, or elicitation) and that automation for the issue is suspended. The record preserves the diagnostic context (error description, last agent activity, placement) so an operator can act.

- A blocked issue remains claimed, so it cannot be re-dispatched while blocked.
- Blocking is released only by tracker-observed change (the issue leaves the active states, becomes terminal, becomes unroutable, or disappears), never by a timer.

#### Workspace

An isolated per-issue working directory in which agent runs for that issue execute, on the local machine or on a remote worker host. Its identity is derived deterministically from the issue's human-readable identifier, so any party knowing the identifier can locate the same workspace.

- Identity derivation is collision-safe, two distinct identifiers never map to the same workspace directory name.
- Lives strictly below a configured workspace root; a workspace path equal to the root or escaping it (including via symlinks) is invalid.
- Is reused across successive runs of the same issue and removed when the issue reaches a terminal tracker state.

#### Worker Host

An execution location for agent runs, either the local machine (when no remote hosts are configured) or one of a configured set of remote hosts. Each remote host has bounded run capacity.

- When remote hosts are configured, every run is placed on exactly one host with available capacity.
- Placement prefers the host a previous run of the same issue used, when that host has capacity; otherwise load is balanced toward less-loaded hosts.

### Concept Relationships

**Tracker** is authoritative for **Issue**. The tracker's current answer defines an issue's existence, workflow state, and routing; every local record about the issue is a revocable cache of that answer.

**Agent Run** works on **Issue**. An agent run exists only to advance one issue; the issue's tracker state governs whether the run may continue to exist.

**Agent Run** executes in **Workspace**. Every run of an issue executes inside that issue's workspace, so successive runs (retries, continuations) see prior work.

**Agent Run** is placed on **Worker Host**. Each run occupies capacity on exactly one worker host for its duration.

**Retry Schedule** defers re-evaluation of **Issue**. A retry schedule postpones the decision to run the issue again; it holds the issue's claim in the meantime.

**Blocked Issue** suspends automation for **Issue**. A blocked-issue record excludes the issue from dispatch and retry until the tracker shows a relevant change.

**Workspace** isolates **Issue**. The workspace confines all filesystem effects of working an issue to a directory dedicated to that issue.

### Responsibilities and Ownership

#### Scheduling and Dispatch

Decide, on a recurring cadence, which eligible issues to start agent runs for, in what order, and where — without exceeding any capacity limit and without ever running the same issue twice concurrently.

It owns:

- The polling cadence and the decision of when a scheduling pass happens.
- Candidate eligibility (routing, active/terminal state membership, claim status).
- Dispatch ordering (priority, then age, then a deterministic tiebreak).
- Admission control against the global limit, the per-issue-state limit, and per-worker-host limits.
- Pre-dispatch revalidation of the issue against the tracker and worker-host placement.

It does not own:

- Issue workflow-state changes in the tracker (only humans or agent-side tools change tracker state).
- The agent's internal execution semantics.

Normative ownership semantics:

- A conforming implementation MUST make the dispatch decision point unambiguous, exactly one authority admits runs against the capacity limits.

#### Run Supervision and Retry

Own the fate of every live agent run, observe its activity and its exit, and translate each outcome into exactly one of continuation check, retry with backoff, blocking for operator input, or release.

It owns:

- Monitoring run liveness and recording last observed agent activity.
- Classifying run endings (normal completion, abnormal exit, stall, input-required).
- The retry policy, attempt counting, delay computation, bounded backoff, and preservation of retry context (error, host affinity, workspace).
- Creating and releasing blocked-issue records.

It does not own:

- Deciding that an issue is finished; only tracker state can retire an issue.
- Capacity policy (it must consult Scheduling and Dispatch's admission rules when re-dispatching).

Normative ownership semantics:

- Every run ending MUST resolve to exactly one supervised outcome; no run may simply vanish from orchestration state.

#### Tracker Reconciliation

Keep local orchestration state (running, retrying, blocked, claimed) convergent with tracker truth by periodically re-reading tracked issues and revoking local state the tracker no longer supports.

It owns:

- Refreshing tracker snapshots for running and blocked issues.
- Stopping runs and releasing claims when issues become terminal, leave the active states, become unroutable, or disappear.
- Deciding which of those revocations also remove the issue's workspace.
- Tolerating transient tracker read failures without revoking anything.

It does not own:

- Interpreting agent activity (that is run supervision).
- Tracker-side mutation of issues.

Normative ownership semantics:

- Reconciliation MUST be fail-safe with respect to tracker outages, absence of an answer is never treated as absence of the issue when the read itself failed.

#### Workspace Management and Safety

Provide each issue with exactly one isolated, reusable workspace, run operator hooks at defined lifecycle points, and guarantee that no destructive operation ever escapes the configured workspace root.

It owns:

- Deriving deterministic, collision-safe workspace identity from issue identifiers.
- Creating, reusing, validating, and removing workspaces locally and on remote worker hosts.
- Enforcing path containment (root membership, symlink-escape rejection) before destructive operations.
- Invoking operator hooks (after creation, before and after runs, before removal) and applying their failure semantics.
- Startup cleanup of workspaces belonging to terminal issues.

It does not own:

- Scheduling decisions about when an issue runs.
- The content or version-control workflow inside a workspace.

Normative ownership semantics:

- Workspace Management MUST be the only party that removes workspace directories; no other responsibility may perform filesystem deletion directly.

## 1. Orchestration State Machine

The heart of the subject is a small per-issue state machine layered on top of the tracker's own workflow states. Each issue the orchestrator touches moves through a claim lifecycle — eligible, running, awaiting retry, blocked, released — in which exactly one form of local ownership exists at a time. Three rules give the machine its character. First, a claim is exclusive, an issue can never be worked twice concurrently. Second, the tracker outranks every local belief, and local state is revoked promptly (but only) when a successful tracker read withdraws the issue. Third, a run that stops to ask a human for input leaves automation entirely, it is held blocked, visible to operators, and no timer will ever restart it. This chapter presents the lifecycle, those three governing invariants, and the operator-input failure that produces the blocked state.

### Lifecycle and State

The lifecycle begins in **Eligible**.

- **Eligible** — The tracker reports the issue in an active workflow state, routed to this orchestrator, and no local claim exists. The issue competes for capacity in every scheduling pass.
- **Running** — The issue is claimed and exactly one live agent run is working it in its workspace on a chosen placement.
- **Awaiting Retry** — The issue is claimed with a single pending retry schedule; no run is live. This covers both the continuation check after a normal run completion and backoff waits after failures, stalls, or capacity contention.
- **Blocked** — The issue is claimed but automation is suspended because its run required operator input or approval; diagnostic context is preserved for the operator. Only tracker-observed change leaves this state.
- **Released** — The local claim is gone; the orchestrator holds no run, schedule, or block for the issue. This ends the orchestration episode. If the tracker later shows the issue active and routable again, a new episode begins as Eligible. This is terminal.

#### Transitions

- **Eligible** → **Running** when a scheduling pass admits the issue and dispatch starts an agent run.
- **Eligible** → **Awaiting Retry** when dispatch is admitted but starting the agent run fails, so a retry is scheduled.
- **Running** → **Awaiting Retry** when the run ends normally (continuation check), ends abnormally (failure retry), or is stopped as stalled without an input-required marker.
- **Running** → **Blocked** when the run ends or stalls while its observed activity marks it as requiring operator input or approval.
- **Running** → **Released** when reconciliation observes the issue terminal, outside the active states, unroutable, or absent from a successful tracker read; the run is stopped and the claim released.
- **Awaiting Retry** → **Running** when the retry comes due, the fresh tracker snapshot is still a dispatch candidate, capacity admits it, and dispatch starts a run.
- **Awaiting Retry** → **Awaiting Retry** when the retry comes due but the tracker read fails or capacity is unavailable; the retry is re-scheduled with a grown, bounded delay.
- **Awaiting Retry** → **Released** when the retry comes due and the fresh snapshot is terminal (workspace also removed), no longer a candidate, or absent.
- **Blocked** → **Released** when reconciliation observes the issue terminal (workspace also removed), outside the active states, unroutable, or absent from a successful tracker read.

#### Lifecycle Constraints

- An issue holds at most one claim, and a claim implies exactly one of Running, Awaiting Retry, or Blocked.
- No transition out of Blocked is driven by elapsed time or by the run itself; only tracker-observed change releases a block.
- Release caused by a terminal tracker state also removes the issue's workspace; release for any other reason preserves it.
- A normal run exit never transitions directly to Released; the continuation check in Awaiting Retry must consult the tracker first.

### Single Run Per Issue

At any moment, at most one live agent run exists per issue, and an issue that is claimed — running, awaiting retry, or blocked — is never admitted for a new dispatch until its claim is released.

**Intent**

Two concurrent runs of the same issue would race in the same workspace and against the same tracker item; the claim makes exclusive ownership explicit across all pending forms of work.

**This prevents**

- Duplicate concurrent runs corrupting a shared workspace.
- A retry firing while the previous run of the same issue is still alive.
- Re-dispatching an issue an operator is being asked to unblock.

**Verification**

- Present the same eligible issue in consecutive scheduling passes while a run, retry schedule, or block for it exists, and verify no second run starts.

### Tracker Authority Converges

No local claim, run, retry schedule, or block outlives tracker withdrawal, once a successful tracker read shows an issue terminal, outside the active states, unroutable, or absent, the orchestrator revokes the corresponding local state within the current reconciliation or retry evaluation; a failed read revokes nothing.

**Intent**

Humans and other tools change the tracker at will; local orchestration state is a cache with defined, prompt revocation, and outage never masquerades as withdrawal.

**This prevents**

- Agents continuing to burn resources on closed, reassigned, or deleted issues.
- Mass termination of healthy runs during a tracker outage.

**Verification**

- Move a running issue to a terminal state, to a non-active state, and out of routing, and verify the run stops by the next reconciliation in each case.
- Fail the reconciliation read and verify all runs and blocks survive.

### Blocked Issues Are Never Auto-Retried

Once a run's observed activity marks it as requiring operator input or approval, the issue is blocked, not retried, no retry schedule is created for it, stall handling does not restart it, and it remains blocked until a successful tracker read shows a relevant change.

**Intent**

Restarting a run that is waiting on a human discards the question being asked and can loop forever; the block converts the situation into an operator-visible escalation.

**This prevents**

- Infinite restart loops on runs that always stop to ask for approval.
- Silently discarding an agent's request for human input.

**Verification**

- End and stall runs in input-required conditions and verify a block (not a retry) results, and that only tracker change releases it.

### Run Requires Operator Input

A run's observed activity shows it waiting on a human — an input-required or approval-required signal, an input-required completion outcome, or an elicitation request — whether the run then exits, crashes, or stalls.

Occurs during **Handle Run Ending**, **Reconcile Active Runs**.

Retryability is **no**.

**Required behavior**

- Stop any still-live run and free its capacity.
- Create a blocked-issue record preserving the claim, a human-readable cause, the blocking moment, the last observed activity, and the placement.
- Cancel any pending retry schedule for the issue; never create a new one while blocked.
- Keep the block until a successful tracker read shows the issue terminal, non-active, unroutable, or absent.

**Recovery**

A human resolves the situation out of band (answers in the tracker, changes state or routing); the next reconciliation observes the change and releases the claim, after which the issue may be scheduled afresh.

## 2. Polling, Scheduling, and Dispatch

The orchestrator makes progress in recurring passes. Each pass first reconciles what it already holds, then asks the tracker for issues in the active workflow states, orders them by urgency and age, and admits as many as capacity allows across three budgets — a global run limit, a per-workflow-state limit, and per-worker-host capacity. Admission is only a nomination, immediately before every run starts, the issue is re-read from the tracker so no stale snapshot is ever dispatched, and a placement is chosen that favors where the issue ran before. This chapter covers the tick itself, the single-issue dispatch it delegates to, the tracker read boundary and observability surface it exposes, the capacity and freshness invariants, and how a pass degrades when the tracker is unreachable or a run fails to start.

### Poll and Dispatch Tick

The recurring scheduling pass, reconcile local state with the tracker, discover currently eligible issues, and start agent runs for as many of them as capacity allows, in priority order.

Participants: **Scheduling and Dispatch**, **Tracker Reconciliation**, **Tracker**, **Issue**, **Agent Run**, **Worker Host**.

The interaction begins when the polling cadence elapses, or an operator explicitly requests an immediate scheduling pass.

Before it begins:

- Orchestration configuration is loadable and names a supported tracker.

The interaction proceeds as follows:

1. **Scheduling and Dispatch** Refresh effective configuration so cadence and capacity changes made by the operator take effect on this pass without a restart.
2. **Tracker Reconciliation** Reconcile all live runs and all blocked issues against fresh tracker state before any new dispatch decision is made (see the two reconciliation interactions).
3. **Tracker** Report the issues currently in the configured active workflow states.
4. **Scheduling and Dispatch** Order the reported issues for dispatch, more urgent priority first, then earlier creation time, then a deterministic identifier tiebreak; issues without a known priority order after all prioritized issues, and issues without a creation time order last within their priority.
5. **Scheduling and Dispatch** For each ordered issue, admit it only if it is a dispatch candidate (routable, active, non-terminal, well-formed), is not already claimed, running, or blocked, and admitting it keeps the run count within the global limit, the limit for the issue's workflow state, and worker-host capacity.
6. **Agent Run** Come into existence for each admitted issue via the Dispatch Issue interaction; each dispatch consumes capacity immediately so later candidates in the same pass see the reduced availability.
7. **Worker Host** Account the placed runs against per-host capacity for subsequent admission decisions.
8. **Scheduling and Dispatch** Schedule the next pass one polling interval after this pass completes, and coalesce operator refresh requests that arrive while a pass is in progress or already due.

On completion:

- Every started run corresponds to a distinct issue that was a valid dispatch candidate at dispatch time.
- The next scheduling pass is scheduled; the cadence continues even when this pass failed or dispatched nothing.

- **MUST** — Reconcile existing runs and blocked issues before admitting new work in the same pass.
- **MUST** — Continue the polling cadence after a failed pass; one failure never stops future passes.
- **MUST NOT** — Dispatch an issue whose snapshot fails candidate validation, even if the tracker returned it for an active state.
- **SHOULD** — Apply configuration changes (interval, limits) no later than the next pass without restarting.

Constrained by **Single Run Per Issue**, **Concurrency Limits Hold at Admission**.

Defined failures: **Tracker Read Failure**.

### Dispatch Issue

Start one agent run for one issue, revalidating freshness against the tracker, choosing a worker host, provisioning the issue's workspace, and recording the claim and run so supervision can begin.

Participants: **Scheduling and Dispatch**, **Workspace Management and Safety**, **Issue**, **Tracker**, **Agent Run**, **Workspace**, **Worker Host**.

The interaction begins when a scheduling pass admits an issue, or a due retry re-admits one.

Before it begins:

- The issue passed admission (candidate checks, claim absence, capacity) in the triggering pass.

The interaction proceeds as follows:

1. **Tracker** Answer a fresh read of the issue by identity, immediately before the run starts.
2. **Scheduling and Dispatch** Abort the dispatch without error if the fresh snapshot is missing or no longer a dispatch candidate; abort and surface the condition if the freshness read itself failed.
3. **Worker Host** Provide a placement, the preferred (previously used) host when it has capacity, otherwise a host with capacity chosen to balance load; when remote hosts are configured but none has capacity, the dispatch does not proceed.
4. **Workspace Management and Safety** Provide the issue's workspace on the chosen placement (see Provision Workspace), reusing it if it already exists.
5. **Agent Run** Start in the workspace, initialized with the fresh issue snapshot, the placement, the retry attempt number (if this dispatch is a retry), and a start timestamp.
6. **Scheduling and Dispatch** Record the run and the issue's claim atomically with respect to other scheduling decisions, and clear any pending retry schedule for the issue.

On completion:

- Exactly one live run exists for the issue, and the issue is claimed.
- Supervision has enough recorded context (attempt, placement, start time) to classify any later ending of the run.

- **MUST** — Revalidate the issue against the tracker between admission and run start, and dispatch only the fresh snapshot.
- **MUST NOT** — Treat a skipped dispatch (stale, missing, or unplaceable issue) as an error that stops the scheduling pass.
- **MUST** — Honor placement affinity, prefer the worker host a previous run of this issue used when it has capacity.

Constrained by **Single Run Per Issue**, **Concurrency Limits Hold at Admission**, **Dispatch Uses a Fresh Snapshot**.

Defined failures: **Agent Run Fails to Start**, **Workspace Provisioning Fails**.

### Tracker Read Boundary

The uniform read contract the orchestrator requires from any issue tracker adapter. Scheduling policy depends on nothing tracker-specific beyond this boundary.

**Input semantics**

- A query by workflow states, given a list of state names, return the issues currently in any of those states within the configured tracker scope.
- A query by identity, given a list of issue dispatch identities, return the current snapshots of those issues.
- State-name matching is case-insensitive after trimming surrounding whitespace.

**Output semantics**

- Each returned issue snapshot carries at least dispatch identity, human-readable identifier, title, workflow state name, and routing attributes (dispatchability, labels, assignment), plus priority and creation time when the tracker provides them.
- Omission of a requested identity from a successful identity query means the issue is not visible in the configured scope; consumers may act on that absence.
- Snapshots are point-in-time reads with no freshness guarantee beyond the moment of the query.

**Failure semantics**

- A failed query is distinguishable from a successful empty result; consumers must never conflate the two.
- Failures carry a describable reason for logging and operator diagnosis.

Implementation-defined mechanisms:

- Tracker product, transport, authentication, pagination, and rate limiting.
- Mapping from provider-native records to the issue snapshot fields.

### Orchestrator Observability

The introspection and nudge surface offered to dashboards and operators, a consistent snapshot of orchestration state and a way to request an immediate scheduling pass.

**Input semantics**

- A snapshot request takes no arguments and must not mutate orchestration state.
- A refresh request asks for a scheduling pass as soon as possible.

**Output semantics**

- The snapshot reports the live runs (issue identity and identifier, workflow state, placement, workspace, attempt/session context, start time, last observed activity), the pending retries (attempt, time remaining, error context, affinity), the blocked issues (error, blocked-since time, last activity, placement), aggregate usage accounting, and polling status (whether a pass is in progress, time until the next pass, configured interval).
- The refresh response reports whether the request was coalesced, a refresh arriving while a pass is in progress or already due schedules no additional pass.

**Failure semantics**

- When the orchestrator is unavailable or slow, callers receive a distinguishable unavailable/timeout answer rather than a stale snapshot presented as fresh.

Implementation-defined mechanisms:

- Invocation mechanism, serialization, and rendering of the snapshot.
- The exact set of usage/accounting metrics beyond the run, retry, blocked, and polling views.

### Concurrency Limits Hold at Admission

A run is admitted only when, at admission time, the count of live runs stays within the global limit, within the configured limit for the issue's workflow state, and within the capacity of the chosen worker host; admissions within one scheduling pass observe each other's consumption.

**Intent**

Capacity is a shared budget across three dimensions; checking each dimension at the moment of admission keeps the budget honest even when many candidates arrive in the same pass.

**This prevents**

- Overcommitting hosts or the whole system when a pass finds more candidates than slots.
- One workflow state's issues starving the limits set aside for another state.

**Verification**

- Offer more eligible issues than each limit permits and verify the run count never exceeds any of the three limits, including mid-pass.

### Dispatch Uses a Fresh Snapshot

Every run is started from an issue snapshot read from the tracker immediately before the run starts, and only if that fresh snapshot is still a valid dispatch candidate.

**Intent**

Between discovery and dispatch (or across a retry delay) the issue may have been closed, blocked, or reassigned; the last read before launch closes that window.

**This prevents**

- Launching work from a stale poll result or from retry metadata that no longer reflects the tracker.

**Verification**

- Change an issue to a non-candidate state between poll and dispatch and verify the dispatch is skipped without error.

### Tracker Read Failure

A read against the tracker (discovery by states, refresh by identity, or the terminal-issue query) fails or the configuration needed to reach the tracker is invalid, so the orchestrator has no current answer about issue state.

Occurs during **Poll and Dispatch Tick**, **Reconcile Active Runs**, **Reconcile Blocked Issues**, **Retry Evaluation**, **Startup Workspace Cleanup**.

Retryability is **yes**.

**Required behavior**

- Treat absence of an answer as unknown, never as withdrawal; keep all live runs, blocks, claims, and schedules unchanged.
- Surface the failure reason for operator diagnosis.
- Continue the polling cadence so the read is retried on the next pass; a retry evaluation whose read failed re-schedules itself with grown, bounded delay.
- During startup cleanup, skip the cleanup and proceed with startup.

**Recovery**

Normal operation resumes automatically at the next successful read; no state reconstruction is needed because nothing was revoked.

### Agent Run Fails to Start

An admitted dispatch cannot bring the agent run into existence (process or resource acquisition fails) after the issue was revalidated.

Occurs during **Dispatch Issue**.

Retryability is **yes**.

**Required behavior**

- Record no live run and consume no capacity for the failed start.
- Schedule a retry with incremented attempt, carrying the failure reason and the intended worker host.

**Recovery**

The retry evaluation re-validates and re-dispatches; persistent inability to start surfaces as repeatedly growing retry delays visible to operators.

## 3. Retry and Reconciliation

Agent runs are assumed to fail, stall, and lie by omission, so the orchestrator supplies reliability from the outside. Every run ending is classified into exactly one outcome, a normal exit earns a prompt continuation check (completion of a run is not completion of the issue), an abnormal exit earns a retry whose delay grows with a preserved attempt history and is bounded above, and silence beyond the stall threshold is treated as failure. When a retry comes due, nothing is trusted, the issue is re-read from the tracker and re-admitted against current capacity, or deferred again. In parallel, every pass re-reads the issues behind live runs and blocks and revokes whatever the tracker no longer supports — carefully distinguishing a failed read (keep everything) from a successful read that omits an issue (stop that run). This chapter collects the ending handler, the retry evaluation, both reconciliation sweeps, the backoff invariant, and the crash, stall, and contention failures.

### Handle Run Ending

Translate the ending of an agent run into exactly one supervised outcome, a prompt continuation check after normal completion, a backoff retry after failure, or a blocked-issue record when the run required operator input.

Participants: **Run Supervision and Retry**, **Agent Run**, **Issue**, **Retry Schedule**, **Blocked Issue**.

The interaction begins when the process executing an agent run exits, normally or abnormally.

The interaction proceeds as follows:

1. **Run Supervision and Retry** Remove the run from live-run accounting (freeing its capacity) and capture its final recorded context, identity, placement, attempt, last observed activity.
2. **Agent Run** Yield its classification, whether its last observed activity marks it as requiring operator input, and whether the exit was normal.
3. **Blocked Issue** Come into existence, preserving the claim and diagnostic context, when the run required operator input — regardless of whether the exit was normal or abnormal.
4. **Retry Schedule** Come into existence otherwise, after a normal exit, a continuation check with a short fixed delay at attempt one; after an abnormal exit, a failure retry whose attempt continues the run's attempt history and whose delay grows with the attempt, carrying the error description and the run's placement affinity.
5. **Issue** Remain claimed in every outcome; the ending of a run never releases the issue back to open competition by itself.

On completion:

- The run no longer occupies any capacity.
- The issue is in exactly one of, blocked, or awaiting a scheduled re-evaluation.

- **MUST** — Treat a normal exit as a trigger for a prompt tracker re-check, not as evidence the issue is finished.
- **MUST** — Give the input-required classification precedence over both the normal and abnormal outcome paths.
- **MUST NOT** — Lose the attempt count, error context, or placement affinity when converting a run ending into a retry schedule.

Constrained by **Retry Backoff Grows and Is Bounded**, **Blocked Issues Are Never Auto-Retried**.

Defined failures: **Agent Run Exits Abnormally**, **Run Requires Operator Input**.

### Retry Evaluation

When a retry schedule comes due, decide from fresh tracker state and current capacity whether to re-dispatch the issue, release it, clean up after it, or defer again.

Participants: **Run Supervision and Retry**, **Scheduling and Dispatch**, **Workspace Management and Safety**, **Retry Schedule**, **Issue**, **Tracker**, **Workspace**.

The interaction begins when an issue's retry schedule becomes due.

Before it begins:

- The due schedule is the issue's current one; superseded or cancelled schedules have no effect when they fire.

The interaction proceeds as follows:

1. **Retry Schedule** Fire, surrendering its attempt number and preserved context to the evaluation.
2. **Tracker** Answer a fresh read of the issue by identity.
3. **Run Supervision and Retry** If the read failed, defer, schedule the next attempt with grown delay rather than guessing. If the issue is now in a terminal state, release the claim and have the issue's workspace removed. If the issue is missing or no longer a dispatch candidate, release the claim without removing the workspace.
4. **Scheduling and Dispatch** If the issue is still a candidate, admit it only within global, per-state, and worker-host capacity, honoring the preserved host affinity; when capacity is unavailable, defer with a grown delay instead of overcommitting.
5. **Workspace Management and Safety** Remove the issue's recorded workspace when the terminal-state path was taken.
6. **Issue** Re-enter execution via Dispatch Issue when admitted, at the preserved attempt number.

On completion:

- The issue is running again, released, or re-scheduled; a due retry never leaves the issue in an undefined limbo.

- **MUST** — Base the retry decision on a tracker read performed at retry time, never on the snapshot that scheduled the retry.
- **MUST** — Remove the issue's workspace when the tracker shows the issue terminal at retry time.
- **MUST NOT** — Act on a retry schedule that has been superseded by a newer one for the same issue.

Constrained by **Tracker Authority Converges**, **Retry Backoff Grows and Is Bounded**, **Concurrency Limits Hold at Admission**.

Defined failures: **Tracker Read Failure**, **No Capacity at Retry Time**, **Workspace Removal Fails**.

### Reconcile Active Runs

Align every live run with tracker truth and with observed liveness, stop runs the tracker has withdrawn, refresh snapshots for runs still valid, and restart or block runs that have gone silent.

Participants: **Tracker Reconciliation**, **Run Supervision and Retry**, **Tracker**, **Agent Run**, **Issue**, **Workspace**.

The interaction begins when a scheduling pass begins and at least one run is live.

The interaction proceeds as follows:

1. **Run Supervision and Retry** Examine each run's last observed activity; when a stall threshold is configured and a non-blocked run has been silent longer than the threshold, stop it and either block it (if its activity marks it input-required) or schedule a failure retry continuing its attempt history.
2. **Tracker** Answer a read of all remaining running issues by identity.
3. **Tracker Reconciliation** If that read failed, keep all runs unchanged. Otherwise, for each reported issue, stop the run and remove the workspace when the state is terminal; stop the run and keep the workspace when the issue is unroutable or has left the active states; refresh the run's stored snapshot when the issue is still active.
4. **Tracker Reconciliation** Stop the run and keep the workspace for every running issue the successful read did not report at all.
5. **Agent Run** When stopped by reconciliation, terminate promptly and release the issue's claim entirely (no retry is scheduled for tracker-withdrawn runs).
6. **Issue** Carry the refreshed snapshot for still-active runs, so per-state capacity accounting and later decisions use current workflow states.

On completion:

- No run remains live for an issue the tracker reported terminal, non-active, unroutable, or absent.
- Stall handling never touched runs already awaiting operator input as blocked.

- **MUST** — Distinguish a failed tracker read (keep everything) from a successful read that omits an issue (stop that issue's run).
- **MUST** — Remove the workspace only on the terminal-state path, not when stopping for non-active, unroutable, or missing issues.
- **MUST NOT** — Automatically restart a stalled run whose observed activity marks it as requiring operator input.

Constrained by **Tracker Authority Converges**, **Blocked Issues Are Never Auto-Retried**.

Defined failures: **Tracker Read Failure**, **Agent Run Stalls**, **Run Requires Operator Input**.

### Reconcile Blocked Issues

Re-check every blocked issue against the tracker and release the block exactly when a human-visible change has occurred, keeping operator escalations alive until then.

Participants: **Tracker Reconciliation**, **Tracker**, **Blocked Issue**, **Issue**, **Workspace**.

The interaction begins when a scheduling pass begins and at least one issue is blocked.

The interaction proceeds as follows:

1. **Tracker** Answer a read of all blocked issues by identity.
2. **Tracker Reconciliation** If the read failed, keep every block unchanged. Otherwise, release the block and claim when the issue is terminal (also removing its workspace), unroutable, outside the active states, or absent from the successful read; refresh the block's stored snapshot when the issue is still active.
3. **Blocked Issue** Persist with refreshed context while the issue stays active, so operators keep seeing an accurate escalation.
4. **Issue** Become eligible for future scheduling passes again once its claim is released.

On completion:

- Every remaining block corresponds to an issue the tracker still reports as active and routed here.
- No block was released merely because time passed or the tracker was unreachable.

- **MUST** — Release a block only on tracker-observed change, terminal, non-active, unroutable, or absent under a successful read.
- **MUST** — Remove the blocked issue's workspace only on the terminal-state release path.

Constrained by **Tracker Authority Converges**, **Blocked Issues Are Never Auto-Retried**.

Defined failures: **Tracker Read Failure**.

### Retry Backoff Grows and Is Bounded

Failure retry delays are strictly positive, non-decreasing in the attempt number, and never exceed the configured maximum backoff; the attempt number carried by a retry continues the issue's prior attempt history rather than resetting on each failure. The continuation check after a normal completion uses a short fixed delay and does not count as a failure attempt.

**Intent**

Growth prevents hot-looping against a persistently failing issue or tracker; the bound preserves eventual re-evaluation; preserved history keeps growth meaningful across successive failures.

**This prevents**

- Tight crash-restart loops consuming capacity and tracker quota.
- Unbounded delays that would effectively abandon an issue.

**Verification**

- Force repeated failures and verify the observed delays are non-decreasing, capped at the configured maximum, and derived from a continuing attempt count.

### Agent Run Exits Abnormally

A live agent run terminates for any reason other than normal completion — crash, kill, or infrastructure error — without its last observed activity marking it as requiring operator input.

Occurs during **Handle Run Ending**.

Retryability is **yes**.

**Required behavior**

- Free the run's capacity and keep the issue claimed.
- Schedule a failure retry whose attempt continues the run's attempt history, carrying the exit reason and the run's worker-host and workspace affinity.
- Record the ending with enough context (issue, session, reason) for diagnosis.

**Recovery**

The retry evaluation re-reads the tracker and re-dispatches into the preserved workspace when the issue is still eligible and capacity allows, so prior partial work is available to the next run.

### Agent Run Stalls

A live, non-blocked run has produced no observed activity for longer than the configured stall threshold (measured from the last agent event or, absent any event, from run start). A threshold of zero disables stall detection.

Occurs during **Reconcile Active Runs**.

Retryability is **yes**.

**Required behavior**

- Stop the run promptly and free its capacity, preserving the issue's workspace.
- If the run's activity marks it input-required, block the issue instead of retrying.
- Otherwise schedule a failure retry continuing the attempt history, recording the stall duration as the error context.

**Recovery**

Same as an abnormal exit, tracker-revalidated re-dispatch with bounded backoff into the preserved workspace.

### No Capacity at Retry Time

A retry comes due for a still-eligible issue, but the global limit, the issue-state limit, or worker-host capacity leaves no slot to admit it.

Occurs during **Retry Evaluation**.

Retryability is **yes**.

**Required behavior**

- Do not overcommit; leave the issue claimed and re-schedule with an incremented attempt and grown, bounded delay.
- Preserve the retry context (error, affinity) across the deferral.

**Recovery**

A later retry evaluation admits the issue when capacity frees up; the bounded backoff guarantees re-evaluation keeps happening.

## 4. Workspace Management and Safety

Every issue works inside one deterministic, isolated directory derived from its identifier — reused across retries and continuations so work accumulates, and removed only when the tracker declares the issue terminal. Because provisioning and cleanup run recursive filesystem operations, locally and on remote hosts, safety is absolute rather than best-effort, every path is validated to sit strictly inside the configured root (never equal to it, never escaping it through symlinks) before anything destructive happens, and identity derivation is collision-free even for hostile identifiers. Operator hooks customize the lifecycle at creation, around runs, and before removal, with asymmetric failure semantics, setup hooks gate progress, teardown hooks never block it. This chapter covers provisioning, startup cleanup of terminal issues' leftovers, the hook interface, the two safety invariants, and the provisioning and cleanup failures.

### Provision Workspace

Produce the issue's isolated workspace on a given placement, creating it if absent, reusing it if present, validating containment, and running the operator's post-creation hook exactly when a fresh directory was created.

Participants: **Workspace Management and Safety**, **Issue**, **Workspace**, **Worker Host**.

The interaction begins when a dispatch needs the issue's workspace.

The interaction proceeds as follows:

1. **Workspace Management and Safety** Derive the workspace identity deterministically from the issue's human-readable identifier, sanitizing unsafe characters and, when sanitization changes the identifier, appending a collision-safe discriminator derived from the original identifier.
2. **Workspace Management and Safety** Resolve the workspace path under the configured root for the placement and validate it, rejecting paths equal to the root, outside the root, escaping the root via symlinks, or (for remote placements) unrepresentable as a safe path.
3. **Workspace** Be reused as-is when it already exists as a directory; otherwise be freshly created (replacing any non-directory obstruction at the path).
4. **Worker Host** Perform the existence check and creation on its own filesystem when the placement is remote, reporting unambiguously whether a fresh directory was created.
5. **Workspace Management and Safety** Run the operator's after-create hook inside the workspace only when a fresh directory was created, under the configured hook timeout; on hook failure or timeout, remove the freshly created directory and fail the provisioning.

On completion:

- On success, the workspace exists, satisfies containment, and is either the prior contents (reuse) or fully initialized (fresh creation with a successful hook).
- On failure, no half-initialized fresh workspace remains.

- **MUST** — Run the after-create hook only for freshly created workspaces, never on reuse.
- **MUST** — Fail provisioning (rather than proceed) when the after-create hook fails, and remove the fresh directory it ran in.
- **MUST NOT** — Create or operate on a workspace path that fails containment validation.

Constrained by **Workspace Containment**, **Deterministic Workspace Identity**.

Defined failures: **Workspace Provisioning Fails**.

### Startup Workspace Cleanup

At orchestrator startup, remove leftover workspaces belonging to issues the tracker already reports in terminal states, reclaiming space from work finished in previous sessions.

Participants: **Workspace Management and Safety**, **Tracker**, **Issue**, **Workspace**, **Worker Host**.

The interaction begins when the orchestrator starts, before its first scheduling pass.

The interaction proceeds as follows:

1. **Tracker** Report the issues currently in the configured terminal workflow states.
2. **Workspace Management and Safety** For each reported terminal issue, derive its workspace identity and remove the workspace, running the operator's before-remove hook first where the workspace exists, and tolerating hook failure.
3. **Worker Host** Perform the removal on every configured remote host when remote placements are configured, since the issue may have run on any of them; otherwise remove locally.
4. **Workspace** Cease to exist for terminal issues, subject to containment validation of every removed path.

On completion:

- Workspaces of tracker-terminal issues no longer consume space on any configured placement, where removal succeeded.

- **MUST** — Skip the cleanup entirely (and proceed with startup) when the terminal-issue read fails; startup never depends on cleanup success.
- **MUST NOT** — Remove any path that fails containment validation, even during bulk cleanup.

Constrained by **Workspace Containment**.

Defined failures: **Tracker Read Failure**, **Workspace Removal Fails**.

### Workspace Lifecycle Hooks

Operator-supplied commands that customize workspace lifecycle moments, executed inside the workspace on its placement, with defined timeout and failure semantics per hook point.

**Input semantics**

- Each hook is an operator-configured command bound to one lifecycle point, after a workspace is freshly created, before a run starts, after a run ends, or before a workspace is removed.
- Hooks execute with the workspace as working directory, on the same placement (local or remote host) as the workspace, under a configured timeout.

**Output semantics**

- A hook succeeds when its command exits successfully within the timeout; the after-create hook runs only for freshly created workspaces, and the before-remove hook runs only when the workspace exists.

**Failure semantics**

- After-create hook failure or timeout aborts provisioning and removes the fresh workspace.
- Before-run hook failure prevents the run from starting.
- After-run and before-remove hook failures are recorded but do not block the surrounding operation.
- Hook output captured for diagnostics is bounded in size before logging.

Implementation-defined mechanisms:

- The shell, environment, and remote-execution transport used to run hook commands.
- The timeout value (configured by the operator).

### Workspace Containment

Every workspace path used for creation or destructive removal resolves strictly inside the configured workspace root for its placement, is never equal to the root, and does not escape the root through symlinks; paths failing validation are rejected, not repaired.

**Intent**

Recursive deletion is the most dangerous operation the orchestrator performs; containment converts a misconfiguration or crafted identifier into a refusal instead of data loss.

**This prevents**

- Deleting the workspace root or arbitrary directories via traversal, absolute-path, or symlink tricks.

**Verification**

- Attempt provisioning and removal with paths that equal the root, live outside it, and symlink out of it, and verify each is rejected with no filesystem effect.

### Deterministic Workspace Identity

An issue's workspace identity is a pure function of its human-readable identifier, safe for use as a directory name, and collision-free, two distinct identifiers never yield the same identity, and any party knowing only the identifier derives the same identity.

**Intent**

Determinism lets retries and continuations resume prior work, and lets cleanup target exactly the right directory from an identifier alone; collision-freedom keeps isolation honest when identifiers contain unsafe characters.

**This prevents**

- Two issues sharing (and corrupting) one workspace after identifier sanitization.
- Cleanup removing a different issue's workspace.

**Verification**

- Derive identities for identifiers that sanitize to the same safe form and verify they differ; derive the same identifier twice from different call sites and verify equality.

### Workspace Provisioning Fails

The issue's workspace cannot be produced, path validation rejects it, creation fails locally or on the remote host, the remote host cannot confirm an unambiguous result, or the after-create hook fails or times out.

Occurs during **Provision Workspace**, **Dispatch Issue**.

Retryability is **yes**.

**Required behavior**

- Start no agent run for the issue on this attempt.
- Remove a freshly created directory when provisioning fails after creation, so no half-initialized workspace persists.
- Never bypass or weaken containment validation to make provisioning succeed.
- Surface the cause, and follow the dispatch failure path (retry with backoff) for the issue.

**Recovery**

Retries re-attempt provisioning; a reused (previously existing) workspace is left untouched by a failed provisioning attempt.

### Workspace Removal Fails

A removal that should delete an issue's workspace cannot complete, the recorded path fails validation, the filesystem or remote host errors, or the remote command fails.

Occurs during **Startup Workspace Cleanup**, **Retry Evaluation**.

Retryability is **yes**.

**Required behavior**

- Report the failure with its cause; never escalate by deleting outside validated containment.
- Leave orchestration decisions unaffected, claim release and scheduling proceed even when cleanup fails.
- Treat before-remove hook failure as non-blocking for the removal itself.

**Recovery**

A later cleanup opportunity (startup cleanup, a subsequent terminal observation) may remove the directory; stale directories are a space cost, not a correctness fault.

## Implementation-Defined Areas

### Execution and concurrency model

The orchestrator may be a single serialized process, multiple cooperating processes, or any other topology; run supervision may use any process-monitoring or job-control mechanism.

Fixed semantics:

- Scheduling admission behaves as a single decision authority; concurrent admissions cannot jointly exceed a limit.
- Every run ending is observed and resolved to exactly one supervised outcome.

### Timer and cadence mechanism

Polling, retry due-times, and stall measurement may use any clock and timer facility. Guarding against stale timer firings (tokens, generation counters, cancellation) is a mechanism choice.

Fixed semantics:

- The next scheduling pass is measured from the completion of the previous pass.
- A superseded or cancelled retry schedule has no effect when its timer fires.
- Stall elapsed time is measured against the run's last observed activity, falling back to run start.

### Backoff curve shape

The exact growth function for failure retry delays (exponential base, initial delay, jitter) is free.

Fixed semantics:

- Delays are positive, non-decreasing in attempt number, and capped at the operator-configured maximum backoff.
- The post-completion continuation check uses a short fixed delay, materially shorter than failure backoff, and does not advance the failure attempt count.

### Worker host selection tie-breaking

Among hosts with available capacity, any load-balancing choice and any deterministic or randomized tie-break is acceptable when no affinity preference applies.

Fixed semantics:

- A preferred (previously used) host with available capacity is chosen over balancing.
- A host at its per-host limit is never chosen.
- When remote hosts are configured and none has capacity, no dispatch occurs.

### Dispatch ordering encoding

How priority values, missing priorities, and missing creation times are encoded into a sort is free, as is the identifier tiebreak's collation.

Fixed semantics:

- More urgent priority is dispatched before less urgent; issues without a recognized priority come after all prioritized issues.
- Within equal priority, earlier-created issues come first; issues without a creation time come last.
- The final tiebreak is deterministic across passes.

### Workspace storage and remote transport

Local filesystem layout under the root, the remote-execution transport (SSH or otherwise), shell quoting strategy, and the collision discriminator's construction (hash function, length) are free.

Fixed semantics:

- Workspace identity remains a deterministic, collision-free pure function of the issue identifier.
- Containment validation (root membership, root inequality, symlink-escape rejection) is enforced before destructive operations.
- Remote provisioning yields an unambiguous created-versus-reused answer or fails.

### Configuration source and reload

Where configuration lives (file, service), its format, and how changes are detected are free.

Fixed semantics:

- Cadence and capacity settings are re-read so operator changes take effect without restart, no later than the next scheduling pass.
- Invalid or missing configuration fails a scheduling pass safely (no dispatch, existing runs untouched) with a diagnosable reason.

### Observability depth

Additional metrics (token accounting, rate-limit visibility, session details) beyond the required snapshot views may be collected and exposed in any form.

Fixed semantics:

- The snapshot's run, retry, blocked, and polling views reflect actual orchestration state; observability reads never mutate it.

## Reference Implementation

The reference implementation is the Elixir orchestrator in the Symphony repository (elixir/lib/symphony_elixir/), a single GenServer (SymphonyElixir.Orchestrator) that serializes all scheduling decisions, supervises agent runs as monitored tasks under a Task.Supervisor, and delegates tracker access, workspace management, and configuration to sibling modules. It realizes this specification but adds no normative requirements; mechanisms listed below are reference-specific choices.

The reference implementation is **not normative**; it is one realization of this specification.

## Conformance

Implement a conforming realization of this specification. Preserve normative semantics and design intent. Do not infer additional constraints from the reference implementation. Where behavior is implementation-defined, choose a reasonable mechanism that preserves all stated invariants.

A conforming implementation:

- satisfies applicable normative semantics.
- preserves conceptual relationships and responsibility boundaries.
- implements the defined interactions and lifecycle semantics.
- preserves invariants and defined failure behavior.
- may choose different mechanisms where implementation freedom is declared.
- does not treat reference-specific choices as additional requirements.
