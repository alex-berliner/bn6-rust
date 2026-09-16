// Decompile every function in the analysed MMBN6F program and write one C file
// per function, each headed with the address and the file:line in
// reference/bn6f where the hand-made disassembly defines it.
//
// Run as a -postScript.  Arguments:
//     BnDecompile.java <symbols.tsv> <outdir> [threads]
//
// The output is a local reading aid, never a build input: it is derived from a
// copyrighted ROM and must stay out of git (see .gitignore).
//
//@category BN
//@runtime Java

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.parallel.DecompileConfigurer;
import ghidra.app.decompiler.parallel.DecompilerCallback;
import ghidra.app.decompiler.parallel.ParallelDecompiler;
import ghidra.app.cmd.disassemble.ArmDisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.task.TaskMonitor;

public class BnDecompile extends GhidraScript {

	/** What symbols.tsv knows about one function. */
	private static class Info {
		String name, mode, asmFile;
		int startLine, endLine;
	}

	/** One function's outcome, collected for the index. */
	private static class Result {
		String name;
		long addr;
		String mode = "?";
		String kind = "declared";
		int bodyBytes;
		int cBytes;
		int cLines;
		boolean ok;
		String status = "ok";
		String error = "";
	}

	private static final int DEFAULT_TIMEOUT_SECS = 120;
	private static final int MAX_REPAIR_ROUNDS = 8;

	/**
	 * Sorted, disjoint [start, end) ranges with a binary-search membership test.
	 */
	private static class Ranges {
		private long[] starts = new long[0];
		private long[] ends = new long[0];

		static Ranges of(List<long[]> raw) {
			Ranges r = new Ranges();
			raw.sort((a, b) -> Long.compare(a[0], b[0]));
			List<long[]> merged = new ArrayList<>();
			for (long[] x : raw) {
				if (x[1] <= x[0]) {
					continue;
				}
				if (!merged.isEmpty() && x[0] <= merged.get(merged.size() - 1)[1]) {
					long[] last = merged.get(merged.size() - 1);
					last[1] = Math.max(last[1], x[1]);
				}
				else {
					merged.add(new long[] { x[0], x[1] });
				}
			}
			r.starts = new long[merged.size()];
			r.ends = new long[merged.size()];
			for (int i = 0; i < merged.size(); i++) {
				r.starts[i] = merged.get(i)[0];
				r.ends[i] = merged.get(i)[1];
			}
			return r;
		}

		boolean contains(long addr) {
			int i = Arrays.binarySearch(starts, addr);
			if (i >= 0) {
				return true;
			}
			i = -i - 2;
			return i >= 0 && addr < ends[i];
		}

		long total() {
			long n = 0;
			for (int i = 0; i < starts.length; i++) {
				n += ends[i] - starts[i];
			}
			return n;
		}
	}

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 2) {
			println("BnDecompile: usage: BnDecompile.java <symbols.tsv> <outdir> [threads]");
			throw new IllegalArgumentException("BnDecompile needs two arguments");
		}
		String symbolsPath = args[0];
		File outDir = new File(args[1]);
		int threads = args.length > 2 ? Integer.parseInt(args[2])
				: Math.max(1, Runtime.getRuntime().availableProcessors() - 1);
		int timeout = DEFAULT_TIMEOUT_SECS;
		String envTimeout = System.getenv("BN_DECOMP_TIMEOUT");
		if (envTimeout != null && !envTimeout.isEmpty()) {
			timeout = Integer.parseInt(envTimeout);
		}

		if (!outDir.isDirectory() && !outDir.mkdirs()) {
			throw new java.io.IOException("cannot create " + outDir);
		}
		// A rerun should not leave last run's files behind, or a function that
		// has since disappeared would look current.
		int removed = 0;
		File[] stale = outDir.listFiles((d, n) -> n.endsWith(".c"));
		if (stale != null) {
			for (File f : stale) {
				if (f.delete()) {
					removed++;
				}
			}
		}
		println("BnDecompile: cleared " + removed + " stale .c files from " + outDir);

		final Map<Long, Info> infoByAddr = readSymbols(symbolsPath);
		Ranges[] byMode = new Ranges[2];
		Ranges declaredCode = readDeclaredCode(symbolsPath, byMode);
		println("BnDecompile: symbols.tsv describes " + infoByAddr.size()
				+ " functions over " + declaredCode.total() + " bytes of declared code");
		reportCoverage(declaredCode, "after analysis");
		repairClearedCode(byMode[0], byMode[1], infoByAddr);
		reportCoverage(declaredCode, "after repair");

		// Partition everything Ghidra calls a function into four kinds, so the
		// index is a complete account and decomp/ holds only files worth opening.
		List<Function> functions = new ArrayList<>();
		final Map<Long, String> kindByAddr = new HashMap<>();
		List<Result> skipped = new ArrayList<>();
		int declared = 0, discovered = 0, spurious = 0, empty = 0;
		StringBuilder examples = new StringBuilder();
		FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
		while (it.hasNext()) {
			Function fn = it.next();
			long addr = fn.getEntryPoint().getOffset();
			int body = (int) fn.getBody().getNumAddresses();

			if (infoByAddr.containsKey(addr)) {
				declared++;
				kindByAddr.put(addr, "declared");
				functions.add(fn);
				continue;
			}

			Result r = new Result();
			r.name = fn.getName();
			r.addr = addr;
			r.bodyBytes = body;
			r.ok = false;
			if (!declaredCode.contains(addr)) {
				spurious++;
				r.kind = "spurious";
				r.status = "skipped";
				r.error = "outside the code reference/bn6f declares -- analysis "
						+ "invented this function in the game's data";
				skipped.add(r);
				if (spurious <= 5) {
					examples.append(" ").append(fn.getName());
				}
			}
			else if (body <= 1) {
				// A function whose body is a single address holds no instruction:
				// the C is `return;` and nothing else.
				empty++;
				r.kind = "empty";
				r.status = "skipped";
				r.error = "body is one address -- no instruction in it";
				skipped.add(r);
			}
			else {
				// Real instructions inside a declared function that Ghidra split
				// off under its own name.  Worth keeping: where it split a real
				// routine, this file holds the half the routine's own C stops at.
				discovered++;
				kindByAddr.put(addr, "discovered");
				functions.add(fn);
			}
		}
		println("BnDecompile: " + declared + " declared functions + " + discovered
				+ " fragments Ghidra split out of them, on " + threads
				+ " threads (timeout " + timeout + "s each)");
		println("BnDecompile: skipping " + spurious
				+ " functions analysis invented in the game's data (e.g."
				+ examples + " ) and " + empty + " with an empty body");

		final String header = "// decompiled by " + ghidra.framework.Application
				.getApplicationVersion() + " from the real MMBN6F cartridge image";
		final List<Result> results = Collections.synchronizedList(new ArrayList<>());
		final AtomicInteger done = new AtomicInteger();
		final int total = functions.size();
		final long t0 = System.currentTimeMillis();

		DecompileConfigurer configurer = new DecompileConfigurer() {
			@Override
			public void configure(DecompInterface d) {
				d.toggleCCode(true);
				d.toggleSyntaxTree(true);
				d.setSimplificationStyle("decompile");
				DecompileOptions opts = new DecompileOptions();
				opts.grabFromProgram(currentProgram);
				d.setOptions(opts);
			}
		};

		DecompilerCallback<Result> callback =
			new DecompilerCallback<Result>(currentProgram, configurer) {
				@Override
				public Result process(DecompileResults res, TaskMonitor mon) throws Exception {
					Result r = writeOne(res, infoByAddr, kindByAddr, outDir, header);
					int n = done.incrementAndGet();
					if (n % 1000 == 0) {
						long secs = (System.currentTimeMillis() - t0) / 1000;
						println("BnDecompile: " + n + "/" + total + " (" + secs + "s)");
					}
					return r;
				}
			};
		callback.setTimeout(timeout);

		try {
			ParallelDecompiler.decompileFunctions(callback, currentProgram,
					functions.iterator(), r -> {
						if (r != null) {
							results.add(r);
						}
					}, monitor);
		}
		finally {
			callback.dispose();
		}

		List<Result> all = new ArrayList<>(results);
		all.addAll(skipped);
		// Any declared function the program does not contain: analysis refused to
		// form a body for it (its extent overlapped a thunk, usually).  Recorded
		// so index.tsv accounts for all 13,646, and a reader asking for one gets
		// an answer instead of a missing file.
		int absent = 0;
		for (Map.Entry<Long, Info> e : infoByAddr.entrySet()) {
			if (kindByAddr.containsKey(e.getKey())) {
				continue;
			}
			Result r = new Result();
			r.addr = e.getKey();
			r.name = e.getValue().name;
			r.mode = e.getValue().mode;
			r.kind = "declared";
			r.status = "absent";
			r.error = "no function at this address after analysis";
			all.add(r);
			absent++;
		}
		if (absent > 0) {
			println("BnDecompile: " + absent + " declared functions have no body "
					+ "in the analysed program; recorded as absent");
		}
		writeIndex(new File(outDir, "index.tsv"), all);

		int ok = 0;
		long cBytes = 0;
		for (Result r : results) {
			if (r.ok) {
				ok++;
				cBytes += r.cBytes;
			}
		}
		long secs = (System.currentTimeMillis() - t0) / 1000;
		println("BnDecompile: DONE " + ok + " decompiled, " + (results.size() - ok)
				+ " failed, of " + total + " attempted (" + skipped.size()
				+ " skipped as spurious)");
		println("BnDecompile: " + cBytes + " bytes of C in " + outDir + " in " + secs + "s");
	}

	// ------------------------------------------------------------------

	private Map<Long, Info> readSymbols(String path) throws Exception {
		Map<Long, Info> out = new HashMap<>();
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("#") || line.trim().isEmpty()) {
					continue;
				}
				String[] f = line.split("\t", -1);
				if (f.length < 8 || !"F".equals(f[0])) {
					continue;
				}
				Info i = new Info();
				i.name = f[1];
				i.mode = f[3];
				i.asmFile = f[5];
				i.startLine = Integer.parseInt(f[6]);
				i.endLine = Integer.parseInt(f[7]);
				out.put(Long.parseLong(f[2], 16), i);
			}
		}
		return out;
	}

	/**
	 * Which bytes the disassembly declares to be instructions: the ELF's
	 * `$t`/`$a` mapping ranges, narrowed to the extent of a declared function.
	 *
	 * This exists to throw work away.  Analysis reads the game's sprite and map
	 * data -- which the linker puts in .text, so it is executable -- finds
	 * byte pairs that look like Thumb function pointers, and declares functions
	 * there: 25,750 of them on this ROM, against 13,646 real ones.  Decompiling
	 * those produces files full of nonsense that a reader has no way to tell from
	 * the real thing.  The disassembly is byte-exact and names every function, so
	 * anything outside this set is an artefact, and saying so is not a guess.
	 */
	private Ranges readDeclaredCode(String path, Ranges[] byMode) throws Exception {
		List<long[]> marks = new ArrayList<>();      // {addr, 0 data / 1 thumb / 2 arm}
		List<long[]> bodies = new ArrayList<>();
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("#") || line.trim().isEmpty()) {
					continue;
				}
				String[] f = line.split("\t", -1);
				if (f.length < 8) {
					continue;
				}
				long addr = Long.parseLong(f[2], 16);
				if ("M".equals(f[0])) {
					long mode = "data".equals(f[3]) ? 0 : ("arm".equals(f[3]) ? 2 : 1);
					marks.add(new long[] { addr, mode });
				}
				else if ("F".equals(f[0])) {
					long size = Long.parseLong(f[4]);
					if (size > 0) {
						bodies.add(new long[] { addr, addr + size });
					}
				}
			}
		}
		marks.sort((a, b) -> Long.compare(a[0], b[0]));
		List<long[]> codeRaw = new ArrayList<>();
		List<long[]> thumbRaw = new ArrayList<>();
		List<long[]> armRaw = new ArrayList<>();
		for (int i = 0; i < marks.size(); i++) {
			if (marks.get(i)[1] == 0) {
				continue;
			}
			long end = (i + 1 < marks.size()) ? marks.get(i + 1)[0] : marks.get(i)[0] + 4;
			long[] range = { marks.get(i)[0], end };
			codeRaw.add(range);
			(marks.get(i)[1] == 2 ? armRaw : thumbRaw).add(new long[] { range[0], range[1] });
		}
		Ranges extents = Ranges.of(bodies);
		if (byMode != null) {
			byMode[0] = intersect(Ranges.of(thumbRaw), extents);
			byMode[1] = intersect(Ranges.of(armRaw), extents);
		}
		return intersect(Ranges.of(codeRaw), extents);
	}

	/** Keep only the parts of `code` that lie inside `extents`. */
	private static Ranges intersect(Ranges code, Ranges extents) {
		List<long[]> both = new ArrayList<>();
		for (int i = 0; i < code.starts.length; i++) {
			for (long a = code.starts[i]; a < code.ends[i]; ) {
				long b = a;
				while (b < code.ends[i] && extents.contains(b)) {
					b++;
				}
				if (b > a) {
					both.add(new long[] { a, b });
					a = b;
				}
				else {
					a++;
				}
			}
		}
		return Ranges.of(both);
	}

	private AddressSet toAddressSet(Ranges r) {
		AddressSet set = new AddressSet();
		for (int i = 0; i < r.starts.length; i++) {
			set.addRange(toAddr(r.starts[i]), toAddr(r.ends[i] - 1));
		}
		return set;
	}

	/**
	 * Put back the code auto-analysis cleared, and the functions that went with
	 * it.
	 *
	 * Analysis erases instructions it decides are unreachable.  On this ROM that
	 * costs about 20 KiB of real code and 60 whole functions -- code the
	 * pre-script had disassembled and whose boundaries reference/bn6f states
	 * outright.  Switching the culprit off is not reliable (the
	 * `Non-Returning Functions - Discovered.Repair Flow Damage` option refuses to
	 * stay false), so instead this re-asserts the truth afterwards: anything
	 * inside the declared code set that has no instruction gets disassembled
	 * again, and any declared function without a body gets recreated.  Being a
	 * repair rather than a prevention, it also does not care which analyser was
	 * responsible.
	 */
	private void repairClearedCode(Ranges thumbCode, Ranges armCode,
			Map<Long, Info> infoByAddr) {
		AddressSet thumb = toAddressSet(thumbCode);
		AddressSet arm = toAddressSet(armCode);
		int rounds = 0;
		long lastGaps = -1;
		for (; rounds < MAX_REPAIR_ROUNDS; rounds++) {
			AddressSet thumbSeeds = gapSeeds(thumb, 2);
			AddressSet armSeeds = gapSeeds(arm, 4);
			long gaps = thumbSeeds.getNumAddresses() + armSeeds.getNumAddresses();
			// The last few gaps never close: they are jump tables the assembler
			// left inside a Thumb mapping range, so they are data and will not
			// decode.  Stop as soon as a round changes nothing.
			if (gaps == 0 || gaps == lastGaps) {
				break;
			}
			lastGaps = gaps;
			if (!thumbSeeds.isEmpty()) {
				new ArmDisassembleCommand(thumbSeeds, thumb, true)
						.applyTo(currentProgram, monitor);
			}
			if (!armSeeds.isEmpty()) {
				new ArmDisassembleCommand(armSeeds, arm, false)
						.applyTo(currentProgram, monitor);
			}
		}
		int remade = 0;
		for (Map.Entry<Long, Info> e : infoByAddr.entrySet()) {
			Address a = toAddr(e.getKey());
			if (getFunctionAt(a) != null) {
				continue;
			}
			CreateFunctionCmd cmd = new CreateFunctionCmd(
					e.getValue().name, a, null, SourceType.IMPORTED);
			if (cmd.applyTo(currentProgram, monitor)) {
				remade++;
			}
		}
		println("BnDecompile: repaired analysis damage in " + rounds
				+ " rounds; " + remade + " declared functions recreated");
	}

	/** The aligned start of each run inside `code` that holds no instruction. */
	private AddressSet gapSeeds(AddressSet code, int align) {
		if (code.isEmpty()) {
			return new AddressSet();
		}
		AddressSet defined = new AddressSet();
		for (Instruction i : currentProgram.getListing().getInstructions(code, true)) {
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
	 * How much of the declared code still holds instructions, measured here
	 * rather than only in the pre-script.
	 *
	 * The pre-script's figure is what disassembly achieved; this one is what
	 * survived auto-analysis, and the two can differ -- an analyser that clears
	 * code it thinks is unreachable takes real functions with it.  This is the
	 * number that decides what the decompiler can see, so it is the one to watch.
	 */
	private void reportCoverage(Ranges declaredCode, String when) {
		AddressSet code = toAddressSet(declaredCode);
		AddressSet defined = new AddressSet();
		for (Instruction i : currentProgram.getListing().getInstructions(code, true)) {
			defined.addRange(i.getMinAddress(), i.getMaxAddress());
		}
		long have = defined.getNumAddresses();
		long want = code.getNumAddresses();
		println(String.format("BnDecompile: %s, %d of %d declared code bytes hold "
				+ "instructions (%.2f%%)", when, have, want,
				want == 0 ? 0.0 : 100.0 * have / want));
	}

	/** Write one function's C file. Called from the decompiler's worker threads. */
	private Result writeOne(DecompileResults res, Map<Long, Info> infoByAddr,
			Map<Long, String> kindByAddr, File outDir, String header) {
		Function fn = res.getFunction();
		Result r = new Result();
		r.name = fn.getName();
		r.addr = fn.getEntryPoint().getOffset();
		r.bodyBytes = (int) fn.getBody().getNumAddresses();

		r.kind = kindByAddr.getOrDefault(r.addr, "declared");
		Info info = infoByAddr.get(r.addr);
		if (info != null) {
			r.mode = info.mode;
		}

		String body = null;
		if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
			body = res.getDecompiledFunction().getC();
			r.ok = body != null && !body.isEmpty();
		}
		else {
			r.ok = false;
		}
		if (!r.ok) {
			String msg = res.getErrorMessage();
			r.status = "failed";
			r.error = (msg == null || msg.isEmpty()) ? "decompiler produced no C"
					: msg.replace('\n', ' ').replace('\t', ' ');
			body = "// DECOMPILATION FAILED: " + r.error + "\n";
		}

		StringBuilder sb = new StringBuilder();
		sb.append("// ").append(r.name)
				.append("  @ 0x").append(String.format("%08X", r.addr));
		if (info != null) {
			sb.append("  ").append(info.mode);
		}
		sb.append("  (").append(r.bodyBytes).append(" bytes of code)\n");
		if (info != null && info.startLine > 0) {
			sb.append("// disassembly: ").append(info.asmFile)
					.append(':').append(info.startLine);
			if (info.endLine > info.startLine) {
				sb.append('-').append(info.endLine);
			}
			sb.append('\n');
		}
		else if (info != null) {
			sb.append("// disassembly: no *.s marker for this symbol\n");
		}
		else {
			sb.append("// disassembly: found by Ghidra's analysis, "
					+ "not present in reference/bn6f\n");
		}
		sb.append(header).append("\n");
		sb.append("// reference only -- nothing in src/ is generated from this file\n\n");
		sb.append(body);

		File out = new File(outDir, r.name + ".c");
		synchronized (BnDecompile.class) {
			// Two functions with the same name would otherwise silently
			// overwrite each other; keep both, distinguished by address.
			if (out.exists()) {
				out = new File(outDir,
						r.name + "." + String.format("%08X", r.addr) + ".c");
			}
			try (BufferedWriter w = new BufferedWriter(new FileWriter(out))) {
				w.write(sb.toString());
			}
			catch (Exception e) {
				r.ok = false;
				r.status = "failed";
				r.error = "write failed: " + e;
				return r;
			}
		}
		r.cBytes = sb.length();
		for (int i = 0; i < sb.length(); i++) {
			if (sb.charAt(i) == '\n') {
				r.cLines++;
			}
		}
		return r;
	}

	private void writeIndex(File path, List<Result> results) throws Exception {
		List<Result> sorted = new ArrayList<>(results);
		Collections.sort(sorted, (a, b) -> Long.compare(a.addr, b.addr));
		try (BufferedWriter w = new BufferedWriter(new FileWriter(path))) {
			w.write("# addr\tname\tmode\tkind\tbody_bytes\tstatus"
					+ "\tc_bytes\tc_lines\terror\n");
			for (Result r : sorted) {
				w.write(String.format("%08X\t%s\t%s\t%s\t%d\t%s\t%d\t%d\t%s%n",
						r.addr, r.name, r.mode, r.kind, r.bodyBytes,
						r.status, r.cBytes, r.cLines, r.error));
			}
		}
		println("BnDecompile: wrote " + path);
	}
}
