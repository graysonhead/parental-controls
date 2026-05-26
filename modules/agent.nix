{ config, lib, pkgs, inputs, ... }:

with lib;

let
  cfg = config.services.parental-controls-agent;
  settingsFormat = pkgs.formats.toml { };
  configFile = settingsFormat.generate "agent.toml" {
    server_url = cfg.serverUrl;
    poll_interval = cfg.pollInterval;
    children = cfg.children;
  };
in
{
  options.services.parental-controls-agent = {
    enable = mkEnableOption "parental-controls agent";

    package = mkOption {
      type = types.package;
      default = inputs.parental-controls.packages.${pkgs.system}.default;
      defaultText = literalExpression "inputs.parental-controls.packages.\${pkgs.system}.default";
      description = "The parental-controls package to use.";
    };

    serverUrl = mkOption {
      type = types.str;
      default = "http://localhost:8000";
      description = "URL of the parental-controls web server.";
    };

    pollInterval = mkOption {
      type = types.int;
      default = 30;
      description = "How often to poll the server, in seconds.";
    };

    children = mkOption {
      type = types.attrsOf types.str;
      default = { };
      example = literalExpression ''{ "Alice" = "alice"; "Bob" = "bob"; }'';
      description = ''
        Mapping from child display name (as shown in the web UI) to the OS
        username on this machine.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.services.parental-controls-agent = {
      description = "Parental Controls Agent";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      serviceConfig = {
        Type = "simple";
        ExecStart = "${cfg.package}/bin/parental-controls-agent -c ${configFile}";
        Restart = "on-failure";
        RestartSec = 10;
        # Needs root to write /var/lib/parental-controls and run runuser
        StateDirectory = "parental-controls";
        StateDirectoryMode = "0755";
        Environment = "PATH=/run/current-system/sw/bin:/run/wrappers/bin";
      };
    };
  };
}
