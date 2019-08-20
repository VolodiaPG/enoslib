import os

from enoslib.infra.enos_g5k.constants import SLASH_22


PROVIDER_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

######
DEFAULT_JOB_NAME = "EnOslib-distem"
DEFAULT_QUEUE = "default"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_IMAGE = "/grid5000/virt-images/debian9-x64-base.qcow2"
PLAYBOOK_PATH = os.path.join(PROVIDER_PATH, "ansible", "site.yml")


#: Sizes of the machines available for the configuration
FLAVOURS = {
    "tiny": {"core": 1, "mem": 512},
    "small": {"core": 1, "mem": 1024},
    "medium": {"core": 2, "mem": 2048},
    "big": {"core": 3, "mem": 3072},
    "large": {"core": 4, "mem": 4096},
    "extra-large": {"core": 6, "mem": 6144},
}

DEFAULT_FLAVOUR = "tiny", FLAVOURS["tiny"]

DEFAULT_NETWORKS = ["enos_network"]

DEFAULT_NUMBER = 1

DEFAULT_WORKING_DIR = "/tmp/enos_distem"

DEFAULT_SUBNET_TYPE = SLASH_22

DEFAULT_FORCE_DEPLOY = False

COORDINATOR_ROLE = "coordinator"
PATH_DISTEMD_LOGS = "/var/log/distem"
FILE_DISTEMD_LOGS = os.path.join(PATH_DISTEMD_LOGS, "distemd-coord.log")
SUBNET_NAME = "enoslib_distem_network"
