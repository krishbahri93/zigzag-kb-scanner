"""pine_port — reusable Pine Script -> Python conversion pipeline.

Three layers, in the order you use them:

  1. `pine_port.lint`     static pre-port analysis of the .pine source:
                          extracts library imports (which YOU must copy-paste
                          from TradingView — they are not auto-fetchable),
                          flags semantic traps, inventories plotted series.
  2. `pine_port.runtime`  Pine-exact building blocks (na/nz, Series history,
                          ta.* with Pine seeding) for authoring the port.
  3. `pine_port.parity`   golden-master comparison against a TradingView CSV
                          export — the ONLY accepted proof of equivalence.

CLI:  python -m pine_port lint <file.pine>
      python -m pine_port parity --csv golden.csv --port mymodule:run

Methodology: see PINE_PORTING.md (the checklist this package automates) and
.claude/skills/pine-to-python (the orchestrating skill).
"""
__version__ = "1.0.0"
