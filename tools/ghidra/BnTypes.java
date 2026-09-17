// Give the analysed MMBN6F program the game's own data types, put them where
// the disassembly says they live, and tell the decompiler about the two
// registers this game passes arguments in that no ARM calling convention
// describes.
//
// Run as a -postScript, before BnDecompile.java.  Arguments:
//     BnTypes.java <bn_types.h> <bn_types.tsv> <bn_globals.tsv> <bn_protos.tsv>
// all four produced by tools/ghidra/bntypes.py.
//
// Why after analysis rather than before it: the C this script exists to improve
// is produced by the decompiler, which runs in the next post-script, and by now
// Ghidra has already worked out each function's return type and its r0-r3
// parameters.  Rewriting a signature here therefore adds r5/r7 to what analysis
// found instead of replacing it.
//
// The three things it does:
//
//   types       parse bn_types.h into the program's data type manager, then
//               check every struct against the offsets bntypes.py measured.
//               A struct Ghidra lays out differently from the cartridge would
//               rename fields wrongly, which is worse than not naming them, so
//               a mismatch is counted and reported rather than passed over.
//
//   globals     apply those types to the addresses reference/bn6f gives them:
//               ewram.s instantiates the structs by name and bn6f.map holds
//               each instance's address, so `0x0203a9b0` becomes a
//               T1BattleObject and `0x08021da8` becomes ChipData[411].
//
//   prototypes  BN6 passes the current BattleObject in r5 and the AI's attack
//               variables in r7.  Both are callee-saved, so the decompiler
//               reads them as `unaff_r5` / `unaff_r7` -- registers live on
//               entry that no convention accounts for.  Ghidra cannot express
//               that with a stock prototype model, but it can express it per
//               function with custom variable storage, which is what this does,
//               only for the functions bntypes.py found evidence for.
//
//@category BN
//@runtime Java

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.cparser.C.CParser;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.ArrayDataType;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DataTypeManager;
import ghidra.program.model.data.DataUtilities;
import ghidra.program.model.data.DataUtilities.ClearDataMode;
import ghidra.program.model.data.DataTypeComponent;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.data.Structure;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Function.FunctionUpdateType;
import ghidra.program.model.listing.Parameter;
import ghidra.program.model.listing.ParameterImpl;
import ghidra.program.model.listing.Variable;
import ghidra.program.model.listing.VariableStorage;
import ghidra.program.model.symbol.SourceType;

public class BnTypes extends GhidraScript {

	/** One `<function> <register> <struct>` row of bn_protos.tsv. */
	private static class Proto {
		String register, struct, evidence;
		int refs;
	}

	/** One global instance: a struct type at an address, maybe an array. */
	private static class Global {
		String label, struct, where;
		long addr;
		int count;
	}

	private DataTypeManager dtm;
	private final Map<String, DataType> byName = new HashMap<>();

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 4) {
			println("BnTypes: usage: BnTypes.java <bn_types.h> <bn_types.tsv> "
					+ "<bn_globals.tsv> <bn_protos.tsv>");
			throw new IllegalArgumentException("BnTypes needs four arguments");
		}
		long t0 = System.currentTimeMillis();
		dtm = currentProgram.getDataTypeManager();

		parseHeader(args[0]);
		verifyLayout(args[1]);
		applyGlobals(args[2]);
		applyPrototypes(args[3]);

		println("BnTypes: done in " + ((System.currentTimeMillis() - t0) / 1000) + "s");
	}

	// ------------------------------------------------------------------
	// Types
	// ------------------------------------------------------------------

	private void parseHeader(String path) throws Exception {
		CParser parser = new CParser(dtm, true, null);
		parser.setParseFileName(path);
		try (FileInputStream in = new FileInputStream(path)) {
			parser.parse(in);
		}
		String messages = parser.getParseMessages();
		if (messages != null && !messages.trim().isEmpty()) {
			for (String line : messages.trim().split("\n")) {
				println("BnTypes: parser: " + line);
			}
		}
		int n = 0;
		for (Map.Entry<String, DataType> e : parser.getComposites().entrySet()) {
			DataType dt = dtm.getDataType(e.getValue().getCategoryPath(),
					e.getValue().getName());
			byName.put(stripTag(e.getKey()), dt != null ? dt : e.getValue());
			n++;
		}
		println("BnTypes: parsed " + path + " -- " + n
				+ " structs into the program's data type manager");
	}

	/** `struct BattleObject` and `BattleObject` are the same type here. */
	private static String stripTag(String name) {
		if (name.startsWith("struct ")) {
			return name.substring(7);
		}
		return name;
	}

	/**
	 * Check what Ghidra built against what the assembler measured.
	 *
	 * Ghidra's C parser is free to align a structure the way the compiler spec
	 * says, which is not necessarily how the game's assembler laid it out.  Any
	 * field that ends up at a different offset would make the decompiler print a
	 * confidently wrong name, so every field in bn_types.tsv is checked and the
	 * mismatches are counted.  A clean run prints 0.
	 */
	private void verifyLayout(String manifest) throws Exception {
		int fields = 0, badOffset = 0, missing = 0, badSize = 0, structs = 0;
		StringBuilder examples = new StringBuilder();
		try (BufferedReader r = new BufferedReader(new FileReader(manifest))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("#")) {
					continue;
				}
				String[] f = line.split("\t", -1);
				if (f.length >= 7 && "STRUCT".equals(f[0])) {
					structs++;
					DataType dt = byName.get(f[1]);
					if (dt == null) {
						missing++;
						continue;
					}
					int want = (int) Long.parseLong(f[5].substring(2), 16);
					if (dt.getLength() != want) {
						badSize++;
						if (examples.length() < 300) {
							examples.append(" ").append(f[1]).append("(")
									.append(dt.getLength()).append("!=")
									.append(want).append(")");
						}
					}
				}
				else if (f.length >= 6 && "FIELD".equals(f[0])) {
					fields++;
					DataType dt = byName.get(f[1]);
					if (!(dt instanceof Structure)) {
						continue;
					}
					int want = (int) Long.parseLong(f[3].substring(2), 16);
					DataTypeComponent c = ((Structure) dt).getComponentAt(want);
					if (c == null || c.getFieldName() == null
							|| !f[2].equals(c.getFieldName())) {
						badOffset++;
						if (examples.length() < 300) {
							examples.append(" ").append(f[1]).append(".").append(f[2]);
						}
					}
				}
			}
		}
		println("BnTypes: layout check: " + structs + " structs, " + fields
				+ " fields -- " + badOffset + " fields at the wrong offset, "
				+ badSize + " structs the wrong size, " + missing
				+ " structs the parser did not produce"
				+ (examples.length() > 0 ? " (e.g." + examples + " )" : ""));
	}

	// ------------------------------------------------------------------
	// Globals
	// ------------------------------------------------------------------

	/**
	 * Type the addresses the disassembly names.
	 *
	 * ewram.s instantiates the structs by name and bn6f.map gives each instance
	 * its address, so `eT1BattleObject0` lands a T1BattleObject on 0x0203a9b0
	 * and `ChipDataArr_8021DA8` lands ChipData[411] on 0x08021da8.  Where two
	 * declarations claim one address only one type can be applied, so the
	 * largest wins -- it names the most bytes -- and the rest are counted.
	 */
	private void applyGlobals(String path) throws Exception {
		Map<Long, Global> best = new TreeMap<>();
		int rows = 0, overlaps = 0;
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
				Global g = new Global();
				g.label = f[0];
				g.struct = f[1];
				g.addr = Long.parseLong(f[2], 16);
				g.count = Integer.parseInt(f[3]);
				g.where = f[4];
				rows++;
				Global prev = best.get(g.addr);
				if (prev == null) {
					best.put(g.addr, g);
				}
				else {
					overlaps++;
					if (sizeOf(g) > sizeOf(prev)) {
						best.put(g.addr, g);
					}
				}
			}
		}

		int applied = 0, failed = 0, unknown = 0, partial = 0, elements = 0;
		StringBuilder why = new StringBuilder();
		for (Global g : best.values()) {
			DataType element = byName.get(g.struct);
			if (element == null) {
				unknown++;
				continue;
			}
			Address a = toAddr(g.addr);
			if (!currentProgram.getMemory().contains(a)) {
				failed++;
				continue;
			}
			DataType dt = g.count > 1
					? new ArrayDataType(element, g.count, element.getLength())
					: element;
			try {
				DataUtilities.createData(currentProgram, a, dt, -1,
						ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
				applied++;
				continue;
			}
			catch (Exception e) {
				if (g.count <= 1) {
					failed++;
					if (why.length() < 300) {
						why.append(" ").append(g.label).append(": ")
								.append(e.getMessage());
					}
					continue;
				}
			}
			// A table of 411 ChipData is one 11 KiB object, and a single byte
			// of it that analysis already claimed defeats the whole array.  The
			// rows are independently useful, so lay them down one at a time and
			// say how many took.
			int n = 0;
			for (int i = 0; i < g.count; i++) {
				Address at = a.add((long) i * element.getLength());
				try {
					DataUtilities.createData(currentProgram, at, element, -1,
							ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
					n++;
				}
				catch (Exception e) {
					// keep going: one bad row does not spoil the table
				}
			}
			if (n == 0) {
				failed++;
			}
			else {
				partial++;
				elements += n;
				if (why.length() < 300) {
					why.append(" ").append(g.label).append(": ").append(n)
							.append("/").append(g.count).append(" rows");
				}
			}
		}
		if (partial > 0) {
			println("BnTypes: globals: " + partial + " arrays laid down row by row ("
					+ elements + " rows) because something already claimed part "
					+ "of the table");
		}
		println("BnTypes: globals: " + rows + " declared instances at "
				+ best.size() + " distinct addresses (" + overlaps
				+ " share an address with a differently sized flavour; the "
				+ "largest wins)");
		println("BnTypes: globals: " + applied + " typed, " + failed
				+ " could not be applied, " + unknown + " of an unknown type"
				+ (why.length() > 0 ? " --" + why : ""));
	}

	private int sizeOf(Global g) {
		DataType dt = byName.get(g.struct);
		return dt == null ? 0 : dt.getLength() * Math.max(g.count, 1);
	}

	// ------------------------------------------------------------------
	// Prototypes
	// ------------------------------------------------------------------

	/**
	 * Add the register parameters the evidence says a function takes.
	 *
	 * Ghidra has no stock ARM prototype model that passes anything in r5 or r7,
	 * and inventing a compiler spec that did would apply it to all 13,646
	 * functions, most of which do not take one.  Custom variable storage says
	 * the same thing per function and only where it is true:
	 *
	 *     void MettaurDecide_8109FD6(BattleObject *self)   // self in r5
	 *
	 * Whatever analysis already worked out is kept: the existing return value
	 * and the existing r0-r3 parameters are re-declared with the storage they
	 * already have, and the register parameters are appended.  So this can only
	 * add information, never drop any.
	 */
	private void applyPrototypes(String path) throws Exception {
		Map<String, List<Proto>> byFunc = new HashMap<>();
		int rows = 0, conflicts = 0;
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.startsWith("# CONFLICT")) {
					conflicts++;
					continue;
				}
				if (line.startsWith("#") || line.trim().isEmpty()) {
					continue;
				}
				String[] f = line.split("\t", -1);
				if (f.length < 5) {
					continue;
				}
				Proto p = new Proto();
				p.register = f[1];
				p.struct = f[2];
				p.evidence = f[3];
				p.refs = Integer.parseInt(f[4]);
				byFunc.computeIfAbsent(f[0], k -> new ArrayList<>()).add(p);
				rows++;
			}
		}
		println("BnTypes: prototypes: " + rows + " register parameters over "
				+ byFunc.size() + " functions (" + conflicts
				+ " skipped upstream as contradictory evidence)");

		// Resolve names to functions.  A name that resolves to more than one
		// function is ambiguous and is left alone rather than applied to both.
		Map<String, Function> functions = new HashMap<>();
		Set<String> ambiguous = new HashSet<>();
		for (Function fn : currentProgram.getFunctionManager().getFunctions(true)) {
			if (functions.put(fn.getName(), fn) != null) {
				ambiguous.add(fn.getName());
			}
		}

		int applied = 0, params = 0, noFunction = 0, dup = 0, noType = 0, failed = 0;
		int replaced = 0;
		StringBuilder why = new StringBuilder();
		Map<String, Integer> perRegister = new TreeMap<>();
		for (Map.Entry<String, List<Proto>> e : byFunc.entrySet()) {
			if (ambiguous.contains(e.getKey())) {
				dup++;
				continue;
			}
			Function fn = functions.get(e.getKey());
			if (fn == null) {
				noFunction++;
				continue;
			}
			List<Proto> protos = new ArrayList<>(e.getValue());
			protos.sort(Comparator.comparing(p -> p.register));

			// Registers this function is about to be given.  A parameter that
			// already sits in one of them is this script's own work from an
			// earlier run (or analysis's guess at the same register), and it is
			// replaced rather than kept -- keeping it would declare the same
			// register twice and Ghidra rejects the whole signature.
			Set<String> targets = new HashSet<>();
			for (Proto p : protos) {
				targets.add(p.register);
			}
			List<Variable> newParams = new ArrayList<>();
			Set<String> used = new HashSet<>();
			boolean ok = true;
			for (Parameter p : fn.getParameters()) {
				VariableStorage vs = p.getVariableStorage();
				Register held = vs == null ? null : vs.getRegister();
				if (held != null && targets.contains(held.getName())) {
					replaced++;
					continue;
				}
				try {
					newParams.add(new ParameterImpl(p, currentProgram));
					used.add(p.getName());
				}
				catch (Exception ex) {
					ok = false;
				}
			}
			if (!ok) {
				failed++;
				continue;
			}
			int added = 0;
			for (Proto p : protos) {
				DataType dt = byName.get(p.struct);
				Register reg = currentProgram.getRegister(p.register);
				if (dt == null || reg == null) {
					noType++;
					continue;
				}
				String name = nameFor(p, used);
				try {
					newParams.add(new ParameterImpl(name, new PointerDataType(dt, dtm),
							reg, currentProgram, SourceType.USER_DEFINED));
					used.add(name);
					added++;
					perRegister.merge(p.register, 1, Integer::sum);
				}
				catch (Exception ex) {
					noType++;
				}
			}
			if (added == 0) {
				continue;
			}
			try {
				fn.updateFunction(null, null, newParams,
						FunctionUpdateType.CUSTOM_STORAGE, true,
						SourceType.USER_DEFINED);
				applied++;
				params += added;
			}
			catch (Exception ex) {
				failed++;
				if (why.length() < 400) {
					why.append(" ").append(fn.getName()).append(": ")
							.append(ex.getMessage());
				}
			}
		}
		StringBuilder regs = new StringBuilder();
		for (Map.Entry<String, Integer> e : perRegister.entrySet()) {
			regs.append(" ").append(e.getKey()).append("=").append(e.getValue());
		}
		println("BnTypes: prototypes: " + applied + " functions given "
				+ params + " register parameters --" + regs
				+ (replaced > 0 ? " (" + replaced + " existing parameters in "
						+ "those same registers replaced)" : ""));
		println("BnTypes: prototypes: " + noFunction
				+ " named functions are not in the program, " + dup
				+ " names are ambiguous, " + noType
				+ " parameters had no type or register, " + failed
				+ " functions rejected the new signature"
				+ (why.length() > 0 ? " --" + why : ""));
	}

	/**
	 * `self` for the object a routine acts on, otherwise the type's own name.
	 * r5 is that object everywhere in this game, which is why it is worth the
	 * special case: `self->CurAction` reads the way the routine is written.
	 */
	private String nameFor(Proto p, Set<String> used) {
		String base = "r5".equals(p.register) ? "self" : lowerFirst(p.struct);
		String name = base;
		int n = 2;
		while (used.contains(name)) {
			name = base + n++;
		}
		return name;
	}

	/**
	 * `AIAttackVars` -> `aiAttackVars`, `BattleObject` -> `battleObject`.
	 * Lower-casing only the first letter would give `aIAttackVars`, which reads
	 * as a typo every time it appears in the C.
	 */
	private static String lowerFirst(String s) {
		if (s.isEmpty()) {
			return "arg";
		}
		int caps = 0;
		while (caps < s.length() && Character.isUpperCase(s.charAt(caps))) {
			caps++;
		}
		int lower = caps <= 1 ? 1 : (caps == s.length() ? caps : caps - 1);
		return s.substring(0, lower).toLowerCase() + s.substring(lower);
	}
}
