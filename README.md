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

### Developer documentation: EMA

The EMA beamline, as the one that first requested such an interface for Bluesky usage, is the most complex extension we have, and has shaped how most functionality was built. As with other extensions, it starts loading from its `load_ipython_extension` function at [its init file](./src/sophys/cli/extensions/ema/__init__.py).

This is not a comprehensive examination of everything, but it aims at sheding light at some of the more complex portions of it.

##### Plans

As with any beamline, EMA has their own plans, which are extensions to Bluesky's base plans, and are defined in the `sophys-ema` internal package. The custom handlers for these plans are all defined in the [`plans.py`](./src/sophys/cli/extensions/ema/plans.py) file. They are then imported into `__init__.py` and used in the `PlanWhitelist` definition.

##### Mnemonics

The EMA beamline uses mnemonics to reference their devices, special shorthand names defined in a table governed by the Data Science Group (GCD/LNLS), with input from the beamline staff. In queueserver, we use a preprocessor to read that table and convert the Ophyd device names to those names, ensuring everything user-facing retains this convention. And because we can have different devices using the same mnemonic, we need to somehow communicate to the server what each mnemonic references for each plan.

We make that using a metadata field that we pass along, called `MNEMONICS`, containing the relations between used mnemonics and their corresponding EPICS prefix. This metadata field is inserted via the `populate_mnemonics` function at `__init__.py`, which is passed along with `PlanWhitelist` for execution at a later point.

##### Input processing

There is some persistence present in the EMA extension, which is not local to IPython. We use the redis instance already available in the `sophys-server` deploy to keep some data available, and we consume from it to automatically populate some fields when running a plan. In particular, detectors are defined in a separate interface (see the section on [`eds`](#eds---ema-device-selector) for more details), and then populated via this mechanism in the plan execution request.

For this, we use the native [input processing](https://ipython.readthedocs.io/en/stable/config/inputtransforms.html) facilities to hook up the functions defined in [`input_processor.py`](./src/sophys/cli/extensions/ema/input_processor.py), so that we can fill in the missing information before execution takes place. And to retrieve that information, we use the `DataSource` abstraction defined in `sophys-cli-core`. All of this is defined in the `setup_input_transformer` function at the `__init__.py` file.

##### `eds` - EMA Device Selector

As mentioned in the previous section, EMA uses a separate interface to select their detectors. This is a simple Qt-based application, generating a formatted form of all available detectors, and allowing the user to select their wanted ones.

This application, like in the previous step, uses a `DataSource` for reading and writing all its information, which is provided to it at startup. All the data it manipulates are the selected mnemonics, so it doesn't interact with any devices on its own.

It also has an small dependency on `sirius-widgets-case`, LNLS's PyDM widgets library, to support configuring ROIs of some AreaDetector-based devices. However, it will only try to import it if you try to use that functionality.

##### Persistent metadata

In EMA, one requirement from the beamline staff is to retain the same metadata file name template during a set of scans. This means defining the base name once, and until removed or overwritten, all plans must use it. And to complicate matters, it is undesirable that this configuration persists after the user session.

To solve this, we use a `sophys-cli-core` feature called `PermanentMetadata`, which is simply a `DataSource`-based object with support for preprocessing the `md` field being forwarded to the RunEngine with its contents. We use an in-memory data source, configured at the `setup_persistent_metadata` function at `__init__.py`. There's also the `newfile` and `disable_auto_increment` magics inside of `UtilityMagics` for users to interact with it.

##### Error handling

We provide some custom error handling bits for users, since the peculiarities of this beamline can cause some problems of its own class. Actually, whether this should go to `sophys-cli-core` is a contentious topic, and maybe they should, but for now they're here!

On the client-side, we provide the `after_plan_request_failed_callback` function at `__init__.py`, which provides some nicer user-facing error messages for failing to submit a plan for execution.
