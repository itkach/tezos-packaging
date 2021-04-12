# SPDX-FileCopyrightText: 2021 TQ Tezos <https://tqtezos.com/>
#
# SPDX-License-Identifier: LicenseRef-MIT-TQ

{ lib, ... }:

with lib;
rec {
  sharedOptions = {

    logVerbosity = mkOption {
      type = types.enum [ "fatal" "error" "warning" "notice" "info" "debug" ];
      default = "warning";
      description = ''
        Level of logs verbosity. Possible values are:
        fatal, error, warn, notice, info or debug.
      '';
    };

  };

  daemonOptions = sharedOptions // {

    baseProtocol = mkOption {
      type = types.enum [ "007-PsDELPH1" "008-PtEdo2Zk" "009-PsFLoren"];
      description = ''
        Base protocol version,
        only '007-PsDELPH1', '008-PtEdo2Zk', and '009-PsFLoren' are supported.
      '';
      example = "008-PtEdo2Zk";
    };

    rpcPort = mkOption {
      type = types.int;
      default = 8732;
      example = 8732;
      description = ''
        Tezos node RPC port.
      '';
    };

  };

  genDaemonConfig = instancesCfg: service-name: service-pkgs: service-script:
    mkIf (instancesCfg != {}) {
      users = mkMerge (flip mapAttrsToList instancesCfg (node-name: node-cfg: genUsers node-name ));
      systemd = mkMerge (flip mapAttrsToList instancesCfg (node-name: node-cfg:
        let tezos-service = service-pkgs."${node-cfg.baseProtocol}";
        in {
          services."tezos-${node-name}-tezos-${service-name}" = genSystemdService node-name node-cfg service-name // {
            preStart =
              ''
                service_data_dir="$STATE_DIRECTORY/client/data"
                mkdir -p "$service_data_dir"

                # Generate or update service config file
                if [[ ! -f "$service_data_dir/config" ]]; then
                  ${tezos-service} -d "$service_data_dir" -E "http://localhost:${toString node-cfg.rpcPort}" \
                  config init --output "$service_data_dir/config" >/dev/null 2>&1
                else
                  ${tezos-service} -d "$service_data_dir" -E "http://localhost:${toString node-cfg.rpcPort}" \
                  config update >/dev/null 2>&1
                fi
              '';
            script = service-script node-cfg;
          };
      }));
    };

  genUsers = node-name: {
    groups."tezos-${node-name}" = { };
    users."tezos-${node-name}" = { group = "tezos-${node-name}"; };
  };

  genSystemdService = node-name: node-cfg: service-name: {
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    description = "Tezos ${service-name}";
    environment = {
      TEZOS_LOG = "* -> ${node-cfg.logVerbosity}";
    };
    serviceConfig = {
      User = "tezos-${node-name}";
      Group = "tezos-${node-name}";
      StateDirectory = "tezos-${node-name}";
      Restart = "always";
      RestartSec = "10";
    };
  };

}
