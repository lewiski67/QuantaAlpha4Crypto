# Engineering Workflow

## Name

engineering-workflow

## Overview

Use this skill for non-trivial software development work.

This skill combines five workflow disciplines:

1. Writing an implementation plan before touching code.
2. Executing the plan step by step.
3. Using test-driven development for implementation.
4. Requesting code review at task or feature checkpoints.
5. Verifying before claiming completion.

Core principle:

```text
Plan first.
Execute exactly.
Test first.
Review early.
Verify before claiming completion.
```

No production code without a failing test first.

No completion claim without fresh verification evidence.

---

## When to Use

Use this skill when:

* Implementing a feature.
* Fixing a bug.
* Refactoring.
* Making behavior changes.
* Executing a written implementation plan.
* Completing a major task.
* Preparing to merge or claim work is complete.

Possible exceptions:

* Throwaway prototypes.
* Generated code.
* Configuration-only changes.
* Pure documentation edits.
* Tiny mechanical changes.

If skipping this workflow, state why.

---

# Phase 1: Write the Plan

Before touching code, create an implementation plan.

Announce:

```text
I'm using the engineering-workflow skill to create and execute an implementation plan.
```

The plan must assume that the implementer has limited context about the codebase, toolset, and problem domain.

The plan must be specific enough that another competent engineer could execute it without guessing.

## 1.1 Scope Check

Before writing tasks, check whether the work covers multiple independent subsystems.

If it does, recommend splitting the work into separate plans, one per subsystem.

Each plan should produce working, testable software on its own.

## 1.2 File Structure

Before defining tasks, map out the files that will be created or modified.

For each file, state what it is responsible for.

Guidelines:

* Design units with clear boundaries and well-defined interfaces.
* Prefer focused files over files that do too much.
* Files that change together should live together.
* Split by responsibility.
* In existing codebases, follow established patterns.
* Do not unilaterally restructure an existing codebase.
* If a file being modified has grown unwieldy, including a split in the plan is reasonable.

This file structure informs task decomposition.

Each task should produce self-contained changes that make sense independently.

## 1.3 Plan Header

Every plan must start with:

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]

**Architecture:** [Two or three sentences about the approach]

**Tech Stack:** [Key technologies, libraries, frameworks, or tools already used by the project]

## Global Constraints

[Project-wide requirements copied from the request or existing project conventions. Include exact values when provided.]
```

Do not invent global constraints that were not given by the user, repository, or existing project conventions.

## 1.4 Task Right-Sizing

A task is the smallest unit that carries its own test cycle and is worth a review checkpoint.

Each task should end with an independently testable deliverable.

Do not create huge tasks such as:

```text
Implement the whole feature.
```

Prefer tasks that can be executed, tested, reviewed, and completed independently.

## 1.5 Task Structure

Each task must include exact file paths, interfaces, steps, tests, and verification.

Use this structure:

```markdown
### Task N: [Task Name]

**Files:**
- Create: `exact/path/to/new_file.ext`
- Modify: `exact/path/to/existing_file.ext`
- Test: `exact/path/to/test_file.ext`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks, with exact names and signatures when known]
- Produces: [what later tasks rely on, with exact names and signatures when known]

- [ ] Step 1: Write the failing test.
- [ ] Step 2: Run the test and verify it fails for the expected reason.
- [ ] Step 3: Write the minimal implementation.
- [ ] Step 4: Run the test and verify it passes.
- [ ] Step 5: Run relevant verification.
- [ ] Step 6: Request or perform code review.
- [ ] Step 7: Fix review findings if needed.
```

## 1.6 No Placeholders

The plan must not contain placeholders.

Never write:

```text
TBD
TODO
implement later
fill in details
add appropriate error handling
add validation
handle edge cases
write tests for the above
similar to Task N
```

Every step must contain the actual information needed to execute it.

If code is required, show the code or describe the exact code change.

If a command is required, show the exact command and expected result.

If an interface is required, define the exact name and signature when possible.

## 1.7 Plan Self-Review

After writing the plan, review it before implementation.

Check:

1. Spec coverage: every requirement has a task.
2. Placeholder scan: no placeholder language remains.
3. Type consistency: names, signatures, and fields match across tasks.
4. File consistency: every file listed in tasks exists or is explicitly created.
5. Testability: every task has a concrete verification path.
6. Scope: no unrelated work is included.

If issues are found, fix the plan before coding.

---

# Phase 2: Execute the Plan

Before executing, load and review the plan critically.

## 2.1 Load and Review

Before editing code:

1. Read the plan.
2. Identify questions or concerns.
3. If there are critical concerns, raise them before starting.
4. If there are no concerns, create a task list and proceed.

Do not start from an unclear plan.

## 2.2 Execute Tasks

For each task:

1. Mark the task as in progress.
2. Follow each step exactly.
3. Use TDD for behavior-changing code.
4. Run verification specified by the plan.
5. Request or perform review at the task checkpoint.
6. Fix Critical and Important review findings before proceeding.
7. Mark the task as completed only after verification succeeds.

## 2.3 Stop Conditions

Stop executing and ask for help when:

* A blocker is encountered.
* A dependency is missing.
* A test fails repeatedly.
* An instruction is unclear.
* The plan has a critical gap.
* The implementation approach needs rethinking.
* Verification fails repeatedly.

Do not guess through blockers.

Return to plan review when the plan changes or the approach must be reconsidered.

---

# Phase 3: Test-Driven Development

Use TDD for all behavior-changing implementation unless explicitly exempted.

## 3.1 Iron Law

```text
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
```

If production code was written before a failing test, delete it and start over.

Do not keep it as reference.

Do not adapt it while writing tests.

Implement fresh from tests.

## 3.2 Red: Write a Failing Test

Write one minimal test showing what should happen.

Requirements:

* One behavior per test.
* Clear test name.
* Test real behavior.
* Avoid mocks unless unavoidable.
* The test should fail because the feature or fix is missing.
* The test should not fail because of typos, broken setup, or unrelated errors.

Run the focused test command.

Confirm:

* The test fails.
* The failure message is expected.
* The failure proves the missing behavior.

If the test passes immediately, it is testing existing behavior. Fix the test.

If the test errors, fix the test setup and rerun until it fails correctly.

## 3.3 Green: Write Minimal Code

Write the simplest production code that passes the failing test.

Do not:

* Add extra features.
* Refactor unrelated code.
* Improve beyond what the test requires.
* Change unrelated behavior.
* Weaken the test to match the implementation.

Run the focused test again.

Confirm:

* The test passes.
* Relevant nearby tests still pass.
* Output is clean enough to trust.

If the test fails, fix the implementation, not the test.

If other tests fail, address them before proceeding.

## 3.4 Refactor

Refactor only after tests are green.

Allowed:

* Remove duplication.
* Improve names.
* Extract helpers.
* Simplify structure.

Not allowed:

* Adding behavior during refactor.
* Changing the test’s meaning.
* Mixing refactor with unrelated changes.

After refactoring, rerun the relevant tests and keep them green.

## 3.5 Repeat

Repeat Red-Green-Refactor for the next behavior.

Do not batch many behaviors into one unverified implementation step.

## 3.6 TDD Checklist

Before marking implementation work complete, verify:

* Every new behavior has a test.
* Each test was observed failing before implementation.
* Each test failed for the expected reason.
* Minimal code was written to pass each test.
* All relevant tests pass.
* Tests use real code where practical.
* Edge cases and errors are covered when required by the task.

If these are not true, TDD was skipped.

---

# Phase 4: Request or Perform Code Review

Review early and often.

## 4.1 When to Review

Code review is mandatory:

* After each task in a task-based workflow.
* After completing a major feature.
* Before merging to main or claiming feature completion.

Code review is optional but valuable:

* When stuck.
* Before refactoring.
* After fixing a complex bug.

## 4.2 Review Input

The reviewer must receive focused context, not the entire session history.

Provide:

* Brief description of the work.
* Plan or requirements.
* Starting commit or baseline diff reference when available.
* Ending commit or current diff reference when available.
* Files changed.
* Tests added or changed.
* Verification already run.

## 4.3 Review Focus

Review should check:

* Does the work match the plan or requirements?
* Are there missing requirements?
* Are there incorrect behaviors?
* Are tests meaningful?
* Are there regressions?
* Are there maintainability problems?
* Are there unnecessary changes?
* Are there risks that should be fixed before proceeding?

## 4.4 Acting on Feedback

Classify findings:

```text
Critical: must fix immediately.
Important: must fix before proceeding.
Minor: may fix now or document for later.
```

Rules:

* Fix Critical issues immediately.
* Fix Important issues before continuing.
* Minor issues may be deferred if clearly noted.
* If the reviewer is wrong, push back with technical reasoning and evidence.
* Do not ignore valid technical feedback.
* Do not skip review because the change seems simple.

---

# Phase 5: Verification Before Completion

Before claiming work is complete, fixed, passing, ready, or successful, run fresh verification.

## 5.1 Iron Law

```text
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
```

If the verification command was not run in the current work session, do not claim it passes.

## 5.2 Verification Gate

Before any completion claim:

1. Identify what command proves the claim.
2. Run the full command.
3. Read the full output.
4. Check the exit code.
5. Count failures, errors, warnings, and skipped tests where relevant.
6. Decide whether the output confirms the claim.
7. If the output confirms the claim, state the claim with evidence.
8. If the output does not confirm the claim, state the actual status with evidence.

Skipping any step means the claim is not verified.

## 5.3 Claims and Required Evidence

Examples:

```text
Claim: tests pass
Required evidence: test command output with zero failures

Claim: linter clean
Required evidence: linter output with zero errors

Claim: build succeeds
Required evidence: build command exits successfully

Claim: bug fixed
Required evidence: the original symptom or regression test passes

Claim: requirements met
Required evidence: requirements checklist checked against implementation
```

Partial verification is not full verification.

A linter passing does not prove the build succeeds.

A build succeeding does not prove tests pass.

An agent report is not verification.

## 5.4 Red Flags

Stop before claiming success if any of these are true:

* You are using “should”, “probably”, or “seems to”.
* You are relying on a previous run.
* You are relying on partial verification.
* You are relying on another agent’s success report.
* You are about to commit, push, merge, or create a PR without verification.
* You are expressing satisfaction before running verification.
* You are moving to the next task without verifying the current one.

## 5.5 Verification Pattern

Use this pattern:

```text
Command:
[exact command]

Result:
[pass/fail]

Evidence:
[key output, exit code, failure count, or relevant summary]
```

If a command cannot be run, state that clearly and explain why.

Do not convert an unrun command into a success claim.

---

# Final Response Format

When the work is complete, respond with:

```markdown
## Summary

[Short description of completed work.]

## Plan Execution

- [Task 1]&#58; completed / not completed
- [Task 2]&#58; completed / not completed

## Files Changed

- `path/to/file`: [reason]
- `path/to/test`: [reason]

## Tests

- [Test added or updated]
- [Behavior covered]

## Review

- Critical: [none or list]
- Important: [none or list]
- Minor: [none or list]

## Verification

- `[command]`: [pass/fail + evidence]
- `[command]`: [pass/fail + evidence]

## Remaining Issues

[None, or list of unresolved items.]
```

Do not claim completion unless the verification section contains fresh evidence.

---

# Compact Workflow

Use this sequence:

```text
1. Write plan.
2. Self-review plan.
3. Execute one task.
4. Write failing test.
5. Run test and confirm expected failure.
6. Write minimal implementation.
7. Run test and confirm pass.
8. Refactor only after green.
9. Run relevant verification.
10. Request or perform code review.
11. Fix Critical and Important findings.
12. Repeat for next task.
13. Run final verification.
14. Report completion with evidence.
```

---

# Anti-Patterns

Do not:

* Start coding without a plan.
* Write production code before a failing test.
* Add tests only after implementation.
* Keep pre-TDD production code as reference.
* Skip verification because the change is small.
* Claim tests pass without running tests.
* Claim build succeeds without running build.
* Trust another agent’s success report without checking.
* Ignore Critical or Important review findings.
* Push through blockers by guessing.
* Include placeholders in the plan.
* Do unrelated cleanup inside the task.
* Treat partial verification as full verification.

---

# Bottom Line

The task is not complete until:

* The plan exists and was reviewed.
* The plan was executed step by step.
* Behavior-changing code followed Red-Green-Refactor.
* Code review found no unresolved Critical or Important issues.
* Fresh verification evidence supports every completion claim.

```
```
