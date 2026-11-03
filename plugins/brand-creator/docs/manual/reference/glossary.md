# Glossary

Plain words for the terms brand-creator uses.

## Words from the process

| Word | What it means |
| --- | --- |
| Project | The folder where one brand lives. Claude makes it when you start, such as `./my-bakery/` inside the folder you work in. It holds your brief, boards, files and a state file, `BRAND-STATE.md`, that remembers where you are |
| Brief | The notes about your business that Claude writes from your answers at the start, in `brief/BRIEF.md`, including where your brand must show up, such as a site |
| Tier | How far to go: Quick, Standard or Full. See [Choose a tier](../getting-started/choose-a-tier.md) |
| Direction | One clearly different idea for your brand: its own look, feel and logo. The first board shows three |
| Board | One page that shows the directions (or the refined one) so you can compare them and answer. Claude checks it and photographs it at desktop and phone width, in light and dark |
| Round | One pass of a board. Round 0 is the style research, round 1 shows the directions; later rounds refine your pick. In Standard and Full, a motion round shows three ways your logo could move. Finished rounds are locked |
| Style board | The page you see before anything is drawn: how brands like yours look, and four to six styles with real examples to pick from |
| Gate | A point where Claude stops and waits for your decision, such as your pick or your OK on the finished files. Nothing continues until you answer |
| Lock | A finished round is saved in the project's `history/` folder with a checksum (a fingerprint of its files) and then protected: nothing can change it quietly |
| Mark | Your logo symbol. A lockup is the mark together with your name |
| Pack | A set of files for one place, such as favicons and web icons, social images, or Apple icons |
| Brand book | One page, `book.html`, with the rules for using your brand: logo at several sizes, colours with contrast, type and files. Built from your project, so it can't drift from the files |
| Brand kit | Your brand in one folder that your website's or app's code can carry a copy of: your colours, logo files and open-licence fonts, your rules and facts, ready-made bits of code, and a few files of your own, such as a recipe for building a page. See [Use your brand kit](../use/use-your-brand-kit.md) |
| Owner files | The files in your brand kit that are yours to write, such as how your brand sounds (`voice.md`), the recipe for building a page and any recipe or file you add: Claude writes the starter files once and never overwrites any of them, while the rest of the kit is made from your project and never edited by hand |
| Hand-off | A step Claude gives to you instead of doing it, such as buying a domain or filing a trademark |
| Leftover search | `/brand-creator:check` with an old value: it searches the whole project for places the old name, colour or rule still shows |

## Words for your website

| Word | What it means |
| --- | --- |
| Website references | The board you see before any page of your site is built: groups of real sites that do the same job for the same visitor, each with a screenshot, what to take from it and what to leave. You pick the groups to build from |
| First screen | What a visitor sees of a page before scrolling (developers call it the hero), and the first part of your site Claude builds |
| Reference page | A page of your site that you approved, kept in your project's `site/` folder (and in your brand kit, if you have one) to show whoever builds your real site what your brand decided and what was only an example: never a template to fill in, and not your live site |
| Brand rule and example | The two kinds of choice on your site's pages: a brand rule is one you decided, which every page keeps unless the rule names certain pages, and an example is one way of doing it, free to change |
| Cold review | A read of a page that sees only its pictures, your brief and your facts, not why it looks the way it does, and gives its verdict ("ship", "fix" or "owner", when what is left is your call) before any reason. Claude does it in your conversation unless you say yes to a separate reviewer, and the review says which it was |
| Layout reference | A short recipe for how a page is organised for one visitor job: what leads, in what order, where the action sits and how it ends. Structure only, a starting point and never a template |
| Page check | `/brand-creator:check --page`: Claude opens one page on your computer at several screen sizes, in light and dark, and lists where it breaks your brand, such as a colour that isn't yours or a claim that isn't in your facts, without changing the page. See [Check a page against your brand](../use/check-a-page.md) |
| Sample | A made-up figure on an unfinished page, such as a price, marked as a sample with a label that says what it stands for, so the page check lets it pass and lists it for you to replace before you publish |
| Local address (localhost) | An address such as `http://localhost:3000/`, where your own computer shows a site while someone works on it, and the only kind of address the page check and the redesign record open |

## Words for your product's code

| Word | What it means |
| --- | --- |
| Repository | The folder on your computer that holds your website's or app's code, with the history of every change saved to it; a product repository is one your brand goes into |
| Branch | A side copy of your code where changes wait until you accept them, so your main version stays as it was |
| Commit, merge, push | Three separate steps, each taken only when you ask: commit saves the changes into your code's history, merge joins your branch into your main version, and push copies your code to where it is kept online, which can publish your site |
| Redesign record | What Claude notes about your site before a redesign and again after it, such as where links go and the names of form fields, so nothing your site relies on goes missing without your say-so; `ADOPTION.md` in your project shows it |

## Words in reports

| Word | What it means |
| --- | --- |
| Not verified | A check could not run (a tool is missing, say). It is never counted as a pass, and the message says why |
| REGISTERED, NOT-FOUND, UNKNOWN | In a name check, what one source said about a name on one day. None of them means "available" or "clear" |
| RGB proof | A PDF made for checking on screen, in screen colours (RGB). It is not print-ready until your printer checks it |

## Words from the file formats

| Word | What it means |
| --- | --- |
| Design tokens | Your colours, fonts and sizes as values a program can read, so a website or app uses exactly the same ones |
| DTCG | The file format brand-creator writes your design tokens in, from the Design Tokens Community Group: a community specification, not an official web standard. From it, Claude builds the files that websites and Apple and Android apps read |
| Favicon | The small icon in a browser tab |
| Open Graph image | The preview picture a link shows when it is shared |

## Words shared across the marketplace

The marketplace is the catalogue you installed brand-creator from. These words mean the same in every plugin in it.

| Word | What it means |
| --- | --- |
| Plugin | brand-creator itself: an add-on to Claude Code |
| Skill | One thing Claude can do, such as making the brand book |
| Command | A skill you type in the chat, starting with `/` |
| Agent | A helper Claude starts for one job |
| Workflow | Several agents run together |
| Hook | A check that runs by itself before Claude changes a file; brand-creator's keeps your finished rounds from being changed |
