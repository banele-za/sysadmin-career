"""Engine tests that don't need the VM: params, ticket loading, grader output."""

import pytest
import yaml

from client import config
from client.engine import params, tickets
from client.engine.grader import parse_output


# ---- params ----------------------------------------------------------------

SPEC = {
    "dir": "/srv/{group}",                     # refers to a param defined later
    "group": {"pick": ["finance", "payroll", "audit"]},
    "users": {"pick_n": 2, "from": ["alice", "bob", "carol", "dan"]},
    "label": "{group} team: {users}",
    "port": 8080,
}


def test_resolve_dependencies_and_types():
    v = params.resolve(SPEC, seed=1)
    assert v["group"] in ("finance", "payroll", "audit")
    assert v["dir"] == f"/srv/{v['group']}"
    assert len(v["users"]) == 2 and len(set(v["users"])) == 2
    assert v["label"] == f"{v['group']} team: {' '.join(v['users'])}"
    assert v["port"] == 8080


def test_same_seed_same_values():
    assert params.resolve(SPEC, seed=42) == params.resolve(SPEC, seed=42)


def test_seeds_vary_values():
    groups = {params.resolve(SPEC, seed=s)["group"] for s in range(50)}
    assert len(groups) > 1


def test_cycle_detected():
    with pytest.raises(params.ParamError, match="circular"):
        params.resolve({"a": "{b}", "b": "{a}"}, seed=0)


def test_pick_n_too_many():
    with pytest.raises(params.ParamError):
        params.resolve({"u": {"pick_n": 3, "from": ["a", "b"]}}, seed=0)


def test_env_names_and_lists():
    env = params.to_env({"group": "finance", "users": ["alice", "bob"]})
    assert env == {"GROUP": "finance", "USERS": "alice bob"}


def test_reserved_env_rejected():
    with pytest.raises(params.ParamError, match="HOME"):
        params.to_env({"home": "/home/admin"})


def test_render_leaves_bash_alone():
    assert params.render("cd {dir} && echo ${HOME} {nope}", {"dir": "/srv"}) == \
        "cd /srv && echo ${HOME} {nope}"


# ---- ticket loading (real content) ----------------------------------------

def test_all_content_loads():
    loaded = tickets.load_all(config.TICKETS_DIR)
    ids = {t.id for t in loaded}
    assert {"tut-01-files", "perm-03-setgid-shared"} <= ids


def test_tickets_reference_known_objectives():
    known = yaml.safe_load((config.CONTENT_DIR / "objectives" / "rhcsa.yaml").read_text())
    for t in tickets.load_all(config.TICKETS_DIR, track="rhel"):
        for key in t.objectives:
            assert key in known, f"{t.id}: unknown objective {key}"


def test_every_ticket_instantiates_and_has_scripts():
    for t in tickets.load_all(config.TICKETS_DIR):
        inst = tickets.instantiate(t, seed=7)
        inst.env                                   # raises on reserved names
        # Every {placeholder} in text the player sees must be a real param.
        texts = [t.title, t.narrative, t.mentor_intro or "", t.callback or "", *t.hints,
                 *[s.say for s in t.mentor_steps]]
        for text in texts:
            # ("${" is Bash, "{}" is find's -exec placeholder; both are fine.)
            rendered = inst.text(text).replace("${", "").replace("{}", "")
            assert "{" not in rendered, f"{t.id}: unfilled placeholder in {text[:60]!r}"
        assert t.script("break", "rhel") and t.script("grade", "rhel")
        assert t.script("solution", "rhel"), f"{t.id}: add a solution.sh for tests"


def test_folder_must_match_id(tmp_path):
    folder = tmp_path / "1" / "wrong-name"
    folder.mkdir(parents=True)
    (folder / "ticket.yaml").write_text(
        "id: right-name\ntitle: t\ntier: 1\nskill: s\ncharacter: c\n"
        "tracks: [rhel]\nnarrative: n\nrewards: {xp: 1, rep: 1}\n")
    (folder / "break.sh").write_text("")
    (folder / "grade.sh").write_text("")
    with pytest.raises(tickets.TicketError, match="folder name"):
        tickets.load_all(tmp_path)


def test_track_override_preferred(tmp_path):
    t = tickets.load_ticket(_ticket(tmp_path))
    (t.folder / "break.rhel.sh").write_bytes(b"echo rhel\r\n")   # a Windows-edited file
    assert t.script("break", "rhel") == "echo rhel\n"     # CRLF stripped too
    assert t.script("break", "suse") == "echo generic\n"


def _ticket(tmp_path):
    folder = tmp_path / "x"
    folder.mkdir()
    (folder / "ticket.yaml").write_text(
        "id: x\ntitle: t\ntier: 1\nskill: s\ncharacter: c\n"
        "tracks: [rhel, suse]\nnarrative: n\nrewards: {xp: 1, rep: 1}\n")
    (folder / "break.sh").write_text("echo generic\n")
    (folder / "grade.sh").write_text("")
    return folder / "ticket.yaml"


# ---- grader output ---------------------------------------------------------

def test_parse_grader_output():
    out = ('noise\n{"check": "a", "pass": true, "msg": "ok"}\n'
           '{"check": "b", "pass": false, "msg": "nope"}\n{broken json\n')
    r = parse_output(out, exit_status=1)
    assert not r.passed
    assert [(c.name, c.passed) for c in r.checks] == [("a", True), ("b", False)]


def test_exit_zero_but_failing_check_is_not_a_pass():
    r = parse_output('{"check": "b", "pass": false, "msg": ""}', exit_status=0)
    assert not r.passed
