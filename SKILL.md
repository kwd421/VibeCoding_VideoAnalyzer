---

name: integration-behavior-verification

description: Perform rigorous end-to-end integration behavior verification for an application or feature. Use this skill when the user asks to verify not just that code runs, but that the full workflow, connected components, UI behavior, state transitions, and outputs all behave as intended. Do not use for superficial smoke tests or syntax-only checks.

---



When invoked, follow this workflow strictly.



\## Goal

Verify that the target system does not merely execute, but actually behaves correctly across the intended user flow, integrated components, state transitions, and outputs.



Do not stop at:

\- import success

\- app launch success

\- no exception on startup

\- one isolated function returning without error



The purpose of this skill is to confirm real behavior, not superficial survivability.



\## Verification standard

Always evaluate from these angles:



1\. End-to-end workflow

\- Check whether the primary user flow works from entry point to final output.

\- Confirm that intermediate states, transitions, and outputs are correct.



2\. Integration consistency

\- Check whether UI, controller, engine, background tasks, persistence, and rendering/output layers remain synchronized.

\- Verify that connected modules exchange the right data at the right time.



3\. Behavior correctness

\- Confirm that the system behaves as intended, not merely that it avoids crashing.

\- Validate visible behavior, internal state changes, downstream effects, and final results.



4\. Error-path reliability

\- Check invalid input, cancellation, partial failure, missing resources, and interrupted flows.

\- Confirm that the system fails safely and recovers properly where appropriate.



5\. Regression safety

\- Check whether the change accidentally broke adjacent behavior, linked workflows, or previously working interactions.



\## Required process



\### Step 1. Define the verification scope

Before testing, identify:

\- target files or modules

\- main user workflows

\- dependent subsystems

\- success criteria for each workflow



State explicitly what counts as:

\- fully verified

\- partially verified

\- not verified



\### Step 2. Build a verification matrix

Break the target into concrete scenarios.



For each scenario, define:

\- trigger

\- expected UI behavior

\- expected state change

\- expected side effect

\- expected final result



Cover:

\- normal flow

\- edge cases

\- failure flow

\- recovery flow

\- linked downstream flow



\### Step 3. Execute meaningful verification

Use the strongest available verification methods, such as:

\- real execution

\- integration tests

\- targeted manual scenario checks

\- reproducing known bug paths

\- inspecting UI-state-to-engine-state synchronization

\- verifying saved/exported/rendered outputs

\- checking that completion handlers and callbacks restore correct state



Do not rely on compile/import/startup checks alone unless the user explicitly asks for that and nothing more.



\### Step 4. Separate evidence levels

Every conclusion must be labeled as one of:



1\. Code-evident

\- clearly guaranteed by code structure or logic inspection



2\. Execution-verified

\- actually confirmed by running the relevant scenario



3\. Partially verified

\- some evidence exists, but the full scenario was not completely confirmed



4\. Unverified

\- not tested or not provable from available evidence



Never present partially verified or unverified behavior as confirmed.



\### Step 5. Evaluate intent match

For each important feature, answer:

\- what is the intended behavior?

\- what evidence shows that it matches?

\- what remains uncertain?

\- what can still break?



This skill must judge behavioral correctness, not just technical survival.



\## Minimum verification expectations

Unless clearly impossible, verify all of the following where relevant:



\- application starts

\- main screen renders correctly

\- primary controls respond

\- user-triggered workflow proceeds correctly

\- state changes are reflected in UI

\- completion/failure restores appropriate UI state

\- linked downstream actions become available when expected

\- outputs are actually produced and usable

\- saved/exported/rendered results match intent

\- error handling does not leave the system in a broken state



\## Reporting format

Always report in this structure:



\### \[1] Verification scope

\- target area

\- workflows examined

\- dependencies involved

\- what was in scope vs out of scope



\### \[2] Verification matrix

For each scenario:

\- scenario name

\- expected behavior

\- evidence type

\- result



\### \[3] Findings

For each issue:

\- severity

\- exact behavior mismatch

\- root cause

\- impact

\- triggering conditions



\### \[4] Evidence by confidence level

Group findings into:

\- code-evident

\- execution-verified

\- partially verified

\- unverified



\### \[5] Final judgment

State clearly:

\- startup-only verified

\- partial integration verified

\- workflow verified

\- production confidence still limited

\- remaining risks



\### \[6] Next required checks

List the most important unverified or risky scenarios that should be checked next.



\## Rules

\- Do not confuse “runs” with “works”.

\- Do not mark a feature as verified without direct evidence.

\- Prefer end-to-end behavior over isolated unit success when the user asks for integration validation.

\- Be explicit about uncertainty.

\- Prioritize real user workflows over superficial checks.

\- If automation cannot fully verify a scenario, say exactly what blocked verification.

