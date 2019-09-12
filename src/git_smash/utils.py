import logging
import sh
import shlex
import string

SH_ERROR_1 = getattr(sh, 'ErrorReturnCode_1')


def get_proc(command: str, **kwargs):
    command_split = shlex.split(command)

    sh_command = getattr(sh, command_split[0])

    return sh_command(*command_split[1:], **kwargs)


def run_command(command: str) -> str:
    proc = get_proc(command)

    return proc.stdout.decode('utf8').strip()


def run_command_with_interactive_fallback(command: str, message: str = None):
    logger = logging.getLogger(f'{__name__}')

    try:
        run_command(command)
    except SH_ERROR_1 as exc:
        message = message or ''

        logger.error(f'could not run "{command}".  {message}')

        run_interactive_shell()

def run_interactive_shell(message: str = None):
    logger = logging.getLogger(f'{__name__}')

    message = message or f'launching a subshell.  when done, exit the shell'

    logger.info(message)

    return sh.bash('-i', _fg=True)
