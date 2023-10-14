.. image:: https://github.com/pvarki/docker-rasenmaeher-integration/actions/workflows/build.yml/badge.svg
   :alt: Build Status

========================
RASENMAEHER integrations
========================

"One Ring to rule them all, One Ring to find them, One Ring to bring them all and in the darkness bind them."

Docker compositions, helpers etc to bring it all together into something resembling grand old ones.


Git submodules
--------------

When cloning for the first time use::

    git clone --recurse-submodules -j8 git@github.com:pvarki/docker-rasenmaeher-integration.git

When updating or checking out branches use::

    git submodule update

And if you forgot to --recurse-submodules run git submodule init to fix things.

The submodules are repos in their own right, if you plan to make changes into them change
to the directory and create new branch, commit and push changes as usual under that directory.

Directories that are submodules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  - api https://github.com/pvarki/python-rasenmaeher-api
  - cfssl https://github.com/pvarki/docker-rasenmaeher-cfssl
  - fpintegration https://github.com/pvarki/python-rasenmaeher-rmfpapi
  - keycloak https://github.com/pvarki/docker-keycloak
  - kw_product_init https://github.com/pvarki/golang-kraftwerk-init-helper-cli
  - openldap https://github.com/pvarki/docker-openldap
  - miniwerk https://github.com/pvarki/python-rasenmaeher-miniwerk
  - ui https://github.com/pvarki/rasenmaeher-ui
  - takserver https://github.com/pvarki/docker-atak-server
  - takintegration https://github.com/pvarki/python-tak-rmapi


Running in local development mode
_________________________________

TLDR::

    alias rmdev="docker compose -p rmdev -f docker-compose-local.yml -f docker-compose-dev.yml"
    rmdev build
    rmdev up

or::

    alias rmlocal="docker compose -p rmlocal -f docker-compose-local.yml"
    rmlocal build
    rmlocal up

OpenLDAP and keycloak-init sometimes fail on first start, just run up again.

IMPORTANT: Only keep either rmlocal or rmdev created at one time or you may have weird network issues
run "down" for one env before starting the other.

Remember to run "down -v" if you want to reset the persistent volumes, or if you have weird issues when
switching between environments.

The dev version launches all the services and runs rasenmaeher-api in uvicorn reload mode so any edits
you make under /api will soon be reflected in the running instance.

If rasenmaeher-ui devel server complains make sure to delete ui/node_modules -directory from host first
the dockder node distribution probably is not compatible with whatever you have installed on the host.

pre-commit notes
----------------

Use "pre-commit run --all-files" liberally (and make sure you have run "pre-commit install"). If you get complaints
about missing environment variables run "source example_env.sh"


Integration tests
-----------------

Pytest is used to handle the integration tests, the requirements are in tests/requirements.txt.
NOTE: The tests have side-effects and expect a clean database to start with so always make sure
to run "down -v" for the composition first, then bring it back up before running integration tests.
