# -*- coding: utf-8 -*-
DEFAULT_JOB_NAME = "EnOSlib"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_NUMBER = 1
DEFAULT_CONFIGURE_NETWORK = False
DEFAULT_NETWORK = {"name": "containernet1"}

PROD = "prod"
NETWORK_TYPES = [PROD]

ROLES = "roles"
ROLES_SEPARATOR = "---"
CONTAINER_LABELS = "labels"
CONTAINER_STATUS = ["Running", "Creating"]
LEASE_ID = "lease_id"
