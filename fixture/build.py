"""Builds the benchmark's fixture: Netflix Dispatch with planted changes in its history.

The last `replay_depth` upstream commits are replayed on top of their base, and
each plant is committed right after the upstream commit named in its `after`
field, so the planted changes sit inside a real history instead of on top of it.
Replayed commits keep their author, committer and dates, so the build is
deterministic: the same inputs always give the same commit ids.

Usage: python3 -I fixture/build.py [--cache DIR] [--out DIR]
Writes OUT/fixture.git (bare, branch main) and OUT/plants.json (plant id -> commit).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def git(*args, cwd=None, env=None, capture=True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=capture, text=True
    )
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip() if capture else ""


def identity_env(name, email, date):
    """Upstream lands every pull request as a squash merge committed by GitHub; plants do too."""
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_AUTHOR_DATE=date,
        GIT_COMMITTER_NAME="GitHub", GIT_COMMITTER_EMAIL="noreply@github.com", GIT_COMMITTER_DATE=date,
    )
    return env


def committer_env(work, commit):
    name, email, date = git("log", "-1", "--format=%cn%x00%ce%x00%cI", commit, cwd=work).split("\0")
    env = dict(os.environ)
    env.update(GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email, GIT_COMMITTER_DATE=date)
    return env


def fetch_upstream(spec, cache):
    mirror = cache / "dispatch.git"
    if not mirror.exists():
        cache.mkdir(parents=True, exist_ok=True)
        git("clone", "--quiet", "--bare", spec["upstream"], str(mirror))
    if subprocess.run(["git", "-C", str(mirror), "cat-file", "-e", spec["head"]]).returncode != 0:
        git("fetch", "--quiet", "origin", cwd=mirror)
    return mirror


def plant(work, p):
    patch = HERE / "plants" / f"{p['id']}.patch"
    git("apply", "--3way", "--index", str(patch), cwd=work)
    name, email = p["author"][:-1].split(" <")
    git("commit", "--quiet", "-m", p["message"], cwd=work,
        env=identity_env(name, email, p["date"]))
    return git("rev-parse", "HEAD", cwd=work)


def expected_tree(mirror, spec, scratch):
    """The tree upstream head would have with every plant applied, built independently."""
    if scratch.exists():
        shutil.rmtree(scratch)
    git("clone", "--quiet", "--shared", str(mirror), str(scratch))
    git("checkout", "--quiet", spec["head"], cwd=scratch)
    for p in spec["plants"]:
        git("apply", "--3way", "--index", str(HERE / "plants" / f"{p['id']}.patch"), cwd=scratch)
    return git("write-tree", cwd=scratch)


def build(spec, cache, out):
    mirror = fetch_upstream(spec, cache)
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    git("clone", "--quiet", "--no-checkout", str(mirror), str(work))
    git("config", "user.name", "fixture-build", cwd=work)
    git("config", "user.email", "fixture-build@invalid", cwd=work)

    base = git("rev-parse", f"{spec['head']}~{spec['replay_depth']}", cwd=work)
    git("checkout", "--quiet", "-B", "main", base, cwd=work)
    replay = git("rev-list", "--reverse", "--first-parent", f"{base}..{spec['head']}", cwd=work).split()

    after = {p["after"]: p for p in spec["plants"]}
    missing = set(after) - set(replay)
    if missing:
        sys.exit(f"plants anchored outside the replayed range: {sorted(missing)}")

    planted = {}
    for commit in replay:
        git("cherry-pick", "--quiet", "--allow-empty", "--keep-redundant-commits", commit,
            cwd=work, env=committer_env(work, commit))
        if commit in after:
            p = after[commit]
            planted[p["id"]] = plant(work, p)

    tree = git("rev-parse", "HEAD^{tree}", cwd=work)
    want = expected_tree(mirror, spec, out / "check")
    shutil.rmtree(out / "check")
    if tree != want:
        sys.exit(f"fixture tree {tree} differs from upstream head + plants {want}")

    # Only main and the tags already in its history leave the build.
    git("remote", "remove", "origin", cwd=work)
    for tag in git("tag", "--no-merged", "main", cwd=work).split():
        git("tag", "-d", tag, cwd=work)
    bare = out / "fixture.git"
    if bare.exists():
        shutil.rmtree(bare)
    git("clone", "--quiet", "--bare", "--no-local", str(work), str(bare))
    git("remote", "remove", "origin", cwd=bare)
    shutil.rmtree(work)

    head = git("rev-parse", "main", cwd=bare)
    (out / "plants.json").write_text(json.dumps({"head": head, "plants": planted}, indent=2) + "\n")
    print(f"fixture {head} ({len(replay)} replayed commits, {len(planted)} plants) -> {bare}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "sobre-bench")
    parser.add_argument("--out", type=Path, default=HERE.parent / "build")
    args = parser.parse_args()
    spec = json.loads((HERE / "plants.json").read_text())
    build(spec, args.cache, args.out.resolve())


if __name__ == "__main__":
    main()
