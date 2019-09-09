import functools
import re

from collections import OrderedDict
from typing import Iterable

from . import errors
from .utils import get_proc, run_command

GIT_COMMAND = 'git --no-pager'

GIT_BRANCH_COMMAND = f'{GIT_COMMAND} branch --no-color --all'
GIT_LOG_COMMAND = f'{GIT_COMMAND} log --no-decorate --no-color --pretty=oneline --merges'
GIT_MERGE_COMMAND = f'{GIT_COMMAND} merge --no-edit'

MERGE_MESSAGE_RE = re.compile((
    r'(?P<decoration>\(.*\) )?'
    r'('
    r'Merge (:?remote-tracking )?branch \'(?P<merge_branch>[^\']*)\'( of.*)? into (?P<target_branch>.*)' \
    r'|Merge pull request .*? from (?P<merge_branch2>.*)'
    r')'
))


class Branch:
    def __init__(self, name: str, current: bool = False):
        self.name = name
        self.current = current

    def __repr__(self):
        current = '*' if self.current else ''

        return f'<{self.__class__.__name__} {current}{self.name}>'

    def __str__(self):
        return str(self.name)


class BranchManager:
    def __init__(self):
        self.branches = []

    @property
    @functools.lru_cache()
    def current_branch(self):
        for item in self.branches:
            if item.current:
                return item
        else:
            raise errors.BranchError('Unable to find current branch')

    @classmethod
    def from_git_output(cls, content: str) -> 'BranchManager':
        manager = cls()

        for line in content.splitlines():
            current = line[0] == '*'
            manager.branches.append(Branch(line[2:], current=current))

        return manager

    def get_matching_branches(self, name: str, best: bool = False) -> Iterable:
        """
        Returns a list of remote branches that match the given name

        Args:
            name: the name of the branch to match
            best: when True, only the best matching branch is returned
        """
        matching = []

        for item in self.branches:
            # prefix with a slash to ensure that we are comparing the same branch name
            # in one case there's a branch named `remotes/origin/revert-204-bugfix/os-1088`
            # that was chosen over `remotes/rubberviscous/bugfix/os-1088` because of the missing `/` prefix
            if item.name.endswith(f'/{name}'):
                matching.append(item)

        if len(matching) < 2:
            return matching

        if best:
            for item in matching:
                if '/' not in item.name:
                    continue

                return [item]

        return matching

    def is_current(self, branch_name: str) -> bool:
        for branch in self.branches:
            if branch.name == branch_name:
                return branch.current

        return False


class Commit:
    def __init__(self, rev: str, message: str):
        self.rev = rev
        self.message = message

    def __repr__(self):
        return f'<{self.__class__.__name__} {self}>'

    def __str__(self):
        return f'{self.rev} {self.message}'

    @classmethod
    def from_log(cls, content: str) -> 'Commit':
        """
        Returns a Commit instance from the given log line

        Args:
            content: one or more log lines
        Return:
            list
        """
        commits = []

        for line in content.splitlines():
            rev, message = line.strip().split(' ', 1)

            commits.append(cls(rev, message))

        return commits

    @property
    def merge_branch(self):
        matches = MERGE_MESSAGE_RE.match(self.message)
        if matches:
            return matches.group('merge_branch') or matches.group('merge_branch2')
        else:
            print(f'could not parse {self.message}')


def get_branch_manager():
    return BranchManager.from_git_output(run_command(GIT_BRANCH_COMMAND))


def get_merge_commits(until: str):
    """
    Returns merge commits until the given revision is found
    """
    merge_commits = []

    git_log_command = f'{GIT_LOG_COMMAND} {until}..HEAD'
    get_proc(git_log_command, _out=functools.partial(process_merge_line, merge_commits))

    return merge_commits


def get_simplified_merge_commits(commits: Iterable[Commit]):
    commits_by_message = OrderedDict()

    for commit in commits:
        commits_by_message.setdefault(commit.merge_branch, commit)

    return commits_by_message.values()


def process_merge_line(commits, line, stdin, process):
    """
    Processes lines until the given commit is found
    """
    commits.append(Commit.from_log(line)[0])
