"""Deployment behavior: optional registration, upgrades and Compose wiring."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [ROOT / 'docker-compose.yml', ROOT / 'docker-compose-dev.yml', *[
    ROOT / 'deployment_scenarios' / f'docker-compose-{name}.yml' for name in (
        'biomero-client', 'biomero-only', 'for-ubuntu-with-SSL', 'from-dockerhub',
        'importer-only', 'with-restored-data',
    )
]]


@pytest.fixture
def startup(monkeypatch):
    spec = importlib.util.spec_from_file_location('analysis_startup', ROOT / 'web/54-configure-data-analysis.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = {
        'omero.web.apps': ['other_app', 'omero_biomero', module.APP],
        'omero.web.ui.center_plugins': [['Other', 'other.html', 'other_panel'], module.CENTER],
        'omero.web.ui.top_links': [['Other', 'other_index'], ['Analysis', 'omero_analysis_index', {}]],
    }
    monkeypatch.setattr(module, 'get_list', lambda key: state[key])
    monkeypatch.setattr(module, 'set_list', lambda key, value: state.__setitem__(key, value))
    monkeypatch.setattr(module, 'host_installed', lambda: True)
    monkeypatch.delenv('INTEGRATE_DATA_ANALYSIS', raising=False)
    monkeypatch.delenv('OMERO_ANALYSIS_DATA_QUERY_WORKER_URL', raising=False)
    monkeypatch.delenv('OMERO_ANALYSIS_DATA_QUERY_WORKER_TOKEN', raising=False)
    return module, state


@pytest.mark.parametrize('value', [None, '', 'FALSE', '0'])
def test_disabled_upgrade_removes_only_analysis(startup, monkeypatch, value):
    module, state = startup
    if value is not None:
        monkeypatch.setenv('INTEGRATE_DATA_ANALYSIS', value)
    monkeypatch.setattr(module, 'host_installed', lambda: pytest.fail('Disabled feature must not require a host'))
    module.configure()
    module.configure()
    assert state == {
        'omero.web.apps': ['other_app', 'omero_biomero'],
        'omero.web.ui.center_plugins': [['Other', 'other.html', 'other_panel']],
        'omero.web.ui.top_links': [['Other', 'other_index']],
    }


@pytest.mark.parametrize('value', ['TRUE', 'true', '1', 'yes', 'on'])
def test_demo_opt_in_is_idempotent_and_can_be_disabled(startup, monkeypatch, value):
    module, state = startup
    monkeypatch.setenv('INTEGRATE_DATA_ANALYSIS', value)
    module.configure()
    module.configure()
    assert state['omero.web.apps'].count(module.APP) == 1
    assert state['omero.web.ui.center_plugins'].count(module.CENTER) == 1
    assert state['omero.web.ui.top_links'] == [['Other', 'other_index']]
    monkeypatch.setenv('INTEGRATE_DATA_ANALYSIS', 'false')
    module.configure()
    assert module.APP not in state['omero.web.apps']


def test_enabled_missing_host_fails_before_changing_config(startup, monkeypatch):
    module, state = startup
    previous = state.copy()
    monkeypatch.setenv('INTEGRATE_DATA_ANALYSIS', 'TRUE')
    monkeypatch.setattr(module, 'host_installed', lambda: False)
    with pytest.raises(RuntimeError, match='compatible installed'):
        module.configure()
    assert state == previous


def test_worker_secret_required_only_when_enabled(startup, monkeypatch):
    module, state = startup
    monkeypatch.setenv('OMERO_ANALYSIS_DATA_QUERY_WORKER_URL', 'http://data-query-worker:8080')
    module.configure()  # Ordinary upgrades need no new secret.
    monkeypatch.setenv('INTEGRATE_DATA_ANALYSIS', 'TRUE')
    with pytest.raises(RuntimeError, match='DQW_API_TOKEN'):
        module.configure()
    assert module.APP not in state['omero.web.apps']
    monkeypatch.setenv('OMERO_ANALYSIS_DATA_QUERY_WORKER_TOKEN', 'synthetic-test-token')
    module.configure()
    assert module.APP in state['omero.web.apps']


@pytest.mark.parametrize('path', SCENARIOS, ids=lambda p: p.stem)
def test_scenarios_have_optional_worker_and_unique_mount_targets(path):
    services = yaml.safe_load(path.read_text())['services']
    assert services['data-query-worker']['profiles'] == ['analysis']
    assert '${OMERO_DATA_QUERY_WORKER_VERSION' in services['data-query-worker']['image']
    assert not services['data-query-worker'].get('ports')
    for service in services.values():
        targets = []
        for mount in service.get('volumes', []):
            if isinstance(mount, dict):
                targets.append(mount['target'])
            else:
                parts = mount.split(':')
                targets.append(parts[-2] if parts[-1] in {'ro', 'rw'} else parts[-1])
        assert len(targets) == len(set(targets)), targets
