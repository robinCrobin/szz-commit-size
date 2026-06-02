import argparse
import json
import logging as log
import os
import signal
from time import time as ts

import dateparser
import yaml
from typing import Dict
from szz.ag_szz import AGSZZ
from szz.aszz.a_szz import ASZZ
from szz.b_szz import BaseSZZ
from szz.util.check_requirements import check_requirements
from szz.dfszz.df_szz import DFSZZ
from szz.l_szz import LSZZ
from szz.ma_szz import MASZZ, DetectLineMoved
from szz.r_szz import RSZZ
from szz.ra_szz import RASZZ
from szz.pd_szz import PyDrillerSZZ
from szz.common.issue_date import parse_issue_date
from pathlib import Path
import random

log.basicConfig(level=log.INFO, format='%(asctime)s :: %(funcName)s - %(levelname)s :: %(message)s')
log.getLogger('pydriller').setLevel(log.WARNING)


SAVE_EVERY = 10

# Timeout por fix (segundos). Se um unico fix travar (ex.: git blame patologico
# num commit gigante), o alarme dispara, o fix e' pulado e o run continua.
# Configure via env SZZ_FIX_TIMEOUT; 0 = desabilitado. So funciona em Unix
# (SIGALRM); no Windows e' ignorado silenciosamente.
FIX_TIMEOUT = int(os.environ.get("SZZ_FIX_TIMEOUT", "0"))
_HAS_ALARM = hasattr(signal, "SIGALRM")


class _FixTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _FixTimeout(f"fix excedeu SZZ_FIX_TIMEOUT={FIX_TIMEOUT}s")


if FIX_TIMEOUT > 0 and _HAS_ALARM:
    signal.signal(signal.SIGALRM, _alarm_handler)


def _make_szz(szz_name: str, repo_name: str, repo_url: str, repos_dir: str):
    if szz_name == 'b':
        return BaseSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'ag':
        return AGSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'ma':
        return MASZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'r':
        return RSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'l':
        return LSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'ra':
        return RASZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'pd':
        return PyDrillerSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'a':
        return ASZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    if szz_name == 'df':
        return DFSZZ(repo_full_name=repo_name, repo_url=repo_url, repos_dir=repos_dir)
    return None


def _run_one(szz_inst, szz_name: str, fix_commit: str, conf: Dict, issue_date):
    if szz_name == 'b':
        imp_files = szz_inst.get_impacted_files(fix_commit_hash=fix_commit, file_ext_to_parse=conf.get('file_ext_to_parse'), only_deleted_lines=True)
        return szz_inst.find_bic(fix_commit_hash=fix_commit,
                                 impacted_files=imp_files,
                                 issue_date_filter=conf.get('issue_date_filter'),
                                 issue_date=issue_date)
    if szz_name == 'ag':
        imp_files = szz_inst.get_impacted_files(fix_commit_hash=fix_commit, file_ext_to_parse=conf.get('file_ext_to_parse'), only_deleted_lines=True)
        return szz_inst.find_bic(fix_commit_hash=fix_commit,
                                 impacted_files=imp_files,
                                 max_change_size=conf.get('max_change_size'),
                                 issue_date_filter=conf.get('issue_date_filter'),
                                 issue_date=issue_date)
    if szz_name in ('ma', 'r', 'l', 'ra'):
        imp_files = szz_inst.get_impacted_files(fix_commit_hash=fix_commit, file_ext_to_parse=conf.get('file_ext_to_parse'), only_deleted_lines=True)
        return szz_inst.find_bic(fix_commit_hash=fix_commit,
                                 impacted_files=imp_files,
                                 max_change_size=conf.get('max_change_size'),
                                 detect_move_from_other_files=DetectLineMoved(conf.get('detect_move_from_other_files')),
                                 issue_date_filter=conf.get('issue_date_filter'),
                                 issue_date=issue_date,
                                 filter_revert_commits=conf.get('filter_revert_commits', False))
    if szz_name == 'pd':
        imp_files = szz_inst.get_impacted_files(fix_commit_hash=fix_commit, file_ext_to_parse=conf.get('file_ext_to_parse'), only_deleted_lines=True)
        return szz_inst.find_bic(fix_commit_hash=fix_commit,
                                 impacted_files=imp_files,
                                 issue_date_filter=conf.get('issue_date_filter'),
                                 issue_date=issue_date)
    if szz_name in ('a', 'df'):
        return szz_inst.start(fix_commit_hash=fix_commit, commit_issue_date=issue_date, **conf)
    log.info(f'SZZ implementation not found: {szz_name}')
    exit(-3)


def main(input_json: str, out_json: str, conf: Dict, repos_dir: str):
    with open(input_json, 'r') as in_file:
        bugfix_commits = json.loads(in_file.read())

    # Sort by repo so we can reuse the cloned repo across all fixes of the same repo.
    bugfix_commits.sort(key=lambda c: c['repo_name'])

    szz_name = conf['szz_name']
    tot = len(bugfix_commits)
    partial_path = out_json.replace('.json', '.partial.json')

    current_repo = None
    szz_inst = None

    try:
        for i, commit in enumerate(bugfix_commits):
            repo_name = commit['repo_name']
            repo_url = f'https://test:test@github.com/{repo_name}.git'
            fix_commit = commit['fix_commit_hash']

            if repo_name != current_repo:
                if szz_inst is not None:
                    del szz_inst
                    szz_inst = None
                current_repo = repo_name

            log.info(f'{i + 1} of {tot}: {repo_name} {fix_commit}')

            issue_date = None
            if conf.get('issue_date_filter', None):
                issue_date = parse_issue_date(commit)

            if szz_inst is None:
                try:
                    szz_inst = _make_szz(szz_name, repo_name, repo_url, repos_dir)
                except Exception as ex:
                    log.warning(f"SZZ init FAILED for repo {repo_name}: {type(ex).__name__}: {ex}")
                    bugfix_commits[i]["inducing_commit_hash"] = []
                    bugfix_commits[i]["szz_error"] = f"init: {type(ex).__name__}: {str(ex)[:200]}"
                    szz_inst = None
                    continue
                if szz_inst is None:
                    log.info(f'SZZ implementation not found: {szz_name}')
                    exit(-3)

            # Isola falhas por fix (ex.: GitCommandError em commits com paths invalidos
            # no NTFS, problemas de blame, etc). Sem isso, um unico fix problematico
            # mata o run inteiro — vide §7.5 de METODOLOGIA.md.
            try:
                if FIX_TIMEOUT > 0 and _HAS_ALARM:
                    signal.alarm(FIX_TIMEOUT)
                bug_inducing_commits = _run_one(szz_inst, szz_name, fix_commit, conf, issue_date) or set()
                log.info(f"result: {bug_inducing_commits}")
                bugfix_commits[i]["inducing_commit_hash"] = [bic.hexsha for bic in bug_inducing_commits if bic]
            except _FixTimeout as ex:
                log.warning(f"FIX TIMEOUT {repo_name} {fix_commit}: {ex}")
                bugfix_commits[i]["inducing_commit_hash"] = []
                bugfix_commits[i]["szz_error"] = f"timeout: {str(ex)[:200]}"
                # O blame foi interrompido no meio; o estado do git pode ter ficado
                # inconsistente. Descarta a instancia para o proximo fix recriar do zero.
                del szz_inst
                szz_inst = None
                current_repo = None
            except Exception as ex:
                log.warning(f"FIX SKIPPED {repo_name} {fix_commit}: {type(ex).__name__}: {str(ex)[:160]}")
                bugfix_commits[i]["inducing_commit_hash"] = []
                bugfix_commits[i]["szz_error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
            finally:
                if FIX_TIMEOUT > 0 and _HAS_ALARM:
                    signal.alarm(0)

            if (i + 1) % SAVE_EVERY == 0:
                with open(partial_path, 'w') as out:
                    json.dump(bugfix_commits, out)
                log.info(f"partial saved ({i + 1}/{tot}): {partial_path}")
    finally:
        if szz_inst is not None:
            del szz_inst

    if os.path.exists(out_json):
        out_json = out_json.replace('.json', f'.{random.randint(1, 99)}.json')
    with open(out_json, 'w') as out:
        json.dump(bugfix_commits, out)

    log.info(f"results saved in {out_json}")
    log.info("+++ DONE +++")


if __name__ == "__main__":
    # check_requirements()

    parser = argparse.ArgumentParser(description='USAGE: python main.py <bugfix_commits.json> <conf_file path> <repos_directory(optional)>\n* If <repos_directory> is not set, pyszz will download each repository')
    parser.add_argument('input_json', type=str, help='/path/to/bug-fixes.json')
    parser.add_argument('conf_file', type=str, help='/path/to/configuration-file.yml')
    parser.add_argument('repos_dir', type=str, nargs='?', help='/path/to/repo-directory')
    args = parser.parse_args()

    if not os.path.isfile(args.input_json):
        log.error('invalid input json')
        exit(-2)
    if not os.path.isfile(args.conf_file):
        log.error('invalid conf file')
        exit(-2)

    with open(args.conf_file, 'r') as f:
        conf = yaml.safe_load(f)

    log.info(f"parsed conf yml '{args.conf_file}': {conf}")
    szz_name = conf['szz_name']

    out_dir = 'out'
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    conf_file_name = Path(args.conf_file).name.split('.')[0]
    out_json = os.path.join(out_dir, f'bic_{conf_file_name}_{int(ts())}.json')

    if not szz_name:
        log.error('The configuration file does not define the SZZ name. Please, fix.')
        exit(-3)

    log.info(f'Launching {szz_name}-szz')

    main(args.input_json, out_json, conf, args.repos_dir)
