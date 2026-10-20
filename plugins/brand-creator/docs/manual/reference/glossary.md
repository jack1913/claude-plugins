# Glossary

Plain words for the terms brand-creator uses.

## Words from the process

| Word | What it means |
| --- | --- |
| Project | The folder where one brand lives. It holds your brief, boards, files and a state file, `BRAND-STATE.md`, that remembers where you are |
| Tier | How far to go: Quick, Standard or Full. See [Choose a tier](../getting-started/choose-a-tier.md) |
| Direction | One clearly different idea for your brand: its own look, feel and logo. The first board shows three |
| Board | One page that shows the directions (or the refined one) so you can compare them and answer. Claude checks it and photographs it at desktop and phone width, in light and dark |
| Round | One pass of a board. Round 1 shows the directions; later rounds refine your pick. Finished rounds are locked |
| Gate | A point where Claude stops and waits for your decision, such as your pick or your OK on the finished files. Nothing continues until you answer |
| Lock | A finished round is saved in `history/` with a checksum and then protected: nothing can change it quietly |
| Mark | Your logo symbol. A lockup is the mark together with your name |
| Pack | A set of files for one place, such as favicons and web icons, social images, or Apple icons |
| Brand book | One page, `book.html`, with the rules for using your brand: logo at several sizes, colours with contrast, type and files. Built from your project, so it can't drift from the files |
| Hand-off | A step Claude gives to you instead of doing it, such as buying a domain or filing a trademark |
| Leftover search | `/brand-creator:check` with an old value: it searches the whole project for places the old name, colour or rule still shows |

## Words in reports

| Word | What it means |
| --- | --- |
| Not verified | A check could not run (a tool is missing, say). It is never counted as a pass, and the message says why |
| REGISTERED, NOT-FOUND, UNKNOWN | What one source said about a name on one day. None of them means "available" or "clear" |
| RGB proof | A print file made for checking on screen. It is not print-ready until your printer checks it |

## Words from the file formats

| Word | What it means |
| --- | --- |
| Design tokens | Your colours, fonts and sizes as values a program can read, so a website or app uses exactly the same ones |
| DTCG | The Design Tokens Community Group's file format for design tokens. A community specification, not a W3C standard. brand-creator writes your tokens in it, then builds CSS, JSON, Swift, Android and colour-set files from it |
| Favicon | The small icon in a browser tab |
| Open Graph image | The preview picture a link shows when it is shared |

## Words shared across the marketplace

- Plugin: brand-creator itself. Skill: one thing Claude can do. Command: a skill you type with `/`. Agent: a helper Claude
  starts for one job. Workflow: several agents run together. Hook: a check that runs before Claude changes a file.
