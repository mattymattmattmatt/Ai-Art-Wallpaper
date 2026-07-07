# Stage 5 — Fullscreen TV display + boot-to-art autostart

Goal: the 70" TV always shows the newest painting, survives reboots, and
the whole system comes up unattended.

## 1. Test the display server

```
scripts\start_display.bat
```

Open <http://localhost:8800>. You'll see the newest image from
`data\images\` on pure black; when a new artwork lands, the page
crossfades to it within `display.refresh_seconds` (20 s).

**The control panel.** Move the mouse into the **top-right corner** of the
screen and a panel slides out showing:
- the live pipeline stage (Idle / Listening back / Composing / Painting),
  with elapsed time while an image is being painted;
- the prompt for whatever is on screen (or being painted right now), with
  a **star** to pin it as a favorite — favorites are never pruned and get
  extra turns in the slideshow;
- a **System** health row — Mic (listener), Cycles (orchestrator),
  Painter (ComfyUI), Prompter (Ollama) — green means alive, red means
  that component is down or stale (see TROUBLESHOOTING);
- a **Gallery** strip of recent artworks — click one to view it (the
  frame returns to live art after 10 minutes, or tap the "back to live"
  pill bottom-left);
- a **"Paint a new one now"** button — the manual override, same as
  `trigger_now.bat` or `data\trigger.flag`.

**Slideshow.** With `display.slideshow_enable: true` (default) the frame
rotates through the gallery every `slideshow_minutes` (12) instead of
holding one painting for 3 hours. A freshly painted artwork always
interrupts the rotation and takes the screen. Favorites appear
`slideshow_favorites_boost` (2) times per shuffle.

When the mouse is idle the screen is **pure artwork** — no cursor, no
buttons. The moment you move the mouse, the cursor and a small round
opener (top-right) fade in; move into the corner or click the opener to
slide the panel out, and everything fades back to bare art a few seconds
after you stop. The panel is also reachable from your phone on the LAN at
`http://<mini-pc-ip>:8800`, and the raw data is at
`http://localhost:8800/api/status`.

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

## 5. Using the PC normally again (on/off switch)

The frame takes over the machine at boot. When you want the PC back:

```
scripts\artframe_off.bat     :: click through the admin prompt
```

This disables the autostart tasks (so they won't return on the next
reboot) **and** stops everything running right now — the kiosk browser,
ComfyUI, and the listener/display/orchestrator — leaving you a normal
desktop. Your regular Edge windows and other Python are left untouched;
it only kills the frame's own processes (matched by command line).

To turn it back into an art frame:

```
scripts\artframe_on.bat      :: re-enables autostart and starts it now
```

No reboot needed — the kiosk reappears within a few seconds. (Both
scripts need admin, which the `.bat` files request for you via a UAC
prompt.)

## 6. Reboot test

Reboot the mini PC and touch nothing. Within ~2 minutes you should get:
fullscreen black page → previous artwork appears → (a few minutes later)
the orchestrator begins its first cycle. Check `data\logs\` if anything
is missing, and `Get-ScheduledTask "ArtFrame*"` to see task states.

## 7. Done when…

- [ ] TV shows art fullscreen with no visible UI
- [ ] New images crossfade in automatically
- [ ] The top-right panel shows live status and the override button works
- [ ] A cold reboot restores everything unattended
- [ ] `artframe_off` / `artframe_on` reclaim and restore the machine

That's the complete system. See **TROUBLESHOOTING.md** for the fix-it
list, and the README for day-2 maintenance.
