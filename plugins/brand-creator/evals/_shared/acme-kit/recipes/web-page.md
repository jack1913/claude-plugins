# Web page

Steps only. The brand's values live in the tokens and rules.json; a line you add that pins a value cites a token or a rule, or is tagged `[example]`.

1. The visitor's job: name the one job a visitor comes to this page for, and the material at hand (facts, photos, data). Start there, never from a list of sections. Then write the page's idea in one line: something only this brand can say, built from its facts (`facts.json`). Test it with a competitor the owner names (ask if none is named): put their name in the line. If it still reads true, it is no idea yet, so rewrite it.

2. References: take the brand's reference pages (`reference-pages/`, when the kit has them) and the layout reference that fits the job (brand-creator's `page-layouts.json`; each layout is named after what the visitor came to do). Take structure and rhythm from them, never another site's look.

3. Tokens and files: colour, type, spacing and motion come from the CSS variables in `brand/assets/tokens/tokens.css` and from `rules.json`. A value the tokens lack is asked for, never invented. The page has to find its brand files where it is served, so copy the ones you use from the kit's `brand/` folder (the tokens, the fonts, the logo) into the product's own public or static folder and link them from there, starting from `snippets/fonts.css` and `snippets/logo.html` with their paths changed to match. Never link into `.claude/skills/`: a built site does not serve it. A font that `kit.json` lists as not copied goes into the product only by the owner's decision, under its own licence.

4. Hero first: build the hero alone, in light and dark, at a phone and a desktop width. Nothing else until it holds. Build it with the owner's web-design skill loaded beside this kit, never instead of it: the kit gives the brand's side, that skill gives the craft. Write the hero to the page check's word budget (`tell:hero-text-budget`) from the first draft, and give the second action a label of its own, because the page check warns on a stock one (`tell:stock-second-action`). For a picture of the product, use a real screenshot, or a plain placeholder marked as a sample (see the last step). A screen drawn out of styled boxes is a warning too (`tell:styled-div-mock`).

5. Page check: run the brand's page check on it, both tiers (the brand rules, which fail the page, and the reflex tells, which warn), from the brand project. Check the built page, never a development server's version of it. For a page in a product repository, use `brand-creator page-check --from <the product's folder, or its build output when a build step makes the page> <page> --project <the brand project>`, or `--url http://localhost:<port>/<path>` for a local preview of the product's production build. Fix every brand-rule failure; fix or argue each reflex warning.

6. Cold read: someone who did not build it gets fixed inputs (the page, the brief line, the visitor's job) and answers with a verdict first, ship or fix, then the reasons.

7. Before publishing: mark every sample with the `[data-sample]` attribute and a label, `data-sample="<label>"`: each made-up figure, name, date or claim, in the copy and in any drawn product preview. Run the page check again. A figure with no label and no FACTS row fails its claims row (`page:claims`), and the page check lists every labelled sample in its `page:samples` row, which is your before-publishing list: each entry needs the fact that must replace it. A claim with no FACTS row stays a sample or goes.

The other pages follow the same steps.
