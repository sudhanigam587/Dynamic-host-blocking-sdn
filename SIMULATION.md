# Interactive Simulation

A browser-based visualization of the Dynamic Host Blocking System, built to help explain how the system works.

**Link:** [Open simulation](https://gemini.google.com/share/0068d21b9389)

## What it shows
- Topology: Ryu controller, OpenFlow switch, hosts h1, h2 (normal clients), h3 (attacker), h4 (server)
- Controls to start/stop normal traffic, simulate an attack from h3, and reset
- Live traffic graph and a flow-statistics table (active flows, packets, bytes per source IP)
- A controller log panel in the style of `events.log`

## Important note
This is an **illustration only**. The numbers and log lines in the simulation are generated for demonstration. The actual results of this project come from the real Mininet + Ryu run documented in [README.md](README.md).
