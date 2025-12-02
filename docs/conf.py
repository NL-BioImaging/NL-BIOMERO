# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# Path setup
sys.path.insert(0, os.path.abspath('..'))

# Read version from .env file
def read_env_values():
    """Read all relevant values from .env file for use in documentation"""
    env_path = Path(__file__).parent.parent / '.env'
    values = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip()
    return values

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'NL-BIOMERO'
copyright = '2025, Core Facility Cellular Imaging'
author = 'Core Facility Cellular Imaging'

# Read all env values once
env_values = read_env_values()
version = env_values.get('NL_BIOMERO_VERSION', 'development')
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.githubpages',
    'myst_parser'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
    'titles_only': False
}

# RST substitutions - these can be used as |version| in any RST file
rst_prolog = f"""
.. |biomero_version| replace:: {env_values.get('BIOMERO_VERSION', 'unknown')}
.. |biomero_importer_version| replace:: {env_values.get('BIOMERO_IMPORTER_VERSION', 'unknown')}
.. |omero_forms_version| replace:: {env_values.get('OMERO_FORMS_VERSION', 'unknown')}
.. |omero_biomero_version| replace:: {env_values.get('OMERO_BIOMERO_VERSION', 'unknown')}

.. |biomero_badge| image:: https://img.shields.io/badge/BIOMERO.analyzer-{env_values.get('BIOMERO_VERSION', 'unknown').lstrip('v')}-purple?style=flat-square
   :alt: BIOMERO Version  
   :target: https://github.com/NL-BioImaging/biomero/releases

.. |biomero_importer_badge| image:: https://img.shields.io/badge/BIOMERO.importer-{env_values.get('BIOMERO_IMPORTER_VERSION', 'unknown')}-green?style=flat-square
   :alt: BIOMERO Importer Version
   :target: https://github.com/NL-BioImaging/BIOMERO.importer/releases

.. |omero_forms_badge| image:: https://img.shields.io/badge/OMERO.forms-{env_values.get('OMERO_FORMS_VERSION', 'unknown')}-orange?style=flat-square
   :alt: OMERO Forms Version
   :target: https://github.com/NL-BioImaging/OMERO.forms/releases

.. |omero_biomero_badge| image:: https://img.shields.io/badge/OMERO.biomero-{env_values.get('OMERO_BIOMERO_VERSION', 'unknown')}-red?style=flat-square
   :alt: OMERO Biomero Version
   :target: https://github.com/NL-BioImaging/OMERO.biomero/releases
"""

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'docker': ('https://docker-py.readthedocs.io/en/stable/', None),
    'omero': ('https://omero.readthedocs.io/en/stable/', None),
    'biomero': ('https://nl-bioimaging.github.io/biomero/', None)
}
