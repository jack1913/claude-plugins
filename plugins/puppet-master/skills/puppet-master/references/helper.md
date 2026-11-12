# Helper commands

Read this before a `puppet` command you have not run since your last compaction, and whenever a command's output surprises you.

## Helper reference

| Command | Does | Prints |
|---|---|---|
| `measure <session> [--window N] [--json]` | tokens, % of the window (1,000,000 unless given), state | `<name>  <tokens>  <pct>%  <state>  (window N from <source>)` (source `flag`, `recorded`, `env` or `default`), or `<name>  0  0%  fresh  (no turns yet)` |
| `list [--name <session>] [--window N] [--json]` | every session in your care, measured, plus unadopted background workers; `--name` prints one, adopted or not | one `measure` line each, then `model <model> <effort>` (`model fresh` before the first turn), kind, role and job; `gone` rows show the resume command, `changed` rows mean a new session id; `DONE? run finish` ends an active job's row whose session reported done; `mod on (<source>)` (then `switched to <model> <effort>` after a `switch`), `mod off (mode <mode>)` or `mod stale` ends the row of a session whose mod beat, and no `mod` means the plugin is not loaded there |
| `adopt <session> [--role analyst\|master] [--window N] [--self-compact]` | takes a session into your care; `--role master` is you; also tells the session's mod its role, and `--self-compact` switches its mod on (only after the user's yes) | `adopted <name> (<kind>, <role>, clean or unknown) in <checkout>`, then `; self-compact switched on` with the flag |
| `assign <session> <job> [--tier T] [--reuse \| --extend] [--scope F] [--git \| --no-git]` | records the job before you send it; `--reuse` refuses at 30% of the window and names `clear` before the `/clear` line; `--extend` merges into the active job, checks the merged scope, keeps the job's git flag unless `--git` or `--no-git` is passed, and adds no label the job already has | `assigned <name>: <job>` (`extended …` with `--extend`), then the tier check: `ok` (`(switched)` after a `switch`), `unchecked`, or `MISMATCH … it runs <model> <effort>`, then `its mod is on: run switch …` where the mod is on, else the session-only paste lines (`/model`, then `s`; `/effort`, then `s`) |
| `finish <session>` | marks the job done | `finished <name>: <job>` |
| `reopen <session>` | undoes `finish`: the last job is active again; refuses a job that is not done, or a checkout another job now edits | `reopened <name>: <job>` |
| `pick <cwd> [--tier T] [--scope F] [--no-git]` | a clean session in that checkout: one matching the tier or whose mod is on first, the user's first | `<name>` and its tier check (after a `MISMATCH`, `its mod is on: run switch …`, else the paste lines: rule 12), or `no clean session for <checkout>; spawn one` |
| `spawn <name> <cwd> <brief file> --tier T \| --effort E [--model M] [--job <label>] [--scope F] [--no-git] [--self-compact]` | `claude --bg --model --effort` with the brief; the tier gives both unless `--model`/`--effort` override; exit 2 with neither tier nor effort; `--self-compact` switches the worker's mod on (only after the user's yes) | `spawned <name> id=<id> in <checkout> (model <m>, effort <e>)`, then `; self-compact switched on` with the flag |
| `cycle <worker> <focus> [--next <brief file>]` | background only: stop, headless `/compact <focus>`, verify, restart | `cycled <name>: <before>→<after> tokens (p1%→p2%), resumed id=<id>` |
| `compact <session> <focus>` | any adopted session whose mod is on and that is idle: the mod compacts it with your focus, the helper checks the transcript for a new `compact_boundary`; your own session is queued for after your turn | `compacted <name>: <before>→<after> tokens`; for yourself `requested <name>'s own compaction: …`; on failure the paste line |
| `switch <session> --tier T \| --model M --effort E \| --reset` | any adopted session whose mod is on and that is idle: the mod sends that model and effort on every main-loop request from the next one on, this session only, no settings written; `--tier` uses `spawn`'s model and effort; `--reset` goes back to the launch model; your own session is queued for after your turn | `switched <name> to <model> <effort> (last request: …)` (or `(switched before to …)`); `reset <name>: …`; for yourself `requested <name>'s own switch …`; on failure the paste lines |
| `clear <worker>` | a worker with a finished job, its mod on and idle: the mod runs `/clear`, the helper re-adopts it as clean under its new session id; refuses a master, an analyst, an active job | `cleared <name>: new session <id>, clean`; on failure the paste line |
| `close <worker>` | background only: stop, `claude rm`; the transcript stays resumable | `closed <name> (resume: cd "<cwd>" && claude --resume <sessionId>)`; a later lookup of the name prints `<name> is closed (resume: …)` |
| `harvest --master <your name> LOGS` | the analyst's: new transcript events, secrets blanked; one harvest at a time | `harvested <n> events from <s> sessions (<l> new lines) into <logs>`, then any session with no transcript or read again from the top |
| `logs LOGS` | the logs folder and the newest earlier report not yet reviewed | `<logs>`, then `unreviewed report: <path>` when there is one |
| `finding --tag --target --evidence --note LOGS` | the analyst's: one finding with harvested evidence | `F-<n> <tag> → <target>` |
| `summary [--day YYYY-MM-DD] LOGS` | the day's counts, flagged items and proposals | a headline that says how much was read, then counts |
| `decide <proposal> approve\|reject\|defer --tag --target --hypothesis LOGS` | logs the user's decision | `<proposal> <decision> (<tag> → <target>)` |
| `shipped <proposal> <sha> LOGS` | links an approved proposal to its commit | `<proposal> shipped as <sha>` |

`cycle` refuses a worker that is not idle. If it fails after stopping, it says so and prints the
`cd "<cwd>" && claude --bg --resume <sessionId>` that restarts the worker; relay that to the user.
