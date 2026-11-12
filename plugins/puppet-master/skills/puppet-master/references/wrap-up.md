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
5. `puppet close` each background worker. Tell the user which of their windows they can close, with
   each one's job.
