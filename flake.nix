{
  description = "RAG-NetTwin dev environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    lib = pkgs.lib;
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        git
        uv
        pre-commit
        gitleaks
        jdk17
        zlib
        stdenv.cc.cc.lib
        libffi
        openssl
        gcc
        just
        python311
      ];

      env = {
        GREET = "nix develop";
        PYTHONPATH = "./";
      };

      shellHook = ''
        export UV_PYTHON_DOWNLOADS=auto
        export UV_PYTHON_PREFERENCE=managed
        export LD_LIBRARY_PATH="${lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.libffi pkgs.openssl ]}:$LD_LIBRARY_PATH"
        echo "Python environment with uv enabled. PYTHONPATH is set to: $PYTHONPATH"
        uv --version
        if command -v docker >/dev/null 2>&1; then
          if ! docker ps --format '{{.Names}}' | grep -q "^batfish$"; then
            if docker ps -a --format '{{.Names}}' | grep -q "^batfish$"; then
              echo "Starting existing Batfish container..."
              docker start batfish
            else
              echo "Creating and starting new Batfish container..."
              docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/allinone
            fi
          else
            echo "Batfish container is already running."
          fi
        else
          echo "Docker not found. Skipping Batfish startup."
        fi
        if command -v pre-commit >/dev/null 2>&1; then
          pre-commit install
        fi
      '';
    };
  };
}
