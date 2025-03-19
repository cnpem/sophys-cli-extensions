# sophys-cli-extensions

A command-line client for the sophys project group.

This is the SIRIUS extensions for [sophys-cli-core](https://github.com/cnpem/sophys-cli-core). It contains custom logic and functionality for particular beamlines.

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

For general usage and development information about sophys-cli, refer to the [`sophys-cli-core`](https://github.com/cnpem/sophys-cli-core?tab=readme-ov-file#usage) documentation.

These extensions make use of environment variables to configure host and port variables for connection with httpserver and redis. These environment variable names are defined in `sophys-cli-core`, under their root [`__init__.py`](https://github.com/cnpem/sophys-cli-core/blob/main/src/sophys/cli/core/__init__.py).

### Developer documentation: All extensions

Basically all extensions will want to do the following configuration on their environment:

- Register available plans and magics for them
- Register magics for other functionality (e.g. httpserver interaction)
- Configure httpserver interaction, mainly session token management
- Print relevant additional information to the user
- Populate the IPython namespace with important variables

For those, we have helper methods and functions that aim to reduce the boilerplate needed for creating a functional extension.

A rather minimal example of all of these functionalities is provided in the form of the [`sophys-test` extension](./src/sophys/cli/extensions/test/__init__.py), which is a really barebones extension, intended to be used by developers on a test setup. Below are some further explanation about some of these topics:

##### Plans and plan magics

For registering plans and their magics, we need to first create a [`PlanWhitelist`](https://github.com/cnpem/sophys-cli-core/blob/5d2581dfc13bf214b1e4bb684cdc189522814446/src/sophys/cli/core/magics/plan_magics.py#L466) object containing our whitelisted plans (generally, these will be plans available on the queueserver environment, that we have already made a magics interface for).

After creating the plan whitelist object, we can use the [`setup_plan_magics`](https://github.com/cnpem/sophys-cli-core/blob/5d2581dfc13bf214b1e4bb684cdc189522814446/src/sophys/cli/core/magics/__init__.py#L144) function to register all these plans with their respective magics.

##### Other magics

Any other magics usually follow the same pattern of running [`ipython.register_magics`](https://ipython.readthedocs.io/en/stable/api/generated/IPython.core.magic.html#IPython.core.magic.MagicsManager.register) on the class with the magics registered to it.

##### Session token management

In a remote environment, we need to keep track of the user's session token, so we can make further HTTP requests authenticated. For managing this token, and also the refresh token for regenerating it upon expiration, we make use of a thread-based class running on the background, handling all that. The `sophys-cli-core` documentation already explains [how to set it up and make use of it](https://github.com/cnpem/sophys-cli-core/tree/main?tab=readme-ov-file#communicating-with-httpserver).
