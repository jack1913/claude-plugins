// The master edits this file on every change; index.html reads it again every 90 s without a page reload.
// The data shape (all fields are plain strings unless noted):
//   workSet     one line naming the work set (it carries over days until a new set of work starts)
//   days        array of the days this set has run, "YYYY-MM-DD"
//   updated     "YYYY-MM-DD HH:MM" (sync-sessions.mjs rewrites it)
//   waitingNow  one line: what waits for the user now; start it with "Nothing waits" when nothing does
//   epics       optional array of { epic, repo, what, status, stamps, tasks, pr, collector, next }; leave it empty
//               to hide the table. epicsAsOf is the line above it.
//   sessions    array of { name, state, model, job, context } (sync-sessions.mjs rewrites it from `puppet list`)
//   tasks       array, in the order shown, of
//               { id, day, origin, title, status, who, evidence, reports, sub }
//     id        "T1", "T2", ... never reused within the work set
//     day       the day it was asked, "MM-DD"
//     origin    initial (asked when this work set started) | added (asked later)
//     status    done | running | waiting-you | queued | open
//     who       the session or person that holds it
//     evidence  where the result is, or "-"
//     reports   optional array of { label, path, pending }: HTML pages, absolute paths (a "#anchor" is allowed);
//               pending: true when the page does not exist yet
//     sub       optional array of short lines: the open asks (with their ids), decisions, results
window.DASH = {
  workSet: "",
  days: [],
  updated: "",
  waitingNow: "Nothing waits for you right now.",
  epicsAsOf: "",
  epics: [],
  sessions: [],
  tasks: []
};
