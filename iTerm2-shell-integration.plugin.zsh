# Automagically add the utilities directory to $PATH

# Add utilities to our path
path+=("${0:h}/utilities")

# And source the helper functions, too.
source "${0:h}/shell_integration/zsh"
