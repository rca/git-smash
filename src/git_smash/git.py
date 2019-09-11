import functools
import logging
import re
import typing

from collections import OrderedDict
from contextlib import contextmanager
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

if typing.TYPE_CHECKING:
    REGEX = type(re.compile('x'))


class Branch:
    def __init__(self, name: str, current: bool = False, commit: 'Commit' = None):
        self.name = name
        self.current = current

        self._commit = commit

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.info}>'

    def __str__(self):
        return str(self.name)

    def checkout(self):
        run_command(f'git checkout {self.name}')

        self.current = True

    @property
    def commit(self):
        """Returns the commit for this branch"""
        if self._commit:
            return self._commit

        return Commit(run_command(f'git rev-list {self.name} --max-count 1').strip(), None)

    @classmethod
    def create(cls, name, rev):
        run_command(f'git checkout -b {name} {rev}')
        run_command('git checkout -')

        return cls(name)

    def delete(self):
        run_command(f'git branch -D {self.name}')

    @property
    def info(self):
        current = '*' if self.current else ''

        return f'{self.commit} @ {current}{self.name}'

    def reset_to(self, commit):
        """Reset the branch to the given commit"""
        self.switch(self.name)
        run_command(f'git reset --hard {commit.rev}')
        self.switch('-')

    @classmethod
    def switch(cls, name: str):
        """Switch to the given branch"""
        branch = cls(name)

        branch.checkout()

        return branch


class BranchManager:
    def __init__(self):
        self.branches = []

    @property
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

    def get_branch(self, name: str):
        return self.get_matching_branches(re.compile('^master$'), best=True)[0]

    def get_matching_branches(self, regex: 'REGEX', best: bool = False) -> Iterable:
        """
        Returns a list of remote branches that match the given name

        Args:
            regex: a regular expression for the pattern to look for
            best: when True, only the best matching branch is returned
        """
        matching = []

        for item in self.branches:
            # prefix with a slash to ensure that we are comparing the same branch name
            # in one case there's a branch named `remotes/origin/revert-204-bugfix/os-1088`
            # that was chosen over `remotes/rubberviscous/bugfix/os-1088` because of the missing `/` prefix
            if regex.search(item.name):
                matching.append(item)

        if len(matching) < 2:
            return matching

        if best:
            branch_len = 1e6  # there's no name a million chars long
            best_branch = None
            for item in matching:
                _len = len(item.name)
                if _len < branch_len:
                    branch_len = _len
                    best_branch = item

            return [best_branch]

        # when best is selected, make sure at most one result is being returned
        if best:
            assert len(matching) < 2, f'{len(matching)}: {matching}'

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
        message = f' {self.message}' if self.message else ''

        return f'{self.rev}{message}'

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

    @property
    def merge_commits(self):
        return run_command(f'{GIT_LOG_COMMAND} --pretty=%P -n 1 {self.rev}').split()

    @property
    def merge_lhs(self):
        return self.merge_commits[0]

    @property
    def merge_rhs(self):
        return self.merge_commits[-1]


def create_branch(name: str, rev: str) -> Branch:
    return Branch.create(name, rev)


def get_branch_manager():
    return BranchManager.from_git_output(run_command(GIT_BRANCH_COMMAND))


def get_merge_commits(until: str, drop: Iterable[str] = None, loglevel: str = 'debug') -> list:
    """
    Returns merge commits until the given revision is found
    """
    logger = logging.getLogger(f'{__name__}')
    logger_fn = getattr(logger, loglevel)

    merge_commits_t = []

    git_log_command = f'{GIT_LOG_COMMAND} {until}..HEAD'
    get_proc(git_log_command, _out=functools.partial(process_merge_line, merge_commits_t))

    drop = drop or []
    merge_commits = []
    for commit in merge_commits_t:
        if commit.merge_branch in drop:
            logger_fn(f'dropping {commit}')
            continue

        logger_fn(f'found {commit.merge_branch} @ {commit.rev}')
        merge_commits.append(commit)

    return merge_commits


def get_simplified_merge_commits(commits: Iterable[Commit], loglevel: str = 'debug'):
    logger = logging.getLogger(f'{__name__}')
    logger_fn = getattr(logger, loglevel)

    commits_by_message = OrderedDict()

    for commit in commits:
        branch_name = commit.merge_branch
        if branch_name not in commits_by_message:
            logger_fn(f'add branch_name={branch_name} @ {commit.rev}')

            commits_by_message[branch_name] = commit

    return commits_by_message.values()


def process_merge_line(commits, line, stdin, process):
    """
    Processes lines until the given commit is found
    """
    commits.append(Commit.from_log(line)[0])


@contextmanager
def temp_branch(name, commit):
    """Sets the branch to the given commit hash

    Will reset the branch back to its original commit if it existed or remove it when done
    """
    logger = logging.getLogger(__name__)

    branch_manager = get_branch_manager()
    current_branch = branch_manager.current_branch
    original_commit = None

    try:
        branch = Branch.switch(name)
    except sh.ErrorReturnCode:  # branch does not exist
        branch = Branch.create(name, commit.rev)

        logger.debug(f'created {branch}')
    else:
        original_commit = branch.commit
        branch.reset_to(commit)

        logger.debug(f'switched to {branch}, original_commit={original_commit}')

    current_branch.checkout()

    try:
        yield branch
    finally:
        if original_commit:
            logger.debug(f'resetting to {original_commit}')

            branch.reset_to(original_commit)
        else:
            logger.debug(f'remove {branch}')

            original_branch.checkout()
            branch.delete()
