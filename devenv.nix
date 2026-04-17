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
    pkgs.jdk17
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
      if docker ps -a --format '{{.Names}}' | grep -q "^batfish$"; then
        echo "Starting existing Batfish container..."
        docker start batfish
      else
        echo "Creating and starting new Batfish container..."
        docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
      fi
    else
      echo "Batfish container is already running."
    fi
  '';

  # https://devenv.sh/basics/
  enterShell = ''
    export UV_PYTHON_DOWNLOADS=auto
    export UV_PYTHON_PREFERENCE=managed
    echo "Python environment with uv enabled."
    uv --version
    batfish-start
    pre-commit install
  '';
}
