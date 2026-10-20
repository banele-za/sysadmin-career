"""Resolve a ticket's randomized parameters.

The `params:` block of ticket.yaml supports:

    group: { pick: [finance, payroll, audit] }        one random item
    users: { pick_n: 2, from: [alice, bob, carol] }   N distinct random items (a list)
    dir:   "/srv/{group}"                             text that can use other params
    port:  8080                                       a fixed value

Params may refer to each other in any order; we resolve them in dependency
order and reject cycles. A seed makes the result repeatable, so a ticket can
be replayed with exactly the same values.

Lists become space-separated text when used inside a template or passed to
Bash, so `for u in $USERS; do ...; done` works in break.sh.
"""

import random
import re

PLACEHOLDER = re.compile(r"\{(\w+)\}")


class ParamError(ValueError):
    pass


def _as_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def render(text: str, values: dict) -> str:
    """Replace {name} with the param's value. Unknown {words} are left alone,
    so Bash like ${HOME} inside ticket text is safe."""
    def sub(match):
        name = match.group(1)
        return _as_text(values[name]) if name in values else match.group(0)
    return PLACEHOLDER.sub(sub, text)


def resolve(spec: dict | None, seed: int) -> dict:
    """Turn a params spec into concrete values."""
    rng = random.Random(seed)
    spec = spec or {}
    values: dict = {}

    # Random picks first, in the order written, so a given seed always
    # produces the same choices.
    templates = {}
    for name, rule in spec.items():
        if isinstance(rule, dict) and "pick" in rule:
            values[name] = rng.choice(rule["pick"])
        elif isinstance(rule, dict) and "pick_n" in rule:
            pool = rule.get("from") or []
            if rule["pick_n"] > len(pool):
                raise ParamError(f"{name}: pick_n {rule['pick_n']} > {len(pool)} choices")
            values[name] = rng.sample(pool, rule["pick_n"])
        elif isinstance(rule, dict):
            raise ParamError(f"{name}: unknown rule {sorted(rule)}")
        elif isinstance(rule, str):
            templates[name] = rule
        else:
            values[name] = rule

    # Then templates, repeatedly filling in any whose references are ready.
    while templates:
        progressed = False
        for name, text in list(templates.items()):
            refs = [r for r in PLACEHOLDER.findall(text) if r in spec]
            if all(r in values for r in refs):
                values[name] = render(text, values)
                del templates[name]
                progressed = True
        if not progressed:
            raise ParamError(f"circular references between params: {sorted(templates)}")
    return values


# Variables the shell itself relies on; a param with one of these names
# would silently break every script, so we refuse it.
RESERVED_ENV = {"HOME", "PATH", "USER", "SHELL", "PWD", "LANG", "TERM", "IFS", "UID", "LOGNAME"}


def to_env(values: dict) -> dict[str, str]:
    """Params as environment variables for break.sh/grade.sh: group -> GROUP."""
    env = {}
    for name, value in values.items():
        var = name.upper()
        if var in RESERVED_ENV:
            raise ParamError(f"param '{name}' would overwrite ${var}; pick another name")
        env[var] = _as_text(value)
    return env
