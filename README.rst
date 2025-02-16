.. image:: https://github.com/pvarki/docker-rasenmaeher-integration/actions/workflows/build.yml/badge.svg
   :alt: Build Status

========================
RASENMAEHER integrations
========================

"One Ring to rule them all, One Ring to find them, One Ring to bring them all and in the darkness bind them."

Docker compositions, helpers etc to bring it all together into something resembling grand old ones.


WTF is RASENMAEHER anyway ?
---------------------------

This `Disobey24 talk`_ explains a lot.

.. _`Disobey24 talk`: https://www.youtube.com/watch?v=m3xd7uygpaY&list=PLLvAhAn5sGfiB9AlEt2KD7H9Dnr6kbd64&index=23

Running Rasenmaher in your own docker environment
---------------------------------

Needed DNS Records pointing to wan address:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  - domain
  - kc.domain
  - tak.domain
  - mtls.domain
  - mtls.tak.domain
  - mtls.kc.domain
  - kc.tak.domain

Needed ports open to internet on firewall, with redirect to server running Rasenmaeher:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  - 80
  - 443
  - 8443
  - 8446
  - 9446
  - 4626

Downloading and composing Rasenmaeher
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Be mindfull on where you download the repository, you will need to perform rest of the commands inside the downloaded repository.

Getting the repository from github::

    git clone --recurse-submodules -j8 git@github.com:pvarki/docker-rasenmaeher-integration.git 

Create .env file that defines environmental variables for Rasenmaeher setup. File must be located inside downloaded repository and file type must be .env to work.

The original example file is: https://github.com/pvarki/docker-rasenmaeher-integration/blob/main/example_env.sh

Example .env-file with the minimal information needed::

    KEYCLOAK_DATABASE_PASSWORD="input-secure-password"
    RM_DATABASE_PASSWORD="input-secure-password"
    POSTGRES_PASSWORD="input-secure-password"
    LDAP_ADMIN_PASSWORD="input-secure-password"
    KEYCLOAK_ADMIN_PASSWORD="input-secure-password"
    TAK_DATABASE_PASSWORD="input-secure-password"
    SERVER_DOMAIN="input-domain"
    CFSSL_CA_NAME="input-ca-name"
    MW_LE_EMAIL="input-email-for-lets-encrypt"
    MW_LE_TEST="false"
    TAKSERVER_CERT_PASS="input-secure-password"
    TAK_CA_PASS="input-secure-password"
    VITE_ASSET_SET="${VITE_ASSET_SET:-neutral}"
    KEYCLOAK_PROFILEROOT_UUID="input-uuid"
    KEYCLOAK_HTTPS_KEY_STORE_PASSWORD="input-secure-password"
    KEYCLOAK_HTTPS_TRUST_STORE_PASSWORD="input-secure-password"

Starting the services::

    docker compose up –d 

Updating the repository from github::

    git submodule update

!DO NOT DO! Deleting the services. Deletes the certificates etc you will need to add all users etc again::

    docker compose down -v

Getting the admin login invite code for first admin::

    docker compose exec -it rmapi /bin/bash -c "rasenmaeher_api addcode" 

Services
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Rasenmaeher login page::

    https://domain (example.com)

Rasenmaeher home page::

    https://mtls.domain (mtls.example.com)

Takserver Admin UI::

    https://tak.domain:8443/ (tak.example.com:8443/)

Keycloack Admin UI. (Later group management will be withing Rasenmaeher)::

    https://kc.domain:9443/admin/RASENMAEHER/console/ (kc.example.com:9443/admin/RASENMAEHER/console/)

OTA update server inside takserver. Is located in the loaded repository, location depends on where you downloaded it::

    /home/user/docker-rasenmaeher-integration/takserver/update

Using the Rasenmaeher service:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Login with first admin code. Create your admin account by typing your first admin invite code and inputting desired admin callsign.
2. Create invite code for other users. Share the invite code. Go to Manage Users -> Add Users -> Create New Invite. Share link, qr code or invite code and domain.
3. Approve users in Rasenmaeher. Open approvement link or scan qr code from users and approve the user. You can also go to Approve Users -> Select Waiting User and input the users approvement code.
4. If desired promote some of the added users as admins. Go to Manage Users -> Manage Users -> Select user and select Promote. You can also Demote Admins or Delete users altogether.

Using Rasenmaeher TAK in EUD:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Login to Rasenmaeher. Go to https://mtls.domain and select TAK.
2. Download Client Package. Select tak package for desired software "Android ATAK or Windows WinTAK" or "iOS iTAK". Select Download Client Package.
3. Go to EUD's TAK Software. Import downloaded package. Device is connected to server.
4. You should also read Quickstart and Usage Guides.

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

Autogenerated (mostly API) docs
-------------------------------

  - Module API docs: https://pvarki.github.io/docker-rasenmaeher-integration/docs/
  - Swagger definition for RASENMAEHER API: https://pvarki.github.io/docker-rasenmaeher-integration/

Running in local development mode
---------------------------------

TLDR::

    alias rmdev="docker compose -p rmdev -f docker-compose-local.yml -f docker-compose-dev.yml"
    rmdev build takinit
    rmdev build
    rmdev up

or::

    alias rmlocal="docker compose -p rmlocal -f docker-compose-local.yml"
    rmlocal build takinit
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

Gaining first admin access in dev and production mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In dev mode::

    docker exec -it rmdev-rmapi-1 /bin/bash -c "source /.venv/bin/activate && rasenmaeher_api addcode"

Under dev mode, the UI runs at https://localmaeher.dev.pvarki.fi:4439.

In VM production mode::

    docker exec -it rmvm-rmapi-1 /bin/bash -c "rasenmaeher_api addcode"

pre-commit notes
----------------

Use "pre-commit run --all-files" liberally (and make sure you have run "pre-commit install"). If you get complaints
about missing environment variables run "source example_env.sh"


Integration tests
-----------------

Pytest is used to handle the integration tests, the requirements are in tests/requirements.txt.
NOTE: The tests have side-effects and expect a clean database to start with so always make sure
to run "down -v" for the composition first, then bring it back up before running integration tests.
