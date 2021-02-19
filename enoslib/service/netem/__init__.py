from enoslib.service.netem.netem import NetemInConstraint, NetemInOutSource, NetemOutConstraint
import logging
import os
import re
from typing import Any, Dict, List, Mapping

from enoslib.api import run_ansible, play_on
from enoslib.constants import TMP_DIRNAME
from enoslib.objects import Host, Network, Networks, Roles
from .htb import HTBSource, netem_htb
from .utils import _build_options
from enoslib.utils import _check_tmpdir
from jsonschema import validate

from ..service import Service
from .schema import SCHEMA
from .netem import netem

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
PLAYBOOK = os.path.join(SERVICE_PATH, "netem.yml")
TMP_DIR = os.path.join(os.getcwd(), TMP_DIRNAME)


logger = logging.getLogger(__name__)


def expand_groups(grp):
    """Expand group names.

    Args:
        grp (string): group names to expand

    Returns:
        list of groups

    Examples:

        * grp[1-3] will be expanded to [grp1, grp2, grp3]
        * grp1 will be expanded to [grp1]
    """
    p = re.compile(r"(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\]")
    m = p.match(grp)
    if m is not None:
        s = int(m.group("start"))
        e = int(m.group("end"))
        n = m.group("name")
        return list(map(lambda x: n + str(x), range(s, e + 1)))
    else:
        return [grp]


def _expand_description(desc):
    """Expand the description given the group names/patterns
    e.g:
    {src: grp[1-3], dst: grp[4-6] ...} will generate 9 descriptions
    """
    srcs = expand_groups(desc["src"])
    dsts = expand_groups(desc["dst"])
    descs = []
    for src in srcs:
        for dst in dsts:
            local_desc = desc.copy()
            local_desc["src"] = src
            local_desc["dst"] = dst
            descs.append(local_desc)

    return descs


def _src_equals_dst_in_constraints(network_constraints, grp1):
    if "constraints" in network_constraints:
        constraints = network_constraints["constraints"]
        for desc in constraints:
            descs = _expand_description(desc)
            for d in descs:
                if grp1 == d["src"] and d["src"] == d["dst"]:
                    return True
    return False


def _same(g1, g2):
    """Two network constraints are equals if they have the same
    sources and destinations
    """
    return g1["src"] == g2["src"] and g1["dst"] == g2["dst"]


def _generate_default_grp_constraints(roles, network_constraints):
    """Generate default symetric grp constraints."""
    default_delay = network_constraints.get("default_delay")
    default_rate = network_constraints.get("default_rate")
    default_loss = network_constraints.get("default_loss", 0)
    except_groups = network_constraints.get("except", [])
    grps = network_constraints.get("groups", roles.keys())
    # expand each groups
    grps = [expand_groups(g) for g in grps]
    # flatten
    grps = [x for expanded_group in grps for x in expanded_group]
    # building the default group constraints
    return [
        {
            "src": grp1,
            "dst": grp2,
            "delay": default_delay,
            "rate": default_rate,
            "loss": default_loss,
        }
        for grp1 in grps
        for grp2 in grps
        if (
            (grp1 != grp2 or _src_equals_dst_in_constraints(network_constraints, grp1))
            and grp1 not in except_groups
            and grp2 not in except_groups
        )
    ]


def _generate_actual_grp_constraints(network_constraints):
    """Generate the user specified constraints"""
    if "constraints" not in network_constraints:
        return []

    constraints = network_constraints["constraints"]
    actual = []
    for desc in constraints:
        descs = _expand_description(desc)
        for desc in descs:
            actual.append(desc)
            if "symetric" in desc and desc["symetric"]:
                sym = desc.copy()
                sym["src"] = desc["dst"]
                sym["dst"] = desc["src"]
                actual.append(sym)
    return actual


def _merge_constraints(constraints, overrides):
    """Merge the constraints avoiding duplicates
    Change constraints in place.
    """
    for o in overrides:
        i = 0
        while i < len(constraints):
            c = constraints[i]
            if _same(o, c):
                constraints[i].update(o)
                break
            i = i + 1


def _build_grp_constraints(roles, network_constraints):
    """Generate constraints at the group level,
    It expands the group names and deal with symetric constraints.
    """
    # generate defaults constraints
    constraints = _generate_default_grp_constraints(roles, network_constraints)
    # Updating the constraints if necessary
    if "constraints" in network_constraints:
        actual = _generate_actual_grp_constraints(network_constraints)
        _merge_constraints(constraints, actual)

    return constraints


def _build_ip_constraints(
    roles: Roles, networks: Networks, constraints: Mapping
) -> List[HTBSource]:
    """Generate the constraints at the ip/device level.

    Those constraints are those used by ansible to enforce tc/netem rules.
    """
    host_htbs = []
    for constraint in constraints:
        gsrc = constraint["src"]
        gdst = constraint["dst"]
        gdelay = constraint["delay"]
        grate = constraint["rate"]
        gloss = constraint["loss"]
        for source_host in roles[gsrc]:
            # one possible source

            # 1) we get all the devices for the wanted networks
            nets = None
            if "networks" in constraints and networks is not None:
                _netss = [
                    networks
                    for role, networks in networks.items()
                    if {role}.issubset(set(constraints["networks"]))
                ]
                nets = []
                for _nets in _netss:
                    nets.extend(_nets)
            local_devices = source_host.filter_interfaces(nets, include_unknown=False)

            host_htb = HTBSource(host=source_host)
            for sdevice in local_devices:
                # one possible device
                for d in roles[gdst]:
                    # one possible destination
                    dall_addrs = d.filter_addresses(nets, include_unknown=False)
                    # Let's keep docker bridge out of this
                    for daddr in dall_addrs:
                        assert daddr.ip is not None
                        host_htb.add_constraint(
                            target=str(daddr.ip.ip),
                            device=str(sdevice),
                            delay=gdelay,
                            rate=grate,
                            loss=gloss,
                        )
            host_htbs.append(host_htb)
    return host_htbs


def _validate(
    roles: Roles, output_dir: str, all_addresses: List[str], extra_vars: Dict = None
):
    logger.debug("Checking the constraints")
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), TMP_DIRNAME)
    if not extra_vars:
        extra_vars = {}

    output_dir = os.path.abspath(output_dir)
    _check_tmpdir(output_dir)
    _playbook = os.path.join(SERVICE_PATH, "netem.yml")
    options = _build_options(
        extra_vars,
        dict(
            enos_action="tc_validate",
            tc_output_dir=output_dir,
            all_addresses=all_addresses,
        ),
    )
    run_ansible([_playbook], roles=roles, extra_vars=options)


class SimpleNetem(Service):
    def __init__(
        self, options: str, hosts: List[Host], networks: List[Network], symetric: bool=False, extra_vars=None
    ):
        """Set homogeneous network constraints between your hosts.

        Geometricaly speaking: nodes are put on the vertices of a regular
        n-simplex.

        Setting bandwith/delay limitations is about running:

        .. code-block:: bash

            tc qdisc add dev <device_name> root netem <netem_options>

        If you live in an ideal world, you'll know in advance the mapping
        between nodes and interface names and you probably won't need this
        Service. Just run the above command on each node. On G5k you could
        use the API for that if your network configuration is *static*.

        But the world isn't that ideal, in my opinion. If you don't want to
        put to much burden in your experimental code just use this. This will
        ensure that constraints are put on all the relevant network cards. For
        example this will work the same if you move from one cluster to
        another, from one job_type to another (on G5k), from one provider to
        another. At least this is the intent of this Service.

        Note that the network constraints are set in all the nodes for
        outgoing packets only.

        Args:
            options   : raw netem options as described here:
                        http://man7.org/linux/man-pages/man8/tc-netem.8.html
            networks  : list of the networks to consider. Any interface with an
                        ip address on one of those network will be considered.
            hosts     : list of host on which the constraints will be applied
            symetric  : Wheter we'll want limitations on inbound and outbound traffic.
            extra_vars: extra variable to inject during the ansible run

        Example:

            .. literalinclude:: ../tutorials/network_emulation/tuto_simple_netem.py
              :language: python
              :linenos:

        """
        self.options = options
        self.hosts = hosts if hosts else []
        self.networks = networks
        self.symetric = symetric
        self.extra_vars = extra_vars if extra_vars is not None else {}
        self.roles = dict(all=self.hosts)

    def deploy(self, chunk_size=100):
        """Apply the constraints on all the hosts."""
        # will hold the number of ifbs to provision
        total_ifbs = 1
        sources = []
        for host in self.hosts:
            interfaces = host.filter_interfaces(self.networks)
            source = NetemInOutSource(host)
            for idx, interface in enumerate(interfaces):
                constraints = []
                constraints.append(NetemInConstraint(device=interface, options=self.options))
                if self.symetric:
                    constraints.append(NetemOutConstraint(device=interface, options=self.options, ifb=f"ifb{idx}"))
                source.add_constraints(constraints)
            total_ifbs = max(total_ifbs, len(interfaces))
            sources.append(source)

        netem(sources, self.extra_vars, chunk_size)

    def backup(self):
        pass

    def validate(self, output_dir=None):
        all_addresses = []
        for host in self.hosts:
            addresses = host.filter_addresses(self.networks)
            all_addresses.extend([str(addr.ip.ip) for addr in addresses])
        _validate(self.roles, output_dir, all_addresses)

    def destroy(self):
        # We need to know the exact device
        # all destroy all the rules on all the devices...
        pass


class Netem(Service):
    def __init__(
        self,
        network_constraints: Dict[Any, Any],
        *,
        roles: Roles = None,
        networks: Networks = None,
        extra_vars: Dict[Any, Any] = None,
        chunk_size: int = 100,
    ):
        """Set heterogeneous constraints between your hosts.

        It allows to setup complex network topology. For a much simpler way of
        applying constraints see
        :py:class:`enoslib.service.netem.SimpleNetem`

        Args:
            network_constraints: the decription of the wanted constraints
                (see the schema below)
            roles: the enoslib roles to consider
            extra_vars: extra variables to pass to Ansible when running (e.g.
                callback options)
            chunk_size: For large deployments, the commands to apply can become too
                long. It can be split in chunks of size chunk_size.

        *Network constraint schema:*

            .. literalinclude:: ../../enoslib/service/netem/schema.py
                :language: python
                :linenos:

        Examples:

            * Using defaults

            The following will apply the network constraints between every
            groups. For instance the constraints will be applied for the
            communication between "n1" and "n3" but not between "n1" and "n2".
            Note that using default leads to symetric constraints.

            .. code-block:: python

                roles = {
                    "grp1": ["n1", "n2"],
                    "grp2": ["n3", "n4"],
                    "grp3": ["n3", "n4"],
                }

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "groups": ["grp1", "grp2", "grp3"]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            Symetricaly, you can use ``except`` to exclude some groups.

            .. code-block:: python

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "except": ["grp3"]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            ``except: []`` is a way to apply the constraints between all groups.

            * Using ``src`` and ``dst``

            The following will enforce a symetric constraint between ``grp1``
            and ``grp2``.

            .. code-block:: python

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "groups": ["grp1", "grp2"]
                    "constraints": [{
                        "src": "grp1"
                        "dst": "grp2"
                        "delay": "10ms"
                        "symetric": True
                    }]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

        Examples:

            .. literalinclude:: examples/netem.py
              :language: python
              :linenos:

        Examples:

            .. literalinclude:: ../tutorials/network_emulation/tuto_netem.py
              :language: python
              :linenos:
        """
        Netem.is_valid(network_constraints)
        self.network_constraints = network_constraints
        self.roles = roles if roles is not None else []
        self.networks = networks
        self.extra_vars = extra_vars if extra_vars is not None else {}
        self.chunk_size = chunk_size

    @classmethod
    def is_valid(cls, network_constraints):
        """Validate the network_constraints (syntax only)."""
        return validate(instance=network_constraints, schema=SCHEMA)

    def deploy(self):
        """Enforce network links emulation."""
        # 1. Build all the constraints (Python)
        #    {source:src, target: ip_dest, device: if, rate:x,  delay:y}
        # 2. Generate the sequence of tc commands to run on the hosts (Python)
        # 3. Run those commands (Ansible)

        # 2.a building the group constraints
        logger.debug("Building all the constraints")
        constraints = _build_grp_constraints(self.roles, self.network_constraints)
        # 2.b Building the ip/device level constaints

        # will hold every single constraint
        host_htbs = _build_ip_constraints(self.roles, self.networks, constraints)

        # 3. Building the sequence of tc commands
        logger.info("Enforcing the constraints")

        netem_htb(host_htbs, self.extra_vars)

    def backup(self):
        """(Not Implemented) Backup.

        Feel free to share your ideas.
        """
        pass

    def destroy(self):
        """Reset the network constraints(latency, bandwidth ...)

        Remove any filter that have been applied to shape the traffic.
        """
        logger.debug("Reset the constraints")

        _check_tmpdir(TMP_DIR)

        _playbook = os.path.join(SERVICE_PATH, "netem.yml")
        options = _build_options(
            self.extra_vars, {"enos_action": "tc_reset", "tc_output_dir": TMP_DIR}
        )
        run_ansible([_playbook], roles=self.roles, extra_vars=options)

    def validate(self, *, output_dir=None):
        """Validate the network parameters(latency, bandwidth ...)

        Performs ping tests to validate the constraints set by
        :py:meth:`enoslib.service.netem.Netem.deploy`.
        Reports are available in the tmp directory
        used by enos.

        Args:
            roles(dict): role -> hosts mapping as returned by
                : py: meth: `enoslib.infra.provider.Provider.init`
            inventory_path(str): path to an inventory
            output_dir(str): directory where validation files will be stored.
                Default to: py: const: `enoslib.constants.TMP_DIRNAME`.
        """
        all_addresses = set()
        for hosts in self.roles.values():
            for host in hosts:
                addresses = host.filter_addresses(self.networks)
                all_addresses = all_addresses.union(
                    set([str(addr.ip.ip) for addr in addresses])
                )
        _validate(self.roles, output_dir, list(all_addresses))
