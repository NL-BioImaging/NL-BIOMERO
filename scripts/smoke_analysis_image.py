"""Check installed releases and actual OMERO CLI registration in a disposable image."""
import importlib.util
import json
import os
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys

from packaging.version import Version
from omero_analysis.host_capabilities import biomero_analysis_host_installed


def main():
    for package, variable in {
        'omero-biomero': 'OMERO_BIOMERO_VERSION',
        'omero-analysis': 'OMERO_ANALYSIS_VERSION',
        'biomero-workflow-skills': 'BIOMERO_WORKFLOW_SKILLS_VERSION',
    }.items():
        assert Version(version(package)) == Version(os.environ[variable]), package
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    import omero_analysis
    runtime = Path(omero_analysis.__file__).parent / 'static/omero_analysis/pyodide/pyodide.mjs'
    assert runtime.is_file(), 'Packaged browser runtime is missing'
    assert biomero_analysis_host_installed(), 'Released host is incomplete'

    spec = importlib.util.spec_from_file_location('analysis_startup', '/startup/54-configure-data-analysis.py')
    startup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(startup)
    # Model an existing configuration, including registrations from an older image.
    startup.set_list('omero.web.apps', ['omero_biomero', 'omero_figure', startup.APP])
    startup.set_list('omero.web.ui.center_plugins', [startup.CENTER])
    startup.set_list('omero.web.ui.top_links', [['Figure', 'figure_index'], ['Analysis', 'omero_analysis_index', {}]])
    os.environ.pop('INTEGRATE_DATA_ANALYSIS', None)
    startup.configure()
    assert startup.get_list('omero.web.apps') == ['omero_biomero', 'omero_figure']
    assert startup.get_list('omero.web.ui.center_plugins') == []
    assert startup.get_list('omero.web.ui.top_links') == [['Figure', 'figure_index']]
    os.environ['INTEGRATE_DATA_ANALYSIS'] = 'TRUE'
    startup.configure()
    startup.configure()
    assert startup.get_list('omero.web.apps').count(startup.APP) == 1
    assert startup.get_list('omero.web.ui.center_plugins') == [startup.CENTER]
    os.environ['INTEGRATE_DATA_ANALYSIS'] = 'FALSE'
    startup.configure()
    assert startup.APP not in startup.get_list('omero.web.apps')
    assert startup.get_list('omero.web.ui.center_plugins') == []
    print('Released packages, runtime, and disabled/enabled/disabled OMERO configuration passed')


if __name__ == '__main__':
    main()
