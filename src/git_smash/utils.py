import sh
import shlex
import string


def get_proc(command: str, **kwargs):
    command_split = shlex.split(command)

    sh_command = getattr(sh, command_split[0])

    return sh_command(*command_split[1:], **kwargs)


def run_command(command: str) -> str:
    proc = get_proc(command)

    return proc.stdout.decode('utf8').strip()
