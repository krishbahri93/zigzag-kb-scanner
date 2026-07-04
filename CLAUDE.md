# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working in this codebase

The user has no coding experience and does not understand how coding, git, or
GitHub work. **Explain everything step by step, in plain language, and over-explain
rather than under-explain.** Before running anything that changes files or git state,
describe what you are about to do and why, and make sure the user understands before
proceeding. Avoid jargon; when a technical term is unavoidable, define it simply.

The user relies on Claude to handle git safely.

**Whenever you make a change, use git and work on a branch — never commit directly to `main`.**

For any change:
1. Create a new branch before editing (e.g. `git checkout -b short-description-of-change`).
2. Make the change on that branch.
3. Commit it there with a clear message.
4. Tell the user what the branch is called and explain in plain language what changed, so they can review or merge it.

Do not push, merge into `main`, or delete branches unless the user explicitly asks.
