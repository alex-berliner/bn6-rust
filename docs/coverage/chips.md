# The reachable chip set (T116) -- what a battle can actually reach, measured from the ROM

The 411-record table `ChipDataArr_8021DA8` (`data/ChipDataArr.s`, stride 0x2c,
`include/rom_structs/ChipData.inc`) is not the playable universe. The game's own
gates, each cited:

1. **id < 0x19B (411)** -- the folder/hand validation replaces any item whose
   id is >= 0x19b with the error chip (`tooManyGigasMegasAntiCheatHappensHere_800B022`,
   `asm/asm00_1.s:17512-17515`, `dword_800B104 = 0x19b`; also :17449).
2. **the record has at least one code** -- a folder item is an (id, code)
   pair; the pack quantity lookup matches the code against the record's four
   code bytes (`getOffsetToQuantityOfChipCodeMaybe_8021c7c`,
   `asm/asm03_0.s:305-333`). Exactly one named id has no code at all:
   MegaBstr (id 0, codes 0xFFFFFFFF).
3. **a display name** -- `data/textscript/TextScriptChipNames0.s` holds 256
   `def_text_script` blocks (ids 0..255) but only 238 `.string` entries;
   `TextScriptChipNames0_unkN` names chip id N, and ids 203..220 carry no
   string (placeholder rows: family 0x14, sharing Cannon's image block and
   the byte_8725914 icon). Ids 256..410 have no def at all. CORRECTION over
   T75's shape: "238 names = ids 0..237" was wrong -- the strings are ids
   0..202 + 221..255 (T75's name-based conclusions only touched ids < 203
   and stand). The DarkChips 320..349 are named from
   `TextScriptChipNames1.s` through a separate render path
   (asm32.s:35325/:35412) and are excluded here; M4's line covers
   standard/mega/giga/secret. NOTE: R also contains no giga id -- the 13
   giga rows (301..319) are named through the same untraced
   TextScriptChipNames1 path, so a follow-up that traces it should expect
   R to grow by 13.

**R = 237: chip ids 1..202 and 221..255.** The battery save
(`/tmp/bn6f_real.srm`, read only, never tracked) is a minimal demo save; its
EWRAM pack, dumped live (`mgba_capture --loadsave /tmp/bn6f_real.srm` + 400
frames, then `--dump 0x2002230:0x1400` --
`getOffsetToQuantityOfChipCodeMaybe_8021c7c`'s 12-bytes-per-id region) owns
12 chip types (ids 1, 4, 5, 54, 71, 72, 89, 154, 163, 175, 184, 192) -- all
inside R: a soundness check, not the universe.

Canon's own reader of the table (step 1, measurement): `getChip8021DA8`
(`asm/asm02.s:2-14`) computes `ChipDataArr_8021DA8 + id*44` (stride 0x2c) --
called at chip use by `useChipFromHand_800FB54` (`asm/asm00_2.s:2037/:2107`)
and at the chip-select/custom-screen draw by `sub_8027D10`
(`asm/asm03_0.s:3780-8832`; the card renderer's 0x540 copy at :4399-4409,
its `getChip8021DA8` call at :4427). Two ids dumped live from
`/tmp/bn6f_real.gba` (`--dump 0x8021DD4:0x2c`, `--dump 0x8022B94:0x2c`) are
byte-identical to the `.s` table:

- id 1 Cannon @0x8021DD4: codes 1a020100, elem 00, libtype 0, mb 6, fam 14, pw 40
- id 81 StepSwrd @0x8022B94: codes ff0f0b01, elem 00, libtype 0, mb 28, fam 13, sub 01, pw 160

(An earlier --dump of id 81 at 0x8022B6C was an off-by-0x20 arithmetic slip
in MY address math, not in the table: 81*44 = 0xDEC, not 0xDCC.)

## Three-way table over all 411 rows

| set | count |
|---|---|
| in `assets/chips.bin` (the pre-T116 48-record asset) | 48 |
| reachable (R) | 237 |
| pixel-verified on the scoreboard (`tools/scoreboard.py` CHIPS) | 43 |
| reachable AND in asset | 48 (the asset is a subset of R) |
| verified AND in asset | 43 |
| classes of R | {'standard': 201, 'secret': 1, 'mega': 35} |

## Gap lists

**Reachable but not in the asset (189)** -- M4's queue once the asset
carries the reachable set:

9(Spreadr1), 10(Spreadr2), 11(Spreadr3), 12(TankCan1), 13(TankCan2), 14(TankCan3), 15(GunDelS1), 16(GunDelS2), 17(GunDelS3), 18(GunDelEX), 19(YoYo), 20(FireBrn1)
21(FireBrn2), 22(FireBrn3), 23(WideSht), 24(TrnArrw1), 25(TrnArrw2), 26(TrnArrw3), 27(BblStar1), 28(BblStar2), 29(BblStar3), 30(Thunder), 31(DolThdr1), 32(DolThdr2)
33(DolThdr3), 34(ElcPuls1), 35(ElcPuls2), 36(ElcPuls3), 37(RskyHny1), 38(RskyHny2), 39(RskyHny3), 40(RlngLog1), 41(RlngLog2), 42(RlngLog3), 43(MachGun1), 44(MachGun2)
45(MachGun3), 46(HeatDrgn), 47(ElecDrgn), 48(AquaDrgn), 49(WoodDrgn), 50(AirHocky), 51(DrilArm), 52(Tornado), 53(Static), 61(AquaNdl1), 62(AquaNdl2), 63(AquaNdl3)
64(CornSht1), 65(CornSht2), 66(CornSht3), 80(WindRack), 82(VarSwrd), 83(NeoVari), 84(MoonBld), 86(MchnSwrd), 87(ElemSwrd), 88(AssnSwrd), 89(CrakShot), 90(DublShot)
91(TrplShot), 92(WaveArm1), 93(WaveArm2), 94(WaveArm3), 95(AuraHed1), 96(AuraHed2), 97(AuraHed3), 101(SandWrm1), 102(SandWrm2), 103(SandWrm3), 104(AirRaid1), 105(AirRaid2)
106(AirRaid3), 107(FireHit1), 108(FireHit2), 109(FireHit3), 110(BurnSqr1), 111(BurnSqr2), 112(BurnSqr3), 113(Sensor1), 114(Sensor2), 115(Sensor3), 116(Boomer), 117(HiBoomer)
118(M-Boomer), 119(Lance), 120(GolmHit1), 121(GolmHit2), 122(GolmHit3), 123(IronShl1), 124(IronShl2), 125(IronShl3), 126(AirSpin1), 127(AirSpin2), 128(AirSpin3), 129(Wind)
130(Fan), 131(Rflectr1), 132(Rflectr2), 133(Rflectr3), 134(Snake), 135(SumnBlk1), 136(SumnBlk2), 137(SumnBlk3), 138(NumbrBl), 139(Meteors), 140(JustcOne), 141(Magnum)
142(CircGun), 143(RockCube), 144(TimeBom1), 145(Mine), 146(Fanfare), 147(Discord), 148(Timpani), 149(Silence), 151(Guardian), 152(Anubis), 153(Otenko), 162(PanlGrab)
164(GrabBnsh), 165(GrabRvng), 166(PnlRetrn), 167(Geddon), 168(HolyPanl), 169(Snctuary), 170(ComingRd), 171(GoingRd), 172(SloGauge), 173(FstGauge), 174(FullCust), 175(BusterUp)
176(BugFix), 181(BblWrap), 182(LifeAur), 183(MagCoil), 184(WhiCapsl), 185(Uninstll), 186(AntiNavi), 187(AntiDmg), 188(AntiSwrd), 189(AntiRecv), 190(CopyDmg), 191(LifeSync)
192(Atk+10), 193(Navi+20), 194(ColorPt), 195(Atk+30), 196(DblPoint), 197(ElemTrap), 198(ColArmy), 199(BlzrdBal), 200(TimeBom2), 201(TimeBom3), 221(Roll), 222(Roll2)
223(Roll3), 224(ProtoMan), 225(ProtoMn[EX]), 226(ProtoMn[SP]), 227(HeatMan), 228(HeatMan[EX]), 229(HeatMan[SP]), 230(ElecMan), 231(ElecMan[EX]), 232(ElecMan[SP]), 233(SlashMan), 234(SlashMn[EX])
235(SlashMn[SP]), 236(EraseMan), 237(EraseMn[EX]), 238(EraseMn[SP]), 239(ChrgeMan), 240(ChrgeMn[EX]), 241(ChrgeMn[SP]), 242(SpoutMan), 243(SpoutMn[EX]), 244(SpoutMn[SP]), 245(TmhkMan), 246(TmhkMan[EX])
247(TmhkMan[SP]), 248(TenguMan), 249(TenguMn[EX]), 250(TenguMn[SP]), 251(GrndMan), 252(GrndMan[EX]), 253(GrndMan[SP]), 254(DustMan), 255(DustMan[EX]@ )

**In the asset but not pixel-verified (5)**: 58(FlshBom2), 59(FlshBom3), 81(StepSwrd), 99(LilBolr2), 100(LilBolr3)

**In neither (174)** -- the nameless placeholder block 203..220
plus the def-less block 256..410 (139 of the 174 carry codes but no name):

0(MegaBstr), 203(), 204(), 205(), 206(), 207(), 208(), 209(), 210(), 211(), 212(), 213()
214(), 215(), 216(), 217(), 218(), 219(), 220(), 256((unnamed)), 257((unnamed)), 258((unnamed)), 259((unnamed)), 260((unnamed))
261((unnamed)), 262((unnamed)), 263((unnamed)), 264((unnamed)), 265((unnamed)), 266((unnamed)), 267((unnamed)), 268((unnamed)), 269((unnamed)), 270((unnamed)), 271((unnamed)), 272((unnamed))
273((unnamed)), 274((unnamed)), 275((unnamed)), 276((unnamed)), 277((unnamed)), 278((unnamed)), 279((unnamed)), 280((unnamed)), 281((unnamed)), 282((unnamed)), 283((unnamed)), 284((unnamed))
285((unnamed)), 286((unnamed)), 287((unnamed)), 288((unnamed)), 289((unnamed)), 290((unnamed)), 291((unnamed)), 292((unnamed)), 293((unnamed)), 294((unnamed)), 295((unnamed)), 296((unnamed))
297((unnamed)), 298((unnamed)), 299((unnamed)), 300((unnamed)), 301((unnamed)), 302((unnamed)), 303((unnamed)), 304((unnamed)), 305((unnamed)), 306((unnamed)), 307((unnamed)), 308((unnamed))
309((unnamed)), 310((unnamed)), 311((unnamed)), 312((unnamed)), 313((unnamed)), 314((unnamed)), 315((unnamed)), 316((unnamed)), 317((unnamed)), 318((unnamed)), 319((unnamed)), 320((unnamed))
321((unnamed)), 322((unnamed)), 323((unnamed)), 324((unnamed)), 325((unnamed)), 326((unnamed)), 327((unnamed)), 328((unnamed)), 329((unnamed)), 330((unnamed)), 331((unnamed)), 332((unnamed))
333((unnamed)), 334((unnamed)), 335((unnamed)), 336((unnamed)), 337((unnamed)), 338((unnamed)), 339((unnamed)), 340((unnamed)), 341((unnamed)), 342((unnamed)), 343((unnamed)), 344((unnamed))
345((unnamed)), 346((unnamed)), 347((unnamed)), 348((unnamed)), 349((unnamed)), 350((unnamed)), 351((unnamed)), 352((unnamed)), 353((unnamed)), 354((unnamed)), 355((unnamed)), 356((unnamed))
357((unnamed)), 358((unnamed)), 359((unnamed)), 360((unnamed)), 361((unnamed)), 362((unnamed)), 363((unnamed)), 364((unnamed)), 365((unnamed)), 366((unnamed)), 367((unnamed)), 368((unnamed))
369((unnamed)), 370((unnamed)), 371((unnamed)), 372((unnamed)), 373((unnamed)), 374((unnamed)), 375((unnamed)), 376((unnamed)), 377((unnamed)), 378((unnamed)), 379((unnamed)), 380((unnamed))
381((unnamed)), 382((unnamed)), 383((unnamed)), 384((unnamed)), 385((unnamed)), 386((unnamed)), 387((unnamed)), 388((unnamed)), 389((unnamed)), 390((unnamed)), 391((unnamed)), 392((unnamed))
393((unnamed)), 394((unnamed)), 395((unnamed)), 396((unnamed)), 397((unnamed)), 398((unnamed)), 399((unnamed)), 400((unnamed)), 401((unnamed)), 402((unnamed)), 403((unnamed)), 404((unnamed))
405((unnamed)), 406((unnamed)), 407((unnamed)), 408((unnamed)), 409((unnamed)), 410((unnamed))

**DarkChips, excluded from R by definition (30)**: 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349.

## Per-id cites (all 237 reachable ids)

| id | name | ChipDataArr line | asset index (pre-T116) | name string line |
|---|---|---|---|---|
| 1 | Cannon | data/ChipDataArr.s:34 | 0 | data/textscript/TextScriptChipNames0.s:7 |
| 2 | HiCannon | data/ChipDataArr.s:65 | 1 | data/textscript/TextScriptChipNames0.s:10 |
| 3 | M-Cannon | data/ChipDataArr.s:96 | 2 | data/textscript/TextScriptChipNames0.s:13 |
| 4 | AirShot | data/ChipDataArr.s:127 | 3 | data/textscript/TextScriptChipNames0.s:16 |
| 5 | Vulcan1 | data/ChipDataArr.s:158 | 4 | data/textscript/TextScriptChipNames0.s:19 |
| 6 | Vulcan2 | data/ChipDataArr.s:189 | 14 | data/textscript/TextScriptChipNames0.s:22 |
| 7 | Vulcan3 | data/ChipDataArr.s:220 | 15 | data/textscript/TextScriptChipNames0.s:25 |
| 8 | SuprVulc | data/ChipDataArr.s:251 | 30 | data/textscript/TextScriptChipNames0.s:28 |
| 9 | Spreadr1 | data/ChipDataArr.s:282 | -- | data/textscript/TextScriptChipNames0.s:31 |
| 10 | Spreadr2 | data/ChipDataArr.s:313 | -- | data/textscript/TextScriptChipNames0.s:34 |
| 11 | Spreadr3 | data/ChipDataArr.s:344 | -- | data/textscript/TextScriptChipNames0.s:37 |
| 12 | TankCan1 | data/ChipDataArr.s:375 | -- | data/textscript/TextScriptChipNames0.s:40 |
| 13 | TankCan2 | data/ChipDataArr.s:406 | -- | data/textscript/TextScriptChipNames0.s:43 |
| 14 | TankCan3 | data/ChipDataArr.s:437 | -- | data/textscript/TextScriptChipNames0.s:46 |
| 15 | GunDelS1 | data/ChipDataArr.s:468 | -- | data/textscript/TextScriptChipNames0.s:49 |
| 16 | GunDelS2 | data/ChipDataArr.s:499 | -- | data/textscript/TextScriptChipNames0.s:52 |
| 17 | GunDelS3 | data/ChipDataArr.s:530 | -- | data/textscript/TextScriptChipNames0.s:55 |
| 18 | GunDelEX | data/ChipDataArr.s:561 | -- | data/textscript/TextScriptChipNames0.s:58 |
| 19 | YoYo | data/ChipDataArr.s:592 | -- | data/textscript/TextScriptChipNames0.s:61 |
| 20 | FireBrn1 | data/ChipDataArr.s:623 | -- | data/textscript/TextScriptChipNames0.s:64 |
| 21 | FireBrn2 | data/ChipDataArr.s:654 | -- | data/textscript/TextScriptChipNames0.s:67 |
| 22 | FireBrn3 | data/ChipDataArr.s:685 | -- | data/textscript/TextScriptChipNames0.s:70 |
| 23 | WideSht | data/ChipDataArr.s:716 | -- | data/textscript/TextScriptChipNames0.s:73 |
| 24 | TrnArrw1 | data/ChipDataArr.s:747 | -- | data/textscript/TextScriptChipNames0.s:76 |
| 25 | TrnArrw2 | data/ChipDataArr.s:778 | -- | data/textscript/TextScriptChipNames0.s:79 |
| 26 | TrnArrw3 | data/ChipDataArr.s:809 | -- | data/textscript/TextScriptChipNames0.s:82 |
| 27 | BblStar1 | data/ChipDataArr.s:840 | -- | data/textscript/TextScriptChipNames0.s:85 |
| 28 | BblStar2 | data/ChipDataArr.s:871 | -- | data/textscript/TextScriptChipNames0.s:88 |
| 29 | BblStar3 | data/ChipDataArr.s:902 | -- | data/textscript/TextScriptChipNames0.s:91 |
| 30 | Thunder | data/ChipDataArr.s:933 | -- | data/textscript/TextScriptChipNames0.s:94 |
| 31 | DolThdr1 | data/ChipDataArr.s:964 | -- | data/textscript/TextScriptChipNames0.s:97 |
| 32 | DolThdr2 | data/ChipDataArr.s:995 | -- | data/textscript/TextScriptChipNames0.s:100 |
| 33 | DolThdr3 | data/ChipDataArr.s:1026 | -- | data/textscript/TextScriptChipNames0.s:103 |
| 34 | ElcPuls1 | data/ChipDataArr.s:1057 | -- | data/textscript/TextScriptChipNames0.s:106 |
| 35 | ElcPuls2 | data/ChipDataArr.s:1088 | -- | data/textscript/TextScriptChipNames0.s:109 |
| 36 | ElcPuls3 | data/ChipDataArr.s:1119 | -- | data/textscript/TextScriptChipNames0.s:112 |
| 37 | RskyHny1 | data/ChipDataArr.s:1150 | -- | data/textscript/TextScriptChipNames0.s:115 |
| 38 | RskyHny2 | data/ChipDataArr.s:1181 | -- | data/textscript/TextScriptChipNames0.s:118 |
| 39 | RskyHny3 | data/ChipDataArr.s:1212 | -- | data/textscript/TextScriptChipNames0.s:121 |
| 40 | RlngLog1 | data/ChipDataArr.s:1243 | -- | data/textscript/TextScriptChipNames0.s:124 |
| 41 | RlngLog2 | data/ChipDataArr.s:1274 | -- | data/textscript/TextScriptChipNames0.s:127 |
| 42 | RlngLog3 | data/ChipDataArr.s:1305 | -- | data/textscript/TextScriptChipNames0.s:130 |
| 43 | MachGun1 | data/ChipDataArr.s:1336 | -- | data/textscript/TextScriptChipNames0.s:133 |
| 44 | MachGun2 | data/ChipDataArr.s:1367 | -- | data/textscript/TextScriptChipNames0.s:136 |
| 45 | MachGun3 | data/ChipDataArr.s:1398 | -- | data/textscript/TextScriptChipNames0.s:139 |
| 46 | HeatDrgn | data/ChipDataArr.s:1429 | -- | data/textscript/TextScriptChipNames0.s:142 |
| 47 | ElecDrgn | data/ChipDataArr.s:1460 | -- | data/textscript/TextScriptChipNames0.s:145 |
| 48 | AquaDrgn | data/ChipDataArr.s:1491 | -- | data/textscript/TextScriptChipNames0.s:148 |
| 49 | WoodDrgn | data/ChipDataArr.s:1522 | -- | data/textscript/TextScriptChipNames0.s:151 |
| 50 | AirHocky | data/ChipDataArr.s:1553 | -- | data/textscript/TextScriptChipNames0.s:154 |
| 51 | DrilArm | data/ChipDataArr.s:1584 | -- | data/textscript/TextScriptChipNames0.s:157 |
| 52 | Tornado | data/ChipDataArr.s:1615 | -- | data/textscript/TextScriptChipNames0.s:160 |
| 53 | Static | data/ChipDataArr.s:1646 | -- | data/textscript/TextScriptChipNames0.s:163 |
| 54 | MiniBomb | data/ChipDataArr.s:1677 | 8 | data/textscript/TextScriptChipNames0.s:166 |
| 55 | EnergBom | data/ChipDataArr.s:1708 | 35 | data/textscript/TextScriptChipNames0.s:169 |
| 56 | MegEnBom | data/ChipDataArr.s:1739 | 36 | data/textscript/TextScriptChipNames0.s:172 |
| 57 | FlshBom1 | data/ChipDataArr.s:1770 | 40 | data/textscript/TextScriptChipNames0.s:175 |
| 58 | FlshBom2 | data/ChipDataArr.s:1801 | 41 | data/textscript/TextScriptChipNames0.s:178 |
| 59 | FlshBom3 | data/ChipDataArr.s:1832 | 42 | data/textscript/TextScriptChipNames0.s:181 |
| 60 | BlkBomb | data/ChipDataArr.s:1863 | 23 | data/textscript/TextScriptChipNames0.s:184 |
| 61 | AquaNdl1 | data/ChipDataArr.s:1894 | -- | data/textscript/TextScriptChipNames0.s:187 |
| 62 | AquaNdl2 | data/ChipDataArr.s:1925 | -- | data/textscript/TextScriptChipNames0.s:190 |
| 63 | AquaNdl3 | data/ChipDataArr.s:1956 | -- | data/textscript/TextScriptChipNames0.s:193 |
| 64 | CornSht1 | data/ChipDataArr.s:1987 | -- | data/textscript/TextScriptChipNames0.s:196 |
| 65 | CornSht2 | data/ChipDataArr.s:2018 | -- | data/textscript/TextScriptChipNames0.s:199 |
| 66 | CornSht3 | data/ChipDataArr.s:2049 | -- | data/textscript/TextScriptChipNames0.s:202 |
| 67 | BugBomb | data/ChipDataArr.s:2080 | 46 | data/textscript/TextScriptChipNames0.s:205 |
| 68 | GrasSeed | data/ChipDataArr.s:2111 | 45 | data/textscript/TextScriptChipNames0.s:208 |
| 69 | IceSeed | data/ChipDataArr.s:2142 | 44 | data/textscript/TextScriptChipNames0.s:211 |
| 70 | PoisSeed | data/ChipDataArr.s:2173 | 43 | data/textscript/TextScriptChipNames0.s:214 |
| 71 | Sword | data/ChipDataArr.s:2204 | 5 | data/textscript/TextScriptChipNames0.s:217 |
| 72 | WideSwrd | data/ChipDataArr.s:2235 | 6 | data/textscript/TextScriptChipNames0.s:220 |
| 73 | LongSwrd | data/ChipDataArr.s:2266 | 7 | data/textscript/TextScriptChipNames0.s:223 |
| 74 | WideBlde | data/ChipDataArr.s:2297 | 25 | data/textscript/TextScriptChipNames0.s:226 |
| 75 | LongBlde | data/ChipDataArr.s:2328 | 26 | data/textscript/TextScriptChipNames0.s:229 |
| 76 | FireSwrd | data/ChipDataArr.s:2359 | 19 | data/textscript/TextScriptChipNames0.s:232 |
| 77 | AquaSwrd | data/ChipDataArr.s:2390 | 20 | data/textscript/TextScriptChipNames0.s:235 |
| 78 | ElecSwrd | data/ChipDataArr.s:2421 | 21 | data/textscript/TextScriptChipNames0.s:238 |
| 79 | BambSwrd | data/ChipDataArr.s:2452 | 22 | data/textscript/TextScriptChipNames0.s:241 |
| 80 | WindRack | data/ChipDataArr.s:2483 | -- | data/textscript/TextScriptChipNames0.s:244 |
| 81 | StepSwrd | data/ChipDataArr.s:2514 | 32 | data/textscript/TextScriptChipNames0.s:247 |
| 82 | VarSwrd | data/ChipDataArr.s:2545 | -- | data/textscript/TextScriptChipNames0.s:250 |
| 83 | NeoVari | data/ChipDataArr.s:2576 | -- | data/textscript/TextScriptChipNames0.s:253 |
| 84 | MoonBld | data/ChipDataArr.s:2607 | -- | data/textscript/TextScriptChipNames0.s:256 |
| 85 | Muramasa | data/ChipDataArr.s:2638 | 31 | data/textscript/TextScriptChipNames0.s:259 |
| 86 | MchnSwrd | data/ChipDataArr.s:2669 | -- | data/textscript/TextScriptChipNames0.s:262 |
| 87 | ElemSwrd | data/ChipDataArr.s:2700 | -- | data/textscript/TextScriptChipNames0.s:265 |
| 88 | AssnSwrd | data/ChipDataArr.s:2731 | -- | data/textscript/TextScriptChipNames0.s:268 |
| 89 | CrakShot | data/ChipDataArr.s:2762 | -- | data/textscript/TextScriptChipNames0.s:271 |
| 90 | DublShot | data/ChipDataArr.s:2793 | -- | data/textscript/TextScriptChipNames0.s:274 |
| 91 | TrplShot | data/ChipDataArr.s:2824 | -- | data/textscript/TextScriptChipNames0.s:277 |
| 92 | WaveArm1 | data/ChipDataArr.s:2855 | -- | data/textscript/TextScriptChipNames0.s:280 |
| 93 | WaveArm2 | data/ChipDataArr.s:2886 | -- | data/textscript/TextScriptChipNames0.s:283 |
| 94 | WaveArm3 | data/ChipDataArr.s:2917 | -- | data/textscript/TextScriptChipNames0.s:286 |
| 95 | AuraHed1 | data/ChipDataArr.s:2948 | -- | data/textscript/TextScriptChipNames0.s:289 |
| 96 | AuraHed2 | data/ChipDataArr.s:2979 | -- | data/textscript/TextScriptChipNames0.s:292 |
| 97 | AuraHed3 | data/ChipDataArr.s:3010 | -- | data/textscript/TextScriptChipNames0.s:295 |
| 98 | LilBolr1 | data/ChipDataArr.s:3041 | 37 | data/textscript/TextScriptChipNames0.s:298 |
| 99 | LilBolr2 | data/ChipDataArr.s:3072 | 38 | data/textscript/TextScriptChipNames0.s:301 |
| 100 | LilBolr3 | data/ChipDataArr.s:3103 | 39 | data/textscript/TextScriptChipNames0.s:304 |
| 101 | SandWrm1 | data/ChipDataArr.s:3134 | -- | data/textscript/TextScriptChipNames0.s:307 |
| 102 | SandWrm2 | data/ChipDataArr.s:3165 | -- | data/textscript/TextScriptChipNames0.s:310 |
| 103 | SandWrm3 | data/ChipDataArr.s:3196 | -- | data/textscript/TextScriptChipNames0.s:313 |
| 104 | AirRaid1 | data/ChipDataArr.s:3227 | -- | data/textscript/TextScriptChipNames0.s:316 |
| 105 | AirRaid2 | data/ChipDataArr.s:3258 | -- | data/textscript/TextScriptChipNames0.s:319 |
| 106 | AirRaid3 | data/ChipDataArr.s:3289 | -- | data/textscript/TextScriptChipNames0.s:322 |
| 107 | FireHit1 | data/ChipDataArr.s:3320 | -- | data/textscript/TextScriptChipNames0.s:325 |
| 108 | FireHit2 | data/ChipDataArr.s:3351 | -- | data/textscript/TextScriptChipNames0.s:328 |
| 109 | FireHit3 | data/ChipDataArr.s:3382 | -- | data/textscript/TextScriptChipNames0.s:331 |
| 110 | BurnSqr1 | data/ChipDataArr.s:3413 | -- | data/textscript/TextScriptChipNames0.s:334 |
| 111 | BurnSqr2 | data/ChipDataArr.s:3444 | -- | data/textscript/TextScriptChipNames0.s:337 |
| 112 | BurnSqr3 | data/ChipDataArr.s:3475 | -- | data/textscript/TextScriptChipNames0.s:340 |
| 113 | Sensor1 | data/ChipDataArr.s:3506 | -- | data/textscript/TextScriptChipNames0.s:343 |
| 114 | Sensor2 | data/ChipDataArr.s:3537 | -- | data/textscript/TextScriptChipNames0.s:346 |
| 115 | Sensor3 | data/ChipDataArr.s:3568 | -- | data/textscript/TextScriptChipNames0.s:349 |
| 116 | Boomer | data/ChipDataArr.s:3599 | -- | data/textscript/TextScriptChipNames0.s:352 |
| 117 | HiBoomer | data/ChipDataArr.s:3630 | -- | data/textscript/TextScriptChipNames0.s:355 |
| 118 | M-Boomer | data/ChipDataArr.s:3661 | -- | data/textscript/TextScriptChipNames0.s:358 |
| 119 | Lance | data/ChipDataArr.s:3692 | -- | data/textscript/TextScriptChipNames0.s:361 |
| 120 | GolmHit1 | data/ChipDataArr.s:3723 | -- | data/textscript/TextScriptChipNames0.s:364 |
| 121 | GolmHit2 | data/ChipDataArr.s:3754 | -- | data/textscript/TextScriptChipNames0.s:367 |
| 122 | GolmHit3 | data/ChipDataArr.s:3785 | -- | data/textscript/TextScriptChipNames0.s:370 |
| 123 | IronShl1 | data/ChipDataArr.s:3816 | -- | data/textscript/TextScriptChipNames0.s:373 |
| 124 | IronShl2 | data/ChipDataArr.s:3847 | -- | data/textscript/TextScriptChipNames0.s:376 |
| 125 | IronShl3 | data/ChipDataArr.s:3878 | -- | data/textscript/TextScriptChipNames0.s:379 |
| 126 | AirSpin1 | data/ChipDataArr.s:3909 | -- | data/textscript/TextScriptChipNames0.s:382 |
| 127 | AirSpin2 | data/ChipDataArr.s:3940 | -- | data/textscript/TextScriptChipNames0.s:385 |
| 128 | AirSpin3 | data/ChipDataArr.s:3971 | -- | data/textscript/TextScriptChipNames0.s:388 |
| 129 | Wind | data/ChipDataArr.s:4002 | -- | data/textscript/TextScriptChipNames0.s:391 |
| 130 | Fan | data/ChipDataArr.s:4033 | -- | data/textscript/TextScriptChipNames0.s:394 |
| 131 | Rflectr1 | data/ChipDataArr.s:4064 | -- | data/textscript/TextScriptChipNames0.s:397 |
| 132 | Rflectr2 | data/ChipDataArr.s:4095 | -- | data/textscript/TextScriptChipNames0.s:400 |
| 133 | Rflectr3 | data/ChipDataArr.s:4126 | -- | data/textscript/TextScriptChipNames0.s:403 |
| 134 | Snake | data/ChipDataArr.s:4157 | -- | data/textscript/TextScriptChipNames0.s:406 |
| 135 | SumnBlk1 | data/ChipDataArr.s:4188 | -- | data/textscript/TextScriptChipNames0.s:409 |
| 136 | SumnBlk2 | data/ChipDataArr.s:4219 | -- | data/textscript/TextScriptChipNames0.s:412 |
| 137 | SumnBlk3 | data/ChipDataArr.s:4250 | -- | data/textscript/TextScriptChipNames0.s:415 |
| 138 | NumbrBl | data/ChipDataArr.s:4281 | -- | data/textscript/TextScriptChipNames0.s:418 |
| 139 | Meteors | data/ChipDataArr.s:4312 | -- | data/textscript/TextScriptChipNames0.s:421 |
| 140 | JustcOne | data/ChipDataArr.s:4343 | -- | data/textscript/TextScriptChipNames0.s:424 |
| 141 | Magnum | data/ChipDataArr.s:4374 | -- | data/textscript/TextScriptChipNames0.s:427 |
| 142 | CircGun | data/ChipDataArr.s:4405 | -- | data/textscript/TextScriptChipNames0.s:430 |
| 143 | RockCube | data/ChipDataArr.s:4436 | -- | data/textscript/TextScriptChipNames0.s:433 |
| 144 | TimeBom1 | data/ChipDataArr.s:4467 | -- | data/textscript/TextScriptChipNames0.s:436 |
| 145 | Mine | data/ChipDataArr.s:4498 | -- | data/textscript/TextScriptChipNames0.s:439 |
| 146 | Fanfare | data/ChipDataArr.s:4529 | -- | data/textscript/TextScriptChipNames0.s:442 |
| 147 | Discord | data/ChipDataArr.s:4560 | -- | data/textscript/TextScriptChipNames0.s:445 |
| 148 | Timpani | data/ChipDataArr.s:4591 | -- | data/textscript/TextScriptChipNames0.s:448 |
| 149 | Silence | data/ChipDataArr.s:4622 | -- | data/textscript/TextScriptChipNames0.s:451 |
| 150 | VDoll | data/ChipDataArr.s:4653 | 47 | data/textscript/TextScriptChipNames0.s:454 |
| 151 | Guardian | data/ChipDataArr.s:4684 | -- | data/textscript/TextScriptChipNames0.s:457 |
| 152 | Anubis | data/ChipDataArr.s:4715 | -- | data/textscript/TextScriptChipNames0.s:460 |
| 153 | Otenko | data/ChipDataArr.s:4746 | -- | data/textscript/TextScriptChipNames0.s:463 |
| 154 | Recov10 | data/ChipDataArr.s:4777 | 9 | data/textscript/TextScriptChipNames0.s:466 |
| 155 | Recov30 | data/ChipDataArr.s:4808 | 10 | data/textscript/TextScriptChipNames0.s:469 |
| 156 | Recov50 | data/ChipDataArr.s:4839 | 16 | data/textscript/TextScriptChipNames0.s:472 |
| 157 | Recov80 | data/ChipDataArr.s:4870 | 17 | data/textscript/TextScriptChipNames0.s:475 |
| 158 | Recov120 | data/ChipDataArr.s:4901 | 18 | data/textscript/TextScriptChipNames0.s:478 |
| 159 | Recov150 | data/ChipDataArr.s:4932 | 27 | data/textscript/TextScriptChipNames0.s:481 |
| 160 | Recov200 | data/ChipDataArr.s:4963 | 28 | data/textscript/TextScriptChipNames0.s:484 |
| 161 | Recov300 | data/ChipDataArr.s:4994 | 29 | data/textscript/TextScriptChipNames0.s:487 |
| 162 | PanlGrab | data/ChipDataArr.s:5025 | -- | data/textscript/TextScriptChipNames0.s:490 |
| 163 | AreaGrab | data/ChipDataArr.s:5056 | 12 | data/textscript/TextScriptChipNames0.s:493 |
| 164 | GrabBnsh | data/ChipDataArr.s:5087 | -- | data/textscript/TextScriptChipNames0.s:496 |
| 165 | GrabRvng | data/ChipDataArr.s:5118 | -- | data/textscript/TextScriptChipNames0.s:499 |
| 166 | PnlRetrn | data/ChipDataArr.s:5149 | -- | data/textscript/TextScriptChipNames0.s:502 |
| 167 | Geddon | data/ChipDataArr.s:5180 | -- | data/textscript/TextScriptChipNames0.s:505 |
| 168 | HolyPanl | data/ChipDataArr.s:5211 | -- | data/textscript/TextScriptChipNames0.s:508 |
| 169 | Snctuary | data/ChipDataArr.s:5242 | -- | data/textscript/TextScriptChipNames0.s:511 |
| 170 | ComingRd | data/ChipDataArr.s:5273 | -- | data/textscript/TextScriptChipNames0.s:514 |
| 171 | GoingRd | data/ChipDataArr.s:5304 | -- | data/textscript/TextScriptChipNames0.s:517 |
| 172 | SloGauge | data/ChipDataArr.s:5335 | -- | data/textscript/TextScriptChipNames0.s:520 |
| 173 | FstGauge | data/ChipDataArr.s:5366 | -- | data/textscript/TextScriptChipNames0.s:523 |
| 174 | FullCust | data/ChipDataArr.s:5397 | -- | data/textscript/TextScriptChipNames0.s:526 |
| 175 | BusterUp | data/ChipDataArr.s:5428 | -- | data/textscript/TextScriptChipNames0.s:529 |
| 176 | BugFix | data/ChipDataArr.s:5459 | -- | data/textscript/TextScriptChipNames0.s:532 |
| 177 | Invisibl | data/ChipDataArr.s:5490 | 13 | data/textscript/TextScriptChipNames0.s:535 |
| 178 | Barrier | data/ChipDataArr.s:5521 | 11 | data/textscript/TextScriptChipNames0.s:538 |
| 179 | Barr100 | data/ChipDataArr.s:5552 | 33 | data/textscript/TextScriptChipNames0.s:541 |
| 180 | Barr200 | data/ChipDataArr.s:5583 | 34 | data/textscript/TextScriptChipNames0.s:544 |
| 181 | BblWrap | data/ChipDataArr.s:5614 | -- | data/textscript/TextScriptChipNames0.s:547 |
| 182 | LifeAur | data/ChipDataArr.s:5645 | -- | data/textscript/TextScriptChipNames0.s:550 |
| 183 | MagCoil | data/ChipDataArr.s:5676 | -- | data/textscript/TextScriptChipNames0.s:553 |
| 184 | WhiCapsl | data/ChipDataArr.s:5707 | -- | data/textscript/TextScriptChipNames0.s:556 |
| 185 | Uninstll | data/ChipDataArr.s:5738 | -- | data/textscript/TextScriptChipNames0.s:559 |
| 186 | AntiNavi | data/ChipDataArr.s:5769 | -- | data/textscript/TextScriptChipNames0.s:562 |
| 187 | AntiDmg | data/ChipDataArr.s:5800 | -- | data/textscript/TextScriptChipNames0.s:565 |
| 188 | AntiSwrd | data/ChipDataArr.s:5831 | -- | data/textscript/TextScriptChipNames0.s:568 |
| 189 | AntiRecv | data/ChipDataArr.s:5862 | -- | data/textscript/TextScriptChipNames0.s:571 |
| 190 | CopyDmg | data/ChipDataArr.s:5893 | -- | data/textscript/TextScriptChipNames0.s:574 |
| 191 | LifeSync | data/ChipDataArr.s:5924 | -- | data/textscript/TextScriptChipNames0.s:577 |
| 192 | Atk+10 | data/ChipDataArr.s:5955 | -- | data/textscript/TextScriptChipNames0.s:580 |
| 193 | Navi+20 | data/ChipDataArr.s:5986 | -- | data/textscript/TextScriptChipNames0.s:583 |
| 194 | ColorPt | data/ChipDataArr.s:6017 | -- | data/textscript/TextScriptChipNames0.s:586 |
| 195 | Atk+30 | data/ChipDataArr.s:6048 | -- | data/textscript/TextScriptChipNames0.s:589 |
| 196 | DblPoint | data/ChipDataArr.s:6079 | -- | data/textscript/TextScriptChipNames0.s:592 |
| 197 | ElemTrap | data/ChipDataArr.s:6110 | -- | data/textscript/TextScriptChipNames0.s:595 |
| 198 | ColArmy | data/ChipDataArr.s:6141 | -- | data/textscript/TextScriptChipNames0.s:598 |
| 199 | BlzrdBal | data/ChipDataArr.s:6172 | -- | data/textscript/TextScriptChipNames0.s:601 |
| 200 | TimeBom2 | data/ChipDataArr.s:6203 | -- | data/textscript/TextScriptChipNames0.s:604 |
| 201 | TimeBom3 | data/ChipDataArr.s:6234 | -- | data/textscript/TextScriptChipNames0.s:607 |
| 202 | BigBomb | data/ChipDataArr.s:6265 | 24 | data/textscript/TextScriptChipNames0.s:610 |
| 221 | Roll | data/ChipDataArr.s:6854 | -- | data/textscript/TextScriptChipNames0.s:667 |
| 222 | Roll2 | data/ChipDataArr.s:6885 | -- | data/textscript/TextScriptChipNames0.s:670 |
| 223 | Roll3 | data/ChipDataArr.s:6916 | -- | data/textscript/TextScriptChipNames0.s:673 |
| 224 | ProtoMan | data/ChipDataArr.s:6947 | -- | data/textscript/TextScriptChipNames0.s:676 |
| 225 | ProtoMn[EX] | data/ChipDataArr.s:6978 | -- | data/textscript/TextScriptChipNames0.s:679 |
| 226 | ProtoMn[SP] | data/ChipDataArr.s:7009 | -- | data/textscript/TextScriptChipNames0.s:682 |
| 227 | HeatMan | data/ChipDataArr.s:7040 | -- | data/textscript/TextScriptChipNames0.s:685 |
| 228 | HeatMan[EX] | data/ChipDataArr.s:7071 | -- | data/textscript/TextScriptChipNames0.s:688 |
| 229 | HeatMan[SP] | data/ChipDataArr.s:7102 | -- | data/textscript/TextScriptChipNames0.s:691 |
| 230 | ElecMan | data/ChipDataArr.s:7133 | -- | data/textscript/TextScriptChipNames0.s:694 |
| 231 | ElecMan[EX] | data/ChipDataArr.s:7164 | -- | data/textscript/TextScriptChipNames0.s:697 |
| 232 | ElecMan[SP] | data/ChipDataArr.s:7195 | -- | data/textscript/TextScriptChipNames0.s:700 |
| 233 | SlashMan | data/ChipDataArr.s:7226 | -- | data/textscript/TextScriptChipNames0.s:703 |
| 234 | SlashMn[EX] | data/ChipDataArr.s:7257 | -- | data/textscript/TextScriptChipNames0.s:706 |
| 235 | SlashMn[SP] | data/ChipDataArr.s:7288 | -- | data/textscript/TextScriptChipNames0.s:709 |
| 236 | EraseMan | data/ChipDataArr.s:7319 | -- | data/textscript/TextScriptChipNames0.s:712 |
| 237 | EraseMn[EX] | data/ChipDataArr.s:7350 | -- | data/textscript/TextScriptChipNames0.s:715 |
| 238 | EraseMn[SP] | data/ChipDataArr.s:7381 | -- | data/textscript/TextScriptChipNames0.s:718 |
| 239 | ChrgeMan | data/ChipDataArr.s:7412 | -- | data/textscript/TextScriptChipNames0.s:721 |
| 240 | ChrgeMn[EX] | data/ChipDataArr.s:7443 | -- | data/textscript/TextScriptChipNames0.s:724 |
| 241 | ChrgeMn[SP] | data/ChipDataArr.s:7474 | -- | data/textscript/TextScriptChipNames0.s:727 |
| 242 | SpoutMan | data/ChipDataArr.s:7505 | -- | data/textscript/TextScriptChipNames0.s:730 |
| 243 | SpoutMn[EX] | data/ChipDataArr.s:7536 | -- | data/textscript/TextScriptChipNames0.s:733 |
| 244 | SpoutMn[SP] | data/ChipDataArr.s:7567 | -- | data/textscript/TextScriptChipNames0.s:736 |
| 245 | TmhkMan | data/ChipDataArr.s:7598 | -- | data/textscript/TextScriptChipNames0.s:739 |
| 246 | TmhkMan[EX] | data/ChipDataArr.s:7629 | -- | data/textscript/TextScriptChipNames0.s:742 |
| 247 | TmhkMan[SP] | data/ChipDataArr.s:7660 | -- | data/textscript/TextScriptChipNames0.s:745 |
| 248 | TenguMan | data/ChipDataArr.s:7691 | -- | data/textscript/TextScriptChipNames0.s:748 |
| 249 | TenguMn[EX] | data/ChipDataArr.s:7722 | -- | data/textscript/TextScriptChipNames0.s:751 |
| 250 | TenguMn[SP] | data/ChipDataArr.s:7753 | -- | data/textscript/TextScriptChipNames0.s:754 |
| 251 | GrndMan | data/ChipDataArr.s:7784 | -- | data/textscript/TextScriptChipNames0.s:757 |
| 252 | GrndMan[EX] | data/ChipDataArr.s:7815 | -- | data/textscript/TextScriptChipNames0.s:760 |
| 253 | GrndMan[SP] | data/ChipDataArr.s:7846 | -- | data/textscript/TextScriptChipNames0.s:763 |
| 254 | DustMan | data/ChipDataArr.s:7877 | -- | data/textscript/TextScriptChipNames0.s:766 |
| 255 | DustMan[EX]@  | data/ChipDataArr.s:7908 | -- | data/textscript/TextScriptChipNames0.s:769 |
