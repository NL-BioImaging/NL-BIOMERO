System Administration Guide
===========================

Deployment, configuration and operation of NL-BIOMERO. Start with the core
setup before enabling dependent features. The demo opts into the supplied
features; existing deployments should follow each feature's enablement guide.

* :doc:`development-setup` — local development/demo setup
* :doc:`deployment` — full NL-BIOMERO deployment
* :doc:`docker-compose-scenarios` — container orchestration options
* :doc:`linux-deployment` — Linux deployment
* :doc:`slurm-integration` — connect BIOMERO.analyzer to the HPC cluster
* :doc:`omero-biomero-admin` — configure the Analyzer and Importer interfaces
* :doc:`analyzer-importer-admin` — shared-storage result import; prerequisite for Zarr workflows and shallow storage
* :doc:`remote-shallower` — reduce duplicate result storage; select local or remote processing
* :doc:`detached-workflows` — continue analysis after the submitting session ends
* :doc:`resumable-uploader` — browser uploads into the importer
* :doc:`metabase-admin` — workflow and importer dashboards
* :doc:`ui-customization` — adapt the interface
* :doc:`backup-restore` — data protection and recovery
* :doc:`metadata-refresh` — explicitly requested annotation maintenance
