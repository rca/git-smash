# Git Smash

A command line tool to manage smashing multiple feature branches into an ephemeral throw-away branch.


## What?

Having a single source of truth is nice.  In Version Control, that's the main branch; `master` in Git parlance.  When making a change, those changes are implemented in a "feature branch", maybe something like `feature/public-access`.

When working on a team, there are multiple devlopers typically working on different features.  For instance, while one dev is working on the public access feature, another is working on some other task, like `bugfix/cant-see-profile`.

Things start to get tricky when multiple developers need to use a shared resource, such as a development environment that the entire team can access.  Since these are features in development, the branches themselves are still in flux.  But they still need to be put somewhere to deploy.  This can be an ephemeral branch, say `env/dev` that itself never gets merged into master, but is simply the placeholder -- the mixing pot -- to deploy and verify multiple changes simultaneously.  Once feature branches are approved and merged into `master`, devs also need a way to clean out this branch, as well as bringing it up to date with the new `master` without adversely affecting what other devs may have put in that branch.

This is what `git-smash` is intended to help with.


## The one rule: No Fast Forward

In ephemeral branches like `env/dev`, features are to always be merged in with `git merge --no-ff`* .  This is because `git-smash` has to have some way to find what has been merged in; it uses the merge commits for this purpose.

\* and in my opinion merges should always drop a merge node; if you aren't looking for a merge node, don't merge, that's what `rebase` is for.


## An example

Here is some broken down output of a development branch when running `git-smash -l debug list` (debug to see what's going on under the hood):

Run the program:

```
[0][~/Projects/work/repo(env/dev:957eacf6:1)]
[berto:env@berto]$ git-smash list -l debug
```

Start getting output; it detected the common branch between `origin/master` and the current branch:

```
INFO looking for merge commits until 683d76e704db935ad12e165329d2c774175f3b16
```

It walks down the commit tree looking for merge nodes:

```
[...]
DEBUG all merges:
DEBUG 	957eacf60ba1aaa0694847ca783ebef12357c39b Merge branch 'bugfix/1268' into env/dev-ad-api
DEBUG 	47d87bb030a5f5344c9ee83efbef0473f97f7655 Merge branch 'bugfix/1268' into env/dev-ad-api
DEBUG 	8c53f4ec2fde59556fa8a4db51601b8df917d05c Merge branch 'bugfix/1268' into env/dev-ad-api
DEBUG 	e8e62208b5b9b700aaf11ac9bf7fab97ab07ac61 Merge branch 'bugfix/1268' into env/dev-ad-api
DEBUG 	a55c8ee1f985653414e101e50e5e3644deb50191 Merge branch 'bugfix/1268' into env/dev-ad-api
DEBUG 	69752e6d0f6168a1cca3a67eb9e35a1f0da520b5 Merge branch 'bugfix/401-error' into env/dev-ad-api
DEBUG 	f18b42ffbca5fbc395002f25ded5695583963929 Merge branch 'bugfix/401-error' into env/dev-ad-api
DEBUG 	a03b3816bed20ee9c793464791345ea067563b51 Merge branch 'bugfix/cant-see-profile' into env/dev-ad-api
DEBUG 	5eaa71173c114ea826909124c628ff435659ba96 Merge branch 'feature/1031' into env/dev-ad-api
DEBUG 	9f65cd6f1e3e7fe1987ade6906e2cc28c855a5d1 Merge branch 'bugfix/401-error' into env/dev-ad-api
DEBUG 	50ae6202bd270da99ae7d18e64138d042507fc99 Merge branch 'bugfix/401-error' into env/dev-ad-api
DEBUG 	cb579e252aa603abb0e0ea63f6634fa6119e8d6a Merge branch 'feature/1031' into env/dev-ad-api
DEBUG 	8209c5de108087515222210ce035f403cf24bb0b Merge branch 'feature/1031' into env/dev-ad-api
DEBUG 	79f1b0bebf8a6249dd831873ad4f31d65acf2884 Merge branch 'feature/1031' into env/dev-ad-api
DEBUG 	c073b813b78202b8647eb1c514ca48837a87cd4e Merge branch 'feature/update-rows' into env/dev-ad-api
DEBUG 	b8bddabdd318688290bcaeb38633ddea77074dfd Merge branch 'feature/1031' into env/dev-ad-api
DEBUG 	248efcf99b96eaf2a7f667c5ce94162ef632d1e3 Merge branch 'feature/public-access' into env/dev-ad-api
DEBUG 	79ed19314fea587d7a611d69c1ca1fbbbd44c951 Merge branch 'feature/1031' into env/dev-ad-api
```

Once all merge nodes are tracked down, they are filtered down to unique branches:

```
[...]
INFO merges:
INFO 	957eacf60ba1aaa0694847ca783ebef12357c39b Merge branch 'bugfix/1268' into env/dev-ad-api
INFO 	69752e6d0f6168a1cca3a67eb9e35a1f0da520b5 Merge branch 'bugfix/401-error' into env/dev-ad-api
INFO 	a03b3816bed20ee9c793464791345ea067563b51 Merge branch 'bugfix/cant-see-profile' into env/dev-ad-api
INFO 	5eaa71173c114ea826909124c628ff435659ba96 Merge branch 'feature/1031' into env/dev-ad-api
INFO 	c073b813b78202b8647eb1c514ca48837a87cd4e Merge branch 'feature/update-rows' into env/dev-ad-api
INFO 	248efcf99b96eaf2a7f667c5ce94162ef632d1e3 Merge branch 'feature/public-access' into env/dev-ad-api
```

This is already looking much cleaner than before.  Now, the magic; replaying the cleaned up list.  Breaking down the `git-smash replay` command, as before it finds where to begin:

```
[0][~/Projects/work/repo(env/dev:957eacf6:1)]
[berto:env@berto]$ git-smash replay
WARNING this branch is not on top of origin/master
INFO find merge commits:
INFO looking for merge commits until 683d76e704db935ad12e165329d2c774175f3b16
```

Note that as it's walking through the merge commits found in the branch history, it looks for a branch of that name within all the remotes known to the local repo.  When one is not found, the branch is temporarily re-created locally based on the information in the merge node, and produces the replay plan:

```
WARNING cannot find commit on any remote, making a temp branch: bugfix/1268
INFO branches to merge:
	4f38955c2538c478c2ad214984964266ddc9518d @ feature/public-access
	4fa88df9f683860242047d9fa93aa26365e3ce08 @ feature/update-rows
	f4c1928a2ff640eb39ecd55bfb3f41c178c2a104 @ feature/1031
	037ea441d8a4f86a07930aee982520ff146c4447 @ remotes/rca/bugfix/401-error
	d393d92a7af97b30d5f3082c714b5394dc8ec159 @ remotes/rca/bugfix/cant-see-profile
	683d76e704db935ad12e165329d2c774175f3b16 @ bugfix/1268
```

As a precaution; the current branch's commit is stored in the branch `smash/env/dev`.  In case anything happens, the current branch can be reset to the un-smashed version by running `git reset --hard smash/env/dev`:

```
INFO backing up current branch to smash/env/dev
```

The branch is first brought up to date with the origin's master branch:

```
INFO resetting to origin/master
```

and it starts replaying the merges found:

```
INFO merging feature/public-access
```

While it's replaying, the branch's commit history is checked to see if replaying a merge is unnecessary.  Likely because that feature branch has landed in `master`:

```
INFO rev=4fa88df9f683860242047d9fa93aa26365e3ce08 from feature/update-rows already in commit history, skipping
INFO merging feature/1031
INFO merging bugfix/401-error
INFO rev=d393d92a7af97b30d5f3082c714b5394dc8ec159 from remotes/rca/bugfix/cant-see-profile already in commit history, skipping
INFO rev=683d76e704db935ad12e165329d2c774175f3b16 from bugfix/1268 already in commit history, skipping
```

And with that, we have a clean, up-to-date history:

```
[berto:env@berto]$ git log --pretty=oneline
0133b63ce32a9384ea0258882a44af39ba133fa8 (HEAD) Merge branch 'bugfix/401-error' into env/dev
ba459e0bf519536bacad01b451aeb644915e4977 Merge branch 'feature/1031' into env/dev
c5fdfe29a1d4acf0de02dc1d2fedfac9f195302d Merge branch 'feature/public-access' into env/dev
534c280ceab7e2845c65550a232013be2dd7fada (tag: 2.2.13, origin/master, origin/HEAD, master) Merge pull request #206 from rca/bugfix/1268
```

Replaying multiple times will result in the same content, however git will re-generate commit hashes.
