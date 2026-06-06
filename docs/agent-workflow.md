# Agent Workflow

Users speak naturally. Do not ask users to call CLI commands directly unless
debugging the tool itself.

## Capture Drafts

If the user says "add a new idea: ...", "record this idea: ...", or similar:

1. Capture the message as a draft with source `agent`.
2. Return the draft ID.
3. Ask whether the user wants to refine it now or later.

Use the internal draft capture operation. Do not force the user to provide a
title, brief, status, JSON payload, or file path.

## Refine Drafts

If the user says "refine draft N":

1. Load draft N.
2. Read existing idea summaries and graph context.
3. Ask at most one clarifying question at a time when needed.
4. Create a new accepted idea or update an existing accepted idea directly.
5. Add research notes only when useful findings or concerns are concrete.
6. Add deterministic relationships only when the connection is explicit enough
   to explain with a short label.
7. Mark the draft accepted and link it to the accepted idea.
8. Tell the user to refresh the dashboard.

The normal draft refinement path does not require dashboard proposal review.
Reserve proposal-style review for risky future actions such as bulk graph
rewrites, merges, or destructive updates.

## Research

External search happens in the agent runtime, not in the dashboard. Store useful
results as agent notes on the accepted idea.

## Internal Commands

Agents may use internal CLI/API operations such as draft capture, draft show,
draft refine prompt, idea add, idea update, agent note add, relationship add, and
draft accept. These are not user-facing commands.
