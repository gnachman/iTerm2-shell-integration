#!/bin/bash
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


function die() {
  echo "${1}"
  exit 1
}

type printf > /dev/null 2>&1 || die "Shell integration requires the printf binary to be in your path."

# Non-POSIX shells may leave POSIX shell path in the $SHELL; perform an additional check.
if [ -n "${XONSHRC}" ]; then
  SHELL=xonsh
else
  SHELL=${SHELL##*/}
fi

URL=""
HOME_PREFIX='${HOME}'
DOTDIR="$HOME"
SHELL_AND='&&'
SHELL_OR='||'
QUOTE=''
# Set by shells that load the script from a directory instead of from a dotfile.
FILENAME_OVERRIDE=''
NO_DOTFILE=''
if [ "${SHELL}" = tcsh ]
then
  URL="https://iterm2.com/shell_integration/v2/tcsh"
  SCRIPT="${HOME}/.login"
  QUOTE='"'
fi
if [ "${SHELL}" = zsh ]
then
  URL="https://iterm2.com/shell_integration/v2/zsh"
  if [ -d "$ZDOTDIR" -a ! -f "${HOME}/.iterm2_shell_integration.${SHELL}" ]; then
    echo "Using ZDOTDIR of $ZDOTDIR"
    DOTDIR="$ZDOTDIR"
    HOME_PREFIX='${ZDOTDIR}'
  fi
  SCRIPT="${DOTDIR}/.zshrc"
  QUOTE='"'
fi
if [ "${SHELL}" = bash ]
then
  URL="https://iterm2.com/shell_integration/v2/bash"
  test -f "${HOME}/.bash_profile" && SCRIPT="${HOME}/.bash_profile" || SCRIPT="${HOME}/.profile"
  QUOTE='"'
fi
if [ "${SHELL}" = fish ]
then
  echo "Make sure you have fish 2.3 or later. Your version is:"
  fish -v

  URL="https://iterm2.com/shell_integration/v2/fish"
  mkdir -p "${HOME}/.config/fish"
  SCRIPT="${HOME}/.config/fish/config.fish"
  HOME_PREFIX='{$HOME}'
  SHELL_AND='; and'
  SHELL_OR='; or'
fi
if [ "${SHELL}" = xonsh ]
then
  URL="https://iterm2.com/shell_integration/v2/xonsh"
  if [ -n "${XDG_CONFIG_HOME}" ]; then
    CONFIG_HOME="${XDG_CONFIG_HOME}"
  else
    CONFIG_HOME="${HOME}/.config"
  fi
  mkdir -p "${CONFIG_HOME}/xonsh/rc.d/"
  SCRIPT="${CONFIG_HOME}/xonsh/rc.d/iterm2.xsh"
  HOME_PREFIX='{$HOME}'
  QUOTE='"'
fi
if [ "${SHELL}" = nu ]
then
  URL="https://iterm2.com/shell_integration/v2/nu"
  # nushell sources every .nu file in its user autoload directory at startup,
  # and does so after config.nu, so there is no dotfile to edit -- dropping the
  # script in place is the whole installation. Ask nu where that directory is
  # rather than guessing: it is under ~/Library/Application Support on macOS and
  # ~/.config on Linux.
  NU_CONFIG_DIR=$(nu --no-config-file -c 'print $nu.default-config-dir' 2>/dev/null)
  test -n "${NU_CONFIG_DIR}" || NU_CONFIG_DIR="${HOME}/.config/nushell"
  mkdir -p "${NU_CONFIG_DIR}/autoload"
  FILENAME_OVERRIDE="${NU_CONFIG_DIR}/autoload/iterm2_shell_integration.nu"
  NO_DOTFILE=1
fi
if [ "${URL}" = "" ]
then
  die "Your shell, ${SHELL}, is not supported yet. Only bash, fish, nu, tcsh, xonsh and zsh are supported. Sorry!"
  exit 1
fi

FILENAME="${FILENAME_OVERRIDE:-${DOTDIR}/.iterm2_shell_integration.${SHELL}}"
RELATIVE_FILENAME="${HOME_PREFIX}/.iterm2_shell_integration.${SHELL}"
echo "Downloading script from ${URL} and saving it to ${FILENAME}..."
curl -SsL "${URL}" > "${FILENAME}" || die "Couldn't download script from ${URL}"
chmod +x "${FILENAME}"
if [ -z "${NO_DOTFILE}" ]; then
  echo "Checking if ${SCRIPT} contains iterm2_shell_integration..."
  if ! grep iterm2_shell_integration "${SCRIPT}" > /dev/null 2>&1; then
	echo "Appending source command to ${SCRIPT}..."
	cat <<-EOF >> "${SCRIPT}"

	test -e ${QUOTE}${RELATIVE_FILENAME}${QUOTE} ${SHELL_AND} source ${QUOTE}${RELATIVE_FILENAME}${QUOTE} ${SHELL_OR} true

EOF
  fi
fi

echo "Done."
echo "iTerm2 shell integration was installed!"
echo ""
echo "A script was installed to ${FILENAME}"
echo ""
echo "To make it work right now, do:"
echo "  source ${FILENAME}"
echo
if [ -z "${NO_DOTFILE}" ]; then
  echo "This line was also added to ${SCRIPT}, so the next time you log in it will be loaded automatically."
else
  echo "It went into a directory ${SHELL} loads at startup, so the next time you log in it will be loaded automatically."
fi
