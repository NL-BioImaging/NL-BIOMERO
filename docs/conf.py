# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import re
from pathlib import Path

# Path setup
sys.path.insert(0, os.path.abspath('..'))

def read_env_at_render_time():
    """Read .env file at render time (when working directory is historical checkout)"""
    values = {}
    
    # Try multiple .env locations
    env_paths = ['.env', '../.env', '../../.env']
    
    env_path = None
    for path in env_paths:
        if os.path.exists(path):
            env_path = path
            break
    
    if env_path and os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip().strip('"\'')
    
    return values

# Fallback env reading for basic config (will be overridden by custom directive)
def read_env_values_fallback():
    """Fallback for basic config - just use current directory"""
    values = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip().strip('"\'')
    return values

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'NL-BIOMERO'
copyright = '2025, Core Facility Cellular Imaging'
author = 'Core Facility Cellular Imaging'

# Use fallback env reading for basic version info
env_values = read_env_at_render_time() 
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
    'myst_parser',
    'sphinxcontrib.mermaid',
    'sphinx_multiversion'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Sphinx-multiversion configuration --------------------------------------  
# Get latest release from environment (set by GitHub Actions)
def get_latest_release_locally():
    """Get latest release tag for local development"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', 'v*.*.*'], 
            capture_output=True, text=True, check=True
        )
        tags = [tag for tag in result.stdout.strip().split('\n') if tag and re.match(r'^v[0-9]+\.[0-9]+\.[0-9]+$', tag)]
        if tags:
            # Sort and get latest
            sorted_tags = sorted(tags, key=lambda x: [int(i) for i in x.lstrip('v').split('.')])
            return sorted_tags[-1]
    except:
        pass
    return 'v1.0.0'  # Ultimate fallback

latest_release = os.environ.get('LATEST_RELEASE_TAG', get_latest_release_locally())

# Extract major version from latest release for dynamic patterns
latest_major = latest_release.lstrip('v').split('.')[0] if latest_release else '1'

# Build tag whitelist dynamically: all X.Y.0 versions + current latest release
smv_tag_whitelist = rf'^v{re.escape(latest_major)}\.[0-9]+\.0$|^{re.escape(latest_release)}$'
smv_branch_whitelist = r'^master$'                 # Include master branch  
smv_remote_whitelist = None                        # Only use local tags/branches

# Pattern for released versions (dynamic major version)
smv_released_pattern = rf'^refs/tags/v{re.escape(latest_major)}\.[0-9]+\.0$'

# Display versions as v1.2, v1.3 (use ref name for now, we'll customize display in templates)
smv_outputdir_format = '{ref.name}'  # v1.2.0, v1.3.0 (will handle display in templates)

# Latest stable version (use actual latest release)
smv_latest_version = latest_release

# Display versions as v1.2, v1.3 (use ref name for now, we'll customize display in templates)
smv_outputdir_format = '{ref.name}'  # v1.2.0, v1.3.0 (will handle display in templates)

# Latest stable version (use actual latest release, not .0 version)
smv_latest_version = latest_release

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Setup custom extensions
def setup(app):
    # Set up dynamic RST prolog before building starts
    app.connect('config-inited', lambda app, config: setup_dynamic_rst_prolog(app))

# Search configuration - ensure search index is built
html_search_language = 'en'

# Fix jQuery not being included - needed for search functionality
html_js_files = [
    'https://code.jquery.com/jquery-3.6.0.min.js',
]

html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
    'titles_only': False
}

# RST substitutions - will be set dynamically during build process
rst_prolog = ""  # Initially empty, will be populated by setup_dynamic_rst_prolog()

def setup_dynamic_rst_prolog(app):
    """Dynamically update RST prolog with current environment values"""
    env_values = read_env_at_render_time()
    
    # Create dynamic badge substitutions that read from current checkout's .env
    biomero_version = env_values.get('BIOMERO_VERSION', 'unknown')
    biomero_importer_version = env_values.get('BIOMERO_IMPORTER_VERSION', 'unknown') 
    omero_forms_version = env_values.get('OMERO_FORMS_VERSION', 'unknown')
    omero_biomero_version = env_values.get('OMERO_BIOMERO_VERSION', 'unknown')
    
    # Clean versions for badges (remove 'v' prefix)
    clean_biomero = biomero_version.lstrip('v') if biomero_version.startswith('v') else biomero_version
    clean_importer = biomero_importer_version.lstrip('v') if biomero_importer_version.startswith('v') else biomero_importer_version
    clean_forms = omero_forms_version.lstrip('v') if omero_forms_version.startswith('v') else omero_forms_version  
    clean_omero_biomero = omero_biomero_version.lstrip('v') if omero_biomero_version.startswith('v') else omero_biomero_version
    
    # Create version tags for links (ensure 'v' prefix)
    tag_biomero = biomero_version if biomero_version.startswith('v') else f'v{biomero_version}'
    tag_importer = biomero_importer_version if biomero_importer_version.startswith('v') else f'v{biomero_importer_version}'
    tag_forms = omero_forms_version if omero_forms_version.startswith('v') else f'v{omero_forms_version}'
    tag_omero_biomero = omero_biomero_version if omero_biomero_version.startswith('v') else f'v{omero_biomero_version}'
    
    # Update the config's rst_prolog
    app.config.rst_prolog = f"""
.. |biomero_version| replace:: {biomero_version}
.. |biomero_importer_version| replace:: {biomero_importer_version}
.. |omero_forms_version| replace:: {omero_forms_version}
.. |omero_biomero_version| replace:: {omero_biomero_version}

.. |biomero_badge| image:: https://img.shields.io/badge/BIOMERO.analyzer-{clean_biomero}-purple?style=flat-square
   :alt: BIOMERO Version  
   :target: https://github.com/NL-BioImaging/biomero/releases/tag/{tag_biomero}

.. |biomero_importer_badge| image:: https://img.shields.io/badge/BIOMERO.importer-{clean_importer}-green?style=flat-square
   :alt: BIOMERO Importer Version
   :target: https://github.com/NL-BioImaging/BIOMERO.importer/releases/tag/{tag_importer}

.. |omero_forms_badge| image:: https://img.shields.io/badge/OMERO.forms-{clean_forms}-orange?style=flat-square
   :alt: OMERO Forms Version
   :target: https://github.com/NL-BioImaging/OMERO.forms/releases/tag/{tag_forms}

.. |omero_biomero_badge| image:: https://img.shields.io/badge/OMERO.biomero-{clean_omero_biomero}-red?style=flat-square
   :alt: OMERO Biomero Version
   :target: https://github.com/NL-BioImaging/OMERO.biomero/releases/tag/{tag_omero_biomero}

.. |biomero_icon| raw:: html

   <img src="https://raw.githubusercontent.com/NL-BioImaging/OMERO.biomero/refs/tags/v1.2.1/webapp/src/img/biomero-logo.svg" alt="BIOMERO" style="height:1em; width:auto; vertical-align:middle; display:inline-block; margin:0 2px;">

.. |biomero_2_0| raw:: html

   <span style="white-space:nowrap"><img src="https://raw.githubusercontent.com/NL-BioImaging/OMERO.biomero/refs/tags/v1.2.1/webapp/src/img/biomero-logo.svg" alt="BIOMERO" style="height:1em; width:auto; vertical-align:middle; display:inline-block; margin:0 2px;"> BIOMERO 2.0</span>
"""

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'docker': ('https://docker-py.readthedocs.io/en/stable/', None),
    'omero': ('https://omero.readthedocs.io/en/stable/', None),
    'biomero': ('https://nl-bioimaging.github.io/biomero/', None)
}
