# Fuzzing the Figures: findings

**What was built against the [decision brief](fuzzing-the-figures.md) on 10 September 2026, what it found, and what it could not find.**

This is the report the brief asked for ("suggest a report first"). Nothing here has been filed as an erratum. The one novel finding is a hypothesis with independent corroboration, and the brief's evidence-class rule still applies: it is reproduced against a real implementation before anyone is asked to change working code.

---

## In one minute

- All three checkers now exist and run in CI in [packet-net/ax25sdl](https://github.com/packet-net/ax25sdl): a static totality and determinism lint ([#88](https://github.com/packet-net/ax25sdl/pull/88)), the reference interpreter with its prose-derived golden traces and the clean-room SREJ traces ([#75](https://github.com/packet-net/ax25sdl/pull/75), [#76](https://github.com/packet-net/ax25sdl/pull/76), both open since July, now merged), and a two-station bounded explorer with a calibration suite ([#89](https://github.com/packet-net/ax25sdl/pull/89)).
- **The figures are total and deterministic.** Every (state, event) arm and every subroutine selects exactly one path over every feasible valuation of its guard atoms. This was also true before the #40 fix, so a static check could not have found #40, as the brief expected.
- **The calibration score is 10 of 11.** Between the explorer's invariants and the golden traces, every known defect except #41 (a numeric timer property) is rediscovered. The explorer alone finds #40 on the pre-fix tables and goes silent on the fixed ones, and finds #42, #47, #9 and the #44/#48 connect-phase pair unprompted on the current tables, with counterexamples of 2 to 30 steps.
- **One novel hypothesis, H1:** a station can enter Timer Recovery and never leave it, because figc4.5 exits only on an F=1 supervisory response and has no T3 arm, so an acknowledgement that arrives on an I frame strands it with T1 stopped. direwolf's source carries an author's note describing the same symptom and a coded workaround. It was the dominant signature on the exploration grid (66 of 116 violating cells), and **it reproduces on packet.net's runtime in both quirk modes** ([packet.net#811](https://github.com/packet-net/packet.net/pull/811)): the stranded station never sends a keepalive poll, and with the figure run as drawn the retry counter ratchets across recoveries on a working link until N2 declares it dead.
- **Nothing else surfaced.** A 576-cell grid over the current tables produced no violation that is not H1, #42 or #47 at k of 4 or less.
- Still to do: the differential step (reproduce H1 against LinBPQ through the oracle stack), then file it; close #38, which PR #65 fixed without closing; and extend the explorer's move set so it can reach #43 and #45.

---

## What landed

| PR | What | Where it runs |
| --- | --- | --- |
| [ax25sdl#88](https://github.com/packet-net/ax25sdl/pull/88) | Static totality and determinism lint over a guard-atom domain model, with a strict allow-list | Every codegen invocation, so every CI drift job |
| [ax25sdl#75](https://github.com/packet-net/ax25sdl/pull/75) | Reference interpreter over `spec/json/*.g.json` plus 15 prose-derived golden traces with strict xfail | `semantic-traces` CI job |
| [ax25sdl#76](https://github.com/packet-net/ax25sdl/pull/76) | Three clean-room SREJ traces, committed before first execution | Same job |
| [ax25sdl#89](https://github.com/packet-net/ax25sdl/pull/89) | Two-station bounded explorer, invariants, calibration suite, pre-fix table fixtures, `docs/explorer.md` | `semantic-explorer` CI job |

The design documents live next to the code: `docs/lint-totality.md`, `docs/golden-traces.md` and `docs/explorer.md` in ax25sdl.

---

## Step 1: static totality and determinism

For every (state, event) arm the lint takes the union of guard atoms the arm's transitions mention, enumerates the feasible valuations of those atoms, and requires exactly one transition to match each. Zero is a hole; two is nondeterminism. Subroutines are checked the same way over their paths. A transition crossing an "Undefined" spec branch counts as covering its valuations but not toward nondeterminism.

Feasibility is the crux, and it is decided by a domain model rather than by hand-written exclusion rules: the 37 atoms are defined as functions of the underlying protocol variables (sequence numbers modulo 8, k in 1..7, the one P/F bit, the command/response role, the frame type, the modulus, T1 as stopped/running/expired, RC against N2 and NM201), each next to a spec citation, and the feasible set falls out of concrete enumeration. Where the spec settles nothing the atom is a free boolean and says so. State-space invariants (for example that outstanding frames never exceed k) are deliberately not encoded: they are reachability facts, not definitions, and leaving them out can only make the lint over-report.

| Run | Arms | Feasible valuations | Holes | Overlaps |
| --- | --- | --- | --- | --- |
| Current figures (pin d8f67ad) | 120 arms, 13 subroutines | 8051 | 0 | 0 |
| Figures before the #40 fix (abd46b0) | same | 4979 | 0 | 0 |
| Mutation: one out-of-window leaf deleted from figc4.4 `I_received` | | | 1, with witness V(r)=1, N(s)=0, k=4, P=0 | 0 |

The honest reading: the figures never had a hole or an overlap in the sense this lint can see. #40 was a drawn branch doing the wrong thing, and static totality cannot see behaviour. There were not even syntactic holes for the domain model to classify out. The lint earns its place as a guard against future transcription slips, not as a defect finder on the figures as they stand. The allow-list file exists but is empty.

---

## The executable model and the golden traces

The reference interpreter executes the JSON tables directly and is backend-free. The golden traces write expected behaviour from the prose before reading the tables, and a trace that fails because the figure is wrong stays prose-true and is marked with the upstream issue; a passing xfail fails the suite.

| Trace | Result | Upstream |
| --- | --- | --- |
| 11 original scenarios (connect, disconnect, I-frame exchange, T1 recovery, REJ both sides, RNR, SABME, resets) | pass | |
| `srej-connected-selective-retransmit` (clean-room) | pass | |
| `srej-round-trip` (clean-room) | **pass, xfail removed** | [#38](https://github.com/packethacking/ax25spec/issues/38), fixed by [#65](https://github.com/packethacking/ax25spec/pull/65) |
| `srej-timer-recovery-f0` (clean-room) | **pass, xfail removed** | same |
| `dl-flow-off-sets-busy` | xfail | [#43](https://github.com/packethacking/ax25spec/issues/43) |
| `dl-connect-v22-awaits-v22` | xfail | [#44](https://github.com/packethacking/ax25spec/issues/44) |
| `frmr-fallback-downgrades-to-sabm` | xfail | [#45](https://github.com/packethacking/ax25spec/issues/45) |
| `sabme-connect-applies-mod128` | xfail | [#54](https://github.com/packethacking/ax25spec/issues/54) |

Suite: 22 pass, 4 strict xfail. The clean-room SREJ traces are the independence control the brief wanted: authored from §4.3.2.4, §4.4.4, §6.4.8 and direwolf only, committed before first execution, they failed against the pre-fix figc4.5 and pass against the fixed one. That is independent confirmation of the #38 correction, and #38 can now be closed (PR #65 said "Refs" rather than "Closes").

---

## Steps 2 and 3: the two-station explorer and its calibration

Two interpreter instances over a modelled channel (FIFO per direction, drop and duplicate faults under a budget, no reordering by default), explored breadth-first from a seeded state over every enabled move: deliver a head frame, spend a fault, pop the I-frame queue, answer an owed LM seize, or fire T1 once nothing is in flight. Invariants run after every step:

- **Safety**, ported from packet.net's `InvariantChecker`: defined states, sequence variables in range, outstanding frames never above k, and each station's delivered data is an exact in-order prefix of what the peer submitted.
- **Reject coherence**, which is #40 stated exactly and generalised: an SREJ or REJ must name a frame the emitter has not received in sequence, and when it arrives the peer must still hold that frame.
- **Acknowledgement coherence**: V(a) never advances past what the peer has actually delivered, tracked with unwrapped counters.
- **Quiescence under a fair channel**, as a graph property over the states reachable after the fault budget is spent, plus the cheaper deadlock check. A station in Timer Recovery is not quiescent, per §4.4.5.1.
- **Selective-recovery progress**: with SREJ negotiated, recovery must not need a T1 expiry. Implemented, but it has no discriminating calibration case yet (the #42 runaway makes the space infinite before it can run), so treat it as unproven.

### Calibration score

Pre-fix tables were regenerated from this repository's history with the current codegen (`abd46b0` for pre-#40, `fb727db` for pre-#38) and checked in as fixtures with the commit and command recorded.

| Defect | Tables | Scenario | Caught by | Shortest |
| --- | --- | --- | --- | --- |
| #40 out-of-window duplicate raises an unclearable exception | pre-40 | 2 frames, budget 1, dup, SREJ on and off | reject coherence, receiver side: A gets a REJ naming a frame it never sent | 4 |
| #40 fixed | current | same | nothing fires: the duplicate is discarded | |
| #38 SREJ go-back-N in Timer Recovery | pre-38 vs pre-40 | 3 frames, 2 drops, SREJ | **not discriminated by any invariant**: go-back-N still delivers in order. The clean-room traces are the detector. A test pins that both table sets give the same verdict | |
| #42 SREJ names the arriving frame | current | 3 frames, 2 drops, SREJ | reject coherence, emitter side: B sends SREJ for a frame it already holds. With that check off, the SREJ-count bound catches the runaway at 16 | 6 |
| #47 Timer Recovery drain decrements V(r) | current | k=2, 1+3 frames, 2 drops, SREJ | delivery safety: a frame is delivered twice after the drain steps V(r) back | 24 |
| #9 acknowledgement progress does not reset RC | current | 3 frames, N2=2, 3 drops restricted to interior I frames | deadlock: both stations Disconnected after DL-ERROR (T) with every frame delivered and acknowledged | 30 |
| #13 window at half the modulus | current | k=7, drop+dup, SREJ off | reject coherence, receiver side, on a wrapped duplicate at distance 6. **Classified as the protocol's own constraint, not a figure defect**; clean at k=4 | 13 |
| #44 mod-128 connect routes to the wrong state, #48 DM to a SABME tears down | current | Disconnected seed, A at modulo 128, peer declines SABME | deadlock: A sits in AwaitingConnection after SABME, the DM disconnects it, the data is lost | 2 |
| #43 DL-FLOW-OFF on the wrong branch | current | not reached: no `DL_FLOW_OFF_request` move | golden trace | |
| #45 FRMR fallback does not re-establish at v2.0 | current | not reached: nothing generates FRMR | golden trace | |
| #54 Set_Version_2_2 never invoked | current | reached but invisible in 3 frames | golden trace | |
| #41 Karn SRT sampling | | out of scope: symbolic timers | not caught | |

Reading it plainly: the invariants have teeth. They discriminate on #40, rediscover four live defects without being told where to look, reach the connect-phase pair in two steps, and correctly classify the k=7 trap. Their blind spots are honest and documented: an inefficiency that still delivers in order (#38), anything numeric (#41), and moves the model does not yet make (#43, #45). The first #9 attempt is worth remembering as a method lesson: with unrestricted drops the explorer found only "three polls lost, N2 exhausted", which is N2 doing its job; the scenario had to restrict losses to interior I frames to isolate the defect.

---

## Novel findings

Hypotheses, not defects. Each has been asked the brief's question: does it depend on a choice the figure did not make?

### H1. A station can enter Timer Recovery and never leave it

Shortest trace 20 steps: no SREJ, A sends 2 frames and B sends 3, one loss. A's second frame is lost. A's T1 expires and it polls. B's F=1 answer acknowledges only the first frame, so A retransmits and stays in Timer Recovery, which is what figc4.5 says. The retransmission gets through. The acknowledgement for it arrives on B's next I frame. In Timer Recovery that I frame runs `Check_I_Frame_Acknowledged`, whose N(r)=V(s) path stops T1 and starts T3, but the state stays Timer Recovery: figc4.5 leaves it only on an F=1 supervisory response, and it has no T3 expiry arm. A now sits in Timer Recovery with T1 stopped, nothing outstanding, RC=1, and no drawn path that will ever move it.

What the figure implies from there: the T3 keepalive is dead for this station (no arm to receive the expiry), and the next data it sends restarts T1 with RC still 1, so the retry counter creeps toward N2 across unrelated exchanges. That is where #9 bites.

Dependency check: the only modelling choice involved is treating Timer Recovery as non-quiescent, which §4.4.5.1 supports ("the timeout condition is cleared by the reception of an acknowledgement for the sent frame(s)"). The retransmission pinning re-emits the frame as every implementation does, and the quiescent-timeout rule only orders events realistically.

Corroboration: direwolf's `i_frame()` in `src/ax25_link.c` (at eda1383f) carries an author's note before its `state_4_timer_recovery && va == vs` exit: "I noticed that we sometimes got stuck in state 4 and rc crept up slowly even though we received 'I' frames with N(R) values indicating that the other side received everything that we sent. Eventually rc could reach the limit and we would get an error". It adds a transition to state 3 on full acknowledgement and notes "a similar situation for RR/RNR for cases other than response, F=1". An implementation has independently hit this and coded around it.

Candidate fix, for the working group rather than this report: either an exit to Connected from the figc4.5 `I_received` arm when the acknowledgement clears the window (direwolf's shape), or a T3 arm in figc4.5, and the RC reset of #9 alongside.

**Reproduced on packet.net.** A deterministic two-station harness test ([packet.net#811](https://github.com/packet-net/packet.net/pull/811)) replays the model's trace on the real runtime with the ack riding on the peer's I frame. In both the default and the strictly-faithful quirk modes the station ends in Timer Recovery with V(s)=V(a), T1 stopped, T3 running and RC=1. A T3 expiry then does nothing: the event has no arm in figc4.5 and the runtime drops it, so no keepalive poll is ever sent. The peer's own polls are answered with RR F=1 and change nothing. The next data restarts T1 with RC still 1, so its first expiry counts as the second retry. Across repeated recoveries the default mode's #9 quirk clamps RC at 2; the faithful figure ratchets 1, 2, 3 and on the next loss tears down a link that was delivering everything (DL-ERROR I, DM, both ends Disconnected), which is direwolf's "rc crept up slowly" note exactly. The control case, the same recovery with the ack on an RR, completes through the poll cycle and returns to Connected with RC=0; only the ack carrier differs. So this is now a figure defect visible in a faithful runtime, not only in a model, and the remaining step before filing is the on-air reproduction against LinBPQ.

**A runtime-only defect seen in the same trace** (packet.net, not the figure): figc4.5's partial-ack arm ends with "Set Acknowledge Pending" and raises no LM-SEIZE, relying on the retransmitted frames popping off the queue to clear the flag. packet.net replays retransmissions inline (so they keep their original N(s)) and never runs the pop arm, so the flag stays set; the peer's next I frame then hits the "ack already pending" arm and is not acknowledged until the peer's own T1 poll. That costs the peer a T1 after every partial-ack recovery, stuck or not. It is pinned by the same test and filed as [packet.net#812](https://github.com/packet-net/packet.net/issues/812).

### H2. `Invoke_Retransmission` with N(r) = V(s) pushes eight frames that do not exist

A nuance under #13, not a separate claim. figc4.7 draws the retransmission loop as a do-while, so with X = V(s) = N(r) the body runs once before the test and then seven more times round the modulus. It is only reachable through an incoherent REJ: on the pre-#40 tables from a duplicate, on the current tables only at k=7. Every real implementation loops while N(s) is not V(s) and sends nothing. It depends on the pinned choice that a frame with no retained copy is an error rather than skipped, and it may be simply unreachable once #40 and the half-modulus constraint hold.

### The grid

The current tables were run over frames 0..3 each way, budget 0..2, k in {2, 4}, SREJ on and off, faults drop, dup and both: 576 cells, every one exhausted under a 1.2 million visited-state cap. Outcomes: 460 clean; 66 deadlocks, all H1; 45 reject-coherence hits, all the #42 signature; 5 delivery duplicates, all #47 at k=2. A second pass with reject coherence off and Timer Recovery counted as quiescent, to look behind #42 and H1, found only the same #42 runaway (caught by the SREJ-count bound) and the same five #47 duplicates. No acknowledgement-coherence, livelock or machine-error violation appeared anywhere at k of 4 or less.

---

## Pinned delegated semantics

The brief's laundering trap is real and the model hit it immediately. The figures delegate retransmission to "the implementation": figc4.7 backtracks V(s) and loops "Push Old I Frame onto Queue", but the only drawn pop path stamps N(s) := V(s), so a literal reading renumbers retransmitted frames and no loss is ever recoverable. The interpreter in #75 had modelled the re-queue and left the re-emission unexpressed (its ambiguity #1). The explorer pins it the way every real implementation does: the station retains each I frame it has sent by N(s), and the push verbs re-emit the retained frame with its original N(s). Two consequences were chosen deliberately: a re-queued frame the station holds no copy of is a model error rather than a silently skipped frame, because that sender-side skip is exactly the guard the brief says absorbed #40; and a twice-queued frame is sent twice, as the figure says.

The full list of nine pinned choices, each with the citation that settles it or a note that it is a judgement call, is in ax25sdl `docs/explorer.md` under "Pinned delegated semantics". Every counterexample above was asked whether it depends on one of them.

---

## Citation coverage map

The brief suggested treating the citation sidecars as a map of which arms have never been compared against a real implementation. Of the 267 transitions and subroutines, 219 carry at least one implementation citation.

| Page | Arms | Uncited | Where the gaps are |
| --- | --- | --- | --- |
| figc4.1 Disconnected | 17 | 0 | |
| figc4.2 Awaiting Connection | 25 | 1 | DL-DISCONNECT request |
| figc4.3 Awaiting Release | 20 | 0 | |
| figc4.4 Connected | 68 | 2 | DL-FLOW-OFF not-busy branch (the #43 arm), DL-FLOW-ON busy branch |
| figc4.5 Timer Recovery | 92 | 38 | nearly all the RR, RNR, REJ and SREJ arms, plus two I-received leaves |
| figc4.6 Awaiting v2.2 Connection | 25 | 0 | |
| figc4.7 Subroutines | 13 | 0 | |
| figc5.1 / figc5.2 Management Data Link | 7 | 7 | all |

Timer Recovery is where H1 lives, where #38 and #47 lived, and where 41 percent of the arms have never been compared. That is the obvious place to spend the next citation pass, and it is also where the differential step should point first.

---

## Decisions, against the brief's suggestions

| Question | Suggestion in the brief | Taken |
| --- | --- | --- |
| Static only, or static plus dynamic? | Static now, gate the model on the calibration score | Both built; the score above is the gate, and it passed |
| TLA+, SPIN, or hand-rolled? | Hand-rolled probably wins on time to first finding | Hand-rolled C# BFS over the JSON tables; first finding the same afternoon |
| Delegated semantics? | Nondeterministic where silent, pinned where the prose settles it, recorded per subroutine | Pinned and recorded (nine entries); nothing left nondeterministic in this version, which is a limit worth revisiting |
| Build on ax25sdl#75 or fresh? | Read it first; finish it if sound | Sound; rebased and merged with #76, then extended |
| Output contract? | Report first | This document; no errata filed |

---

## Limits to keep in mind

- Static totality sees structure, not behaviour. It could not have found any of the eleven known defects.
- An invariant cannot see an inefficiency that still delivers in order, so #38-class defects are the traces' territory.
- Timers are symbolic. Anything numeric (#41, Karn, T1 backoff) is out of reach until a numeric extension exists.
- T3 is disabled in the explorer and T1 fires only when nothing is in flight. Premature-timeout interleavings are not explored.
- The channel does not reorder, on the grounds that a single AX.25 channel does not; the N(r) validity checks presuppose order.
- k above half the modulus is unsound by construction and every calibration case except #13 runs at k of 4 or less.
- Selective-recovery progress is implemented but unproven.
- The management data-link machine is not modelled; XID negotiation and its figures are untouched by all three checkers.

---

## Recommended next steps

1. **Differential, step 4 of the brief.** Reproduce H1 against LinBPQ through the pdn-bbs oracle stack and the KISS tee: bidirectional data, lose one I frame from the LinBPQ side's peer, let the acknowledgement ride on an I frame, then watch whether LinBPQ's keepalive poll ever comes. A dated transcript is what turns H1 into an erratum.
2. **File H1** once reproduced on air, with the packet.net reproduction and the direwolf note as the second and third pieces of evidence, and propose the fix shape above together with #9. Decide in packet.net whether to carry a quirk (an exit to Connected on a clearing I-frame ack, direwolf's shape) ahead of the figure fix, since the runtime is exposed today.
3. **Fix the packet.net acknowledge-pending defect** left behind by inline retransmission ([packet.net#812](https://github.com/packet-net/packet.net/issues/812)), which is independent of the figure.
4. **Close #38.**
5. **Extend the explorer's move set** with `DL_FLOW_OFF_request` / `DL_FLOW_ON_request` and a v2.0 peer model that answers SABME with FRMR or DM, so #43, #45 and #48 become reachable as invariant violations rather than trace expectations.
6. **Add a golden trace for #48** (DM to a SABME) and for the H1 scenario, so a future figure change is noticed.
7. **Spend the next citation pass on Timer Recovery** and the management data-link pages.
8. **A numeric-timer extension** would bring #41 and the T1 backoff behaviour into reach; it is the one class no checker here can express.
