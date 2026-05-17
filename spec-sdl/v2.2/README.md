# `spec-sdl/v2.2/` — clean published v2.2 transcriptions

This directory will hold transcriptions of the **published v2.2 spec** — the black-only content of the SDL figures, with no errata applied.

It's currently empty. The published v2.2 baseline is **pending backfill** (planned by Tom). Once it lands, codegen will emit two parallel namespaces (`Packet.Ax25.Sdl.Published.*` and `Packet.Ax25.Sdl.WithErrata.*`) and consumers will be able to pick at runtime via `SdlRevision.{Published, WithErrata}`.

Until then, the only transcribed revision is the **v2.2-errata** variant — see [`../v2.2-errata/`](../v2.2-errata/). Consumers can only use that revision; the `Published` enum entry will throw or be hidden until this directory is filled.

## Source of truth

The figures themselves are the canonical source. Within each AX.25 SDL figure:

- **Black-only content** is the published v2.2 spec → transcribed here.
- **Red and green annotations** are errata that haven't been formally released → transcribed in [`../v2.2-errata/`](../v2.2-errata/) (the file there should match what the figure looks like with errata applied, i.e. black + red + green).

A page that has no errata gets transcribed identically into both directories (CI lint enforces byte-identity for those, eventually).

See [the repo CLAUDE.md](../../CLAUDE.md) for the SDL transcription discipline.
