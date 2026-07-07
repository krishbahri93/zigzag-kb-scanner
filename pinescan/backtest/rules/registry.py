"""
registry.py — wires rule NAMES (in policy JSON) to rule CLASSES (in code) and loads
policies.
==================================================================================

Two halves:
  * Rule registry: each rule file calls @register("<category>","<name>") so a policy
    can refer to it by name. build_rules() turns a loaded Policy into live rule
    instances for the simulator. Rules self-register on import; _load_all() imports
    every rule module so registration has happened before a lookup.
  * Policy loading: load_policy() parses a policies/*.json into a Policy dataclass
    (capital params + the chosen rule names). build_rules() resolves the names.

HOW TO EXTEND
  * add a rule      -> see rules/__init__.py (just a new file + @register)
  * add a policy    -> copy a JSON in policies/, change rule names/params
  * add a CATEGORY  -> add a key to RULES below + a hook in base.py + a line in
                       build_rules()  (rare)
"""
import json
import importlib
from dataclasses import dataclass, field

# category -> {rule_name -> rule class}. Populated by the @register decorator.
RULES = {"sizing": {}, "selection": {}, "rotation": {}, "exit": {}}


def register(category, name):
    """Class decorator that records a rule class so policies can name it.
    Usage:  @register("rotation", "nearest_to_target_band")."""
    def deco(cls):
        RULES[category][name] = cls
        return cls
    return deco


def _load_all():
    """Import every category subpackage so its rule files run their @register.
    Each rules/<category>/__init__.py imports its own rule modules. Categories that
    don't exist yet (early in the build) are skipped silently."""
    for category in RULES:
        try:
            importlib.import_module(f"{__package__}.{category}")
        except ModuleNotFoundError:
            pass


def get_rule(category, name):
    """Return a registered rule class, or raise KeyError listing what IS available
    (so a typo in a policy gives a useful message)."""
    _load_all()
    try:
        return RULES[category][name]
    except KeyError:
        avail = ", ".join(sorted(RULES.get(category, {}))) or "(none registered yet)"
        raise KeyError(f"unknown {category} rule '{name}'. Available: {avail}")


@dataclass
class Policy:
    """A parsed policy: capital PARAMS + the chosen rule NAMES (resolved to instances
    by build_rules) + cost params. Mirrors a policies/*.json file 1:1; the JSON's
    `description` field documents the intent."""
    name: str
    description: str
    total_capital: float        # starting cash
    max_concurrent: int         # max simultaneous open positions (simulator enforces)
    sizing: str                 # sizing rule name
    sizing_params: dict          # its params, e.g. {"amount": 200000} (fixed) or {"pct": 10}
    selection: str
    rotation: str
    rotation_params: dict        # params for the rotation rule (e.g. start/step/max)
    exit: str
    costs: dict                 # {brokerage_pct, slippage_pct, stt_pct}
    # Automation Lab: selection/exit rules are parametric too (entry filters, dynamic exits)
    selection_params: dict = field(default_factory=dict)
    exit_params: dict = field(default_factory=dict)
    # Combined long+short book: optional per-side position caps (None = uncapped).
    # With fixed sizing these ARE the capital split, e.g. 6/4 = Rs 12L long / Rs 8L short.
    max_long: object = None
    max_short: object = None


def load_policy(path):
    """Parse a policies/*.json into a Policy. Validates required keys but does NOT
    resolve rule names yet (build_rules does), so a policy can be inspected without
    importing any rules. Raises KeyError if a required key is missing."""
    with open(path) as f:
        d = json.load(f)
    cap = d["capital"]
    sizing = d["sizing"]
    return Policy(
        name=d["name"], description=d.get("description", ""),
        total_capital=cap["total"], max_concurrent=cap["max_concurrent"],
        sizing=sizing["rule"], sizing_params=sizing.get("params", {}),
        selection=d["selection"]["rule"],
        rotation=d["rotation"]["rule"], rotation_params=d["rotation"].get("params", {}),
        exit=d["exit"]["rule"], costs=d.get("costs", {}),
        selection_params=d["selection"].get("params", {}),
        exit_params=d["exit"].get("params", {}),
        max_long=cap.get("max_long"), max_short=cap.get("max_short"),
    )


def build_rules(policy):
    """Resolve a Policy's rule names to live instances, passing each its params, and
    return {"sizing","selection","rotation","exit"} for the simulator.

    Param convention (keep rule __init__ signatures matching these):
      sizing(total_capital=, **sizing_params) · selection(**selection_params) ·
      rotation(**rotation_params) · exit(**exit_params)
    Raises KeyError (via get_rule) on an unknown rule name.
    """
    return {
        "sizing": get_rule("sizing", policy.sizing)(
            total_capital=policy.total_capital, **policy.sizing_params),
        "selection": get_rule("selection", policy.selection)(**policy.selection_params),
        "rotation": get_rule("rotation", policy.rotation)(**policy.rotation_params),
        "exit": get_rule("exit", policy.exit)(**policy.exit_params),
    }
