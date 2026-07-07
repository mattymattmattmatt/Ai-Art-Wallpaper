# Stage 5 — Fullscreen TV display + boot-to-art autostart

Goal: the 70" TV always shows the newest painting, survives reboots, and
the whole system comes up unattended.

## 1. Test the display server

```
scripts\start_display.bat
```

Open <http://localhost:8800>. You'll see the newest image from
`data\images\` on pure black; when a new artwork lands, the page
crossfades to it within `display.refresh_seconds` (20 s). Useful extras:

- `http://localhost:8800/api/status` — last prompt + gallery count
  (also reachable from your phone on the LAN: `http://<mini-pc-ip>:8800`)
- Tap the **bottom-right corner** of the page → requests a new painting.

`display.fit` in config: `contain` letterboxes the full painting;
`cover` fills the whole 70" panel edge-to-edge (crops a little).

## 2. Test kiosk mode manually

```
start msedge --kiosk http://localhost:8800 --edge-kiosk-type=fullscreen
```

True fullscreen, no browser chrome, cursor hidden by the page CSS.
Exit with `Ctrl+Alt+Del` → sign out, or `Alt+F4`.

## 3. Autostart everything at boot

One elevated PowerShell, one time:

```
powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
```

This registers five logon tasks with staggered start delays (so the N150
isn't slammed): ComfyUI → listener → display → kiosk browser →
orchestrator. Each restarts automatically if it crashes. Ollama already
autostarts via its own installer.

For a true appliance, also enable **auto-logon** so a power cut brings
the frame back with no keyboard: run `netplwiz`, untick "Users must enter
a user name and password", enter the password once. (Standard trade-off:
anyone at the physical machine gets in — fine for a home art frame.)

And in Windows Settings:
- Power → screen: **never turn off** when plugged in; sleep: **never**.
- TV side: disable auto-off / enable "PC mode" for clean 1:1 pixels.
- Windows Update → set Active Hours so it doesn't reboot mid-evening
  (the frame recovers after reboot anyway, thanks to the tasks).

## 4. Reboot test

Reboot the mini PC and touch nothing. Within ~2 minutes you should get:
fullscreen black page → previous artwork appears → (a few minutes later)
the orchestrator begins its first cycle. Check `data\logs\` if anything
is missing, and `Get-ScheduledTask "ArtFrame*"` to see task states.

## 5. Done when…

- [ ] TV shows art fullscreen with no visible UI
- [ ] New images crossfade in automatically
- [ ] A cold reboot restores everything unattended

That's the complete system. See **TROUBLESHOOTING.md** for the fix-it
list, and the README for day-2 maintenance.
