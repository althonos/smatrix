import argparse
import collections
import itertools
import json
import math
import subprocess
import tempfile
import textwrap
import pkg_resources

import jinja2
from rich import print
from rich.syntax import Syntax

from . import __name__ as __package__
from .slurm import QosConfiguration


_MAX_JOBS = 2000


def build_sbatch_parser():
    parser = argparse.ArgumentParser()
    with pkg_resources.resource_stream(__package__, "data/sbatch.json") as f:
        sbatch_arguments = json.load(f)

    # add options to pass transparently to sbatch
    for section in sbatch_arguments:
        for option in section["options"]:
            args, kwargs = [], {}
            if "short" in option:
                args.append("-{}".format(option["short"]))
            args.append("--{}".format(option["name"]))
            kwargs["help"] = option["help"]
            if "meta" in option:
                kwargs["action"] = "store"
                kwargs["metavar"] = option["meta"]
                if "nargs" in option:
                    kwargs["nargs"] = option["nargs"]
            else:
                kwargs["action"] = "store_true"
            parser.add_argument(*args, **kwargs)

    # add a custom `setup` option
    parser.add_argument(
        "--setup",
        action="append",
        help="setup command to run once per node (can be repeated)"
    )

    #
    parser.add_argument(
        "--triangular",
        action="store_true",
        help="use only a triangular matrix of parameters"
    )

    return parser


def parse_param_args(argv):

    param_name = _UNKNOWN = object()
    params = {_UNKNOWN: []}

    for arg in argv:

        if arg.startswith(("-P:", "--param:")):
            _, param_name = arg.split(":", maxsplit=1)
            if not param_name:
                raise ValueError("invalid parameter name")
            if param_name in params:
                raise ValueError("parameter name given twice: {}".format(param_name))
            params[param_name] = []
        elif arg == "--":
            param_name = _UNKNOWN
        else:
            params[param_name].append(arg)

    unknown_params = params.pop(_UNKNOWN)
    if unknown_params:
        raise ValueError("unrecognized arguments: {}".format(unknown_params))

    return params


def main(argv=None):
    # parse CLI
    sbatch_parser = build_sbatch_parser()
    args, remainder = sbatch_parser.parse_known_args()
    args.param = parse_param_args(remainder)

    # build the jinja environment
    env = jinja2.Environment(loader=jinja2.PackageLoader(__package__))
    env.filters.setdefault("quote", "{!r}".format)

    # extract parameters
    for name, values in args.param.items():
        print("[bold green]Using[/bold green] parameter [bold]{}[/bold] with [bold]{}[/bold] values".format(name, len(values)))

    # find a separator for the parameters
    separator = next(
        sep for sep in ";,!@"
        if all(sep not in parameter for parameter in args.param.values())
    )

    # build parameter matrix
    matrix = list(itertools.product(*args.param.values()))
    print("[bold green]Preparing[/bold green] a total of [bold]{}[/bold] tasks".format(len(matrix)))

    # query max number of jobs and adjust the number of task per array job
    # TODO: use sacctmgr
    #config = QosConfiguration(qos=args.qos or "normal")
    #max_job_count = config.max_submit_per_user or config.max_submit_per_account or _MAX_JOBS
    max_job_count = _MAX_JOBS
    job_count = min(max_job_count, len(matrix) or 1)
    tasks_per_job = math.ceil((len(matrix) or 1) / job_count)
    job_count = math.ceil((len(matrix) or 1) / tasks_per_job)
    print("[bold green]Using[/bold green] [bold]{}[/bold] job arrays with maximum [bold]{}[/bold] tasks each".format(job_count, tasks_per_job))

    # get the job count and script template
    tasks_count = len(matrix) or 1
    if args.triangular and tasks_count > 1:
        template = env.get_template("triangle.sh.j2")
        shape = list(map(len, args.param.values()))
        if not all(x == shape[0] for x in shape):
            dims = 'x'.join(map(str, shape))
            print("[bold red]Failed[/bold red] launching triangular job with non-square matrix ({})".format(dims))
            return 1
    else:
        template = env.get_template("square.sh.j2")

    # check the argument matrix is square if in triangular mode


    # render the script
    script = template.render(
        separator=separator,
        tasks_count=tasks_count,
        tasks_per_job=tasks_per_job,
        args=args,
    )
    # print(Syntax(script, "bash"))

    # write the script file to a temporary location and pass it to sbatch
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False, mode="w") as script_file:
        print("[bold green]Writing[/bold green] job script to [bold blue]{}[/bold blue]".format(script_file.name))
        script_file.write(script)
        script_file.flush()

        print("[bold green]Launching[/bold green] job script with [bold]sbatch[/bold]")
        args = ["sbatch", "--array=0-{}".format(job_count-1), script_file.name]
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # check the job was successfully queued
    if proc.returncode == 0:
        job_id = int(proc.stdout.rsplit(b" ", maxsplit=1)[-1].strip())
        print("[bold green]Successfully[/bold green] launched job with id [bold]{}[/bold]".format(job_id))
    else:
        print("[bold red]Failed[/bold red] launching job with error:")
        print(Syntax(textwrap.indent(proc.stderr.decode('utf-8'), '    '), "bash"))

    return proc.returncode
