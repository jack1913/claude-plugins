# Show a switch in your status line

When puppet-master switches a session to another model and effort, your status line keeps showing the ones the session
started with. This optional change makes your own status line script show the switch, for example `⇄ sonnet  medium`.
puppet-master works the same without it.

## Before you start

- puppet-master is installed, and its mod is on in the sessions it switches. See
  [Let sessions compact themselves](run-background-workers.md#let-sessions-compact-themselves).
- You already have a status line script of your own, set as `statusLine` in your `~/.claude/settings.json`. The
  snippet below is for a PowerShell script.

## Why your status line doesn't show the switch

Claude Code passes your status line script the model and effort the session started with. A switch changes neither:
the mod changes the model and effort only on the requests the session sends. Its own line under the prompt,
`puppet-master: switched to <model> <effort>`, names the switch, and stays there whether you make this change or not.

The mod also writes a small file for each session, its heartbeat, which your script can read:

- **Where:** `heartbeat/<session id>.json` in the mod folder. The mod folder is `PUPPET_MOD_DIR` when you set it,
  else `puppet-master/mod` in `CLAUDE_CONFIG_DIR` when you set that, else `~/.claude/puppet-master/mod`.
- **What it holds:** `beat`, the time the mod last wrote it in milliseconds since 1970, and `override`: the model
  and effort the session is switched to, as `{ "model": "sonnet", "effort": "medium" }`, or `null` when no switch is in
  force. A switch the mod isn't allowed to apply in that session is `null` here too.
- **How often:** the mod rewrites it every 3 seconds while the session runs.

Use the heartbeat only while it is fresh. A heartbeat stops changing when the mod stops: the session closed, the plugin
was disabled, or the window was opened without it. An old heartbeat would keep showing a switch that no longer
applies, so a missing or old one falls back to what Claude Code passes your script.

## Add the switch to your script

1. Open your status line script. Find where it reads the model and the effort from the JSON Claude Code passes it.
   The snippet calls that parsed JSON `$d`; use your script's own name for it.
2. Paste this lookup before those lines. It treats a heartbeat older than 15 seconds as stale:

   ```powershell
   # puppet-master: the switch in force for this session, from the mod's heartbeat
   $pmOv = $null
   if ($d.session_id) {
       $modDir = if ($env:PUPPET_MOD_DIR) { $env:PUPPET_MOD_DIR }
                 elseif ($env:CLAUDE_CONFIG_DIR) { Join-Path $env:CLAUDE_CONFIG_DIR 'puppet-master\mod' }
                 else { Join-Path $env:USERPROFILE '.claude\puppet-master\mod' }
       try {
           $hb = Get-Content (Join-Path $modDir "heartbeat\$($d.session_id).json") -Raw -ErrorAction Stop | ConvertFrom-Json
           $ageMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - [double]$hb.beat
           if ($hb.override -and $ageMs -lt 15000) { $pmOv = $hb.override }
       } catch {}
   }
   ```

3. Replace the two lines that read the model and the effort:

   ```powershell
   $modelText = if ($pmOv) { "$([char]0x21C4) $($pmOv.model)" } else { $d.model.display_name }
   $effortLevel = if ($pmOv) { $pmOv.effort } else { $d.effort.level }
   ```

   The model shows as puppet-master names it, such as `sonnet` or a full `claude-…` id, not as Claude Code's display
   name.

4. Under Windows PowerShell 5.1 (`powershell`, not `pwsh`), add this line near the top of the script:

   ```powershell
   [Console]::OutputEncoding = [Text.Encoding]::UTF8
   ```

   Claude Code reads your script's output through a pipe, and Windows PowerShell 5.1 writes it in the console's
   code page, so the `⇄` arrow comes out as `?`. Rather keep the output as it is? Use a plain marker instead of the
   arrow, for example `"pm> $($pmOv.model)"`.

## Check it worked

In a session puppet-master switched, the status line shows the switch after its next refresh:

```text
…  ⇄ sonnet  medium  …
```

A session without a switch, or without the mod, shows the model and effort as before.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `? sonnet` in place of `⇄ sonnet` | Add the `OutputEncoding` line from step 4, or use a plain marker |
| The old model, though the line under the prompt says `switched to …` | Check that the mod folder your script uses is the one the mod writes to: set `PUPPET_MOD_DIR` or `CLAUDE_CONFIG_DIR` the same way for both |
| The switch still shows after a reset | Wait a few seconds: the mod rewrites the heartbeat every 3 seconds |

## Related

- [Run background workers](run-background-workers.md): how and when puppet-master switches a session
- [Troubleshooting](../reference/troubleshooting.md)
