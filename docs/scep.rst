====
SCEP
====

MDM driven device enrolment. An operator adds an Android phone to whatever MDM a unit already
runs, and the phone comes out a provisioned Deploy App user: a client certificate whose private
key was generated on the device, and no application of ours on the phone.

The responder is `python-rasenmaeher-scep`_, composed here as ``rmscep``.

.. _python-rasenmaeher-scep: https://github.com/pvarki/python-rasenmaeher-scep

How it fits together
--------------------

The MDM proxies each device's certificate request to ``https://<domain>/scep``; the phone never
reaches us directly. The responder unwraps the request and asks RASENMAEHER to complete an
enrolment an admin already planned. RASENMAEHER is the certificate authority; nothing is signed in
the responder.

What it may do is one line of RASENMAEHER configuration. ``RM_MDM_AGENT_CNS`` lists the certificate
common names allowed to complete a planned enrolment, and ``rmscep`` is on it. It cannot create a
callsign, approve anything a human started, revoke, promote or sign. It is deliberately **not** a
kraftwerk product: a product common name may have any certificate request signed whatever its
subject, skips role checks, and cannot be revoked at the edge, which is far more than this needs.

Two containers
--------------

``scepinit``
    Runs once, gets the client identity signed by the deployment CA, and exits. It is separate so
    the long running responder never sits on the CA network, where anything can have a certificate
    signed for an arbitrary subject.

``rmscep``
    The responder. On ``scepnet``, whose only other member is ``rmnginx``, so it cannot reach
    ``rmapi`` directly. It talks to RASENMAEHER the way any mTLS client does, through the proxy.

Configuration
-------------

``RMSCEP_CHALLENGE`` is the only thing an operator sets, in ``.env``. It is **not a secret**: it
ends up in the MDM's own configuration and travels in every device's request. It keeps noise off
the endpoint; the control is that an admin planned the callsign, and that lives in RASENMAEHER.
Leave it empty and the responder runs but refuses to enrol anything.

The endpoint is rate limited in nginx, and the upstream is resolved per request, so a responder
that is down or absent costs a 502 on ``/scep`` and nothing else.

What the devices get
--------------------

A phone that enrols is not useful until it has the deployment's applications, the permissions they
need, and a browser willing to present the certificate. That is stated to the MDM once, from
``mdm/template.json``::

    docker compose run --rm \
      -e RMSCEP_MDM_URL=https://<your mdm> \
      -e RMSCEP_MDM_TOKEN_FILE=/run/secrets/mdm_token \
      -v /path/to/token:/run/secrets/mdm_token:ro \
      rmscep rmscep mdm-apply

The token is passed at run time and never mounted into the running responder. Something that
holds an MDM's API token, and can therefore reach every device a unit owns, has no business also
being an internet facing parser.

``mdm/template.json`` is deployment data, not responder code. The responder knows no package name
at all, and a test enforces that, so changing what is installed is an edit to that file and
nothing else.

**Applications install at enrolment and at no other time.** This is a property of managed Android,
not a choice. A device that has already joined will not pick up a template applied afterwards: it
has to enrol again, under a callsign that has not been spent. Arm the team first, then enrol.

Two halves make the browser present the certificate, and both are in the template. The policy's
key selection rules settle which key may be used, without which a certificate installed by the
MDM belongs to the installing app and nothing else can see it. The browser's own
``AutoSelectCertificateForUrls`` then settles whether it sends one at all; with no matching entry
it silently declines, and the proxy answers that exactly as it answers a missing certificate.
