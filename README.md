# `smatrix`

*Not the slurm job dispatcher you need, but the one you deserve.*

[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square&maxAge=2678400)](https://choosealicense.com/licenses/mit/)
[![Source](https://img.shields.io/badge/source-GitHub-303030.svg?maxAge=2678400&style=flat-square)](https://github.com/althonos/smatrix/)
[![GitHub issues](https://img.shields.io/github/issues/althonos/smatrix.svg?style=flat-square&maxAge=600)](https://github.com/althonos/smatrix/issues)

## Introduction

`slurm` is a workload manager, and it is typically used to parallelize work
at a job level. It is heavily configurable, but can sometimes be quite
overwhelming when the work to be performed is simple.

A typical usecase in our lab is to use `slurm` to process metagenomes in the
EMBL cluster: we want to run a single command (like `hmmsearch` or `gecco`)
on a very large number of files, and also possibly with different threshold
values. Doing so efficiently requires writing a custom script that ends up
being copied and pasted around. **As a programmer, I found this unacceptable.**

`smatrix` leverages the most common tasks of splitting the workload evenly,
generating a job script with the parameters, and launching the jobs to the
cluster. Think `xargs`, except it spawns `slurm` jobs instead of processes.


## Usage

`smatrix` uses the same names as `sbatch` or `srun` for parameters if needed,
and some additional flags to pass parameters. A quick example:

```console
$ smatrix                                            \
    --cpus-per-task 2                                \
    -P:f1 0.02 0.01                                  \
    -P:file /data/seq1.fa /data/seq2.fa              \
    --wrap 'hmmsearch --F1=$f1 Pfam.hmm $file'
```

### `-P` / `--param` flag

The `-P` flag is the only new flag introduced by `smatrix`. Use it to specify
parameter arrays

The format for the `--param` flag is designed to accommodate globing and
sub-command calls in the shell:
```console
$ smatrix --param:n $(seq 1 100) --param:file /etc/*.conf --wrap '...'
```

Note that, in this example, the glob pattern expansion is done by the shell
and may have escaping issues if the filenames contain whitespace characters`


### `--wrap` flag

`--wrap` was already there in `sbatch`, but `smatrix` wraps the command
differently, since it will also expose the parameters you request with `-P`.


## Compatibility

Designed to work with `bash` in mind. `fish` generally works, but has some
issues with subshell expansion and CLI parameter handling. Untested with
`zsh` or any other shell.
