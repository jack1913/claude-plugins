# Wrapping up the day

Read this when the user ends the day, and when `puppet logs` names an unreviewed report.

## Wrap-up

1. Tell the analyst `wrap-up: harvest, then write the report`, and wait for its one-line answer.
2. Run `puppet summary LOGS`, and read `<logs>/<day>/report.md`.
3. Walk the user through the proposals one at a time: the proposal, the findings it cites, your
   recommendation, and approve, reject or defer. Log each answer:
   `puppet decide <proposal> <answer> --tag <tag> --target <target> --hypothesis "<text>" LOGS`.
   Then add a last line `Reviewed: <date>` to the report. If the user would rather not review now,
   leave it; the next start offers it.
4. An approved proposal is a job for another time, in the plugin's own checkout. When its commit
   lands, `puppet shipped <proposal> <sha> LOGS`.
5. Run `puppet list` and `close` every finished or `dead` background worker before you tell the user the day is
   done. Tell the user which of their windows they can close, with
   each one's job.
6. Give the user ONE `!` line that removes the temp folders of the day's finished jobs under
   `<logs>/tmp/` (the logs folder `puppet logs LOGS` prints): list that folder first, then
   `! rm -rf "<logs>/tmp/<session>" "<logs>/tmp/<session>" …`, full paths with forward slashes. It
   holds only finished jobs' folders: never the folder of a session whose job is still active (its
   `list` row). For a folder that is no finished job's: ask the user in the same message. No session
   deletes these during the day: a user's deny rules often refuse a session's delete, and the line
   the user types is theirs to run.
