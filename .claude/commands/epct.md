---
description: Execute a structured EPCT workflow (Explore, Plan, Code, Test)
allowed-tools:
  [
    Read,
    Write,
    Edit,
    Glob,
    Grep,
    Bash,
    Task,
    TodoWrite,
    mcp__ide__getDiagnostics,
  ]
argument-hint: [task description]
---

# EPCT Workflow: $ARGUMENTS

You will follow the EPCT (Explore, Plan, Code, Test) methodology to complete this task systematically and thoroughly.

## Context & Purpose

EPCT is a structured development workflow that ensures thorough understanding before implementation:

- **Explore**: Understand the codebase and requirements deeply
- **Plan**: Design the solution architecture before coding
- **Code**: Implement changes following the plan
- **Test**: Verify the implementation works correctly

This approach reduces errors, improves code quality, and ensures nothing is overlooked.

## Phase 1: EXPLORE

**Objective**: Gather comprehensive understanding of the task context.

**Actions to take**:

1. **Read relevant files** - Use Read, Glob, and Grep to understand:

   - Existing code that will be modified or referenced
   - Related components and their interactions
   - Configuration files and dependencies
   - Test files for similar features

2. **Analyze patterns** - Identify:

   - Coding conventions and style in this project
   - Architecture patterns being used
   - Similar implementations to learn from
   - Potential edge cases and requirements

3. **Ask clarifying questions** if the requirements are ambiguous:
   - Use AskUserQuestion for critical decisions
   - Clarify scope, constraints, and expectations

**IMPORTANT**: Do NOT speculate about code you haven't read. Always inspect files before making assumptions.

**Output**: Provide a brief summary of findings and confirm understanding of:

- What needs to be changed
- Where changes will occur
- What existing patterns to follow

---

## Phase 2: PLAN

**Objective**: Design a clear implementation strategy before writing code.

**Actions to take**:

1. **Create a todo list** using TodoWrite with specific, actionable tasks:

   - Break down the work into logical steps
   - Identify file creation, modification, and deletion needs
   - Note any refactoring or cleanup required
   - Include testing steps

2. **Design the solution**:

   - Outline the approach and architecture
   - Identify which files will be created/modified
   - Consider error handling and edge cases
   - Plan for backwards compatibility if needed

3. **Validate the plan**:
   - Ensure the approach follows project conventions
   - Verify all requirements are addressed
   - Check for potential conflicts or issues

**Key Principle**: "Plan the work, then work the plan." A good plan prevents costly refactoring later.

**Output**: Present the implementation plan with:

- List of files to create/modify
- Step-by-step approach
- Any architectural decisions
- Expected challenges or risks

---

## Phase 3: CODE

**Objective**: Implement the solution following the plan precisely.

**Actions to take**:

1. **Follow the plan incrementally**:

   - Mark todos as in_progress before starting
   - Complete one task at a time
   - Mark todos as completed immediately after finishing
   - Keep exactly ONE todo in_progress at any time

2. **Write quality code**:

   - Follow existing project patterns and conventions
   - Add comments only where logic isn't self-evident
   - Use TypeScript types appropriately
   - Handle errors at system boundaries only
   - Avoid over-engineering - keep solutions minimal

3. **Update todos continuously**:
   - Use TodoWrite after each completed task
   - Add new tasks if unexpected work is discovered
   - Remove tasks that become irrelevant

**Key Principles**:

- "Implement changes rather than only suggesting them"
- Focus on the specific requirements - no extra features
- Use EXACTLY the values/names specified by the user
- Prefer editing existing files over creating new ones

**Anti-patterns to avoid**:

- Don't add features beyond what was requested
- Don't refactor unrelated code
- Don't add error handling for impossible scenarios
- Don't create abstractions for one-time operations

---

## Phase 4: TEST

**Objective**: Verify the implementation works correctly and completely.

**Actions to take**:

1. **Run existing tests**:

   - Execute relevant test suites
   - Check for any broken tests
   - Verify test coverage if applicable

2. **Manual verification**:

   - If it's a UI change, describe what to test visually
   - For backend changes, suggest manual test scenarios
   - Use mcp**ide**getDiagnostics to check for type errors

3. **Mark completion**:
   - Mark the final todo as completed only when ALL tests pass
   - Summarize what was accomplished
   - Note any follow-up work needed

**IMPORTANT**:

- Only mark tasks completed when FULLY accomplished
- If tests fail, keep the task in_progress and fix issues
- Never mark completed if errors remain unresolved

**Output**: Provide test results and confirmation that:

- All requirements are met
- Tests are passing
- No errors or warnings introduced
- The implementation is production-ready

---

## Workflow Execution Guidelines

Throughout the EPCT process:

✅ **DO**:

- Be proactive and take initiative when requirements are clear
- Use tools in parallel when operations are independent
- Update todos in real-time as you work
- Read files before suggesting changes
- Follow project conventions strictly
- Focus on incremental progress

❌ **DON'T**:

- Skip phases or rush to implementation
- Batch multiple todo updates
- Speculate about unread code
- Add unrequested features
- Create files unnecessarily
- Over-engineer solutions

---

## Summary

The EPCT workflow ensures systematic, high-quality development:

1. **Explore** → Understand deeply before acting
2. **Plan** → Design before implementing
3. **Code** → Execute the plan incrementally
4. **Test** → Verify everything works

Now, let's begin the EPCT workflow for: **$ARGUMENTS**

Starting with Phase 1: EXPLORE...
