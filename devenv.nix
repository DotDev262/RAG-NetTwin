{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [ 
    pkgs.git
    pkgs.uv
    pkgs.pre-commit
    pkgs.gitleaks
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    package = pkgs.python311;
    uv = {
      enable = true;
      sync.enable = true;
    };
    venv.enable = true;
  };

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  scripts.batfish-start.exec = ''
    if ! docker ps --format '{{.Names}}' | grep -q "^batfish$"; then
      echo "Starting Batfish container..."
      docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
    else
      echo "Batfish container is already running."
    fi
  '';

  # https://devenv.sh/basics/
  enterShell = ''
    echo "Python environment with uv enabled."
    uv --version
    batfish-start
    pre-commit install
  '';
}
