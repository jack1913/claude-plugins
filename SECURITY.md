# Security

Plugins run on your machine with your permissions, and some ship hooks and permission tooling. A problem in one can
matter more than a bug in a normal library, so reports about those are welcome.

## Report a problem

Private vulnerability reporting is not turned on for this repository. So:

1. Open an [issue](https://github.com/jack1913/claude-plugins/issues) that says you have a security problem. Leave out
   the details and any way to exploit it.
2. Ask for a private channel to send the rest.

I'll answer in the issue and move the details there.

## What counts

Reports about what a plugin does with your files, shell, permissions or settings are in scope. That includes its hooks,
its permission rules and anything it downloads. A plugin acting outside what its README says it does is a bug.
