{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [ 
    pkgs.git
    pkgs.uv
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

  # https://devenv.sh/basics/
  enterShell = ''
    echo "Python environment with uv enabled."
    uv --version
  '';
}
