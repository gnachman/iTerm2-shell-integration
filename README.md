# iTerm2-shell-integration
Shell integration and utilities for iTerm2

## ZSH framework usage

The repository contains `iTerm2-shell-integration.plugin.zsh` to make it easier to use with ZSH frameworks like zgenom, antigen and oh-my-zsh.

### [Zgenom](https://github.com/jandamm/zgenom)

Add `zgenom load gnachman/iTerm2-shell-integration` to your `.zshrc` with your other load commands, then run `zgenom save` to update its `init.zsh` file. The integration will be automatically loaded the next time you start a ZSH session.

### [Antigen](https://github.com/zsh-users/antigen)

Add `antigen bundle gnachman/iTerm2-shell-integration@main` to your `.zshrc`

☝  **Note** that until <https://github.com/zsh-users/antigen/issues/717> gets fixed in Antigen, it only automatically recognizes plugins on the `master` branch, so you need to explicitly specify `@main` here.

### [Oh-My-Zsh](http://ohmyz.sh/)

1. `git clone --depth 1 https://github.com/gnachman/iTerm2-shell-integration.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/fzf-zsh-plugin`
2. Add **iterm2-shell-integration** to your plugin list - edit `~.zshrc` and change `plugins=(...)` to `plugins=(... iterm2-shell-integration)`
