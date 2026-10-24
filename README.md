# Medway Lunch Menu for Tronbyt

A native Tronbyt app that displays the published lunch menu for Medway Middle
School on a 64×32 Tidbyt/Tronbyt device. It reads the public Nutrislice menu
without a separate computer, login, or background service.

The app shows **only the single menu item directly below** Nutrislice's
**American Classics** heading for each weekday. It rotates between two
full-width screens: Monday, Tuesday, and Wednesday for the first half of the
display duration; Thursday and Friday for the second half. Weekend menus are
never displayed. On Saturday or Sunday, it previews the upcoming
Monday-to-Friday week.

## Requirements

- A running [Tronbyt server](https://github.com/tronbyt/server) and a configured
  64×32 device.
- The public [Medway Middle School lunch menu](https://medwayschools.nutrislice.com/menu/medway-middle-school/lunch).
- Python 3.10+ only if you use the optional installer. No Python packages are
  required.

## Install through Tronbyt

1. In your device's **Add App** page, upload
   [`tronbyt/lunch_schedule.star`](tronbyt/lunch_schedule.star).
2. Add the uploaded app to the device.
3. Set the app's **School timezone** to `US/Eastern`.
4. Set the app's **Display Time Seconds** and device display duration to the
   same value (for example, `60` seconds).
5. Set the render interval to **1 minute** and enable **Show full animation**.
6. Save and check the preview.

Each screen gets half the configured duration. Each row spans the full display
width, and long meal names scroll in the space beside the weekday label.
The scroll restarts on each screen, and the two-screen animation loops.

## Optional command-line installer

Copy `.env.example` to `.env`, fill in your Tronbyt server and device details,
then run:

```sh
python install_tronbyt.py
```

The installer uploads the app, adds it to the selected device, and configures
the display duration. It records the installation ID in
`.local/installation.json`, so running it again updates the same installation.
Keep this local state file to avoid creating a duplicate app. If you installed
manually, update the app through the Tronbyt web UI.

The installer overwrites this app's configuration and display settings on each
run. It does not modify other apps or firmware. A successful upload does not
guarantee that a menu is currently published; verify the app's preview.

## How it works

- Requests the public Nutrislice weekly menu API for Medway Middle School's
  lunch menu.
- Uses the `US/Eastern` school timezone to choose the current school week, or
  the upcoming week on Saturday and Sunday.
- Displays only the food item immediately following the American Classics
  heading for each weekday, rotating between Monday-Wednesday and
  Thursday-Friday screens.
- Caches reduced menu data for four hours and pauses retries for 15 minutes
  after an API error.
- Uses the school's published menu data directly; it does not log in to
  Nutrislice or send menu data to a third-party service.

Nutrislice menu publication and API behavior are controlled by the school and
the provider. If the menu is unavailable or the endpoint changes, the display
shows a visible error and retries later.

## Privacy

No Nutrislice credentials are needed. The optional installer uses your Tronbyt
login and device API key to configure your own server. Anyone with sufficient
access to that server may be able to read those credentials or app settings.
Never commit `.env`, `.local/`, or private device details.

## Development

Run the offline regression tests:

```sh
python -m unittest discover
```

Tests use synthetic API responses and mocked Pixlet modules. They cover
featured-meal extraction, the two-column weekly layout, upcoming-week
selection, caching, date boundaries, and installer configuration. They do not
replace a render test on Tronbyt.

Files:

- `tronbyt/lunch_schedule.star`: native app, Nutrislice fetch, and display.
- `install_tronbyt.py`: optional app deployment helper.
- `config.py`: local installer configuration loader.
- `test_*.py`: offline regression tests.

## License

MIT. See [LICENSE](LICENSE). Not affiliated with Medway Public Schools,
Nutrislice, Tidbyt, or Tronbyt.
