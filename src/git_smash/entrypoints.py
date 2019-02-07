import sh

from collections import OrderedDict

from . import git
from .utils import run_command

SH_ERROR_1 = getattr(sh, 'ErrorReturnCode_1')


def git_smash(base_branch: str = 'origin/master'):
    # get the revison that is common with origin/master
    base_rev = run_command(f'git merge-base HEAD {base_branch}')

    # get the master revison
    master_rev = run_command(f'git rev-list {base_branch} --max-count 1')

    if base_rev != master_rev:
        # TODO: rebase on base branch based on optional arg
        print(f'WARNING: this branch is not on top of {base_branch}')

    print(f'looking for merge commits until {base_rev}')

    merge_commits = git.get_merge_commits(base_rev)

    for commit in merge_commits:
        print(commit)

    print('\n\nsimplify merges\n\n')

    simplified = git.get_simplified_merge_commits(merge_commits)

    for commit in simplified:
        print(commit)

    print('\n\nfind current commits\n\n')

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
            print(f'skipping {commit}, no remote branch found')
            continue

        branches_to_merge.append(branches[0])

    # apply the branches backwards
    branches_to_merge.reverse()

    print(f'branches_to_merge={branches_to_merge}')

    run_command(f'git checkout -b smash/{current_branch} {base_branch}')

    for branch in branches_to_merge:
        try:
            run_command(f'{git.GIT_MERGE_COMMAND} {branch.name}')
        except SH_ERROR_1 as exc:
            print(f'could not merge {branch} automatically.  launching a subshell so you can resove the conflict')
            print(f'once the conflict is resolved exit the shell')

            sh.bash('-i', _fg=True)
