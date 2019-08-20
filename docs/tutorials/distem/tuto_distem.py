from enoslib.api import run_command
from enoslib.infra.enos_distem.provider import Distem
from enoslib.infra.enos_distem.configuration import Configuration

import logging
import os


FORCE = True

logging.basicConfig(level=logging.DEBUG)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_name="wip-distem",
                                   force_deploy=FORCE,
                                   gateway="access.grid5000.fr",
                                   gateway_user="msimonin")\
    .add_machine(roles=["compute"],
                 cluster="parapide",
                 number=1,
                 flavour="tiny")\
    .add_machine(roles=["controller"],
                 cluster="parapide",
                 number=5,
                 flavour="tiny")\
    .finalize()
provider = Distem(conf)

roles, networks = provider.init()

print(roles)
print(networks)
result = run_command("date", roles=roles)
