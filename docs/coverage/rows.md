# The harness's real row names -- authoritative list, regenerate with `python3 tools/harness.py --list`

Why this file exists: TODO.md's ticket texts and several landed Result paragraphs name guard rows that the harness has never
defined, so a worker told to re-run 'the 8-row guard set' spends captures on names that print DID NOT RUN, and a stamp that
reports one of those numbers is reporting nothing. Checked 2026-09-17 with `git log -S <name> -- tools/harness.py` (0 commits
ever touched the literal) and with `grep -rn <name> tools/*.py` (no definition anywhere):

| name cited in tickets | exists? | the real row it probably meant |
|---|---|---|
| `chip-volport` | NEVER EXISTED | `chip-vdoll` (or `wave`) |
| `chip-wave` | NEVER EXISTED | `wave` |
| `memcheck` | NEVER EXISTED | `chip-recovery`/`chip-recov30..300`, or `tiles`+`gauge` for the HUD |
| `chips` | NEVER EXISTED as a row | the `chip-*` family, 44 rows |
| `chip-poison` | NEVER EXISTED | `chip-poisseed` |
| `chip-godstone`, `chip-collect`, `chip-paralyze`, `chip-tornado` | NEVER EXISTED | no close analogue; T130's own land gate named them |
| `emblem`, `menu` | NEVER EXISTED | `banner`, `card`, `window`, `windowclose`, `popup`, `rollup` |
| `result_lose`, `panel_steal`, `navi1`, `super_armor` | exist only on their own UNMERGED branches | that is why those branches are not landed |

## Today's full table (69 rows, from --list)

opening both  40 | mettaur isolated  70 | cannon isolated  40 | chip-cannon isolated  40 | chip-hicannon isolated  40 | chip-mcannon isolated  40 | chip-airshot isolated  40 | chip-vulcan isolated  60 | chip-vulcan2 isolated  70 | chip-vulcan3 isolated  80 | chip-suprvulc isolated  113 | chip-sword isolated  40 | chip-wideswrd isolated  40 | chip-longswrd isolated  40 | chip-wideblde isolated  40 | chip-longblde isolated  40 | chip-fireswrd isolated  40 | chip-aquaswrd isolated  40 | chip-elecswrd isolated  40 | chip-bambswrd isolated  40 | chip-muramasa isolated  40 | chip-minibomb isolated  60 | chip-energbom isolated  60 | chip-megenbom isolated  60 | chip-flshbom isolated  48 | chip-blkbomb isolated  50 | chip-bigbomb isolated  75 | chip-lilbolr isolated  48 | chip-poisseed isolated  70 | chip-iceseed isolated  70 | chip-grasseed isolated  70 | chip-bugbomb isolated  70 | chip-vdoll isolated  70 | chip-recovery isolated  40 | chip-recov30 isolated  40 | chip-recov50 isolated  40 | chip-recov80 isolated  40 | chip-recov120 isolated  40 | chip-recov150 isolated  40 | chip-recov200 isolated  40 | chip-recov300 isolated  40 | chip-areagrab isolated  77 | chip-invisibl isolated  80 | chip-barrier isolated  80 | chip-barr100 isolated  80 | chip-barr200 isolated  80 | tiles both  8 | gauge both  8 | field both  40 | field-bg1 isolated  40 | field-bg2 isolated  40 | field-bg3 isolated  40 | warp both  30 | buster both  28 | buster_charge both  32 | chip-use both  30 | wave isolated  90 | gunner both  130 | window isolated  16 | card isolated  16 | cursor isolated  170 | windowclose isolated  40 | result isolated  40 | banner isolated  58 | popup isolated  80 | emotion_syn isolated  40 | emotion_face_b isolated  40 | emotion_skip isolated  40 | rollup n/a  2600 | 
