# Glossary

The words used across these pages, in plain terms.

| Word | Meaning |
|---|---|
| plugin | A bundle you add to Claude Code. It can bring skills, commands, agents, workflows and hooks. This marketplace has three: batbelt, brand-creator and swift. |
| marketplace | A catalog of plugins. This one is called `jack1913`. You add it once, then install any plugin from it as `<plugin>@jack1913`. |
| skill | A set of instructions Claude loads when a task calls for it, like writing Swift concurrency code. Some start when you ask in plain words. |
| command | Something you type that starts with `/`, like `/batbelt:grill-me`. The plugin's name comes first, so commands from different plugins never clash. |
| agent | A helper Claude can hand a job to. It works on its own and reports back. |
| workflow | A scripted run of several steps, sometimes with several agents. Plugins that use them ask before they start one. |
| hook | A small check that runs by itself at a set moment, such as before a command. Plugins use hooks for safety. |
| scope | Where an install applies. **User**: you, in every project. **Project**: everyone on one repository. **Local**: just you, in one repository. |
| typed-only | A command or skill that runs only when you type it. Claude never starts it on its own. |
| automatic | A skill Claude can start itself when your words match, with no command typed. |
