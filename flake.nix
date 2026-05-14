{
  description = "Parental controls web service and polling agent";

  inputs = {
    nixpkgs     = { url = "github:nixos/nixpkgs/nixpkgs-unstable"; };
    flake-utils = { url = "github:numtide/flake-utils"; };
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
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
        py = pkgs.python313;

        package = py.pkgs.buildPythonApplication {
          pname = "parental-controls";
          version = "0.1.0";
          format = "pyproject";
          src = pkgs.lib.cleanSource ./.;

          nativeBuildInputs = with py.pkgs; [ poetry-core ];

          propagatedBuildInputs = with py.pkgs; [
            # Server
            fastapi
            uvicorn
            sqlmodel
            aiosqlite
            pydantic-settings
            bcrypt
            itsdangerous
            # fastapi[standard] extras
            python-multipart
            email-validator
            httptools
            uvloop
            websockets
            # Agent
            httpx
          ];

          doCheck = false;
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
            py
            pkgs.poetry
          ];
        };
      }
    ) // { inherit nixosModules; };
}
