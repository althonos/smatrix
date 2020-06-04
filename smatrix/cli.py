import argparse
import collections
import itertools
import json
import subprocess
import tempfile
import pkg_resources

import jinja2
from rich import print
from rich.syntax import Syntax

from . import __name__ as __package__


_MAX_JOBS = 1000


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

    return parser


def parse_param_args(argv):

    param_name = ""
    params = {"": []}

    for arg in argv:

        if arg.startswith(("-P:", "--param:")):
            _, param_name = arg.split(":", maxsplit=1)
            if not param_name:
                raise ValueError("invalid parameter name")
            params[param_name] = []
        elif arg == "--":
            param_name = ""
        else:
            params[param_name].append(arg)

    unknown_params = params.pop("")
    if unknown_params:
        raise ValueError("unrecognized arguments: {}".format(unknown_params))

    return params


def main(argv=None):
    # parse CLI
    sbatch_parser = build_sbatch_parser()
    args, remainder = sbatch_parser.parse_known_args()
    args.param = parse_param_args(remainder)
    print(args)

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
    print("[bold green]Preparing[/bold green] a total of [bold]{}[/bold] jobs".format(len(matrix)))

    # build flat list of parameters to embed in the script
    parameters_list = separator.join(p for params in matrix for p in params)

    # get the job count and script template
    # FIXME: handle len(matrix) > max slurm job count using script template
    #        with inner loop
    job_count = len(matrix) or 1
    template = env.get_template("flat.sh.j2")

    # render the script
    script = template.render(
        separator=separator,
        parameters=args.param,
        parameters_list=parameters_list,
        cmd=args.wrap,
        args=args,
    )

    # write the script file to a temporary location and pass it to sbatch
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False, mode="w") as script_file:
        print("[bold green]Writing[/bold green] job script to [bold blue]{}[/bold blue]".format(script_file.name))
        script_file.write(script)
        script_file.flush()

        print("[bold green]Launching[/bold green] job script with [bold]sbatch[/bold]")
        args = ["sbatch", "-a", "1-{}".format(job_count), script_file.name]
        proc = subprocess.run(args, capture_output=True)

    # check the job was successfully queued
    if proc.returncode == 0:
        job_id = int(proc.stdout.rsplit(b" ", maxsplit=1)[-1].strip())
        print("[bold green]Successfully[/bold green] launched job with id [bold]{}[/bold]".format(job_id))
    else:
        print("[bold red]Failed[/bold red] launching job")
        print(Syntax(proc.stderr, "bash"))

    return proc.returncode
