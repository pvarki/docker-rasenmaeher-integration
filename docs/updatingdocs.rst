Updating docs
=============

The documentation is autobuilt using github action `.github/docs.yml <https://github.com/pvarki/docker-rasenmaeher-integration/blob/main/.github/workflows/docs.yml>`_ on every push to the main branch docs get built and pushed to gh-pages branch.
Workflow runs visible at `https://github.com/pvarki/docker-rasenmaeher-integration/actions<https://github.com/pvarki/docker-rasenmaeher-integration/actions>`_.
Documentation is then visible at `https://pvarki.github.io/docker-rasenmaeher-integration/docs <https://pvarki.github.io/docker-rasenmaeher-integration/docs>`_.

Adding new documentation
------------------------
Add new file to the `docs` directory and add a reference to it in the `index.rst` file.
For example newpage.md or newpage.rst depending on the formatting you prefer.


Testing the documentation locally
----------------------------------

Docs are built using Sphinx. To update the docs, follow these steps:

1. Ensure you have ``doxygen`` installed. If not, install it using Homebrew:

   .. code-block:: bash

      brew install doxygen

2. Navigate to the ``docs`` directory:

   .. code-block:: bash

      cd docs

3. Create a virtual environment for the documentation project:

   .. code-block:: bash

      python -m venv venv

4. Activate the virtual environment:

   .. code-block:: bash

      source venv/bin/activate

5. Install the required Python packages:

   .. code-block:: bash

      pip install -r requirements.txt

6. Build the HTML documentation:

   .. code-block:: bash

      make html

7. Open the documentation in your browser:

   .. code-block:: bash

      open build/html/index.html

Formatting for reStructuredText
-------------------------------
- `Li-Pro.Net Sphinx Primer ( best formatting tutorial ) <https://lpn-doc-sphinx-primer-devel.readthedocs.io/index.html>`_
- `reStructuredText Primer <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_

Formatting for Markdown
----------------------
- `Markdown Cheatsheet <https://www.markdownguide.org/cheat-sheet/>`_
- `Markdown Guide <https://www.markdownguide.org/>`_