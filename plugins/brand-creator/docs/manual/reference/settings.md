# Settings

Two options control where brand-creator keeps your work and where boards show up.

Change them in `/plugin` (Installed, then brand-creator, then **Configure options**) or in `/config`.

| Setting | What it does |
| --- | --- |
| `projects_root` | The folder for your brand projects. Empty: you're asked, with a folder named after the project (like `./my-bakery/`) offered first |
| `review_surface` | Where boards show up. `auto` (default): asks once per project whether boards may go to claude.ai as a private page, and uses a local file until you answer. `artifact`: always a private claude.ai page. `local`: always a local file |

## Where the plugin keeps things

- **Your brand project:** its own folder, such as `./my-bakery/`, unless you pick another place.
- **The tools:** the plugin's data folder, where [setup](../use/start-a-brand.md) installs Node packages and Chromium.
  Nothing is written inside the plugin folder itself, because it changes on every update.

## Related

- [Permissions](permissions.md)
- [Costs](costs.md)
