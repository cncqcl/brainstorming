# Natural-Language Draft Inbox Redesign

## Purpose

This redesign changes Brainstorm Tool from a form-first idea database into a
thinking inbox. The user should be able to write a rough note, paste a message,
or speak through an agent client without knowing the internal schema. The system
captures the raw message first, then lets an LLM-backed coding agent refine it
into structured ideas, comments, concerns, research prompts, and graph
connections.

The CLI remains useful, but only as an internal contract for agents, tests, and
the dashboard backend. It should not be presented as the normal user workflow.

## Current Problem

The existing project already supports ideas, versions, comments, annotations,
attachments, agent notes, and deterministic relationships. That is a good
foundation, but the user workflow still assumes someone can register a complete
idea with title, briefing, status, and content.

That is not how the tool is expected to be used. A normal user writes something
closer to a message:

> I want a project that collects coding agent best practices and keeps updating
> with new tools from GitHub, YouTube, and Reddit.

The system should accept that immediately. Structure should be generated later
by an agent and reviewed by the user before it mutates the accepted idea
database.

## Recommended Direction

Use three layers:

1. Human layer: natural language only.
2. Agent skill or command layer: tells the coding agent how to perform the
   refinement.
3. Internal tool layer: deterministic CLI, API, database, and explicit graph
   records.

The user-facing product should feel like this:

- "Record this idea..."
- "Add a new idea: ..."
- "Refine my drafts."
- "Find concerns for this idea."
- "Suggest connections between these ideas."
- "Turn this draft into a project plan."

The internal system can still use explicit commands, JSON payloads, and record
IDs, but those details should be hidden from ordinary users. The one exception
is a draft ID, because it gives the user and agent a simple shared handle such
as "draft 12".

## Dashboard Design

The dashboard should make quick capture the primary action. Replace the current
form-like "new idea" entry with a natural-language capture panel.

Main workspace areas:

- Inbox: raw draft messages that have not yet become accepted ideas.
- Ideas: accepted idea records with briefing, status, version, and activity.
- Graph: deterministic idea connections, including agent-suggested connections
  after the user accepts them.
- Context panel: comments, concerns, annotations, attachments, and agent notes.

The main page should answer:

- What have I captured recently?
- What needs review?
- Which ideas are active?
- Which ideas are connected?
- What should I ask an agent to do next?

The user should not need to choose a database operation. A single prompt box
captures rough ideas. Each captured draft receives a visible ID. The dashboard
can provide a simple "Refine" action that copies or displays a short agent
prompt:

```text
Refine draft 12 using the Brainstorm Tool project skill. Ask me any needed
questions, update the local database when the refined idea is ready, and tell me
to refresh the dashboard.
```

The dashboard does not need to manage an LLM job lifecycle. It records the draft,
shows its ID, provides a prompt for the agent, and lets the user refresh after
the agent updates the database.

The same capture behavior must be available through coding agents. If the user
tells an agent "add a new idea: ..." or "record this idea: ...", the project
skill should create a captured draft, return the draft ID, and tell the user
they can refine it now or later from the dashboard.

## Data Model Changes

Add an `idea_drafts` table for raw capture.

Suggested fields:

- `id`
- `raw_message`
- `source`
- `status`: `captured`, `refining`, `accepted`, `archived`
- `created_at`
- `updated_at`
- `refinement_prompt`
- `last_refined_at`
- `accepted_idea_id`

Keep drafts separate from accepted ideas. A draft is evidence of what the user
actually said. An accepted idea is the curated project record.

Do not keep proposal review in the normal draft-refinement path. The ordinary
path is: draft ID, agent discussion, direct database update, dashboard refresh.
Proposal-style review can be reintroduced later for risky actions such as graph
rewrites, merges, or bulk updates.

## Agent Skill Behavior

Create a project-specific Codex skill or command, for example
`brainstorming-project-agent`, that tells agents how to operate this repository.
The dashboard "Refine" button should return a short prompt that points the agent
to this skill or command and names the draft ID.

The skill should say:

- Users speak naturally; never ask them to provide JSON, IDs, flags, or file
  paths unless debugging.
- If the user says "record", "capture", "register", or "add this idea", create
  a draft first.
- If the user says "add a new idea: ..." in an agent session, create a captured
  draft and return its ID. Do not force immediate refinement.
- If the user says "refine draft N", load that captured draft, inspect nearby
  accepted ideas, ask the user any needed questions, then update the database.
- If the user says "connect ideas", propose relationships instead of silently
  changing the graph.
- If the user asks for research, search externally in the agent runtime and
  submit recommendations as agent notes.
- Confirm before applying broad, destructive, or ambiguous changes.

This skill is the real user interface for CodeX, Claude Code, OpenCode, and
phone-based agent clients. The CLI is only the tool the skill uses.

## Internal Operations

Internal operations should be stable and boring. They can have arguments because
agents and tests will call them, not ordinary users.

Needed operations:

- Capture draft.
- List drafts.
- Show draft.
- Emit refinement prompt for a draft.
- Mark draft as refining.
- Mark draft as accepted and link it to an accepted idea.
- Suggest graph connections.
- Add agent note.

Where possible, commands should return machine-readable output and clear status
messages. The dashboard can use the API equivalents.

## Refinement Flow

The recommended default flow is:

1. User writes a rough message.
2. System stores it as a captured draft with an ID.
3. User clicks "Refine" and receives a short prompt such as "Refine draft 12
   using the Brainstorm Tool project skill."
4. User pastes that prompt into CodeX, Claude Code, OpenCode, or another coding
   agent.
5. The agent runs the project skill or command, reads the draft by ID, inspects
   existing ideas, asks the user any needed questions, and updates the database.
6. The agent marks the draft accepted and links it to the accepted idea.
7. User refreshes the dashboard and sees the refined idea, notes, and
   connections.

This preserves the original message while still using LLM strength for
organization, summarization, critique, and connection discovery.

## Research Flow

Web search should remain outside this app in v1. The app should prepare prompts
and store results.

The agent can:

- Search comparable projects, GitHub repositories, discussions, and examples.
- Summarize findings.
- Recommend next actions.
- Add concerns and open questions.
- Suggest links to existing ideas.

The app stores useful submitted results as agent notes. This avoids building a
web-search subsystem too early.

## Implementation Sequence

1. Add `IdeaDraft` domain model and `idea_drafts` persistence.
2. Add API routes for natural-language draft capture and draft listing.
3. Add dashboard Inbox and Quick Capture panels.
4. Add a dashboard "Refine" action that emits a short agent prompt for the draft
   ID.
5. Add internal CLI/API operations for draft capture, prompt generation, and
   accepted-draft linking. The same draft capture operation is used by the
   dashboard and by coding agents.
6. Add a project Codex skill that captures "add a new idea: ..." as a draft and
   performs actual draft refinement from the draft ID.
7. Add proposed graph connection review before accepted relationship creation.
8. Add tests for draft capture, prompt generation, accepted-draft linking, and
   dashboard API behavior.

## Open Design Question

The main resolved product decision is that the dashboard should not run or
simulate an agent job in v1. It captures drafts and emits simple prompts that
users paste into coding agents.

The second resolved product decision is that ordinary draft refinement can
update the database directly after the agent has interacted with the user. A
separate dashboard proposal review is not required for the normal path.
Proposals remain useful for risky actions such as graph rewrites, merges, and
bulk changes.
