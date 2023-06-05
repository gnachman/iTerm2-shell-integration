# Automagically add the utilities directory to $PATH

# Add utilities to our path
PLUGIN_BIN="$(dirname $0)/utilities"
export PATH=${PATH}:${PLUGIN_BIN}

# And source the helper functions, too.
source "${0:h}/shell_integration/zsh"
