# LIFEOS Demo Script

Target duration: 3 to 4 minutes.

## 0:00-0:20 - Problem

Narration: "A single changed flight can ripple through the rest of a workday. The meeting moves, the client needs an update, teammates need to know, and the result has to be verified."

Action: Open LIFEOS on the hosted or local workspace. Show the main command center.

## 0:20-0:45 - Product

Narration: "LIFEOS turns a real-world change into a reviewed cross-app workflow. It reads context, proposes exact actions, asks for approval, executes only what was approved, and reads each provider back."

Action: Point to the event input, approval center and consequence graph.

## 0:45-1:35 - Create Workflow

Narration: "I will describe a changed flight. LIFEOS extracts the event, checks the calendar and related application context, then creates a plan."

Action: Run the demo flight scenario or enter: `My flight tomorrow moved to 7:20 AM`.

Expected result: An event appears with Calendar, notification and verification actions. The graph shows dependencies.

Fallback: If a live provider is unavailable, use the local demo scenario and state that demo records are persistent local application records, not fake live-provider success.

## 1:35-2:25 - Approval and Execution

Narration: "High-impact actions are not automatic. The approval binds the exact arguments and plan version, so edits require reapproval."

Action: Review action details, approve the safe set, execute the plan and watch statuses update.

Expected result: Actions move through executing, verified or manual-review states. Evidence appears on completed actions.

Fallback: If a provider write cannot be performed, show the saved plan, approval state and release status document explaining the live acceptance boundary.

## 2:25-3:05 - Architecture and Safety

Narration: "The model helps understand the change, but the server owns authority. Provider context is untrusted, actions are server-built, approvals are hashed, and the system requires read-back before resolution."

Action: Open `ARCHITECTURE.md` or the README diagram, then show the audit verification view.

## 3:05-3:40 - Outcome

Narration: "The value is not a chatbot response. LIFEOS turns a messy operational change into a controlled workflow with evidence, audit history and recovery paths."

Action: Show audit history, evidence and saved work/history views.

## 3:40-4:00 - Close

Narration: "LIFEOS is a production-shaped automation workspace for consequence management. The current release notes are honest about what is verified and what still needs live acceptance."

Action: End on the README or release status.

