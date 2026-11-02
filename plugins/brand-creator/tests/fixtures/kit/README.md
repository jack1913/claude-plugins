# Kit fixture

An overlay for a copy of the Acme project: one approved reference page, `start`, and the files it loads. `site/site.json` is in the format of `brand-creator site approve` (schema 1), and its
`sha256` is that of `site/start/index.html`. The page-check report and the stills are made by the tests (`page_check_report` and `capture_record` of `tests/helpers.py`), so no browser is needed.

- `site/start/index.html` loads the token stylesheet and the mark (both are in the kit already), `assets/web/base.css` (a stylesheet outside the page folder, which loads `assets/web/dot.svg`),
  `site.css` (in the page folder, which loads `img/pic.svg`) and `img/pic.svg`.
- A change to the page needs the `sha256` in `site/site.json` to follow (the tests do it with `mutate_json`).
