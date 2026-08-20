# Pressure Monitor — How It Works

This document explains what `pressure_monitor.py` does and how its pieces fit
together. It's a refrigeration/HVAC monitoring tool that checks pressure
readings against setpoints, calculates superheat and subcooling, and gives a
plain-language fault diagnosis for each reading cycle.

## Requirements

- Python 3
- `tkinter` (used for the setup form — most Python installs include this
  already; on Linux it may need installing separately, e.g. `python3-tk`)

No other dependencies. Everything else used (`logging`, `dataclasses`,
`datetime`, `sys`) is part of the Python standard library.

## Running it

```
python3 pressure_monitor.py
```

A setup window opens first (see below). Once you submit it, the program
switches to the terminal and starts asking for live readings on a loop.

To force a different client instead of reusing the saved one:

```
python3 pressure_monitor.py --new-client
```

## The two phases

The program runs in two distinct phases:

1. **Setup (once, via a GUI window)** — client info, refrigerant, pressure
   setpoints, target superheat/subcooling, and the check interval are all
   collected in a single Tkinter form (`collect_setup_gui()`).
2. **Monitoring (repeating, via the terminal)** — `monitor()` loops
   indefinitely: take a reading, check it, print/log the result, ask
   whether to continue. It only stops when the user types `q`.

Everything collected in phase 1 gets bundled into one `SystemConfig` object
and passed into phase 2, so the monitoring loop never has to ask "what's the
setpoint again?" — it already knows.

## Phase 1: the setup form

`collect_setup_gui(force_new_client=False)` builds a small window with these
fields, in this order:

| Field | Comes from |
|---|---|
| Client Name | typed, or pre-filled from last run |
| Client Address | typed, or pre-filled from last run |
| Refrigerant | dropdown — one of `R410A`, `R22`, `R134A`, `R404A` |
| High Pressure limit (bar) | typed, or pre-filled |
| Low Pressure limit (bar) | typed, or pre-filled |
| Target Superheat (C) | typed, or pre-filled |
| Target Subcooling (C) | typed, or pre-filled |
| Interval (hours) | typed, or pre-filled |

Clicking **Continue** runs `parse_and_validate_setup_inputs()`, which checks:
- Name and address aren't blank
- Refrigerant is one of the four supported types
- Every numeric field actually parses as a number

If anything fails, an error message appears in the window and nothing
closes. If everything's valid, the values are saved to disk and the window
closes.

### Why the form pre-fills itself

Every value from a submitted form gets written to **`setup_config.txt`** via
`save_setup()`. The next time the program runs, `load_setup()` reads that
file back and the form opens with everything already filled in — so on a
second run you can just click Continue without retyping anything.

`--new-client` only clears the **name and address** fields before showing
the form; everything else still pre-fills. The reasoning: a pressure
setpoint or target superheat belongs to the *equipment* you're servicing,
not to whichever client happens to own it this visit, so switching clients
shouldn't wipe out equipment settings you'd otherwise have to re-enter.

### The file format

`setup_config.txt` is a plain text file, one value per line, in a fixed
order (`SETUP_FIELDS`):

```
client_name
client_address
high_pres
low_pres
target_superheat
target_subcooling
interval_hours
```

Refrigerant is **not** saved here — it's always re-selected fresh each run
from the dropdown.

## Phase 2: the monitoring loop

`monitor(config, interval_seconds)` repeats this sequence until you type `q`:

1. **Take a reading** — `take_readings()` asks four questions in the
   terminal: Analogue High pressure, Analogue Low pressure, Suction Line
   Temperature, Liquid Line Temperature. All four are currently typed in by
   hand — they're written as stand-ins for values that will eventually come
   from real analogue sensors, which is why the prompts are worded
   "Analogue High Input value" etc.
2. **Log who and when** — `get_reading_time()` grabs the current date/time,
   and it's printed/logged alongside the client's name and address so every
   line in the log file is traceable to a specific visit.
3. **Check pressure against the setpoints** — `fault_alarm()` (see below).
4. **Check superheat/subcooling against the targets** —
   `report_superheat_subcooling()` (see below).
5. **Ask whether to continue** — Enter continues the loop, `q` stops it.

Everything printed to the terminal is also written to **`faults.log`** via
`log_and_print()`, a small helper that just does both at once so the two
never drift out of sync.

## Concept: tolerance and classification

Pressure readings are never going to land on an *exact* setpoint — a sensor
reading 30 bar when the setpoint is 30.0 will actually show something like
30.02 or 29.97. To handle that, every comparison in this program goes
through a "close enough" check rather than `==`.

**`tolerance(measured, setpoint, percentage)`** — returns `True` if
`measured` is within `percentage` (default 5%) of `setpoint`. The allowed
gap scales with the setpoint itself: a 30 bar setpoint gets a wider gap than
a 5 bar one.

**`classify(value, setpoint)`** — uses `tolerance()` to bucket a pressure
reading into one of three states:
- `"equal"` — within tolerance of the setpoint
- `"above"` — clearly higher
- `"below"` — clearly lower

This three-way classification is what drives the pressure fault lookup
below.

## Concept: the pressure fault table

**`FAULTS`** is a dictionary keyed by `(high_state, low_state)` — the
classification of the high-side reading paired with the classification of
the low-side reading — mapping to a plain-English diagnosis:

| High side | Low side | Diagnosis |
|---|---|---|
| equal | above | TEV Failure |
| above | below | High Pressure Exceeded |
| below | above | Refrigerant Leak / Airflow Restricted |
| below | below | Inefficient Compressor |
| above | above | Condenser Airflow Restricted |
| equal | equal | No fault detected |
| below | equal | Possible Low-Side Restriction *(needs review)* |
| equal | below | Possible TEV Overfeeding *(needs review)* |
| above | equal | Possible Partial High-Side Fault *(needs review)* |

`fault_alarm()` looks up this table each cycle. If a combination isn't
listed, it defaults to `"No fault detected"` rather than crashing.

### Confirmed alarms

A single bad reading could just be sensor noise. `monitor()` tracks how many
**consecutive** cycles produce the *same* fault message
(`CONSECUTIVE_READINGS_REQUIRED = 3`); only once that streak is hit does it
print/log a `*** CONFIRMED ALARM ***` line at `WARNING` level instead of the
normal `INFO` level. Any different result — including "No fault detected" —
resets the streak.

## Concept: superheat and subcooling

Raw pressure alone can be misleading for diagnosing a refrigeration system —
the industry-standard approach is to compare pressure-derived saturation
temperatures against actual measured temperatures.

**PT tables (`PT_TABLES`)** — every refrigerant has its own
pressure-to-saturation-temperature relationship. This program has that
relationship baked in as a lookup table (already converted to bar/°C) for
four refrigerants. R404A is a blend with "temperature glide," so it needs
*two* curves — `"bubble"` for the liquid side (used for subcooling) and
`"dew"` for the vapor side (used for superheat). The other three refrigerants
use one shared curve, stored under `"single"`.

**`saturation_temp(pressure, pt_table)`** — given a pressure, linearly
interpolates between the two nearest table points to estimate the
saturation temperature. Returns `None` if the pressure falls outside the
table's range entirely.

**`calc_superheat()`** — `suction line temperature − saturated evaporating
temperature` (looked up from the low-side pressure).

**`calc_subcooling()`** — `saturated condensing temperature − liquid line
temperature` (looked up from the high-side pressure).

## Concept: charge diagnosis

Once superheat and subcooling are known, `classify_sh_sc()` buckets each one
into `"low"`, `"normal"`, or `"high"` relative to the **target range** set
during setup (target value ± `SH_SC_TOLERANCE`, currently 2°C either side).

**`SH_SC_DIAGNOSIS`** maps each `(superheat_state, subcooling_state)`
combination to a diagnosis, based on standard HVACR service-training logic:

| Superheat | Subcooling | Diagnosis |
|---|---|---|
| high | low | Undercharge / refrigerant leak |
| low | high | Overcharge / TXV stuck open |
| high | normal | Restriction or low evaporator airflow |
| high | high | Liquid-line restriction |
| low | normal | Floodback risk |
| normal | low | Borderline undercharge |
| normal | high | Overcharge or condenser issue |
| normal | normal | No charge-related fault |

`diagnose_charge()` looks this up; any combination not covered falls back to
an "inconclusive" message rather than guessing.

**Why a TXV matters here:** on a system with a thermostatic expansion valve
(TXV), the valve actively works to hold superheat near a fixed target, which
can partly mask an undercharge on the superheat reading alone — that's why
subcooling tends to be the more reliable charge indicator on TXV systems,
and why both are checked together rather than either alone.

## Data files this program creates

| File | Written by | Contents |
|---|---|---|
| `setup_config.txt` | `save_setup()` | Client info, setpoints, targets, interval — one value per line |
| `faults.log` | Python's `logging` module | Timestamped record of every reading, fault, and diagnosis |

Both are plain text and safe to open in any text editor.

## Known limitations / things to know before relying on this

- **Every reading is currently typed in by hand.** The prompts say
  "Analogue" because they're placeholders for real sensor input that hasn't
  been wired in yet — swapping them for actual ADC/sensor reads shouldn't
  require touching anything outside `take_readings()`.
- **`SH_SC_TOLERANCE` (2°C) and `TOLERANCE_PERCENTAGE` (5%) are starting
  placeholders**, not calibrated values — tighten or loosen them to match
  your actual sensor precision and service practice.
- **Target superheat/subcooling are fixed values you set once**, which
  matches how TXV systems work. Fixed-orifice systems don't have one
  correct target superheat — it shifts with outdoor/indoor conditions and
  needs a manufacturer's target-superheat chart. Using this program as-is
  on a fixed-orifice system will give a target that's often wrong.
- **The interval value is currently unused.** `set_interval()`/
  `interval_seconds` are collected and passed through, but nothing in the
  loop actually pauses — each cycle waits on you pressing Enter, not on a
  timer.
