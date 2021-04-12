# SPDX-FileCopyrightText: 2020 TQ Tezos <https://tqtezos.com/>
#
# SPDX-License-Identifier: LicenseRef-MIT-TQ
import os, shutil, sys, subprocess, json

from .model import Service, ServiceFile, SystemdUnit, Unit, Install, OpamBasedPackage, TezosSaplingParamsPackage, TezosBakingServicesPackage

networks = ["mainnet"]

signer_units = [
    SystemdUnit(
        ServiceFile(Unit(after=["network.target"],
                         description="Tezos signer daemon running over TCP socket"),
                    Service(environment_file="/etc/default/tezos-signer-tcp",
                            environment=["ADDRESS=127.0.0.1", "PORT=8000", "TIMEOUT=1"],
                            exec_start="/usr/bin/tezos-signer-start launch socket signer " \
                            + " --address ${ADDRESS} --port ${PORT} --timeout ${TIMEOUT}",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target"])),
        suffix="tcp",
        startup_script="tezos-signer-start",
        config_file="tezos-signer.conf"),
    SystemdUnit(
        ServiceFile(Unit(after=["network.target"],
                         description="Tezos signer daemon running over UNIX socket"),
                    Service(environment_file="/etc/default/tezos-signer-unix",
                            environment=["SOCKET="],
                            exec_start="/usr/bin/tezos-signer-start launch local signer " \
                            + "--socket ${SOCKET}",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target"])),
        suffix="unix",
        startup_script="tezos-signer-start",
        config_file="tezos-signer.conf"),
    SystemdUnit(
        ServiceFile(Unit(after=["network.target"],
                         description="Tezos signer daemon running over HTTP"),
                    Service(environment_file="/etc/default/tezos-signer-http",
                            environment=["CERT_PATH=", "KEY_PATH=", "ADDRESS=127.0.0.1", "PORT=8080"],
                            exec_start="/usr/bin/tezos-signer-start launch http signer " \
                            + "--address ${ADDRESS} --port ${PORT}",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target"])),
        suffix="http",
        startup_script="tezos-signer-start",
        config_file="tezos-signer.conf"),
    SystemdUnit(
        ServiceFile(Unit(after=["network.target"],
                         description="Tezos signer daemon running over HTTPs"),
                    Service(environment_file="/etc/default/tezos-signer-https",
                            environment=["CERT_PATH=", "KEY_PATH=", "ADDRESS=127.0.0.1", "PORT=8080"],
                            exec_start="/usr/bin/tezos-signer-start launch https signer " \
                            + "${CERT_PATH} ${KEY_PATH} --address ${ADDRESS} --port ${PORT}",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target"])),
        suffix="https",
        startup_script="tezos-signer-start",
        config_file="tezos-signer.conf")
]

packages = [
    OpamBasedPackage("tezos-client",
                     "CLI client for interacting with tezos blockchain",
                     optional_opam_deps=["tls", "ledgerwallet-tezos"],
                     requires_sapling_params=True),
    OpamBasedPackage("tezos-admin-client",
                     "Administration tool for the node",
                     optional_opam_deps=["tls"]),
    OpamBasedPackage("tezos-signer",
                     "A client to remotely sign operations or blocks",
                     optional_opam_deps=["tls", "ledgerwallet-tezos"],
                     systemd_units=signer_units),
    OpamBasedPackage("tezos-codec",
                     "A client to decode and encode JSON")
]

postinst_steps_common = '''
useradd --home-dir /var/lib/tezos tezos || true
'''


def mk_node_unit(suffix, env, desc):
    service_file = ServiceFile(Unit(after=["network.target", f"tezos-baking-{suffix}.service"],
                                    requires=[], description=desc,
                                    part_of=[f"tezos-baking-{suffix}.service"]),
                               Service(environment=env,
                                       exec_start="/usr/bin/tezos-node-start",
                                       exec_start_pre="/usr/bin/tezos-node-prestart",
                                       state_directory="tezos", user="tezos"
                               ),
                               Install(wanted_by=["multi-user.target", f"tezos-baking-{suffix}.service"]))
    return SystemdUnit(suffix=suffix, service_file=service_file, startup_script="tezos-node-start",
                       prestart_script="tezos-node-prestart")


# v8.2 tezos-node doesn't have predefined config for edo2net, so we're providing
# this config to the service manually
edo2net_config = '''{
"p2p": {},
"network":
    { "genesis":
        { "timestamp": "2021-02-11T14:00:00Z",
          "block": "BLockGenesisGenesisGenesisGenesisGenesisdae8bZxCCxh",
          "protocol": "PtYuensgYBb3G3x1hLLbCmcav8ue8Kyd2khADcL5LsT5R1hcXex" },
      "genesis_parameters":
        { "values":
            { "genesis_pubkey":
                "edpkugeDwmwuwyyD3Q5enapgEYDxZLtEUFFSrvVwXASQMVEqsvTqWu" } },
      "chain_name": "TEZOS_EDO2NET_2021-02-11T14:00:00Z",
      "sandboxed_chain_name": "SANDBOXED_TEZOS",
      "default_bootstrap_peers":
        [ "edonet.tezos.co.il", "188.40.128.216:29732", "edo2net.kaml.fr",
          "edonet2.smartpy.io", "51.79.165.131", "edonetb.boot.tezostaquito.io" ] }
}
'''

node_units = []
node_postinst_steps = postinst_steps_common
node_postrm_steps = ""
common_node_env = ["NODE_RPC_ADDR=127.0.0.1:8732", "CERT_PATH=", "KEY_PATH="]
for network in networks:
    env = [f"DATA_DIR=/var/lib/tezos/node-{network}", f"NETWORK={network}"] + common_node_env
    node_units.append(mk_node_unit(suffix=network, env=env, desc=f"Tezos node {network}"))
    node_postinst_steps += f'''mkdir -p /var/lib/tezos/node-{network}
[ ! -f /var/lib/tezos/node-{network}/config.json ] && tezos-node config init --data-dir /var/lib/tezos/node-{network} --network {network}
chown -R tezos:tezos /var/lib/tezos/node-{network}

cat > /usr/bin/tezos-node-{network} <<- 'EOM'
#! /usr/bin/env bash

TEZOS_NODE_DIR="$(cat $(systemctl show -p FragmentPath tezos-node-{network}.service | cut -d'=' -f2) | grep 'DATA_DIR' | cut -d '=' -f3 | cut -d '"' -f1)" tezos-node "$@"
EOM
chmod +x /usr/bin/tezos-node-{network}
systemctl enable tezos-node-{network}.service > /dev/null || true
'''
    node_postrm_steps += f'''
rm -f /usr/bin/tezos-node-{network}
systemctl disable tezos-node-{network}.service > /dev/null || true
'''

# Add custom config service
node_units.append(mk_node_unit(suffix="custom", env=["DATA_DIR=/var/lib/tezos/node-custom",
                                                     "CUSTOM_NODE_CONFIG="] + common_node_env,
                               desc="Tezos node with custom config"))
node_postinst_steps += "mkdir -p /var/lib/tezos/node-custom\n"

# Add edo2net service
node_units.append(mk_node_unit(suffix="edo2net", env=common_node_env + ["DATA_DIR=/var/lib/tezos/node-edo2net"],
                               desc="Tezos node edo2net"))

node_postinst_steps += f'''mkdir -p /var/lib/tezos/node-edo2net
rm -f /var/lib/tezos/node-edo2net/config.json
cat > /var/lib/tezos/node-edo2net/config.json <<- EOM
{edo2net_config}
EOM
chown -R tezos:tezos /var/lib/tezos/node-edo2net
cat > /usr/bin/tezos-node-edo2net <<- 'EOM'
#! /usr/bin/env bash

TEZOS_NODE_DIR="$(cat $(systemctl show -p FragmentPath tezos-node-edo2net.service | cut -d'=' -f2) | grep 'DATA_DIR' | cut -d '=' -f3 | cut -d '"' -f1)" tezos-node "$@"
EOM
chmod +x /usr/bin/tezos-node-edo2net
systemctl enable tezos-node-edo2net.service > /dev/null || true
'''
node_postrm_steps += f'''
rm -f /usr/bin/tezos-node-edo2net
systemctl disable tezos-node-edo2net.service > /dev/null || true
'''

packages.append(OpamBasedPackage("tezos-node",
                                 "Entry point for initializing, configuring and running a Tezos node",
                                 node_units,
                                 optional_opam_deps=[
                                     "tezos-embedded-protocol-001-PtCJ7pwo",
                                     "tezos-embedded-protocol-002-PsYLVpVv",
                                     "tezos-embedded-protocol-003-PsddFKi3",
                                     "tezos-embedded-protocol-004-Pt24m4xi",
                                     "tezos-embedded-protocol-005-PsBABY5H",
                                     "tezos-embedded-protocol-005-PsBabyM1",
                                     "tezos-embedded-protocol-006-PsCARTHA"],
                                 requires_sapling_params=True,
                                 postinst_steps=node_postinst_steps,
                                 postrm_steps=node_postrm_steps))

active_protocols = json.load(open(f"{os.path.dirname( __file__)}/../../protocols.json", "r"))["active"]

daemons = ["baker", "accuser", "endorser"]

daemon_decs = {
    "baker": "daemon for baking",
    "accuser": "daemon for accusing",
    "endorser": "daemon for endorsing"
}

daemon_postinst_common = postinst_steps_common + "\nmkdir -p /var/lib/tezos/.tezos-client\nchown -R tezos:tezos /var/lib/tezos/.tezos-client\n"

# TODO remove once v9.0 is released use 'networks' instead
daemons_instances = networks + ["edo2net"]

def gen_daemon_specific_postinst(daemon_name):
    daemon_postinst = ""
    for instance in daemons_instances:
        daemon_postinst += f"systemctl enable {daemon_name}@{instance}.service > /dev/null || true\n"
    return daemon_postinst

def gen_daemon_specific_postrm(daemon_name):
    daemon_postrm = ""
    for instance in daemons_instances:
        daemon_postrm += f"systemctl disable {daemon_name}@{instance}.service > /dev/null || true\n"
    return daemon_postrm

for proto in active_protocols:
    service_file_baker = ServiceFile(Unit(after=["network.target"],
                                          description="Tezos baker"),
                                     Service(environment_file=f"/etc/default/tezos-baker-{proto}",
                                             environment=[f"PROTOCOL={proto}", "NODE_DATA_DIR="],
                                             exec_start="/usr/bin/tezos-baker-start",
                                             state_directory="tezos", user="tezos"),
                                     Install(wanted_by=["multi-user.target"]))
    service_file_baker_instantiated = \
        ServiceFile(Unit(after=["network.target", "tezos-node-%i.service", "tezos-baking-%i.service"],
                         requires=["tezos-node-%i.service"],
                         part_of=["tezos-baking-%i.service"],
                         description="Instantiated tezos baker daemon service"),
                    Service(environment_file=f"/etc/default/tezos-baker-{proto}",
                            environment=[f"PROTOCOL={proto}", "NODE_DATA_DIR=/var/lib/tezos/node-%i"],
                            exec_start="/usr/bin/tezos-baker-start",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target", "tezos-baking-%i.service"]))
    service_file_accuser = ServiceFile(Unit(after=["network.target"],
                                            description="Tezos accuser"),
                                       Service(environment_file=f"/etc/default/tezos-accuser-{proto}",
                                               environment=[f"PROTOCOL={proto}"],
                                               exec_start="/usr/bin/tezos-accuser-start",
                                               state_directory="tezos", user="tezos"),
                                       Install(wanted_by=["multi-user.target"]))
    service_file_accuser_instantiated = \
        ServiceFile(Unit(after=["network.target", "tezos-node-%i.service", "tezos-baking-%i.service"],
                         requires=["tezos-node-%i.service"],
                         part_of=["tezos-baking-%i.service"],
                         description="Instantiated tezos accuser daemon service"),
                    Service(environment_file=f"/etc/default/tezos-accuser-{proto}",
                            environment=[f"PROTOCOL={proto}"],
                            exec_start="/usr/bin/tezos-accuser-start",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target", "tezos-baking-%i.service"]))
    service_file_endorser = ServiceFile(Unit(after=["network.target"],
                                             description="Tezos endorser"),
                                        Service(environment_file=f"/etc/default/tezos-endorser-{proto}",
                                                environment=[f"PROTOCOL={proto}"],
                                                exec_start="/usr/bin/tezos-endorser-start",
                                                state_directory="tezos", user="tezos"),
                                        Install(wanted_by=["multi-user.target"]))
    service_file_endorser_instantiated = \
        ServiceFile(Unit(after=["network.target", "tezos-node-%i.service", "tezos-baking-%i.service"],
                         requires=["tezos-node-%i.service"],
                         part_of=["tezos-baking-%i.service"],
                         description="Instantiated tezos endorser daemon service"),
                    Service(environment_file=f"/etc/default/tezos-endorser-{proto}",
                            environment=[f"PROTOCOL={proto}"],
                            exec_start="/usr/bin/tezos-endorser-start",
                            state_directory="tezos", user="tezos"),
                    Install(wanted_by=["multi-user.target", "tezos-baking-%i.service"]))
    packages.append(OpamBasedPackage(f"tezos-baker-{proto}", "Daemon for baking",
                                     [SystemdUnit(service_file=service_file_baker,
                                                  startup_script="tezos-baker-start",
                                                  config_file="tezos-baker.conf"),
                                      SystemdUnit(service_file=service_file_baker_instantiated,
                                                  startup_script="tezos-baker-start",
                                                  instances=daemons_instances)],
                                     proto,
                                     optional_opam_deps=["tls", "ledgerwallet-tezos"],
                                     requires_sapling_params=True,
                                     postinst_steps= \
                                        daemon_postinst_common + gen_daemon_specific_postinst(f"tezos-baker-{proto}"),
                                     postrm_steps=gen_daemon_specific_postrm(f"tezos-baker-{proto}")))
    packages.append(OpamBasedPackage(f"tezos-accuser-{proto}", "Daemon for accusing",
                                     [SystemdUnit(service_file=service_file_accuser,
                                                  startup_script="tezos-accuser-start",
                                                  config_file="tezos-accuser.conf"),
                                      SystemdUnit(service_file=service_file_accuser_instantiated,
                                                  startup_script="tezos-accuser-start",
                                                  instances=daemons_instances)],
                                     proto,
                                     optional_opam_deps=["tls", "ledgerwallet-tezos"],
                                     postinst_steps= \
                                        daemon_postinst_common + gen_daemon_specific_postinst(f"tezos-accuser-{proto}"),
                                     postrm_steps=gen_daemon_specific_postrm(f"tezos-accuser-{proto}")))
    packages.append(OpamBasedPackage(f"tezos-endorser-{proto}", "Daemon for endorsing",
                                     [SystemdUnit(service_file=service_file_endorser,
                                                  startup_script="tezos-endorser-start",
                                                  config_file="tezos-endorser.conf"),
                                      SystemdUnit(service_file=service_file_endorser_instantiated,
                                                  startup_script="tezos-endorser-start",
                                                  instances=daemons_instances)],
                                     proto,
                                     optional_opam_deps=["tls", "ledgerwallet-tezos"],
                                     postinst_steps= \
                                        daemon_postinst_common + gen_daemon_specific_postinst(f"tezos-endorser-{proto}"),
                                     postrm_steps=gen_daemon_specific_postrm(f"tezos-endorser-{proto}")))

packages.append(TezosSaplingParamsPackage())
packages.append(TezosBakingServicesPackage(
    target_networks=["mainnet", "edo2net"],
    target_protos=["008-PtEdo2Zk"]
    ))
