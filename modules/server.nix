{ config, lib, pkgs, inputs, ... }:

with lib;

let
  cfg = config.services.parental-controls;
in
{
  options.services.parental-controls = {
    enable = mkEnableOption "parental-controls web server";

    package = mkOption {
      type = types.package;
      default = inputs.parental-controls.packages.${pkgs.system}.default;
      defaultText = literalExpression "inputs.parental-controls.packages.\${pkgs.system}.default";
      description = "The parental-controls package to use.";
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = "Host address to bind to.";
    };

    port = mkOption {
      type = types.port;
      default = 8000;
      description = "Port to listen on.";
    };

    databasePath = mkOption {
      type = types.str;
      default = "/var/lib/parental-controls/db.sqlite";
      description = "Path to the SQLite database file.";
    };

    secretKey = mkOption {
      type = types.str;
      default = "change-me-in-production";
      description = "Session secret key. Override via environmentFile in production.";
    };

    adminPin = mkOption {
      type = types.str;
      default = "0000";
      description = "Admin PIN for the parent UI. Override via environmentFile in production.";
    };

    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      example = "/run/secrets/parental-controls.env";
      description = ''
        Path to an environment file containing secrets. Variables in this file
        override the module options above. Useful for SECRET_KEY and ADMIN_PIN.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.services.parental-controls = {
      description = "Parental Controls Web Server";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      environment = {
        DATABASE_URL = "sqlite:///${cfg.databasePath}";
        SECRET_KEY = cfg.secretKey;
        ADMIN_PIN = cfg.adminPin;
        HOST = cfg.host;
        PORT = toString cfg.port;
      };

      serviceConfig = {
        Type = "simple";
        ExecStartPre = "${cfg.package}/bin/parental-controls-migrate";
        ExecStart = "${cfg.package}/bin/parental-controls-server";
        StateDirectory = "parental-controls";
        DynamicUser = true;
        Restart = "on-failure";
      } // optionalAttrs (cfg.environmentFile != null) {
        EnvironmentFile = cfg.environmentFile;
      };
    };
  };
}
