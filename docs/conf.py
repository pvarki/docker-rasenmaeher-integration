"""
Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# pylint: disable=invalid-name
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import textwrap
from pathlib import Path
import re

# FIXME: switch all the os.path stuff to use pathlib.Path

# define BASEDIR folder of the git repository
BASEDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # pylint: disable=E1101 # false positive
APIDIR = Path(__file__).parent.parent / "api"


sys.path.insert(0, os.path.abspath("."))  # pylint: disable=E1101 # false positive
sys.path.insert(0, os.path.abspath(".."))  # pylint: disable=E1101 # false positive

# -- Project information -----------------------------------------------------

project = "Rasenmaeher docs"
copyright = "2023, PVARKI"  # pylint: disable=W0622
author = "PVARKI"
tomltext = (APIDIR / "pyproject.toml").read_text(encoding="utf-8")
if match := re.search(r"^version\s*=\s*\"(.+)\"$", tomltext, re.MULTILINE):
    version = match.group(1)
else:
    version = "unresolved"
release = version  # FIXME: Should this be something else ??
language = "en"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    #'breathe',              # Doxygen C/C++ integration
    #'exhale',               # Doxygen Python integration
    "sphinx.ext.autodoc",  # Core Sphinx library for auto html doc generation from docstrings
    #'sphinx.ext.autosummary',  # Create neat summary tables for modules/classes/methods etc
    "sphinx.ext.intersphinx",  # Link to other project's documentation (see mapping below)
    "sphinx.ext.viewcode",  # Add a link to the Python source code for classes, functions etc.
    "sphinx_autodoc_typehints",  # Automatically document param types (less noise in class signature)
    #'sphinx_autopackagesummary',
    "sphinx_rtd_theme",  # Read The Docs theme
    "myst_parser",  # Markdown parsing
    "sphinx_sitemap",  # sitemap generation for SEO
    "autoapi.extension",
    "sphinxcontrib.mermaid",
]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}
autoapi_generate_api_docs = True

autosummary_generate = True  # Turn on sphinx.ext.autosummary
autoclass_content = "both"  # Add __init__ doc (ie. params) to class summaries
html_show_sourcelink = False  # Remove 'view source code' from top of page (for html, not python)
autodoc_inherit_docstrings = True  # If no docstring, inherit from base class
set_type_checking_flag = True  # Enable 'expensive' imports for sphinx_autodoc_typehints
nbsphinx_allow_errors = True  # Continue through Jupyter errors
autodoc_typehints = "description"  # Sphinx-native method. Not as good as sphinx_autodoc_typehints
add_module_names = False  # Remove namespaces from class/method signatures
autodoc_default_flags = [
    # Make sure that any autodoc declarations show the right members
    "members",
    "inherited-members",
    "private-members",
    "show-inheritance",
]

myst_enable_extensions = ["colon_fence"]
myst_html_meta = {
    "description": "docker-rasenmaeher-integration docs",
    "keywords": "docker-rasenmaeher-integration docs, documentation",
    "robots": "all,follow",
    "googlebot": "index,follow,snippet,archive",
    "property=og:locale": "en_US",
}

html_baseurl = "https://pvarki.github.io/docker-rasenmaeher-integration/docs"
sitemap_filename = "sitemap.xml"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
# exclude_patterns = []

# Setup the exhale extension
exhale_args = {
    # These arguments are required
    "containmentFolder": "./api",
    "rootFileName": "index.rst",
    "doxygenStripFromPath": "..",  # strip '..' from paths in xml
    # Suggested optional arguments
    "createTreeView": True,  # Create tree-view in sidebar
    # TIP: if using the sphinx-bootstrap-theme, you need
    # "treeViewIsBootstrap": True,
    "exhaleExecutesDoxygen": True,
    "exhaleDoxygenStdin": textwrap.dedent(
        """
        EXTRACT_ALL = YES
        SOURCE_BROWSER = YES
        EXTRACT_STATIC = YES
        OPTIMIZE_OUTPUT_FOR_C  = YES
        HIDE_SCOPE_NAMES = YES
        QUIET = YES
        INPUT = api cfssl miniwerk keycloak kw_product_init nginx openldap pg_init
        FILE_PATTERNS = *.py
        EXAMPLE_RECURSIVE = YES
        GENERATE_TREEVIEW = YES
    """
    ),
}
# -- c docs configuration ---------------------------------------------------

# Breathe Configuration
breathe_default_project = "api"  #
# breathe_build_directory = f"{BASEDIR}/build/docs/html/xml"
# breathe_separate_member_pages = True
# breathe_default_members = ('members', 'private-members', 'undoc-members')
# breathe_domain_by_extension = {
#    "py": "py",
# }
# breathe_implementation_filename_extensions = ['.py', '.py']
# breathe_doxygen_config_options = {}
breathe_projects = {
    "api": f"{BASEDIR}/docs/html/api/xml",
    "cfssl": f"{BASEDIR}/docs/html/cfssl/xml",
    "miniwerk": f"{BASEDIR}/docs/html/miniwerk/xml",
    "keycloak": f"{BASEDIR}/docs/html/keycloak/xml",
    "kw_product_init": f"{BASEDIR}/docs/html/kw_product_init/xml",
    "nginx": f"{BASEDIR}/docs/html/nginx/xml",
    "openldap": f"{BASEDIR}/docs/html/openldap/xml",
    "pg_init": f"{BASEDIR}/docs/html/pg_init/xml",
}

# autoapi_dirs = ['api', 'cfssl', 'miniwerk', 'keycloak', 'kw_product_init', 'nginx', 'openldap', 'pg_init']
autoapi_dirs = [
    "../api",
    "../cfssl",
    "../miniwerk",
    "../keycloak",
    "../kw_product_init",
    "../nginx",
    "../openldap",
    "../pg_init",
]
autoapi_root = "technical/api"
# only document files that have accompanying .cc files next to them
print("searching for py_docs...")
for root, _, files in os.walk(BASEDIR):  # pylint: disable=E1101 # false positive
    found = False
    breath_src = {}
    breathe_srcs_list = []

    for file in files:
        pyFile = os.path.join(root, file)[:-2] + ".py"  # pylint: disable=E1101 # false positive

        if os.path.exists(pyFile):  # pylint: disable=E1101 # false positive
            f = os.path.join(root, file)  # pylint: disable=E1101 # false positive

            parent_dir_abs = os.path.dirname(f)  # pylint: disable=E1101 # false positive
            parent_dir = parent_dir_abs[len(BASEDIR) + 1 :]
            parent_project = parent_dir.replace("/", "_")
            print(f"\tFOUND: {f} in {parent_project}")

            breathe_srcs_list.append(file)
            found = True

        if found:
            breath_src[parent_project] = (parent_dir_abs, breathe_srcs_list)
            breathe_projects.update({k: v[0] for k, v in breath_src.items()})  # mypy: ignore

print(f"breathe_projects_source: {breathe_projects.keys()}")

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"
html_show_copyright = True

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']
# html_logo = '_static/logo.png'
# html_favicon = '_static/favicon.ico'
html_theme_options = {
    "logo_only": False,
    "display_version": True,
    "vcs_pageview_mode": "blob",
    "style_nav_header_background": "#000000",
}
# html_extra_path = ['_static']

mermaid_params = ["-p", "puppeteer-config.json"]
