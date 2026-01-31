# Agent-Driven Incremental Development Workflow

## Purpose

This document defines the **canonical workflow** for building systems using
AI agents (ChatGPT, Antigravity, etc.) as **implementers**, while maintaining
tight scope control, correctness, and momentum.

This workflow is optimized for:
- event-driven systems
- PoCs that must survive real-world failure modes
- multi-agent collaboration without confusion or scope creep

---

## Roles

### Human (Orchestrator)
- Owns the repository
- Runs the agent
- Commits and ships code
- Decides when a step is complete

### ChatGPT (Spec + Prompt Author)
- Produces incremental Markdown specs (MDs)
- Produces agent prompts tied to those MDs
- Reviews agent output for correctness
- Provides commit messages and summaries

### Agent (Implementer)
- Reads MD
- Writes or modifies code to satisfy the MD
- Summarizes changes
- Does NOT redesign scope or suggest future steps

---

## Core Loop (Repeat Per Step)

1. **Spec Creation**
   - ChatGPT produces:
     - ONE Markdown spec (MD)
     - ONE agent prompt that references the MD
   - The MD defines:
     - purpose
     - in-scope behavior
     - out-of-scope guardrails
     - success criteria

2. **Implementation**
   - Human downloads the MD and places it in `/prompts/`
   - Human runs the agent with the provided prompt
   - Agent implements the MD

3. **Review**
   - Human pastes agent output back to ChatGPT
   - ChatGPT verifies:
     - scope discipline
     - correctness vs MD
     - absence of forbidden behavior

4. **Commit**
   - If approved:
     - ChatGPT provides a git commit message
     - Human commits and pushes
   - If not approved:
     - MD or implementation is corrected
     - Same step is rerun

5. **Advance**
   - Only after approval does ChatGPT produce the next MD

---

## Invariants (Non-Negotiable)

- One MD at a time
- One concern per MD
- No skipping steps
- No “future work” inside current step
- Explicit failure handling > silent assumptions
- Never drop core events due to missing context

---

## Design Principles

- Prefer **explicit uncertainty** over guessing
- Prefer **downgrade-not-reject** behavior
- Treat agents as **builders**, not auditors
- Treat MDs as **contracts**, not suggestions

---

## When to Stop

A PoC is complete when:
- Real data flows end-to-end
- Failure modes are observed and safe
- Logs tell a coherent causal story
- Downstream consumers can reason without special cases
