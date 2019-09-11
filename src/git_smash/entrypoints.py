import argparse
import logging
import re
import sh
import sys

from collections import OrderedDict

from . import git
from .utils import run_command

SH_ERROR_1 = getattr(sh, 'ErrorReturnCode_1')


def git_smash():
    parser = argparse.ArgumentParser()

    parser.add_argument('-l', '--loglevel', default='info', help='log level, default=info')
    parser.add_argument('--drop', action='append', help='drop the given branches')
    parser.add_argument('--reset-base', action='store_true', help='reset the branch to the base branch')
    parser.add_argument('action', help='the action to take')

    args = parser.parse_args()

    loglevel = getattr(logging, args.loglevel.upper())
    log_format = '%(levelname)s %(message)s'
    logging.basicConfig(level=loglevel, format=log_format)

    # drop sh logging
    logger = logging.getLogger('sh').setLevel(logging.WARNING)

    smash = Smash(args)

    fn = getattr(smash, args.action, None)
    if not fn:
        sys.exit(f'ERROR: action {args.action} not defined')

    sys.exit(fn())


class Smash:
    def __init__(self, args, base_branch: str = 'origin/master'):
        self.args = args
        self.base_branch = base_branch

    def apply_branch(self, branch, merge_commit=None):
        """Attempt to merge the found branch,  name or fallback to the merge commit"""
        for action in ('merge_branch', 'merge_merge'):
            if action == 'merge_branch':
                with git.temp_branch(merge_commit.merge_branch, branch.commit) as _branch:
                    self.logger.info(f'merging {_branch.name}')
                    try:
                        run_command(f'{git.GIT_MERGE_COMMAND} {_branch.name}')
                    except SH_ERROR_1 as exc:
                        self.logger.warning(f'merging {_branch} failed')
                        run_command('git reset --hard')
                    else:
                        break
            elif action == 'merge_merge':
                self.logger.warning(f'attempting to merge the merge commit')

                with git.temp_branch(merge_commit.merge_branch, merge_commit) as merge_branch:
                    try:
                        run_command(f'{git.GIT_MERGE_COMMAND} {merge_branch.name}')
                    except SH_ERROR_1 as exc:
                        self.logger.error(f'could not merge {merge_branch} automatically.  launching a subshell so you can resove the conflict')
                        self.logger.error(f'once the conflict is resolved exit the shell')

                        sh.bash('-i', _fg=True)

    @property
    def base_rev(self) -> str:
        """Returns the revison that is common with origin/master"""
        return run_command(f'git merge-base HEAD {self.base_branch}')

    def clean(self):
        """
        Remove all smash/ branches
        """
        branch_manager = git.get_branch_manager()

        for branch in branch_manager.get_matching_branches(re.compile(fr'^smash/')):
            self.logger.info(f'remove {branch.info}')

            run_command(f'git branch -D {branch.name}')

    @property
    def logger(self):
        return logging.getLogger(f'{__name__}.{self.__class__.__name__}')

    def get_merges(self, simplify: bool = True) -> list:
        self.logger.info(f'looking for merge commits until {self.base_rev}')

        merges = git.get_merge_commits(self.base_rev, drop=self.args.drop)
        self.logger.debug('all merges:')
        for merge in merges:
            self.logger.debug(f'\t{merge}')

        if simplify:
            merges = git.get_simplified_merge_commits(merges)

        return merges

    def list(self):
        merges = self.get_merges()

        self.logger.info('merges:')

        for merge in merges:
            self.logger.info(f'\t{merge}')

    @property
    def master_rev(self):
        """Returns the master revison"""
        return run_command(f'git rev-list {self.base_branch} --max-count 1')

    def replay(self):
        on_base = self.base_rev == self.master_rev
        if not on_base:
            # TODO: rebase on base branch based on optional arg
            self.logger.warning(f'this branch is not on top of {self.base_branch}')

        self.logger.info('find merge commits:')

        commits = self.get_merges()

        branch_manager = git.get_branch_manager()
        current_branch = branch_manager.current_branch

        branches_to_merge = []

        for commit in commits:
            # skip trying to merge the current branch
            if commit.merge_branch == current_branch.name:
                self.logger.info(f'{commit.merge_branch} merging self; skipping')

                continue

            branches = branch_manager.get_matching_branches(re.compile(fr'{commit.merge_branch}$'), best=True)
            if not branches:
                branch = git.Branch(commit.merge_branch, commit=git.Commit(commit.merge_rhs, None))

                self.logger.warning(f'cannot find commit on any remote, making a temp branch: {branch}')

                branches.append(branch)

            branches_to_merge.append((commit, branches[0]))

        # apply the branches backwards
        branches_to_merge.reverse()

        branches_s = '\n\t'.join([x.info for _, x in branches_to_merge])
        self.logger.info(f'branches to merge:\n\t{branches_s}')

        backup_branch = f'smash/{current_branch}'
        self.logger.info(f'backing up current branch to {backup_branch}')

        run_command(f'git checkout -b {backup_branch}')

        base = self.base_branch

        self.logger.info(f'resetting to {base}')

        run_command(f'git checkout -')
        run_command(f'git reset --hard {base}')

        for commit, branch in branches_to_merge:
            # get the entire commit history and see if the rev about to be merged
            # is already in the history
            branch_commits = run_command(f'git rev-list HEAD').splitlines()
            rev = branch.commit.rev

            # print(f'branch={branch}, rev={rev}, {len(branch_commits)} branch_commits={branch_commits}')

            if rev in branch_commits:
                self.logger.info(f'rev={rev} from {branch} already in commit history, skipping')

                continue

            self.apply_branch(branch, merge_commit=commit)
