# The it2 CLI (it2.py) is embedded into each shell integration script so it can be
# materialized on the remote over SSH integration. It is carried as a gzip+base64
# blob and substituted into the ${IT2_PY_B64} placeholder with envsubst (restricted
# to those variables, so the scripts' own $vars pass through untouched).
# -n drops the name+mtime from the gzip header so the blob is reproducible (without
# it, gzip stamps the current time and the blob churns on every build).
IT2_PY_B64 := $(shell gzip -9nc it2.py | base64 | tr -d '\n')
export IT2_PY_B64

# Content hash of it2.py. The materialized file is named it2.$(hash).py so a shipped
# update lands under a new name and replaces a stale copy, rather than being skipped
# forever by a file-exists check.
IT2_PY_HASH := $(shell shasum -a 256 it2.py | cut -c1-16)
export IT2_PY_HASH

VARS := '$$IT2_PY_B64 $$IT2_PY_HASH'
PREEXEC := ../submodules/bash-preexec/bash-preexec.sh

# Each recipe truncates its output with `> file` before the pipeline runs, so a
# failed command (e.g. envsubst missing) would otherwise leave an empty script in
# place with a fresh mtime and ship it. Delete the target on failure instead.
.DELETE_ON_ERROR:

all: bash zsh fish tcsh xonsh nu it2-wrapper

bash: source/bash.0 source/bash.1 $(PREEXEC) it2.py
	cat source/bash.0 $(PREEXEC) source/bash.1 | envsubst $(VARS) > bash

zsh: source/zsh.in it2.py
	envsubst $(VARS) < source/zsh.in > zsh

fish: source/fish.in it2.py
	envsubst $(VARS) < source/fish.in > fish

tcsh: source/tcsh.in it2.py
	envsubst $(VARS) < source/tcsh.in > tcsh

xonsh: source/xonsh.in it2.py
	envsubst $(VARS) < source/xonsh.in > xonsh

nu: source/nu.in it2.py
	envsubst $(VARS) < source/nu.in > nu

# ~/.iterm2/bin/it2: runs it2.py, falling back to the copy named by its hash. iTerm2 uploads it
# over SSH Integration and the installers install it, always alongside the it2.py it was built
# with. Only $IT2_PY_B64 and $IT2_PY_HASH are substituted, so its shell variables survive.
it2-wrapper: source/it2-wrapper.in it2.py
	envsubst $(VARS) < source/it2-wrapper.in > it2-wrapper
	chmod 755 it2-wrapper

.PHONY: all
