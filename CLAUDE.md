# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a greenfield repository. As of this writing it contains only `README.md` and `LICENSE` — there is no source code, build tooling, or test suite yet. When scaffolding the project, update this file with the actual build/lint/test commands and architecture once they exist.

## What this project is

OpenFieldDay is a self-hosted alternative to the N3FJP amateur-radio logging software. N3FJP is the de-facto Windows logging suite used for ham-radio contests and ARRL Field Day; this project aims to replace it with software that runs on a Raspberry Pi connected to a TV (the TV acting as a shared scoreboard/log display for an operating group).

Implications worth keeping in mind for any implementation:
- **Target hardware is a Raspberry Pi** — keep the runtime lightweight and ARM-compatible.
- **Primary output is a TV display** — the UI is meant to be read at a distance by a room, not just an individual operator. Favor large, glanceable layouts.
- **Domain is amateur radio contest logging** — core concepts will include QSOs (contacts), callsigns, bands/frequencies, modes, exchanges, dupe checking, and scoring. N3FJP's feature set and file/log formats (e.g. ADIF, Cabrillo) are the reference point for compatibility.

## Notes

- The `LICENSE` is MIT but still carries a template copyright line ("Copyright (c) 2021 Julien Phalip"). Update it to the real author/year before publishing.
