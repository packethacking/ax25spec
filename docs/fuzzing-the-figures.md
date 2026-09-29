# Fuzzing the Figures

**A decision brief on searching the AX.25 SDL figures themselves for defects, rather than the runtimes that implement them.**

Written 10 September 2026, out of the [ax25spec#40](https://github.com/packethacking/ax25spec/issues/40) cascade. Positions marked *suggest* are recommendations, not decisions. A rendered version of this brief is also published as an artifact.

**Status (10 September 2026, evening):** actioned. The findings, the calibration score and one novel hypothesis are in [fuzzing-the-figures-findings.md](fuzzing-the-figures-findings.md).

---

## Why this is newly possible

The AX.25 v2.2 Annex C state machines stopped being pictures some time ago. They are now machine-readable tables in this repository, emitted by [packet-net/ax25sdl](https://github.com/packet-net/ax25sdl) into seven language backends with typed closed sets over guards, events and action verbs. The design is executable data.

That changes what a search campaign can target. Until now every property test in this ecosystem has run against *an implementation* of the figures and inferred things about the figures from how it behaved. You can now interrogate the figures directly, and a counterexample is a figure defect rather than a bug report.

The provoking case is ax25spec#40. The out-of-sequence `I_received` arm had no receive-window guard, so a duplicate of an already-acknowledged frame drew an SREJ naming a frame that would never exist. It was found by sampling, took a specific loss pattern to hit, and sat undiscovered for as long as it did because sender-side guards in every runtime absorbed the symptom.

> **The trap that shaped this brief.** The erratum's own citation says it plainly: sender-side live-window guards "absorb the spurious SREJs this path used to emit, which is why the receiver-side gap went unnoticed. Absence of observed breakage is not evidence the figure was sound here." A campaign that only looks for observable misbehaviour will keep missing this class.

## The framing that matters most

A search over a design finds only what its invariants can express. **The invariants are the product; the search is just how you look for violations of them.** Most of the effort, and nearly all of the judgement, goes into deciding what must be true, which is also the part that yields something worth sending upstream.

The sharpest invariants here are *cross-station*: properties of the pair, not of one machine. That is structurally what the existing single-sided property tests cannot state, and it is exactly where #40 lived.

## Three things "fuzz the design" could mean

| Approach | What it does | Effort | Yield |
| --- | --- | --- | --- |
| **Static totality** | Per (state, event), enumerate assignments of the live guard atoms; assert exactly one transition matches. Zero is a hole in the figure, two is nondeterminism. | Low | High |
| **Two-station model** | Explore two interacting instances over a lossy, duplicating, reordering channel. Checks progress, not just safety. | High | High |
| **Differential** | Drive our stack and a real implementation against each other through a fault-injecting channel; flag divergence. | Medium | Very high |

Static totality is the cheapest by a wide margin and needs no modelling judgement at all. `ax25sdl` already lints decision-branch completeness and guard overlap, but syntactically: it checks the drawn Yes/No pairs, not the semantic space. The exhaustive version is tractable because only a handful of atoms are live on any one arm, not all 37.

The two-station model is the one that finds #40-class defects, because a livelock is a *progress* violation and sampling is worst at those. The state space is small once bounded: six data-link states plus the MDL pair, sequence variables mod 8, bounded queues.

Differential has the best evidence-to-effort ratio because the infrastructure already exists, and because its findings come with the one thing a model checker cannot produce: a real implementation visibly doing the wrong thing.

## Calibrate before trusting a single novel finding

**This is the strongest idea in the brief.** The quirk registry is a catalogue of known figure defects with known reproductions. Run any checker against the figures *as they stood before* each erratum landed, and require it to rediscover them. If it cannot find the ones we already know about, its silence on everything else means nothing.

Two are ground truth in the strongest sense, found, filed, fixed upstream, and the quirk retired:

| Erratum | Defect |
| --- | --- |
| ax25spec#38 | SREJ retransmitted go-back-N rather than the single frame |
| ax25spec#40 | out-of-window duplicate raised an unclearable exception |

The rest are live, still-unfixed figure defects carried as named quirks in all three runtimes. Each is a defect a sufficiently powerful checker ought to surface unprompted:

| Erratum | Defect |
| --- | --- |
| #41 | Karn SRT sampling: unguarded T1V feedback is self-amplifying |
| #42 | SREJ targets the arriving frame, not the gap |
| #43 | DL-FLOW-OFF acts on the wrong branch, so a not-busy station never enters busy |
| #44 | mod-128 connect routes to the wrong state |
| #45 | FRMR fallback does not re-establish at v2.0 |
| #47 | TimerRecovery drain decrements V(r) instead of incrementing |
| #48 | DM to a SABME tears down rather than degrading |
| #9 | acknowledgement progress does not reset RC |
| #13 | SREJ window is not clamped to half the modulus |

Nine live defects and two settled ones is a respectable regression suite for a technique that has not yet earned trust. Build it first; treat it as the gate on believing anything new.

## Invariants worth stating

Safety is largely covered already by `InvariantChecker` in packet.net (in-order, gap-free, duplicate-free delivery). The unclaimed ground is progress and coherence:

- **Every SREJ names a frame the peer can actually send.** That is #40 stated exactly, and it generalises: a reject that asks for something outside the peer's outstanding set is incoherent whatever produced it.
- **No unclearable exception.** No reachable state where one station holds a REJ or SREJ condition that no behaviour available to the peer can clear. This is the livelock, expressed as a state property rather than as a timeout.
- **Quiescence under a fair channel.** From any reachable state, if the channel eventually delivers, both ends return to a quiescent Connected state. The classic liveness property, and the one sampling approximates badly with a settle bound.
- **Acknowledgement coherence.** A station's V(a) never advances past what the peer has actually sent, across every interleaving of loss and duplication.

## Traps to design around

**Laundering implementation choices as spec findings.** The figures deliberately delegate to "the implementation" in places: buffer behaviour, what *Check I Frames Acknowledged* actually does. A model must fill those in. Fill them in with packet.net's choices and you are testing our runtime again while calling the result a spec defect. Every counterexample needs the question asked of it: *does this depend on a choice the figure did not make?*

**Mod-8 with a large k is unsound by construction.** Selective repeat requires k of at most half the modulus. At modulo 8 with k up to 7, wrapped-duplicate counterexamples are the protocol's own constraint, not a figure bug. This is precisely why `Ax25Spec13` exists. Constrain k in the model or classify those out, or the real findings drown in them.

**Evidence class decides whether an erratum lands.** The BPQ finding of 10 September carries weight because it is a dated transcript of a widely-deployed implementation misbehaving on 40m. "Our model checker found a trace" is weaker and more arguable to someone who has to change working code. Treat checker output as a *hypothesis generator*, and reserve filing for what can then be reproduced against a real implementation.

## Suggested order of work

1. **Static totality and determinism.** Exhaustive per (state, event) over the live atoms. No channel, no invariants to argue about, every hit a figure defect. Lands as an `ax25sdl` lint that actually runs, unlike the five fail-open ones deleted on 10 September, whose targets lived in other repos and never executed.
2. **The calibration suite.** Rediscover #38 and #40 against their pre-fix figures. Then see how many of the nine live quirks fall out. Publish that score before making any novel claim.
3. **Two-station progress model.** Only worth the effort once step 2 says the invariants have teeth. Build on the reference interpreter in [ax25sdl#75](https://github.com/packet-net/ax25sdl/pull/75) rather than starting fresh.
4. **Differential against real implementations.** Reuse pdn-bbs's LinBPQ oracle stack and the KISS tee. Use it to promote model-checker hypotheses into filable evidence.

## Decisions to make

**Static only, or static plus dynamic?** The static check is nearly free and self-justifying. The dynamic model is a real project. *Suggest committing to static now and gating the model on the calibration score.*

**TLA+, SPIN, or a hand-rolled explorer?** A hand-rolled breadth-first explorer in C# reads the JSON tables directly and reuses `InvariantChecker` and `TwoStationHarness`; TLA+ gives better counterexample minimisation and a language for fairness. *The reuse argument is strong enough that the hand-rolled option probably wins on time-to-first-finding.*

**How are the delegated semantics pinned?** Pin them from packet.net (fast, but risks laundering) or leave them nondeterministic (purer, larger space). *Suggest nondeterministic where the figure is genuinely silent, pinned where the prose settles it, with the choice recorded per subroutine.*

**Build on ax25sdl#75, or fresh?** That PR has been open since 9 July and is most of an executable model already. *Read it before writing anything; if it is sound, finishing it is the cheapest path to step 3.*

**What is the output contract?** Errata PRs straight to this repository, or a findings report first. *Suggest a report first. The working group's appetite is finite, and a flood of unsound-by-construction findings would spend credibility that the on-air transcript just earned.*

## What already exists

| | |
| --- | --- |
| **Tables** | 8 state pages plus subroutines, 254 transitions, 37 guards / 143 action verbs / 38 events. `ax25sdl/spec/json/*.g.json`, schema-validated. |
| **In flight** | `ax25sdl#75` reference interpreter and golden traces; `ax25sdl#76` clean-room SREJ conformance traces. Both open since 9 July. |
| **Harnesses** | `packet.net/tests/Packet.Ax25.Tests/Session/Conformance/`: `TwoStationHarness.cs`, `InvariantChecker.cs` (safety oracle), `LossRecoveryProperties.cs` (FsCheck, found #40), `AdversarialChannelProperties.cs` (duplicating channel), `TransitionCoverageTests.cs` (242 of 254 reachable). |
| **Real peers** | `pdn-bbs/docker/compose.oracle.yml` stands up LinBPQ plus net-sim. The KISS tee (`radio1:/tmp/kisstee.py`) decodes both directions and injects faults on a live link. |
| **Evidence** | `spec-sdl/**/*.citations.yaml` records direwolf and LinBPQ behaviour per transition, with file and line. |

The citation sidecars deserve a second look. They already record, per transition, how direwolf and LinBPQ handle it. That is a hand-built differential analysis covering the paths someone thought to check, and a campaign could treat it both as prior art and as a map of which arms have never been compared.
