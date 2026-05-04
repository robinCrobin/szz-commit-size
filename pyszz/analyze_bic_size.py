"""
Classify BICs by commit size and answer:
  A. Among the BICs found by SZZ, what fraction are "large" vs "small"?
  B. Among ALL commits of the analyzed repos, what is the BIC rate
     for "large" vs "small" commits? (the causal-style question)

"Large" is defined as: > THRESH_FILES files modified AND > THRESH_LINES lines changed
(both have to hold). Pass --or to flip to OR semantics.

Lines changed = additions + deletions across all modifications in the commit.
Merge commits and commits with zero modifications are skipped.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

from pydriller import RepositoryMining

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


THRESH_FILES = 5
THRESH_LINES = 125


def commit_size(commit):
    files = 0
    lines = 0
    for m in commit.modifications:
        files += 1
        lines += (m.added or 0) + (m.removed or 0)
    return files, lines


def is_large(files: int, lines: int, mode: str) -> bool:
    if mode == 'and':
        return files > THRESH_FILES and lines > THRESH_LINES
    return files > THRESH_FILES or lines > THRESH_LINES


def measure_commits(repo_path, commit_hashes=None, log_every=2000):
    """Iterate commits in repo_path with PyDriller. If commit_hashes is given,
    return only the requested ones; otherwise return every non-merge, non-empty commit.
    Yields (hash, files, lines)."""
    target = set(commit_hashes) if commit_hashes else None
    seen = 0
    for commit in RepositoryMining(repo_path).traverse_commits():
        if commit.merge:
            continue
        if target is not None and commit.hash not in target:
            continue
        try:
            files, lines = commit_size(commit)
        except Exception as e:
            print(f'  warn: could not measure {commit.hash[:10]}: {e}', file=sys.stderr)
            continue
        if files == 0:
            continue
        seen += 1
        if seen % log_every == 0:
            print(f'  ... measured {seen} commits', file=sys.stderr)
        yield commit.hash, files, lines


def analysis_a(bic_json_path, repos_dir, mode):
    print('=' * 70)
    print('ANALYSIS A: distribution of BICs by size class')
    print('=' * 70)

    data = json.load(open(bic_json_path))

    # Map repo -> set of BIC hashes returned by SZZ
    bics_per_repo = defaultdict(set)
    for fix in data:
        for h in (fix.get('inducing_commit_hash') or []):
            bics_per_repo[fix['repo_name']].add(h)

    measurements = {}  # (repo, hash) -> (files, lines)
    for repo_name, hashes in bics_per_repo.items():
        repo_path = os.path.join(repos_dir, repo_name)
        if not os.path.isdir(repo_path):
            print(f'WARN: repo not found, skipping: {repo_path}', file=sys.stderr)
            continue
        print(f'measuring {len(hashes)} BICs in {repo_name} ...')
        for h, files, lines in measure_commits(repo_path, commit_hashes=hashes):
            measurements[(repo_name, h)] = (files, lines)

    # Aggregate
    total = len(measurements)
    if total == 0:
        print('no BICs measured (no repos accessible?)')
        return measurements

    large = sum(1 for f, l in measurements.values() if is_large(f, l, mode))
    small = total - large

    files_all = sorted(f for f, _ in measurements.values())
    lines_all = sorted(l for _, l in measurements.values())

    def median(xs):
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    print()
    print(f'BICs únicos medidos: {total}')
    print(f'  grandes ({mode} mode, >{THRESH_FILES} arquivos & >{THRESH_LINES} linhas): {large} ({100*large/total:.1f}%)')
    print(f'  pequenos:                                                                  {small} ({100*small/total:.1f}%)')
    print()
    print(f'arquivos modificados | mediana={median(files_all)} | min={files_all[0]} | max={files_all[-1]}')
    print(f'linhas alteradas     | mediana={median(lines_all)} | min={lines_all[0]} | max={lines_all[-1]}')
    print()
    print('Por repo:')
    by_repo = defaultdict(lambda: [0, 0])
    for (r, _), (f, l) in measurements.items():
        by_repo[r][0] += 1
        if is_large(f, l, mode):
            by_repo[r][1] += 1
    for r, (tot, lg) in sorted(by_repo.items()):
        pct = 100 * lg / tot if tot else 0
        print(f'  {r:<35} {lg:>4}/{tot:<4} grandes ({pct:.1f}%)')
    print()

    return measurements


def analysis_b(bic_json_path, repos_dir, mode, measurements_a):
    print('=' * 70)
    print('ANALYSIS B: BIC rate among ALL commits, by size class')
    print('=' * 70)

    data = json.load(open(bic_json_path))

    # repo -> set of BIC hashes
    bics_per_repo = defaultdict(set)
    for fix in data:
        for h in (fix.get('inducing_commit_hash') or []):
            bics_per_repo[fix['repo_name']].add(h)

    # 2x2 contingency: rows = size class, cols = bic-or-not
    overall = {'large_bic': 0, 'large_clean': 0, 'small_bic': 0, 'small_clean': 0}
    per_repo_stats = {}

    for repo_name, bic_set in bics_per_repo.items():
        repo_path = os.path.join(repos_dir, repo_name)
        if not os.path.isdir(repo_path):
            print(f'WARN: repo not found, skipping: {repo_path}', file=sys.stderr)
            continue
        print(f'enumerating ALL commits in {repo_name} ...')
        counts = {'large_bic': 0, 'large_clean': 0, 'small_bic': 0, 'small_clean': 0}
        for h, files, lines in measure_commits(repo_path):
            large = is_large(files, lines, mode)
            is_bic = h in bic_set
            key = ('large_' if large else 'small_') + ('bic' if is_bic else 'clean')
            counts[key] += 1
        per_repo_stats[repo_name] = counts
        for k, v in counts.items():
            overall[k] += v

    def report(label, c):
        large_total = c['large_bic'] + c['large_clean']
        small_total = c['small_bic'] + c['small_clean']
        large_rate = c['large_bic'] / large_total if large_total else 0
        small_rate = c['small_bic'] / small_total if small_total else 0
        rr = (large_rate / small_rate) if small_rate else float('inf')
        print(f'\n[{label}]')
        print(f'  Grande:  {c["large_bic"]:>5} BIC / {large_total:<6} total  -> taxa = {100*large_rate:.2f}%')
        print(f'  Pequeno: {c["small_bic"]:>5} BIC / {small_total:<6} total  -> taxa = {100*small_rate:.2f}%')
        if small_rate > 0:
            print(f'  Risk ratio (grande / pequeno): {rr:.2f}x')
        else:
            print(f'  Risk ratio: indefinido (zero BIC entre os pequenos)')

    print()
    for r, c in sorted(per_repo_stats.items()):
        report(r, c)
    report('AGREGADO', overall)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bic_json', help='SZZ output JSON (out/bic_*.json)')
    ap.add_argument('repos_dir', help='directory containing the local repos used by SZZ')
    ap.add_argument('--or', dest='mode', action='store_const', const='or', default='and',
                    help='use OR semantics for "large" (default: AND)')
    ap.add_argument('--skip-b', action='store_true', help='skip the expensive Analysis B')
    args = ap.parse_args()

    if not os.path.isfile(args.bic_json):
        print(f'ERROR: bic_json not found: {args.bic_json}', file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.repos_dir):
        print(f'ERROR: repos_dir not found: {args.repos_dir}', file=sys.stderr)
        sys.exit(1)

    print(f'thresholds: files > {THRESH_FILES}, lines > {THRESH_LINES} (mode={args.mode})')
    print(f'input: {args.bic_json}')
    print(f'repos: {args.repos_dir}')
    print()

    measurements = analysis_a(args.bic_json, args.repos_dir, args.mode)

    if not args.skip_b:
        analysis_b(args.bic_json, args.repos_dir, args.mode, measurements)


if __name__ == '__main__':
    main()
