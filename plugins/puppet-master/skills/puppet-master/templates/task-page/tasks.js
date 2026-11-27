// The master edits this file on every change; index.html reads it again every 90 s without a page reload.
// The page sorts every list itself (the order is named on the page), so the order in this file does not matter:
// tasks by group (A to Z, no group last), then by id, lowest first; asks by task, then by id; side questions newest first.
// The data shape (all fields are plain strings unless noted):
//   workSet     one line naming the work set (it carries over days until a new set of work starts)
//   days        array of the days this set has run, "YYYY-MM-DD"
//   updated     "YYYY-MM-DD HH:MM" (sync-sessions.mjs rewrites it)
//   waitingNow  one line under the header, on every tab: what waits for the user now, or a note such as a stand-in
//               master's; start it with "Nothing waits" when nothing does. The counts come from asks and tasks.
//   asks        array of the asks (questions and actions for the user), each its own record; shown in the Questions tab
//               grouped by their task, open ones in full, answered ones folded:
//               { id, task, state, asked, question, facts, recommend, noHurry, answer, answered, movedFrom }
//     id        "A1", "A2", ... never reused within the work set
//     task      the id of the task it belongs to; an open ask keeps its task in Open, also while the task is done
//     state     open | answered
//     asked     "MM-DD HH:MM" when it was asked
//     question  the question, one line
//     facts     array of { label, text, kind, path }: the data to decide on; kind: text | quote | link
//               (a link opens path, an absolute path or URL, in the side panel)
//     recommend the recommended answer
//     noHurry   true when the user said it can wait; it still counts as open
//     answer    the user's answer, quoted; answered "MM-DD HH:MM" when it came
//     movedFrom optional: the task it was asked in first
//   epics       array, one row per epic (the Jira tasks tab, by epic id; empty: "no rows recorded"):
//               { epic, what, status, stamps, repos }
//     epic · what       "EPIC-####" and its title, from the epic's epic.md
//     status · stamps   from epic.md: its status, and "dev_review <date> · agentic <state>"
//     repos     array, one per repo and PR (backend before frontend):
//               { repo, pr, url, prState, check, tasks, review, jira, last }
//       repo · pr · url "backend", "#197", the PR's URL (optional; prUrl is read the same): the Jira tab links the PR to it,
//                 in a new tab, and a task's title or lines link "#197" when one PR on the board has that number
//       prState   "draft | ready · mergeable, clean | unstable | conflicting" (gh pr view)
//       check     optional: a failing check, "check <name>: failure"
//       tasks     "7 of 7 landed" (the boxes of the epic's tasks.md on its branch)
//       review    { verdict, note }: the newest review verdict (fixed-clean, undecided, blocked, ...) and one line
//       jira      { key, status, category, type, assignee, url }: the Jira issue and its board status; url (optional)
//                 links the key on the Jira tab and wherever a task's title or lines name it;
//                 category is Jira's status category: new | indeterminate | done (it sets the colour)
//       last      "HH:MM · what": the newest change (branch tip, PR event or board line)
//       log       optional: up to 4 event lines for the Jira card, newest first, each "MM-DD HH:MM · what" (or { at, text }):
//                 PR events and board lines, no commit ids (the page drops any it finds). Without it the card shows `last`
//                 as its one line. The master writes it where it writes `last`; sync-epics.mjs could add the PR events
//                 (merged, review requested, checks) from `gh pr view --json timelineItems`.
//       asOf      optional: "MM-DD HH:MM" this line was last read (sync-epics.mjs writes it); the tab shows each epic's
//                 read time and its age, and marks it stale after 2 hours
//               An older flat row { epic, repo, what, status, stamps, tasks, pr, collector, next } still shows,
//               as one repo line (next as the last change).
//   epicsAsOf   when each source was read: { "brain origin": "21:35", "gh": "21:35", "Jira": "22:59" }
//               (a plain string is shown as it is); sync-epics.mjs rewrites "gh" and "Jira"
//   sessions    array of { name, state, model, job, context } (sync-sessions.mjs rewrites it from `puppet list`)
//   sessionsAsOf "HH:MM" the list was read (sync-sessions.mjs rewrites it)
//   previous    array of { label, days, tasks, open, path }: earlier work sets, linked from the sidebar, newest first;
//               open: what was left open there, path: its master page (absolute path)
//   sideQuestions array of the user's side questions to the master (asked beside the tasks, not an ask of a task);
//               the Side questions tab, the newest first: { id, asked, question, answer, answered }
//     id        "S1", "S2", ... never reused within the work set
//     asked     "MM-DD HH:MM" when the user asked it; question: the user's words, verbatim
//     answer    the master's short answer; answered "MM-DD HH:MM" when it was given
//   tasks       array of
//               { id, day, origin, group, title, status, blocked, who, evidence, reports, sub }
//     id        "T1", "T2", ... never reused within the work set
//     day       the day it was asked, "MM-DD"
//     origin    initial (asked when this work set started) | added (asked later)
//     group     optional: the epic (its id, as in epics[]) or theme the task belongs to ("CI", "status page"); the Tasks tab
//               shows a heading per group, A to Z, and the tasks without one last; the Jira tab lists an epic's tasks by it
//     title     one line; the task's row shows its id, status and title only, the rest opens under Show more
//     status    running | waiting-you | queued | open | pending-report | blocked | done
//               read loosely: "pending report" is pending-report; any other word gets its own filter in the sidebar.
//               Done tasks are not in the Open list (the Done filter lists them).
//               pending-report: finished, with a report the user has not read yet; not counted as waiting.
//               The page's "Mark seen" button shows it as done in that browser and gives the user a line for
//               the master ("seen on the task page: T22 (11-26 23:40)"); on that line, set the status to done.
//     blocked   optional: what it is blocked on (shown as a Blocked pill on a task that is not done)
//     who       the session or person that holds it; "name (what it does)" shows the brackets under the name
//     evidence  where the result is, or "-"
//     reports   optional array of { label, path, pending }: HTML pages, absolute paths or URLs (a "#anchor" is
//               allowed), the oldest first (append a new one); pending: true when the page does not exist yet
//               (shown muted, "not written yet", with no link)
//     sub       optional array of short lines, the newest first (add a new line on top): decisions, results, and
//               each ask's line ("A57 ASKED 11-26: ...", "A57 ANSWERED 11-26: “...” — ...")
window.DASH = {
  workSet: "",
  days: [],
  updated: "",
  waitingNow: "Nothing waits for you right now.",
  asks: [],
  epicsAsOf: {},
  epics: [],
  sessionsAsOf: "",
  sessions: [],
  previous: [],
  sideQuestions: [],
  tasks: []
};
