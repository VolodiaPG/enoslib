import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# claim the resources
network = en.G5kNetworkConf(type="prod", roles=["my_network"], site="rennes")

conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name, walltime="0:10:00")
    .add_network_conf(network)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["control", "network"],
        cluster="paravance",
        nodes=1,
        primary_network=network,
    )
)


provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
