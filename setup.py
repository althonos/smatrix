#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import json
import os

import setuptools
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.sdist import sdist as _sdist


class sdist(_sdist):
    """An extension to the `sdist` command that generates a `pyproject.toml`.
    """

    def run(self):
        # build `pyproject.toml` from `setup.cfg`
        c = configparser.ConfigParser()
        c.add_section("build-system")
        c.set("build-system", "requires", str(self.distribution.setup_requires))
        c.set("build-system", 'build-backend', '"setuptools.build_meta"')
        with open("pyproject.toml", "w") as pyproject:
            c.write(pyproject)
        # run the rest of the packaging
        _sdist.run(self)


class build_py(_build_py):

    def run(self):
        # generate `smatrix/templates/header.sh.j2` using sbatch CLI data
        in_ = os.path.join(__file__, "..", "smatrix", "data", "sbatch.json")
        with open(os.path.realpath(in_)) as f:
            cli = json.load(f)

        out = os.path.join(__file__, "..", "smatrix", "templates", "header.sh.j2")
        with open(os.path.realpath(out), "w") as f:
            f.write("#!/bin/sh\n")
            for option in (option for section in cli for option in section['options']):
                if not option.get("transmit", True):
                    continue
                kebab, snake = option["name"], option["name"].replace("-", "_")
                if "meta" in option:
                    f.write("{{%- if not args.{} is none %}}\n".format(snake))
                    f.write("# SBATCH --{} {{{{ args.{} }}}}\n".format(kebab, snake))
                    f.write("{%- endif %}\n")
                else:
                    f.write("{{%- if args.{} %}}\n".format(snake))
                    f.write("# SBATCH --{}\n".format(kebab))
                    f.write("{%- endif %}\n")


        # run the rest of the build
        _build_py.run(self)


if __name__ == "__main__":
    setuptools.setup(
        cmdclass={
            "build_py": build_py,
            "sdist": sdist,
        },
    )
