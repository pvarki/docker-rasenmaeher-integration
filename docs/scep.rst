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
