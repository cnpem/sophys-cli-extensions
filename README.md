# sophys-cli-extensions

A command-line client for the sophys project group.

This is the SIRIUS extensions for sophys-cli-core. It contains custom logic and functionality for particular beamlines.

## Installation

To use it, you'll have to be in a valid Python environment (consider using [micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)). In there, you'll need to do the following:

Normal installation (TODO: Create pre-built packages):

```bash
$ pip install git+https://github.com/cnpem/sophys-cli-extensions.git
```

Developer installation:

```bash
$ cd <path where you will clone the sophys-cli package>
$ git clone https://github.com/cnpem/sophys-cli-extensions.git
$ pip install -e sophys-cli-extensions
```

With that, you'll have access to the `sophys-cli` command in the environment you installed it. Furthermore, to use `sophys-cli` with a particular beamline configuration, you must also install the `sophys-<beamline>` package in that environment. After that, to use that configuration, see the [Usage](#usage) section.

## Usage and development

For usage and development information, refer to the `sophys-cli-core` documentation.

These extensions make use of environment variables to configure host and port variables for connection with httpserver and redis. These environment variable names are defined in `sophys-cli-core`, under their root `__init__.py`.
