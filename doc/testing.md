## Continuous integration and testing for OpenQuake

### Automatic testing

The OpenQuake code is automatically tested by Continuous integration systems, [Jenkins](https://ci.openquake.org) and [Travis](https://travis-ci.org/gem/oq-engine), at every merge and every night.

### Manual testing

The full suite of tests for the OpenQuake Engine can be run using `nose` from [**source code**](installing/development.md):

```bash
$ pytest -v openquake
```

Python packages can also be specified to run only a subset of tests. Some examples are:

```bash
# Hazardlib
$ pytest -vs openquake/hazardlib

# Calculators
$ pytest -vs openquake/calculators

# Engine server
$ oq dbserver start
$ pytest -vs openquake/server
```

See the [man page](http://nose.readthedocs.io/en/latest/man.html) of `nosetests` for further information and command options.

***

## Getting help
If you need help or have questions/comments/feedback for us, you can:
  * Subscribe to the OpenQuake users mailing list: https://groups.google.com/forum/?fromgroups#!forum/openquake-users
  * Contact us on IRC: irc.freenode.net, channel #openquake
