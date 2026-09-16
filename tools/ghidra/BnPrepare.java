// Prepare a raw MMBN6F cartridge image for decompilation: build the GBA memory
// map, tell Ghidra which stretches are Thumb and which are ARM, import every
// symbol from the reference/bn6f disassembly, and disassemble from each function
// entry -- all before auto-analysis runs.
//
// Run as a -preScript.  Arguments:
//     BnPrepare.java <memmap.tsv> <symbols.tsv>
// both produced by tools/ghidra/bnsyms.py.
//
// Why this script has to exist: a .gba file is headerless machine code.  Ghidra
// cannot know that 0x02000000 is RAM, that the image is almost entirely Thumb
// (the one thing it will get wrong by default, since ARM is the fallback), or
// where the 13,646 functions begin.  The disassembly submodule knows all three,
// and its build is byte-identical to the cartridge, so it is authoritative.
//
//@category BN
//@runtime Java

import java.io.BufferedReader;
import java.io.FileReader;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import ghidra.app.cmd.disassemble.ArmDisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.listing.DefaultProgramContext;
import ghidra.program.model.listing.FlowOverride;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

public class BnPrepare extends GhidraScript {

	/** A row of symbols.tsv. */
	private static class Sym {
		String kind, name, mode;
		long addr, size;

		Sym(String kind, String name, long addr, String mode, long size) {
			this.kind = kind;
			this.name = name;
			this.addr = addr;
			this.mode = mode;
			this.size = size;
		}
	}

	private int labelsMade, labelsFailed, funcsMade, funcsRenamed, funcsFailed;

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 2) {
			println("BnPrepare: usage: BnPrepare.java <memmap.tsv> <symbols.tsv>");
			throw new IllegalArgumentException("BnPrepare needs two arguments");
		}
		String memmapPath = args[0];
		String symbolsPath = args[1];

		long t0 = System.currentTimeMillis();
		setAnalysisOptions();
		applyMemoryMap(memmapPath);

		List<Sym> syms = readSymbols(symbolsPath);
		println("BnPrepare: read " + syms.size() + " symbol rows from " + symbolsPath);

		AddressSet[] code = applyThumbRanges(syms);
		createLabels(syms);
		disassembleCode(syms, code[0], code[1]);
		createFunctions(syms);
		reportCoverage(code[0], code[1]);

		println("BnPrepare: labels " + labelsMade + " created, " + labelsFailed + " failed");
		println("BnPrepare: functions " + funcsMade + " created, " + funcsRenamed
				+ " renamed in place, " + funcsFailed + " failed");
		println("BnPrepare: function manager now holds "
				+ currentProgram.getFunctionManager().getFunctionCount() + " functions");
		println("BnPrepare: done in " + ((System.currentTimeMillis() - t0) / 1000) + "s");
	}

	// ------------------------------------------------------------------
	// Analysis options
	// ------------------------------------------------------------------

	/**
	 * Analysis on a headerless 8 MiB cartridge image needs steering. Everything
	 * switched off here either guesses at something we already know exactly, or
	 * rummages through the 6.4 MiB of sprite/map data for patterns that are not
	 * there. The pattern-based function finders are the important ones: their
	 * guesses on a Thumb image land as ARM functions in the middle of data.
	 */
	private void setAnalysisOptions() {
		String[][] off = {
			// We have every function from the ELF; these only invent wrong ones.
			{ "Function Start Pre Search", "false" },
			{ "Function Start Search", "false" },
			{ "Function Start Search After Code", "false" },
			{ "Function Start Search After Data", "false" },
			{ "Aggressive Instruction Finder", "false" },
			{ "ARM Aggressive Instruction Finder", "false" },
			// Real pointer tables are already imported as labels; letting this
			// loose in the sprite data invents thousands of bogus ones.
			{ "Create Address Tables", "false" },
			// The game's text uses a custom charmap (charmap.inc), not ASCII, so
			// a string scan over the whole ROM is noise.
			{ "ASCII Strings", "false" },
			// No PNG/GIF/WAV in a GBA ROM, no mangled C++ names, no C headers.
			{ "Embedded Media", "false" },
			{ "Demangler GNU", "false" },
			{ "Apply Data Archives", "false" },
			// A signature database for desktop toolchains; this ROM predates it
			// and we already have the real names.
			{ "Function ID", "false" },
		};
		String[][] on = {
			// Jump-table recovery.  BN6 dispatches almost everything through
			// tables of `.word handler+1`, so these two decide whether the C
			// shows a switch or a bare `(*code)()`.
			{ "Decompiler Switch Analysis", "true" },
			{ "ARM Constant Reference Analyzer", "true" },
			{ "ARM Constant Reference Analyzer.Switch Table Recovery", "true" },
			{ "Non-Returning Functions - Discovered", "true" },
			{ "Stack", "true" },
		};
		// Off by default because it costs a second whole-program decompile pass;
		// BN_DECOMP_PARAM_ID=1 turns it on for noticeably better parameter and
		// return-type recovery.
		boolean paramId = "1".equals(System.getenv("BN_DECOMP_PARAM_ID"));

		for (String[] kv : off) {
			setAnalysisOption(currentProgram, kv[0], kv[1]);
		}
		for (String[] kv : on) {
			setAnalysisOption(currentProgram, kv[0], kv[1]);
		}
		setAnalysisOption(currentProgram, "Decompiler Parameter ID", paramId ? "true" : "false");
		println("BnPrepare: analysis tuned (Decompiler Parameter ID = " + paramId + ")");
	}

	// ------------------------------------------------------------------
	// Memory map
	// ------------------------------------------------------------------

	/**
	 * memmap.tsv rows are `kind name addr size src perms`:
	 *
	 * ROM  split the loader's single cartridge block at this boundary and give
	 *      the piece these permissions -- only the linker's executable range
	 *      gets +x, which keeps the analysers out of the data half.
	 * COPY an initialised block filled from ROM address `src`.  The iwram_text
	 *      overlay lives at 0x081D6000 in the cartridge but runs at 0x03005B00;
	 *      without the copy its 86 functions have no bytes to decompile.
	 * BSS  an uninitialised hardware region (EWRAM, IWRAM, I/O, palette, VRAM,
	 *      OAM), so a reference to 0x0203F7D8 resolves to a named global instead
	 *      of falling off the end of the program.
	 */
	private void applyMemoryMap(String path) throws Exception {
		Memory mem = currentProgram.getMemory();
		List<String[]> rows = new ArrayList<>();
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("#") || line.trim().isEmpty()) {
					continue;
				}
				rows.add(line.split("\t", -1));
			}
		}

		// ROM rows first: split before renaming, working from the highest
		// boundary down so each split lands in the piece we still own.
		List<String[]> romRows = new ArrayList<>();
		for (String[] f : rows) {
			if ("ROM".equals(f[0])) {
				romRows.add(f);
			}
		}
		Collections.sort(romRows, (a, b) -> Long.compare(
				Long.parseLong(b[2], 16), Long.parseLong(a[2], 16)));
		for (String[] f : romRows) {
			long addr = Long.parseLong(f[2], 16);
			MemoryBlock block = mem.getBlock(toAddr(addr));
			if (block == null) {
				println("BnPrepare: WARNING no loaded block at " + f[2] + "; skipping " + f[1]);
				continue;
			}
			if (block.getStart().getOffset() != addr) {
				mem.split(block, toAddr(addr));
				block = mem.getBlock(toAddr(addr));
			}
		}
		for (String[] f : rows) {
			if (!"ROM".equals(f[0])) {
				continue;
			}
			long addr = Long.parseLong(f[2], 16);
			MemoryBlock block = mem.getBlock(toAddr(addr));
			if (block == null) {
				continue;
			}
			block.setName(f[1]);
			applyPerms(block, f[5]);
			println("BnPrepare: ROM  " + f[1] + " " + block.getStart() + ".."
					+ block.getEnd() + " " + f[5]);
		}

		for (String[] f : rows) {
			long addr = Long.parseLong(f[2], 16);
			long size = Long.parseLong(f[3], 16);
			if ("COPY".equals(f[0])) {
				long src = Long.parseLong(f[4], 16);
				byte[] bytes = new byte[(int) size];
				int got = mem.getBytes(toAddr(src), bytes);
				MemoryBlock block = mem.createInitializedBlock(
						f[1], toAddr(addr), size, (byte) 0, monitor, false);
				mem.setBytes(toAddr(addr), bytes);
				applyPerms(block, f[5]);
				block.setComment("overlay: the cartridge stores these " + got
						+ " bytes at " + toAddr(src) + ", the game runs them here");
				println("BnPrepare: COPY " + f[1] + " " + block.getStart() + ".."
						+ block.getEnd() + " " + f[5] + " <- " + toAddr(src));
			}
			else if ("BSS".equals(f[0])) {
				MemoryBlock block = mem.createUninitializedBlock(
						f[1], toAddr(addr), size, false);
				applyPerms(block, f[5]);
				println("BnPrepare: BSS  " + f[1] + " " + block.getStart() + ".."
						+ block.getEnd() + " " + f[5]);
			}
		}
	}

	private void applyPerms(MemoryBlock block, String perms) {
		block.setRead(perms.indexOf('r') >= 0);
		block.setWrite(perms.indexOf('w') >= 0);
		block.setExecute(perms.indexOf('x') >= 0);
	}

	// ------------------------------------------------------------------
	// Symbols
	// ------------------------------------------------------------------

	private List<Sym> readSymbols(String path) throws Exception {
		List<Sym> out = new ArrayList<>();
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("#") || line.trim().isEmpty()) {
					continue;
				}
				String[] f = line.split("\t", -1);
				if (f.length < 5) {
					continue;
				}
				out.add(new Sym(f[0], f[1], Long.parseLong(f[2], 16), f[3],
						Long.parseLong(f[4])));
			}
		}
		return out;
	}

	/**
	 * Seed the TMode context register from the ELF's `$a`/`$t`/`$d` mapping
	 * symbols, and work out exactly which bytes are code.
	 *
	 * ARM ELF emits `$t` where a Thumb stretch begins, `$a` where an ARM one does
	 * and `$d` for data embedded in code -- literal pools, jump tables, the
	 * `byte_`/`dword_` tables this game keeps next to the routine that reads
	 * them.  Each symbol owns the bytes up to the next one, whatever its kind.
	 * That gives two different answers to two different questions:
	 *
	 *   TMode      is set over `$d` too, carrying the surrounding instruction set
	 *              through it, so that if anything ever does decode a literal
	 *              pool it at least decodes it the way its neighbours read.  It
	 *              is set as a *default* value, so the explicit values the
	 *              disassembler writes still win.
	 *   the code set  is `$t` and `$a` only.  It is what gap-filling is allowed
	 *              to disassemble and what coverage is measured against.  This
	 *              distinction is not cosmetic: .text is 1.93 MiB, of which only
	 *              767 KiB is instructions, so conflating the two would both
	 *              invent instructions inside jump tables and report a coverage
	 *              figure that is meaningless.
	 */
	private AddressSet[] applyThumbRanges(List<Sym> syms) throws Exception {
		AddressSet thumbCode = new AddressSet();
		AddressSet armCode = new AddressSet();
		ProgramContext ctx = currentProgram.getProgramContext();
		Register tmode = ctx.getRegister("TMode");
		if (tmode == null) {
			println("BnPrepare: WARNING no TMode register in this language; "
					+ "Thumb code will decode as ARM");
			return new AddressSet[] { thumbCode, armCode };
		}
		RegisterValue thumbValue = new RegisterValue(tmode, BigInteger.ONE);
		RegisterValue armValue = new RegisterValue(tmode, BigInteger.ZERO);
		DefaultProgramContext defCtx =
			(ctx instanceof DefaultProgramContext) ? (DefaultProgramContext) ctx : null;

		// Only mapping symbols inside executable blocks matter; `$d` rows in the
		// data half of the cartridge describe data we never disassemble anyway.
		List<Sym> marks = new ArrayList<>();
		for (Sym s : syms) {
			if (!"M".equals(s.kind)) {
				continue;
			}
			MemoryBlock b = currentProgram.getMemory().getBlock(toAddr(s.addr));
			if (b != null && b.isExecute()) {
				marks.add(s);
			}
		}
		Collections.sort(marks, (a, b) -> Long.compare(a.addr, b.addr));

		int nThumb = 0, nArm = 0, nData = 0;
		MemoryBlock lastBlock = null;
		String lastCodeMode = null;
		for (int i = 0; i < marks.size(); i++) {
			Sym s = marks.get(i);
			MemoryBlock block = currentProgram.getMemory().getBlock(toAddr(s.addr));
			if (block != lastBlock) {
				lastCodeMode = null;                 // do not carry a mode across blocks
				lastBlock = block;
			}
			long end = block.getEnd().getOffset();
			if (i + 1 < marks.size() && marks.get(i + 1).addr - 1 < end) {
				end = marks.get(i + 1).addr - 1;
			}
			if (end < s.addr) {
				continue;
			}
			Address lo = toAddr(s.addr);
			Address hi = toAddr(end);

			String mode = s.mode;
			if ("data".equals(mode)) {
				nData++;
				mode = lastCodeMode;                 // inherit, purely for TMode
				if (mode == null) {
					continue;
				}
			}
			else {
				lastCodeMode = mode;
				if ("thumb".equals(mode)) {
					nThumb++;
					thumbCode.addRange(lo, hi);
				}
				else {
					nArm++;
					armCode.addRange(lo, hi);
				}
			}
			RegisterValue v = "thumb".equals(mode) ? thumbValue : armValue;
			if (defCtx != null) {
				defCtx.setDefaultValue(v, lo, hi);
			}
			else {
				ctx.setRegisterValue(lo, hi, v);
			}
		}
		println("BnPrepare: TMode from " + nThumb + " thumb, " + nArm + " arm and "
				+ nData + " data ranges, as "
				+ (defCtx != null ? "defaults" : "explicit values"));
		println("BnPrepare: the ELF marks " + thumbCode.getNumAddresses()
				+ " bytes thumb and " + armCode.getNumAddresses()
				+ " bytes arm as code, inside "
				+ executableBytes() + " executable bytes");

		// Narrow to bytes that are inside a function.  A `.s` file that emits
		// `.byte` tables without leaving Thumb mode leaves them inside a `$t`
		// range -- the npcscript/cutscenescript blobs, the sprite pointer lists --
		// and seeding those would manufacture instructions out of script
		// bytecode.  No function claims them, so intersecting with the ELF's
		// function extents removes exactly them and nothing else.
		AddressSet bodies = new AddressSet();
		for (Sym s : syms) {
			if ("F".equals(s.kind) && s.size > 0) {
				Address lo = toAddr(s.addr);
				Address hi = toAddr(s.addr + s.size - 1);
				if (currentProgram.getMemory().contains(lo)
						&& currentProgram.getMemory().contains(hi)) {
					bodies.addRange(lo, hi);
				}
			}
		}
		thumbCode = new AddressSet(thumbCode.intersect(bodies));
		armCode = new AddressSet(armCode.intersect(bodies));
		println("BnPrepare: inside declared functions: " + thumbCode.getNumAddresses()
				+ " bytes thumb, " + armCode.getNumAddresses()
				+ " bytes arm -- this is the code set");
		return new AddressSet[] { thumbCode, armCode };
	}

	private long executableBytes() {
		long n = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.isExecute()) {
				n += b.getSize();
			}
		}
		return n;
	}

	private void createLabels(List<Sym> syms) {
		SymbolTable st = currentProgram.getSymbolTable();
		Memory mem = currentProgram.getMemory();
		for (Sym s : syms) {
			if (!"D".equals(s.kind)) {
				continue;
			}
			Address a = toAddr(s.addr);
			if (!mem.contains(a)) {
				labelsFailed++;
				continue;
			}
			try {
				st.createLabel(a, s.name, SourceType.IMPORTED);
				labelsMade++;
			}
			catch (Exception e) {
				labelsFailed++;
			}
		}
	}

	/**
	 * Disassemble everything the ELF says is code, and nothing it says is not.
	 *
	 * Three passes, because each unblocks the next:
	 *
	 * 1. Seed every function entry.  ArmDisassembleCommand writes TMode at each
	 *    seed and follows the flow, so a Thumb function stays Thumb throughout.
	 *    Two commands (one per instruction set) rather than 13.6k.
	 *
	 * 2. Check the indirect-call idiom.  BN6 calls through a pointer as
	 *    `mov lr, pc` / `bx rN`, 1928 times.  Read as a jump rather than a call,
	 *    the `bx` would end the flow and everything after a dispatch -- often the
	 *    rest of the function -- would go undisassembled and unseen by the
	 *    decompiler.  Ghidra's ARM sleigh does recognise the pair as a
	 *    COMPUTED_CALL; this pass verifies that, counts it, and applies
	 *    FlowOverride.CALL to any site where it did not, so a regression shows up
	 *    as a number instead of as silently truncated C.
	 *
	 * 3. Fill the gaps.  Anything still undisassembled inside a `$t`/`$a` range
	 *    is code Ghidra could not reach by flow (reached only through a pointer,
	 *    say).  Seeding it is safe precisely because the ELF's `$d` ranges are
	 *    excluded: a literal pool or jump table is never a seed.
	 *
	 * 2 and 3 feed each other -- a newly disassembled stretch can hold more
	 * dispatches -- so they repeat until nothing new appears.
	 */
	private void disassembleCode(List<Sym> syms, AddressSet thumbCode, AddressSet armCode) {
		AddressSet thumbSeeds = new AddressSet();
		AddressSet armSeeds = new AddressSet();
		Memory mem = currentProgram.getMemory();

		for (Sym s : syms) {
			if (!"F".equals(s.kind)) {
				continue;
			}
			Address a = toAddr(s.addr);
			if (!mem.contains(a)) {
				println("BnPrepare: WARNING " + s.name + " at " + a + " is outside memory");
				continue;
			}
			if ("thumb".equals(s.mode)) {
				thumbSeeds.addRange(a, a);
			}
			else {
				armSeeds.addRange(a, a);
			}
		}
		println("BnPrepare: pass 1: " + thumbSeeds.getNumAddresses() + " thumb and "
				+ armSeeds.getNumAddresses() + " arm function entries");
		disassemble(thumbSeeds, null, true);
		disassemble(armSeeds, null, false);

		int fixed = 0, native_ = 0;
		long lastGaps = -1;
		for (int round = 1; round <= MAX_ROUNDS; round++) {
			int[] calls = checkIndirectCalls(thumbCode, armCode);
			fixed += calls[0];
			native_ = calls[1];

			AddressSet thumbGaps = gapSeeds(thumbCode, 2);
			AddressSet armGaps = gapSeeds(armCode, 4);
			long gaps = thumbGaps.getNumAddresses() + armGaps.getNumAddresses();
			println("BnPrepare: round " + round + ": " + gaps
					+ " unreached code runs to seed, " + calls[0]
					+ " indirect calls needing an override");
			// A handful of gaps never close: they are jump tables the assembler
			// left inside a Thumb mapping range, so they are data.  Stop as soon
			// as a round changes nothing.
			if ((gaps == 0 || gaps == lastGaps) && calls[0] == 0) {
				break;
			}
			lastGaps = gaps;
			disassemble(thumbGaps, thumbCode, true);
			disassemble(armGaps, armCode, false);
		}
		println("BnPrepare: `mov lr, pc` / `bx rN` call sites: " + native_
				+ " recognised by the ARM sleigh, " + fixed + " needed an override");
	}

	private static final int MAX_ROUNDS = 8;

	private void disassemble(AddressSet seeds, AddressSet restricted, boolean thumbMode) {
		if (seeds.isEmpty()) {
			return;
		}
		ArmDisassembleCommand cmd = new ArmDisassembleCommand(seeds, restricted, thumbMode);
		cmd.enableCodeAnalysis(false);
		cmd.applyTo(currentProgram, monitor);
	}

	/**
	 * Every aligned start of an undisassembled run inside `code`.
	 *
	 * Only the first address of each gap is seeded: the disassembler follows on
	 * from there, so one seed usually clears the whole run, and the outer loop
	 * catches whatever it does not.
	 */
	private AddressSet gapSeeds(AddressSet code, int align) {
		if (code.isEmpty()) {
			return new AddressSet();
		}
		Listing listing = currentProgram.getListing();
		AddressSet defined = new AddressSet();
		for (Instruction i : listing.getInstructions(code, true)) {
			defined.addRange(i.getMinAddress(), i.getMaxAddress());
		}
		AddressSet seeds = new AddressSet();
		for (AddressRange range : code.subtract(defined).getAddressRanges()) {
			long start = range.getMinAddress().getOffset();
			if (start % align != 0) {
				start += align - (start % align);
			}
			if (start <= range.getMaxAddress().getOffset()) {
				Address a = toAddr(start);
				seeds.addRange(a, a);
			}
		}
		return seeds;
	}

	/**
	 * Count `mov lr, pc` / `bx rN` call sites, and override the ones Ghidra read
	 * as a plain jump.  Returns {overridden, already correct}.
	 *
	 * The test is on the instructions, not on a byte pattern: the previous
	 * instruction must move pc into lr (whatever the assembler spelled it), and
	 * this one must be an indirect branch. That is the ARM/Thumb way of saying
	 * "call through this register", and nothing else looks like it.
	 */
	private int[] checkIndirectCalls(AddressSet thumbCode, AddressSet armCode) {
		AddressSet code = new AddressSet(thumbCode);
		code.add(armCode);
		Listing listing = currentProgram.getListing();
		Register lr = currentProgram.getRegister("lr");
		Register pc = currentProgram.getRegister("pc");
		if (lr == null || pc == null) {
			return new int[] { 0, 0 };
		}
		int overridden = 0, alreadyCalls = 0;
		Instruction prev = null;
		for (Instruction here : listing.getInstructions(code, true)) {
			boolean adjacent = prev != null && prev.getMaxAddress().next() != null
					&& prev.getMaxAddress().next().equals(here.getMinAddress());
			if (adjacent && here.getFlowType().isComputed()
					&& setsLinkFromPc(prev, lr, pc)) {
				if (here.getFlowType().isCall()
						|| here.getFlowOverride() != FlowOverride.NONE) {
					alreadyCalls++;
				}
				else {
					here.setFlowOverride(FlowOverride.CALL);
					overridden++;
				}
			}
			prev = here;
		}
		return new int[] { overridden, alreadyCalls };
	}

	private boolean setsLinkFromPc(Instruction insn, Register lr, Register pc) {
		if (insn.getNumOperands() != 2) {
			return false;
		}
		return isRegister(insn.getOpObjects(0), lr) && isRegister(insn.getOpObjects(1), pc);
	}

	private boolean isRegister(Object[] operands, Register want) {
		return operands.length == 1 && operands[0] instanceof Register
				&& ((Register) operands[0]).equals(want);
	}

	/** Declare a function at each entry the disassembly names. */
	private void createFunctions(List<Sym> syms) {
		Memory mem = currentProgram.getMemory();
		List<Sym> funcs = new ArrayList<>();
		for (Sym s : syms) {
			if ("F".equals(s.kind) && mem.contains(toAddr(s.addr))) {
				funcs.add(s);
			}
		}
		int i = 0;
		for (Sym s : funcs) {
			if (monitor.isCancelled()) {
				break;
			}
			if (++i % 4000 == 0) {
				println("BnPrepare: functions " + i + "/" + funcs.size());
			}
			Address a = toAddr(s.addr);
			Function existing = getFunctionAt(a);
			if (existing != null) {
				try {
					if (!s.name.equals(existing.getName())) {
						existing.setName(s.name, SourceType.IMPORTED);
						funcsRenamed++;
					}
				}
				catch (Exception e) {
					funcsFailed++;
				}
				continue;
			}
			CreateFunctionCmd cmd =
				new CreateFunctionCmd(s.name, a, null, SourceType.IMPORTED);
			if (cmd.applyTo(currentProgram, monitor)) {
				funcsMade++;
			}
			else {
				funcsFailed++;
				// Keep the name visible even where no body could be formed, so
				// the address is never anonymous in the listing.
				try {
					Symbol sym = currentProgram.getSymbolTable()
							.createLabel(a, s.name, SourceType.IMPORTED);
					sym.setPrimary();
				}
				catch (Exception e) {
					// nothing more to try
				}
			}
		}
	}

	/**
	 * How much of what the ELF calls code did we actually disassemble?  This is
	 * the number to watch: the .text section is 60% literal pools, jump tables
	 * and embedded data, so comparing against the section size would flatter us
	 * by a factor of two and hide real gaps.
	 */
	private void reportCoverage(AddressSet thumbCode, AddressSet armCode) {
		Listing listing = currentProgram.getListing();
		AddressSet code = new AddressSet(thumbCode);
		code.add(armCode);
		if (code.isEmpty()) {
			return;
		}
		AddressSet defined = new AddressSet();
		int insns = 0;
		for (Instruction i : listing.getInstructions(code, true)) {
			defined.addRange(i.getMinAddress(), i.getMaxAddress());
			insns++;
		}
		long have = defined.getNumAddresses();
		long want = code.getNumAddresses();
		println(String.format(
				"BnPrepare: coverage %d of %d code bytes disassembled (%.2f%%), %d instructions",
				have, want, 100.0 * have / want, insns));
		if (have < want) {
			int shown = 0;
			for (AddressRange range : code.subtract(defined).getAddressRanges()) {
				if (shown++ >= 10) {
					println("BnPrepare:   ... and more");
					break;
				}
				println("BnPrepare:   still undisassembled: " + range.getMinAddress()
						+ ".." + range.getMaxAddress() + " ("
						+ range.getLength() + " bytes)");
			}
		}
	}
}
