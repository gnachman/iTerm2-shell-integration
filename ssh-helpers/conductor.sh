#!/usr/bin/sh
# Usage:
# conductor.sh token

# Global variables
login_shell=""
shell_name=""
quit=0
python_detected="0"
perl_detected="0"
exec_shell=0
run_cmd=0
run_python=0
stty_settings=$(command stty -g)

# Utilities
################################################################################

cleanup() {
  log cleanup "$stty_settings"
  command stty "$stty_settings"
  command stty echo
}

die() {
    log die "$*"
    printf "\033[31m%s\033[m\n\r" "$*" > /dev/stderr
    cleanup
    exit 1
}

it2ssh_verbose=0

log() {
    return
}

# Printing control sequences
################################################################################

print_dcs() {
    local token=$1
    local uniqueid=$2
    local boolargs=$3
    local sshargs=$4
    log osc print_dcs $1 $2 $3 $4

    printf "\033P2000p"
    printf "%s %s %s - %s\n" "${token}" "${uniqueid}" "${boolargs}" "${sshargs}"
}

# String parsing
################################################################################

first_word() {
    local input="$1"
    printf "%s" ${input%% *}
}

drop_first_word() {
    local input="$1"
    log drop first word from: "$input"
    if [ "${input#* }" != "$input" ]; then
        printf "%s" "${input#* }"
    fi
}

if command -v base64 > /dev/null 2>&1; then
    log "found base64 command"
    base64_encode() { command base64 | command tr -d \\n\\r; }
    base64_decode() { command base64 -d; }
elif command -v b64encode > /dev/null 2>&1; then
    log "found b64encode, b64decode commands"
    base64_encode() { command b64encode - | command sed '1d;$d' | command tr -d \\n\\r; }
    base64_decode() { command fold -w 76 | command b64decode -r; }
elif detect_python; then
    log "using python for base64"
    pybase64() { command "$python" -c "import sys, base64; getattr(sys.stdout, 'buffer', sys.stdout).write(base64.standard_b64$1(getattr(sys.stdin, 'buffer', sys.stdin).read()))"; }
    base64_encode() { pybase64 "encode"; }
    base64_decode() { pybase64 "decode"; }
elif detect_perl; then
    log "using perl for base64"
    base64_encode() { command "$perl" -MMIME::Base64 -0777 -ne 'print encode_base64($_)'; }
    base64_decode() { command "$perl" -MMIME::Base64 -ne 'print decode_base64($_)'; }
else
    die "base64 executable not present on remote host"
fi

# Get user's login shell
################################################################################

parse_passwd_record() {
    printf "%s" "$(command grep -o '[^:]*$')"
}

# sets $login_shell as a side effect.
# returns if it looks executable.
login_shell_is_ok() {
    log login_shell_is_ok with arg "$1"
    [ -n "$1" ] && login_shell=$(echo $1 | parse_passwd_record)
    [ -n "$login_shell" -a -x "$login_shell" ] && return 0
    log "login shell of $login_shell is bad"
    return 1
}

using_getent() {
    cmd=$(command -v getent) && [ -n "$cmd" ] && output=$(command "$cmd" passwd "$USER" 2>/dev/null) \
    && login_shell_is_ok "$output"
}

using_id() {
    cmd=$(command -v id) && [ -n "$cmd" ] && output=$(command "$cmd" -P "$USER" 2>/dev/null) \
    && login_shell_is_ok "$output"
}

detect_python() {
    if [ python_detected = "1" ]; then
        [ -n "$python" ] && return 0
        return 1
    fi
    python_detected="1"
    python=$(command -v python3)
    [ -z "$python" ] && python=$(command -v python2)
    [ -z "$python" ] && python=$(command -v python)
    if [ -z "$python" -o ! -x "$python" ]; then python=""; return 1; fi
    log found python at $python
    return 0
}

using_python() {
    detect_python && output=$(command "$python" -c "import pwd, os; print(pwd.getpwuid(os.geteuid()).pw_shell)") \
    && login_shell="$output" && login_shell_is_ok
}

detect_perl() {
    if [ perl_detected = "1" ]; then
        [ -n "$perl" ] && return 0
        return 1
    fi
    perl_detected="1"
    perl=$(command -v perl)
    if [ -z "$perl" -o ! -x "$perl" ]; then perl=""; return 1; fi
    log found perl at $perl
    return 0
}

using_perl() {
    detect_perl && output=$(command "$perl" -e 'my $shell = (getpwuid($<))[8]; print $shell') \
    && login_shell="$output" && login_shell_is_ok
}

using_shell_env() {
    [ -n "$SHELL" ] && login_shell="$SHELL" && login_shell_is_ok
}

guess_login_shell() {
    [ -n "$login_shell" ] || using_getent || using_id || using_python || using_perl || using_passwd || using_shell_env || login_shell="sh"
    printf "%s" "$login_shell"
    log login shell is "$login_shell"
}

# Execute login shell
################################################################################

execute_with_perl() {
    if detect_perl; then
        log execute login shell using perl
        exec "$perl" "-e" "exec {'$login_shell'} '-$shell_name'"
    fi
    return 1
}

execute_with_python() {
    if detect_python; then
        log execute login shell: "$python" "-c" "import os; os.execlp('$login_shell', '-' '$shell_name')"
        exec "$python" "-c" "import os; os.execlp('$login_shell', '-' '$shell_name')"
    fi
    return 1
}

exec_login_shell() {
    local login_shell=${1}
    shell_name=$(command basename "$login_shell")

    log exec_login_shell "$login_shell" with name "$shell_name"

    cleanup
    # We need to pass the first argument to the executed program with a leading -
    # to make sure the shell executes as a login shell. Note that not all shells
    # support exec -a so we use the below to try to detect such shells
    [ "$(exec -a echo echo OK 2> /dev/null)" = "OK" ] && exec -a "-$shell_name" "$login_shell"
    log failed, try python
    execute_with_python
    log failed, try perl
    execute_with_perl
    log failed, just run it with -l
    # TODO - this is complicated, come back and do it later.
    #execute_sh_with_posix_env
    unset RCOUNT
    exec "$login_shell" "-l"
    log failed completely
    printf "%s\n" "Could not execute the shell $login_shell as a login shell" > /dev/stderr
    exec "$login_shell"
}

# Commands
################################################################################

# Figure out the user's login shell and run it.
conductor_cmd_exec_login_shell() {
    log conductor_cmd_exec_login_shell
    exec_shell=1
}

really_exec_login_shell() {
    exec_login_shell $(guess_login_shell)
}

# Set an environment variable.
conductor_cmd_setenv() {
    log conductor_cmd_setenv
    if [ "$#" -ne 2 ]; then
        log bad args
        (exit 1)
        return
    fi
    local name=$1
    local value=$2

    log setenv ${name}=${value}
    export ${name}=${value}
}

conductor_cmd_run() {
    log conductor_cmd_run
    run_cmd=1
}

conductor_cmd_pythonversion() {
    log conductor_cmd_pythonversion
    printf "\033]135;:"
    command -v python3 >/dev/null 2>&1 && python3 -V
    printf "\033\\"
}

conductor_cmd_runpython() {
    log conductor_cmd_runpython
    run_python=1
}

really_run_python() {
  log really_run_python
  unset RCOUNT
  ttypath=$(tty)
  log "tty is $ttypath"
  exec python3 << ENDOFSCRIPT
import os
import sys
tty_path = "$ttypath"
sys.stdin = open(tty_path, "r")
try:
  print(f"\\033]135;:{os.getpid()}\\033\\\\", end="", flush=True)
  print(f"\\033]135;:end $boundary r 0\\033\\\\", end="", flush=True)
  program=""
  for line in sys.stdin:
    if line.rstrip() == "EOF":
      exec(program)
      print(f"\\033]135;:unhook\\033\\\\", end="", flush=True)
      break
    program += line
except Exception as e:
  print(e)
ENDOFSCRIPT
  log "unexpected return from exec"
  exit 0
}

really_run() {
    log "really_run $@"
    if [ "$#" -lt 1 ]; then
        log bad args
        (exit 1)
        return
    fi
    log exec "$SHELL" -c "$*"
    unset RCOUNT
    exec "$SHELL" -c "$*"
}

conductor_cmd_shell() {
    log conductor_cmd_shell
    if [ "$#" -lt 1 ]; then
        log bad args
        (exit 1)
        return
    fi
    printf "\033]135;:"
    set +e
    log will run $*
    $*
    printf "\033\\"
}

# Untar a base64-encoded file at a specified location.
conductor_cmd_write() {
    log conductor_cmd_write
    log have $# arguments
    if [ "$#" -ne 2 ]; then
        log bad args
        (exit 1)
        return
    fi

    log will write to "$2"

    local b64data=$1
    # Use eval to expand $HOME
    local destination=$(eval printf %s "$2")
    mkdir -p "$destination" || true
    log writing to $destination based on $2

    # extract the tar file atomically, in the sense that any file from the
    # tarfile is only put into place after it has been fully written to disk
    # suppress STDERR for tar as tar prints various warnings if for instance, timestamps are in the future
    old_umask=$(umask)
    umask 000
    printf "%s" ${b64data} | base64_decode | command tar "xpzf" "-" "-C" "$destination" > /dev/null 2>&1
    local rc=$?
    umask "$old_umask"
    (exit $rc)
}

conductor_cmd_cd() {
    log cd
    if [ "$#" -ne 1 ]; then
        log "bad args"
        (exit 1)
        return
    fi

    local dir=$1

    log cd $dir
    cd "$dir" > /dev/null 2>&1
}

conductor_cmd_quit() {
    log quit
    quit=1
}

conductor_cmd_getshell() {
    log getshell
    printf "\033]135;:"
    shell=$(guess_login_shell)
    echo "$shell"
    echo ~
    $shell --version || true
    printf "\033\\"
}

conductor_cmd_eval() {
    log "eval $@"
    local b64="$1"
    local mydir=$(mktemp -d "${TMPDIR:-/tmp/}it2ssh.XXXXXXXXXXXX")
    local file="$mydir/it2ssh-eval"
    log "mydir=$mydir tmpdir=${TMPDIR:-/tmp/} file=$file"
    printf "%s" "$b64" | base64_decode > "$file"
    log will source "$file" with content $(cat "$file")
    . "$file"
    rm -f "$file"
    log "$file" finished executing
}

write() {
    printf "\033]135;:%s\033\\" "$*"
}

# Main Loop
################################################################################

randomnumber() {
    if [ -z "${RCOUNT}" ]; then
      export RCOUNT=0
    else
      export RCOUNT=$((RCOUNT + 1))
    fi

    printf "%s." $RCOUNT
    awk 'BEGIN { srand(); print int(rand() * 65536)""int(rand() * 65536)""int(rand() * 65536)""int(rand() * 65536) }'
}

handle_command() {
    local unparsed=${1}

    log handle_command $unparsed

    local cmd_name=$(first_word "${unparsed}")
    log cmd_name is $cmd_name
    local args=$(drop_first_word "${unparsed}")
    log args is $args

    local boundary=$(randomnumber)
    write begin $boundary
    log invoke $cmd_name with arguments $args
    set +e
    if ( LC_ALL=C type conductor_cmd_${cmd_name} 2>/dev/null | head -n 1 | grep -q function ); then
        conductor_cmd_${cmd_name} $args
    else
        write "bad command ${cmd_name}"
        false
    fi
    if [ $run_python = 1 ]; then
        really_run_python "$boundary"
    fi
    write end $boundary $? r
    if [ $quit = 1 ]; then
        log quitting
        exit 0
    fi
    if [ $exec_shell = 1 ]; then
        log successfully executed the login shell. Unhook.
        write unhook
        cleanup
        really_exec_login_shell
    fi
    if [ $run_cmd = 1 ]; then
        log successfully ran a command. Unhook.
        write unhook
        cleanup
        really_run $args
    fi

    set -e
}

iterate() {
    log iterate

    line=""
    while true; do
        read part
        log read part "$part"
        if [ -z "$part" ]; then
            break
        fi
        line="${line}${part}"
    done

    log read line "$line"
    log decodes to: $(printf "%s" "$line" | base64_decode)
    handle_command "$(printf "%s" "$line" | base64_decode)"
}

drain_stdin() {
  log drain_stdin
  stty -echo -icanon time 0 min 0
  while :
  do
      key="$(printf x; dd bs=1 count=1 2> /dev/null; printf x)"
      if [ "$key" = "xx" ]; then
          log "done draining"
          break
      fi
      log "$key"
  done
  cleanup
}

main() {
    local token=$(printf "%s" "$1" | base64_decode)
    local uniqueid=$(printf "%s" "$2" | base64_decode)
    local booleanargs=$(printf "%s" "$3" | base64_decode)
    local sshargs=$(printf "%s" "$4" | base64_decode)

    log starting with token $token
    log $(env)
    log "token: $token"
    log "uniqueid: $uniqueid"
    log "booleanargs: $booleanargs"
    log "sshargs: $sshargs"

    trap "cleanup" EXIT
    drain_stdin
    stty -echo -onlcr -opost
    print_dcs "$token" "$uniqueid" "$booleanargs" "$sshargs"

    log begin mainloop

    while true; do
        iterate
    done
}

