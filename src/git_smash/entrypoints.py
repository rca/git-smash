import argparse
import sh
import sys

from collections import OrderedDict

from . import git
from .utils import run_command

SH_ERROR_1 = getattr(sh, 'ErrorReturnCode_1')


def git_smash():
    parser = argparse.ArgumentParser()

    parser.add_argument('--reset-base', action='store_true', help='reset the branch to the base branch')
    parser.add_argument('action', help='the action to take')

    args = parser.parse_args()

    smash = Smash(args)

    fn = getattr(smash, args.action, None)
    if not fn:
        sys.exit(f'ERROR: action {args.action} not defined')

    sys.exit(fn())


class Smash:
    def __init__(self, args, base_branch: str = 'origin/master'):
        self.args = args
        self.base_branch = base_branch

    @property
    def base_rev(self) -> str:
        """Returns the revison that is common with origin/master"""
        return run_command(f'git merge-base HEAD {self.base_branch}')

    def get_merges(self, simplify: bool = True) -> list:
        print(f'looking for merge commits until {self.base_rev}')

        merge_commits = git.get_merge_commits(self.base_rev)

        for commit in merge_commits:
            print(commit)

        if not simplify:
            return merge_commits

        print('\n\nsimplify merges\n\n')

        simplified = git.get_simplified_merge_commits(merge_commits)

        # for commit in simplified:
        #     print(commit)
        #
        return simplified

    def list(self):
        self.get_merges()

    @property
    def master_rev(self):
        """Returns the master revison"""
        return run_command(f'git rev-list {self.base_branch} --max-count 1')

    def simplify(self):
        on_base = self.base_rev == self.master_rev
        if not on_base:
            # TODO: rebase on base branch based on optional arg
            print(f'WARNING: this branch is not on top of {self.base_branch}')

        simplified = self.get_merges()

        print('\n\nfind current commits...')

        branch_manager = git.get_branch_manager()

        current_branch = branch_manager.current_branch

        branches_to_merge = []

        for commit in simplified:
            if commit.merge_branch == current_branch.name:
                print(f'{commit.merge_branch} merging self; skipping')

                continue

            branches = branch_manager.get_matching_branches(commit.merge_branch, best=True)
            assert len(branches) < 2

            if not branches:
                print(f'WARNING: Cannot find commit on any remote, making a temp branch: {commit}')

                branches.append(git.create_branch(f'smash/{commit.merge_branch}', commit.merge_rhs))

            branches_to_merge.append(branches[0])

        # apply the branches backwards
        branches_to_merge.reverse()

        branches_s = '\n'.join([str(x) for x in branches_to_merge])
        print(f'\n\nbranches to merge\n\n{branches_s}')

        base = self.base_branch

        run_command(f'git checkout -b smash/{current_branch} {base}')

        for branch in branches_to_merge:
            try:
                print(f'merging {branch.name} ...')
                run_command(f'{git.GIT_MERGE_COMMAND} {branch.name}')
            except SH_ERROR_1 as exc:
                print(f'could not merge {branch} automatically.  launching a subshell so you can resove the conflict')
                print(f'once the conflict is resolved exit the shell')

                sh.bash('-i', _fg=True)
