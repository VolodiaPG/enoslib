from itertools import islice
import logging
from pathlib import Path

import enoslib as en

en.init_logging(logging.INFO)

job_name = Path(__file__).name

CLUSTER = "parasilo"
SITE = "rennes"


prod_network = en.G5kNetworkConf(
    id="n1",
    type="prod",
    roles=["my_network"],
    site=SITE)
conf = (
    en.G5kConf
    .from_settings(
        job_type="allow_classic_ssh",
        job_name=job_name
    )
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_22",
        roles=["my_subnet"],
        site=SITE
    )
    .add_machine(
        roles=["role1"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["role2"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
 )

provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)

# Retrieving subnets
subnet = networks["my_subnet"]
logging.info(subnet)

# We describe the VMs types and placement in the following
# We build a VMonG5KConf with some extra fields:
# - undercloud: where the VMs should be placed (round robin)
# - macs: list of macs to take: on G5k the dhcp is configured to assign specific
#   ip based on the configured mac

n_vms = 16
virt_conf = (
    en.VMonG5kConf
    .from_settings(image="/grid5000/virt-images/debian11-x64-base.qcow2")
    # Starts some vms on a single role
    # Here that means start the VMs on a single machine
    .add_machine(
        roles=["vms"],
        number=n_vms,
        undercloud=roles["role1"],
        macs=list(islice(subnet[0].free_macs, n_vms))
        # alternative
        # macs=list(islice(en.mac_range(subnet), n_vms))
    )
    .finalize()
)

# Start them
vmroles = en.start_virtualmachines(virt_conf)
print(vmroles)
print(networks)