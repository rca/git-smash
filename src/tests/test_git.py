import re

from unittest import TestCase, mock

from git_smash import git

from tests.utils import get_content


class BranchManagerTestCase(TestCase):
    def _get_manager(self, content=None):
        content = content or get_content('git-branch.txt')
        manager = git.BranchManager.from_git_output(content)

        return manager

    def test_from_git_output(self, *mocks):
        manager = self._get_manager()

        self.assertEquals(16, len(manager.branches))

    def test_get_matching_branches(self, *mocks):
        manager = self._get_manager()

        branches = manager.get_matching_branches(re.compile('master$'))

        self.assertEquals(4, len(branches))

    def test_get_best_branch_without_slash(self, *mocks):
        """Local master would be the preferred branch"""
        manager = self._get_manager()

        branches = manager.get_matching_branches(re.compile('master$'), best=True)

        self.assertEquals(1, len(branches))

        branch = branches[0]
        self.assertEqual('master', branch.name)

    def test_get_matching_branches_prefer_local(self, *mocks):
        manager = self._get_manager()

        branches = manager.get_matching_branches(re.compile(r'env/dev-fb-provider$'), best=True)

        self.assertEquals(1, len(branches), branches)

        branch = branches[0]
        self.assertEquals('env/dev-fb-provider', branch.name)

    def test_get_matching_branches_match_full_name(self, *mocks):
        """
        ensure a branch that has a similar name, but prefixed with something else (e.g. revert-) isn't preferred
        """
        manager = self._get_manager()

        branches = manager.get_matching_branches(re.compile(r'2168-w4-accessing-blockl$'), best=True)

        self.assertEquals(1, len(branches), branches)

        branch = branches[0]
        self.assertEquals('remotes/rca/2168-w4-accessing-blockl', branch.name)



class GitTestCase(TestCase):
    def test_get_simplified_merge_commits(self, *mocks):
        """
        Ensure the merge commits are properly simplified down
        """
        content = get_content('git-log.txt')

        commits = git.Commit.from_log(content)

        self.assertEquals(36, len(commits))

        simplified = git.get_simplified_merge_commits(commits)

        self.assertEquals(6, len(simplified))

    def test_get_merge_branch_name_from_message(self, *mocks):
        log = "b6c8143086e2f3b8b30d0adaf798f97c1b13b463 Merge branch 'feature/2168-w4-accessing-blockl' into env/dev-fb-provider"

        commit = git.Commit.from_log(log)[0]

        self.assertEquals('feature/2168-w4-accessing-blockl', commit.merge_branch)

    def test_get_merge_branch_name_from_remote_message(self, *mocks):
        log = "6a13d77b2df0a045f75c3d476bdc1b160ddfb4c7 Merge remote-tracking branch 'remotes/rca/feature/2168-w4-accessing-blockl' into smash/env/dev-fb-provider"

        commit = git.Commit.from_log(log)[0]

        self.assertEquals('remotes/rca/feature/2168-w4-accessing-blockl', commit.merge_branch)

    def test_get_merge_branch_name_from_pr(self, *mocks):
        log = "11e189e57d1e0bb24e67f94bdc17883d0cb94744 (master) Merge pull request #14 from rca/feature/add-staging-profile"

        commit = git.Commit.from_log(log)[0]

        self.assertEquals('rca/feature/add-staging-profile', commit.merge_branch)
