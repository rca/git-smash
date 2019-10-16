import logging
import re
from typing import List

import sh

from . import git
from .utils import (
    SH_ERROR_1,
    run_command,
    run_command_with_interactive_fallback,
    run_interactive_shell,
)


class Smash:
    def __init__(
        self,
        clean_backups: bool = True,
        drop_branches: List[str] = None,
        push: bool = False,
        base_branch: str = "origin/master",
    ):
        self.base_branch_name = base_branch
        self.clean_backups = clean_backups
        self.drop_branches = drop_branches
        self.push = push  # whether to push upstream

    def apply_branch(self, branch, merge_commit=None):
        """Attempt to merge the found branch,  name or fallback to the merge commit"""
        for idx, action in enumerate(("merge_branch", "merge_merge", "merge_branch")):
            # get the entire commit history and see if the rev about to be merged
            # is already in the history
            branch_commits = run_command(f"git rev-list HEAD").splitlines()

            rev = branch.commit.rev
            if rev in branch_commits:
                if idx == 0:
                    self.logger.info(
                        f"rev={rev} from {branch} already in commit history, skipping"
                    )

                break

            if action == "merge_branch":
                with git.temp_branch(
                    merge_commit.merge_branch, branch.commit
                ) as _branch:
                    self.logger.info(f"merging {_branch.info}")
                    try:
                        run_command(f"{git.GIT_MERGE_COMMAND} {_branch}")
                    except SH_ERROR_1 as exc:
                        self.logger.warning(f"merging {_branch.info} failed")

                        if idx == 0:
                            run_command("git reset --hard")
                        else:
                            run_interactive_shell(
                                "launching a subshell.  fix the conflict, but do not commit.  exit when done"
                            )

                            run_command(f"{git.GIT_COMMAND} add --all")
                            run_command(git.GIT_COMMIT_COMMAND)
                    else:
                        break
            elif action == "merge_merge":
                with git.temp_branch(
                    merge_commit.merge_branch, merge_commit
                ) as merge_branch:
                    self.logger.info(f"merging the merge commit: {merge_branch.info}")

                    run_command_with_interactive_fallback(
                        f"{git.GIT_MERGE_COMMAND} {merge_branch}",
                        message="launching a subshell so you can resove the conflict",
                    )
            elif action == "cherry_pick_local":
                # perform a cherry pick on the
                self.logger.info(f"cherry picking after merging merge")

                run_command_with_interactive_fallback(
                    f"{git.GIT_CHERRY_PICK_COMMAND} {merge_branch}",
                    message="launching a subshell so you can resove the conflict",
                )

                run_command(f"{git.GIT_COMMIT_AMEND_COMMAND}")

    @property
    def base_rev(self) -> str:
        """Returns the revison that is common with origin/master"""
        return run_command(f"git merge-base HEAD {self.base_branch_name}")

    def clean(self):
        """
        Remove all smash/ branches
        """
        branch_manager = git.get_branch_manager()

        for branch in branch_manager.get_matching_branches(re.compile(fr"^smash/")):
            self.logger.info(f"remove {branch.info}")

            run_command(f"git branch -D {branch.name}")

    @property
    def logger(self):
        return logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_merges(self, simplify: bool = True) -> list:
        self.logger.info(f"looking for merge commits until {self.base_rev}")

        merges = git.get_merge_commits(self.base_rev, drop=self.drop_branches)
        self.logger.debug("all merges:")
        for merge in merges:
            self.logger.debug(f"\t{merge}")

        if simplify:
            merges = git.get_simplified_merge_commits(merges)

        return merges

    def list(self):
        merges = self.get_merges()

        self.logger.info("merges:")

        for merge in merges:
            self.logger.info(f"\t{merge}")

    @property
    def master_rev(self):
        """Returns the master revison"""
        return run_command(f"git rev-list {self.base_branch_name} --max-count 1")

    def replay(self):
        on_base = self.base_rev == self.master_rev
        if not on_base:
            # TODO: rebase on base branch based on optional arg
            self.logger.warning(f"this branch is not on top of {self.base_branch_name}")

        self.logger.info("find merge commits:")

        commits = self.get_merges()

        branch_manager = git.get_branch_manager()
        current_branch = branch_manager.get_current_branch()

        branches_to_merge = []

        for commit in commits:
            # skip trying to merge the current branch
            if commit.merge_branch == current_branch.name:
                self.logger.info(f"{commit.merge_branch} merging self; skipping")

                continue

            branches = branch_manager.get_matching_branches(
                re.compile(fr"{commit.merge_branch}$"), best=True
            )
            if not branches:
                branch = git.Branch(
                    commit.merge_branch, commit=git.Commit(commit.merge_rhs, None)
                )

                self.logger.warning(
                    f"cannot find commit on any remote, making a temp branch: {branch}"
                )

                branches.append(branch)

            branches_to_merge.append((commit, branches[0]))

        # apply the branches backwards
        branches_to_merge.reverse()

        branches_s = "\n\t".join([x.info for _, x in branches_to_merge])
        self.logger.info(f"branches to merge:\n\t{branches_s}")

        backup_branch = f"smash/{current_branch}"

        clean = None
        for i in range(2):
            if not clean:  # write this just once
                self.logger.info(f"backing up current branch to {backup_branch}")

            try:
                run_command(f"git checkout -b {backup_branch}")
            except sh.ErrorReturnCode_128:
                branch = branch_manager.get_branch(backup_branch)

                clean = self.clean_backups
                if not clean:
                    var = input(
                        f"{branch.info} already exists; remove it? [Y|n]: "
                    ).strip()
                    clean = var.lower() in ("", "y")

                if clean:
                    self.clean()
                else:
                    raise
            else:
                # switch back out of backup_branch
                run_command(f"git checkout -")

                break

        base = git.Branch(self.base_branch_name)

        current_branch = branch_manager.get_current_branch()
        self.logger.info(f"resetting {current_branch} to {base.info}")

        run_command(f"git reset --hard {base}")

        for commit, branch in branches_to_merge:
            self.apply_branch(branch, merge_commit=commit)
