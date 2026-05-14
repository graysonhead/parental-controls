{
  description = "Parental controls web service and polling agent";

  inputs = {
    nixpkgs     = { url = "github:nixos/nixpkgs/nixpkgs-unstable"; };
    flake-utils = { url = "github:numtide/flake-utils"; };
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, ... }:
    let
      # NixOS modules are system-independent — defined outside eachDefaultSystem
      nixosModules = rec {
        parental-controls-server = import ./modules/server.nix;
        parental-controls-agent  = import ./modules/agent.nix;
        default = { imports = [ parental-controls-server parental-controls-agent ]; };
      };
    in
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Compat shims for poetry2nix against newer nixpkgs:
        #
        # 1. lib.licenses now includes SPDX operator functions (AND, OR, WITH).
        #    poetry2nix iterates lib.attrValues lib.licenses expecting only attr sets,
        #    so we filter those functions out before handing pkgs to poetry2nix.
        #
        # 2. Python 3.11+ has tomllib built-in, so nixpkgs dropped the `tomli`
        #    parameter from the `build` package function. poetry2nix's bootstrapping
        #    still calls build.override { tomli = ...; }, which fails. We wrap
        #    `build.override` in all Python package sets to strip the tomli arg.
        pkgsForPoetry2nix = import nixpkgs {
          inherit system;
          overlays = [
            (_: prev: {
              lib = prev.lib // {
                licenses = prev.lib.filterAttrs (_: v: builtins.isAttrs v) prev.lib.licenses;
              };
              pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
                (_: pyPrev: {
                  build = pyPrev.build // {
                    override = newArgs: pyPrev.build.override (builtins.removeAttrs newArgs [ "tomli" ]);
                  };
                  pyproject-hooks = pyPrev.pyproject-hooks // {
                    override = newArgs: pyPrev.pyproject-hooks.override (builtins.removeAttrs newArgs [ "tomli" ]);
                  };
                })
              ];
            })
          ];
        };

        inherit (poetry2nix.lib.mkPoetry2Nix { pkgs = pkgsForPoetry2nix; })
          mkPoetryApplication defaultPoetryOverrides;

        python = pkgs.python313;
        projectDir = ./.;
        myOverrides = defaultPoetryOverrides.extend (final: prev: {
          # Python dependency overrides go here
        });

        # Single package containing both server and agent entry points.
        # The console scripts (parental-controls-server, parental-controls-agent)
        # are defined in pyproject.toml [tool.poetry.scripts].
        package = mkPoetryApplication {
          inherit python projectDir;
          overrides = myOverrides;
          # preferWheels = true triggers a poetry2nix/pyproject.nix bug where
          # packages with riscv64 wheel tags crash evaluation, causing deps to
          # be silently dropped. Build from source (sdist) to avoid this.
          preferWheels = false;
          groups = [ "agent" ];
          checkGroups = [ ];
        };
      in
      {
        packages = {
          parental-controls-server = package;
          parental-controls-agent  = package;
          default = package;
        };

        inherit nixosModules;

        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            pkgs.poetry
          ];
        };
      }
    ) // { inherit nixosModules; };
}
