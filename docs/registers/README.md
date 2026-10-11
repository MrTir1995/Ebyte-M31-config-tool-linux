# M31 register evidence inventory

Research date: **2026-10-11**. This is an offline, source-backed inventory,
**not a device-tested map, runtime allowlist, or authorization to probe/write**.
`document_extraction: 1.0` measures transcription confidence, not live firmware
availability. Every hardware-verification flag is false. No binaries, full
manuals, copied implementations, or private capture files are included.

## Files and coverage

| Artifact | Scope |
|---|---|
| [non-u-en-v1.1.json](non-u-en-v1.1.json) | Complete register inventory of the English non-U V1.1 manual: all **13 tables** in §4.8, continued pages and register-bearing prose. **30 table definitions + 1 conflicting AO prose claim**, **70 table rows + 1 prose row**, **50 distinct explicit hexadecimal addresses**. Includes evidence, raw references, types, access, defaults, ambiguity, profiles, model scope and runtime-name aliases. |
| [known-host-ranges.csv](known-host-ranges.csv) | **38** finite, derived host-only channel-family ranges across **12** primary-manual host models; excludes speculative expansion endpoints and the alternative AO prose base. |
| [analog-process-values.csv](analog-process-values.csv) | **40** process-value rows from four AI conversion tables, including two original decimal/hex conflicts. These hexadecimal numbers are **values**, not addresses. |
| [source-comparison.json](source-comparison.json) | Source URLs/hashes/revisions, relationships, evidence policy, patterns, counterexamples and reference/frame findings. |
| [cross-model-comparison.csv](cross-model-comparison.csv) | **25** feature comparisons, with source-specific physical PDF/printed-page citations and scope/FC/stride counterexamples. |
| [u-only-registers.csv](u-only-registers.csv) | **64 U1 field/family definitions**, scoped to U devices only. Includes overlapping IO/network fields as well as U-specific identity, commands, pulse, startup/fault AO, PT100 and web fields. **Not 64 newly discovered non-U addresses.** |
| [hypotheses.json](hypotheses.json) | Six inert candidate groups, alternatives, conflicts, support counts and requirements for future evidence. Never merged into the non-U definitions. |
| [community-evidence.json](community-evidence.json) | Four attributable public sources, **25 register/code claims**, pinned GitHub citations, community report and bounded negative-search coverage. Code-derived claims remain hypotheses; community-reported behavior is not our hardware verification. |

“Complete” means all register material in this primary manual, **not all hidden
firmware registers**. Firmware/model identity, save, restart, factory reset,
startup/failsafe AO, channel counters, discovery payloads and software-offset
addresses are not established for non-U by this manual. Manual V1.1 is not a
minimum supported firmware version; the firmware compatibility discussion
mentions non-U host V1.1/V1.2 without a per-register availability matrix.

## Source matrix

All primary definition evidence names `m31_non_u_en_v1_1`. Page fields distinguish
physical `pdf_page_one_based` from printed `manual_page`; the English register
tables occupy printed pp.45–53 / physical pp.49–57. Full SHA256 values, revision
dates, source model lists and citations remain in the JSON/CSV artifacts.

| Source ID | Own source / revision | Interpretation and independence |
|---|---|---|
| `m31_non_u_en_v1_1` | [English non-U host V1.1](https://www.cdebyte.com/pdf-down.aspx?id=3402), 2026-01-29; 63 PDF pages | Primary definition source; SHA256 `d6fc301f…aa58545`. |
| `N1` | [Chinese non-U host V1.1](https://www.ebyte.com/downpdf/2086.html), 2026-01-29; 53 pages | Same vendor/model family, translated/shared material; documents-only comparison. |
| `E1` | [Chinese non-U expansion V1.1](https://www.ebyte.com/downpdf/2101.html), 2026-01-29; 38 pages | Twelve expansion models; tables describe the aggregate host space, **not independent per-slot slave maps**. Shared text is not another hardware test. |
| `U0`, `U0EN` | [Chinese U V1.0](https://www.ebyte.com/Uploadfiles/Files/2025-5-7/2025571054433756.pdf), 2025-05-06; [English companion](https://www.cdebyte.com/Uploadfiles/Files/2025-5-29/2025529157331126.pdf) | One U manual lineage; translation is not independent support. |
| `U1` | [Chinese U V1.4](https://www.ebyte.com/downpdf/2460.html), 2026-05-19; 73 pages | Updated U scope; revisions do not constitute separate device observations. |
| `UE1` | [Chinese U expansion V1.3](https://www.ebyte.com/downpdf/2462.html), 2026-01-29; 52 pages | U-only; extensive shared host/expansion wording. |
| `L1` | [Chinese LoRa V1.1](https://www.ebyte.com/downpdf/2307.html), 2025-07-02; 62 pages | Different -L/-L9 variant; copied text cannot prove non-U compatibility. |
| `S1` | [English document on Spanish official site](https://www.es-ebyte.com/pdf-down.aspx?id=5094), V1.1; 63 pages | **Identical SHA256 to the primary English PDF**; not Spanish technical text or independent corroboration. |
| `F1` | [Official non-U upgrade instructions](https://www.ebyte.com/pdf-down/3538.html), V1.2 package | Instructions establish version information, not a register/discovery/firmware wire protocol. |
| `github-m31config` | [PVKonovalov/m31config](https://github.com/PVKonovalov/m31config), pinned commit in JSON | M31-AAAX4440G; console reports and Go layout/setters. Requests 89 words but decodes 88; the last requested word is not another established field. |
| `github-gunio-m31` | [Gunio2322/M31](https://github.com/Gunio2322/M31), pinned commit in JSON | M31-AAAX4440G; explicitly manual-derived DI/DO/AI mapping. Float high-word-first is a code assumption, not a known-value capture. |
| `github-hacs` | [bartosz-777/ebyte-m31-hacs](https://github.com/bartosz-777/ebyte-m31-hacs), pinned commit in JSON | DI implementation and mocked tests. Model dropdowns/default eight bits do not prove installed channel counts. |
| `community-modbus-cn` | [modbus.cn report](https://www.modbus.cn/28388.html), 2024 community setup/screenshots | Model/firmware UI visible; underlying register commands and discovery payload unknown. |

The user's own repository is explicitly excluded as independent evidence.
Public repositories are attributable, but not necessarily independent
derivations of the manual. Bounded GitHub/issues/forum/indexed searches located
no additional usable non-U register captures for the queried models/addresses;
that is **not proof that no other post or implementation exists**.

## Established patterns versus counterexamples

- Addresses are **zero-based PDU addresses**. A vendor prefix `0/1/3/4` names a
  Modbus table; its normalized numeric reference is PDU decimal **+1**. Preserve
  inconsistent printed references separately. DI0, DO0, AI0 and AO0 belong to
  four different tables.
- Non-U has ten channel families, two **global** filter fields, and **18 module
  fields** at `0x7530`–`0x7589`, including negotiation trigger **`0x7585`**.
  Multiword fields occupy exactly their documented words: MAC3, IPv4 fields2,
  destination64, fault bitmap2. `0x753F`/`0x7540` have **no defined semantics**.
  An example community block read covering the gaps does not define them.
- Installed channels append **within their IO type**, not a guessed per-module
  block. IEEE754 families have **two words/value and stride2**; others stride1.
  Host models with zero channels have no local family range. Model count symbol
  **`A` means 16**, not hexadecimal ten; this pattern is only checked against
  the twelve listed non-U models, not a universal model-name decoder.
- Repeated non-U/U/LoRa networking addresses are a pattern across three variant
  document families from **one vendor, zero independent hardware tests**.
  U DI filtering is **per-channel `0x1388`**, not non-U global `0x0DA3`;
  U AI filtering is table **per-channel `0x0FA0`**, despite conflicting U prose
  `0x0DA2`. U/non-U negotiation write FC permissions also differ.
- Non-U AO range table **`0x1194`** conflicts with prose **`0x0DAC`**.
  U agreement favors a copied prose error but does **not resolve non-U hardware**.
  AO process table FC/zone identifies HR`0x01F4`, yet prints `3-0501`; normalized
  `4-0501` is computed, not a silently corrected quotation. XGXX current/voltage
  classification, voltage units and two process-value conversions also conflict.
- An eight-DI continuation printed `0x0008..0x0010` has nine addresses; channel
  arithmetic ends `0x000F`. U reference columns have separate +1/duplicate
  errors. The **five primary RTU example CRCs and TCP lengths/PDU equivalence
  match offline calculations**; this does not validate device behavior.
- Sixteen expansion modules, U maximum sixteen including host, thirty-two
  descriptor slots, sixteen storage flags and thirty-two bitmap bits are
  **different limits**, not justification for thirty-two physical expansions.

The registry contains negotiation commands for completeness. The existing
device snapshot omits trigger `0x7585`; retaining command evidence here does
not add it to the snapshot or trigger negotiation. All data here is inert.
Conflicts never provide automatic write permission, including AO range.

## Candidate matrix (not non-U facts)

Exact addresses, source-specific citations and rejection/conflict conditions
are in [hypotheses.json](hypotheses.json). Every group has **zero independent
device observations** and disabled runtime/probe/write flags.

| Group | Candidate / support | Alternative or counterexample preventing promotion |
|---|---|---|
| `H1` | Host identity: U `0x0C1F`/`0x0C20`/`0x0C2C`; two U revisions, **one lineage, zero non-U address sources** | Official non-U UI may use discovery/private transport; known filter-map changes defeat blind U transfer. |
| `H2` | Expansion descriptors/version/storage arrays; two U revisions, **one lineage, zero non-U address sources** | Discovery-derived tree, different packing or host-internal slot ordering; 32 descriptor slots versus 16 storage/physical limits. |
| `H3` | Restart/reset: U `0x0C1D`/`0x0C1E` and U magic value; **one U lineage, zero non-U address sources** | Private tool command or different generation map. Never try a command to settle a hypothesis. |
| `H4` | Gap `0x753F`–`0x7540`: three document variant families, **one vendor, zero semantic sources** | Padding, legacy/private fields or invalid addresses; Go `Free` field is not a meaning. |
| `H5` | Save-to-flash: two sources describe UI save, **zero identify a register** | Auto-persistence or separate commit/reload command; U storage-enable flags are not save triggers. |
| `H6` | Discovery/firmware transport: **zero wire-spec sources** | Broadcast/unicast/proprietary/bootloader transport; UDP socket mode is not discovery evidence. |

Promote only with model/firmware-specific vendor confirmation or offline
interpretation of an already captured official-tool exchange identifying
address, table, FC, length and semantics. No automatic probe, inferred gap
scan, save/reset command or hardware test is part of this research.

## Offline validation

Run `python -m unittest tests.test_register_inventory` in the project's existing
environment. Tests check portable data/schema, evidence separation, aliases,
addresses, finite host footprints, channel counts, source relationships and
printed frame arithmetic; they do not open a connection.

## Integrated software acceptance

Version **0.5.0** passed the complete Linux and native Windows suites:
**229 tests, 228 passed, one opt-in hardware test skipped** on each platform.
Windows completed in 103.377 seconds using its normal text-codepage default,
without a UTF-8-mode override. Inventory text reads specify UTF-8 explicitly.
Compilation, dependency checks, wheel build and native GUI startup/close passed.
The operational read-preparation catalog has 12 IO entries plus the 17 existing
device read fields; exact word counts and selection without IO are tested.

These checks establish artifact consistency and software behavior, **not
physical register availability**. Candidate groups remain inert and separate;
no manufacturer EXE, hardware probe or experimental write was executed.
