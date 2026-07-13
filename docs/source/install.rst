.. raw:: html

    <style>
      .heading {font-size: 34px; font-weight: 700;}
    </style>

.. role:: heading

:heading:`Getting Started`

Real Time Monitoring Information Systems


Prerequisite
------------

-  Docker > v19
-  Docker Compose > v2.1


Environment Setup
-----------------

Expected that PORT 5432 and 3000 are not being used by other services.

Start
^^^^^

The app's ``node_modules`` are kept in a named Docker volume that is
declared ``external``. Docker never creates an ``external`` volume
automatically, so on **every** operating system (Linux, macOS and Windows
alike) you must create it once before the first run — otherwise
``docker compose up`` aborts with an *"external volume not found"* error:

.. code:: bash

   docker volume create akvo-mis-docker-sync

Then start the stack:

.. code:: bash

   ./dc.sh up -d

.. note::
   The separate ``docker-sync`` tool is **not** required on any OS — the
   stack uses this named volume with native bind mounts. The legacy
   ``docker-sync.yml`` in the repo is only an optional file-sync
   accelerator for macOS/Windows Docker Desktop and can be ignored.

**Adjusting volume permissions on Linux.** On a standard Docker Engine setup
the frontend container runs as ``root`` and installs ``node_modules`` into the
volume without trouble. On some Linux configurations — rootless Docker,
user-namespace remapping, or an SELinux-enforcing host — the container cannot
write into the freshly created (root-owned) volume, and startup fails with a
*permission denied* / ``EACCES`` error while installing dependencies. Fix the
volume ownership with a throwaway container (no ``sudo`` needed, and no poking
around ``/var/lib/docker/volumes``):

.. code:: bash

   # Own the volume as your host user (fixes rootless / userns-remap setups)
   docker run --rm -v akvo-mis-docker-sync:/data alpine \
       chown -R "$(id -u):$(id -g)" /data

On an SELinux host the volume is readable but mislabeled; relabel it for
container access instead (run on the host, where ``chcon`` is available):

.. code:: bash

   sudo chcon -Rt svirt_sandbox_file_t \
       "$(docker volume inspect akvo-mis-docker-sync --format '{{.Mountpoint}}')"

Then re-run ``./dc.sh up -d``.

The app should be running at:
`localhost:3000 <http://localhost:3000>`__. Any endpoints with prefix -
``^/api/*`` is redirected to
`localhost:8000/api <http://localhost:8000/api>`__ -
``^/static-files/*`` is for worker service in
`localhost:8000 <http://localhost:8000/static-files>`__

Network Config: -
`setupProxy.js <https://github.com/akvo/akvo-mis/blob/main/frontend/src/setupProxy.js>`__
-
`mainnetwork <https://github.com/akvo/akvo-mis/blob/docker-compose.override.yml#L4-L8>`__
container setup

Log
^^^

.. code:: bash

   ./dc.sh log --follow <container_name>

Available containers: - backend - frontend - mainnetwork - db - pgadmin

Stop
^^^^

.. code:: bash

   ./dc.sh stop

Teardown
^^^^^^^^

.. code:: bash

   docker-compose down -v
   docker volume rm akvo-mis-docker-sync
