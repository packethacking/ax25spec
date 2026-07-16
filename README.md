# ax25spec

[doc/ax.25.2.2.4_Oct_25.md](doc/ax.25.2.2.4_Oct_25.md) is a Markdown version of AX.25 Link Access Protocol for Amateur Packet Radio version 2.2 Revision 4: 27 October 2025

[doc/ax.25.2.3-draft.md](doc/ax.25.2.3-draft.md) is an in-progress draft of a v2.3 AX.25 spec. The filename is stable across revisions; each iteration of the draft is marked with an annotated git tag (`ax25-v2.3.1.0`, `ax25-v2.3.1.1`, `ax25-v2.3.1.2`, …). The first three components are the version the working group will eventually release (v2.3.1 — the number chosen by the author); the fourth increments per draft iteration, and `ax25-v2.3.1` itself is reserved for the release. The draft's changelog table records what changed. Tags are namespaced with `ax25-` so revisions of the other specs in this repo can be tagged alongside.

[doc/kiss-tnc-protocol.md](doc/kiss-tnc-protocol.md) is a Markdown version of the KISS TNC protocol specification.

[doc/multi-drop-kiss-operation.md](doc/multi-drop-kiss-operation.md) is a Markdown version of the Multi-Drop KISS operation specification. This document also describes G8BPQ's Acknowledgement Mode, better known as ACKMODE.

[doc/il2p-specification-v0.6.md](doc/il2p-specification-v0.6.md) is a Markdown version of version 0.6 of the Improved Layer 2 Protocol (IL2P).

The source documents are in [/src](src).

[doc/fbb-forwarding-protocol.md](doc/fbb-forwarding-protocol.md) is a description of the FBB (F6FBB) Forwarding Protocol compiled from public sources, covering message forwarding between amateur packet radio BBS systems, including compressed transfer modes and the B2F extension used by Winlink.

## Machine-readable SDL sources — `spec-sdl/`

[spec-sdl/](spec-sdl) holds the normative machine-readable transcriptions of the AX.25 state-machine SDL figures (the Annex C figc4.x series), relocated here from [packet-net/ax25sdl](https://github.com/packet-net/ax25sdl) (git history preserved) so that a single PR in this repo can change a figure and its prose together.

| Path | What | Normative or derived |
| --- | --- | --- |
| `spec-sdl/**/sdl/*.graphml` | The canonical yEd figure sources | **Normative** |
| `spec-sdl/**/yaml/*.sdl.yaml` | Transcriptions generated from the graphml by ax25sdl's `Packet.Sdl.Transcribe` walker, committed here | Derived (drift-locked by CI) |
| `spec-sdl/**/yaml/*.citations.yaml` | Human-curated evidence/citation sidecars | Normative |
| `spec-sdl/**/svg/` | Figure renders — the human-reviewable visual diff for figure changes (regenerate with `python3 tools/render/render_all.py`) | Derived |
| `spec-sdl/**/mmd/*.g.mmd` | Mermaid renderings (emitted by ax25sdl's codegen) | Derived |
| `spec-sdl/schema/`, `events.yaml`, `predicates.yaml`, `actions.yaml`, `lint-targets.yaml` | The SDL YAML DSL schema + canonical event/predicate/action catalogues | Normative |

The derived-artifact chain: **graphml → yaml happens here** — CI's `transcribe-drift` job regenerates the yaml with the [packet-net/ax25sdl](https://github.com/packet-net/ax25sdl) tooling commit pinned in [.github/ax25sdl-tooling-ref](.github/ax25sdl-tooling-ref) and fails on drift. **yaml → generated code happens downstream** in packet-net/ax25sdl, which consumes this repo as a pinned git submodule and emits ready-to-use state tables for C#, TypeScript, Go, Rust, C, Python and JSON. Figure/spec changes are made **here**; a pin-bump PR in ax25sdl then regenerates the language backends.

The transcription discipline (shape classes, encode-then-verify, revision provenance) is documented in ax25sdl's [docs/](https://github.com/packet-net/ax25sdl/tree/main/docs) (`sdl-primer.md`, `sdl-transcription-runbook.md`).

Please feel free to raise issues and PRs vs this repo.

## Future targets

- APRS101.pdf and the corrections page
