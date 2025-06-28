.. image:: https://github.com/pvarki/docker-rasenmaeher-integration/actions/workflows/build.yml/badge.svg
   :alt: Build Status

==========
Deploy App
==========

"One Ring to rule them all, One Ring to find them, One Ring to bring them all and in the darkness bind them."

Docker compositions, helpers etc to bring it all together into something resembling grand old ones.

Codename RASENMAEHER because infantry jokes.

WTF is this anyway ?
--------------------

This `Disobey24 talk`_ explains a lot.

.. _`Disobey24 talk`: https://www.youtube.com/watch?v=m3xd7uygpaY&list=PLLvAhAn5sGfiB9AlEt2KD7H9Dnr6kbd64&index=23



Running Deploy App in your own docker environment
-------------------------------------------------


Needed DNS Records
^^^^^^^^^^^^^^^^^^

These need to point to your WAN address.

  - domain
  - kc.domain
  - tak.domain
  - bl.domain
  - mtls.domain
  - mtls.tak.domain
  - mtls.kc.domain
  - mtls.bl.domain
  - kc.tak.domain

When more products are added to the deployment they will follow the same naming pattern, you will need subdomains
for all products listed in the composition for miniwerk service variable MW_PRODUCTS and "kc" for Keycloak.

Needed ports open
^^^^^^^^^^^^^^^^^

And redirected to the server if behind NAT or similar.

  - 80
  - 443
  - 8443 (TAK)
  - 8446 (TAK)
  - 9446 (Keycloak)
  - 4626 (Product integration APIs port)
  - 4666 (Battlelog API/UI port)

Downloading and composing Deploy App
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Be mindfull on where you download the repository, you will need to perform rest of the commands inside the downloaded repository.

Getting the repository from github (on Windows **first** see "Windows notes" below)::

    git clone --recurse-submodules -j8 git@github.com:pvarki/docker-rasenmaeher-integration.git

Create ``.env`` file that defines environmental variables for Deploy App setup. File must be located inside downloaded repository
and file type must be named literally ``.env`` (not ``something.env``)  to work.

The original example file is: https://github.com/pvarki/docker-rasenmaeher-integration/blob/main/example_env.sh

Example .env-file with the minimal information needed::

    KEYCLOAK_DATABASE_PASSWORD="input-secure-password"  # pragma: allowlist secret
    RM_DATABASE_PASSWORD="input-secure-password"  # pragma: allowlist secret
    POSTGRES_PASSWORD="input-secure-password"  # pragma: allowlist secret
    LDAP_ADMIN_PASSWORD="input-secure-password"  # pragma: allowlist secret
    KEYCLOAK_ADMIN_PASSWORD="input-secure-password"  # pragma: allowlist secret
    TAK_DATABASE_PASSWORD="input-secure-password"  # pragma: allowlist secret
    SERVER_DOMAIN="input-domain"
    CFSSL_CA_NAME="input-ca-name"
    MW_LE_EMAIL="input-email-for-lets-encrypt"
    MW_LE_TEST="false"
    TAKSERVER_CERT_PASS="input-secure-password"  # pragma: allowlist secret
    TAK_CA_PASS="input-secure-password"  # pragma: allowlist secret
    VITE_ASSET_SET="${VITE_ASSET_SET:-neutral}"
    KEYCLOAK_PROFILEROOT_UUID="input-uuid"
    KEYCLOAK_HTTPS_KEY_STORE_PASSWORD="input-secure-password"  # pragma: allowlist secret
    KEYCLOAK_HTTPS_TRUST_STORE_PASSWORD="input-secure-password"  # pragma: allowlist secret
    BL_POSTGRES_PASSWORD="input-secure-password"  # pragma: allowlist secret
    RMMTX_POSTGRES_PASSWORD="input-secure-password"  # pragma: allowlist secret

Replace "intput-secure-password" with a good passphrase that is unique for each replacment.

If you wish to use one deployment for longer than the *design lifetime* of 1-2 months you can change the following
env variables. But do understand that this is **not recommended** and has **security implications**. If you do this
**you** take **responsibility** to go through all Dockerfiles and compositions to understand **exactly** how things are done
and how apply security updates into the containers::

    CFSSL_CA_EXPIRY="8800h" # Input time in hours = xxh, 8800h is 366.. days
    CFSSL_SIGN_DEFAULT_EXPIRY="8800h" # Input time in hours = xxh, 8800h is 366.. days

Starting the services::

    docker compose up -d

Updating the repository from github::

    git submodule update

!DO NOT DO! Deleting the services. Deletes the certificates etc you will need to add all users etc again::

    docker compose down -v

Getting the admin login invite code for first admin::

    docker compose exec -it rmapi /bin/bash -c "rasenmaeher_api addcode"

If you get "no such service -d", make sure whatever you copy-pasted the command from did not render
the dash (ASCII 0x2D) as some other codepoint with a glyph that looks deceptively similar. When in doubt
write the commands yourself instead of copy-pasting.

Services
^^^^^^^^

Deploy App login page::

    https://domain (example.com)

Deploy App home page::

    https://mtls.domain (mtls.example.com)

Takserver Admin UI::

    https://tak.domain:8443/ (tak.example.com:8443/)

Keycloack Admin UI. (Later group management will be withing Deploy App)::

    https://kc.domain:9443/admin/RASENMAEHER/console/ (kc.example.com:9443/admin/RASENMAEHER/console/)

OTA update server inside takserver. Is located in the loaded repository, location depends on where you downloaded it::

    /home/user/docker-rasenmaeher-integration/takserver/update

Using the Deploy App service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Login with first admin code. Create your admin account by typing your first admin invite code and inputting desired admin callsign.
2. Create invite code for other users. Share the invite code. Go to Manage Users -> Add Users -> Create New Invite. Share link, qr code or invite code and domain.
3. Approve users in Deploy App. Open approvement link or scan qr code from users and approve the user. You can also go to Approve Users -> Select Waiting User and input the users approvement code.
4. If desired promote some of the added users as admins. Go to Manage Users -> Manage Users -> Select user and select Promote. You can also Demote Admins or Delete users altogether.

Using Deploy App TAK in EUD
^^^^^^^^^^^^^^^^^^^^^^^^^^^

EUD=End User Device

1. Login to Deploy App. Go to https://mtls.domain and select TAK.
2. Download Client Package. Select tak package for desired software "Android ATAK or Windows WinTAK" or "iOS iTAK". Select Download Client Package.
3. Go to EUD's TAK Software. Import downloaded package. Device is connected to server.
4. You should also read Quickstart and Usage Guides.

Git submodules
--------------

When cloning for the first time use::

    git clone --recurse-submodules -j8 git@github.com:pvarki/docker-rasenmaeher-integration.git

When updating or checking out branches use::

    git submodule update --init --recursive

And if you forgot to --recurse-submodules run the update command above.

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
  - battlelog https://github.com/pvarki/typescript-liveloki-app

Autogenerated (mostly API) docs
-------------------------------

  - Module API docs: https://pvarki.github.io/docker-rasenmaeher-integration/docs/
  - Swagger definition for Deploy App API: https://pvarki.github.io/docker-rasenmaeher-integration/


Running in local development mode
---------------------------------

Windows notes
^^^^^^^^^^^^^

  1. Do **NOT** use git-bash, it will cause *weirdest* issues with Docker containers
  2. Use WSL, see best_practises_ -repo for instructions on how to set it up.
  3. Make sure whatever git client or IDE you use it does not mess with line-endings, for CLI client this does the trick::

      git config --global core.eol lf
      git config --global core.autocrlf false

.. _best_practises: https://github.com/pvarki/markdown-pvarki-best_practises

Compositions
^^^^^^^^^^^^

Generally start with "rmlocal", it corresponds best to a real running environment.
"rmdev" starts a bunch of things in development mode which does make developing more convenient
but also introduces extra variability to how things work.

Make sure to always check your changes work correctly in rmlocal mode where assets
are minified and baked in.

TLDR::

    alias rmlocal="docker compose -p rmlocal -f docker-compose-local.yml"
    rmlocal build takinit
    rmlocal build
    rmlocal up

or::

    alias rmdev="docker compose -p rmdev -f docker-compose-local.yml -f docker-compose-dev.yml"
    rmdev build takinit
    rmdev build
    rmdev up


OpenLDAP and keycloak-init sometimes fail on first start, just run up again.

IMPORTANT: Only keep either rmlocal or rmdev created at one time or you may have weird network issues
run "down" for one env before starting the other.

Remember to run "down -v" if you want to reset the persistent volumes, or if you have weird issues when
switching between environments.

The dev version launches all the services and runs rasenmaeher-api in uvicorn reload mode so any edits
you make under /api will soon be reflected in the running instance.

If rasenmaeher-ui devel server complains make sure to delete ``ui/node_modules`` -directory from host first.
The docker NodeJS distribution probably is not compatible with whatever you have installed on the host.

Gaining first admin access in dev and production mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In dev mode::

    docker exec -it rmdev-rmapi-1 /bin/bash -c "source /.venv/bin/activate && rasenmaeher_api addcode"

Under dev mode, the UI runs at https://localmaeher.dev.pvarki.fi:4439.

In VM production mode::

    docker exec -it rmvm-rmapi-1 /bin/bash -c "rasenmaeher_api addcode"

pre-commit notes
----------------

Use "pre-commit run --all-files" liberally (and make sure you have run "pre-commit install --install-hooks"). If you get complaints
about missing environment variables run "source example_env.sh"


Integration tests
-----------------

Pytest is used to handle the integration tests, the requirements are in tests/requirements.txt.
NOTE: The tests have side-effects and expect a clean database to start with so always make sure
to run "down -v" for the composition first, then bring it back up before running integration tests.
