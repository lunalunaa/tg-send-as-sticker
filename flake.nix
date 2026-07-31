{
  description = "tg-sticker-bypass: auto-convert text to Telegram stickers";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python312.withPackages (ps: [
        ps.telethon
        ps.pillow
        ps.fonttools
      ]);
      latinFont = "${pkgs.dejavu_fonts}/share/fonts/truetype/DejaVuSans-Bold.ttf";
      cjkFont = "${pkgs.noto-fonts-cjk-sans}/share/fonts/opentype/noto-cjk/NotoSansCJK-VF.otf.ttc";
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [ python pkgs.dejavu_fonts pkgs.noto-fonts-cjk-sans ];
        shellHook = ''
          export TG_FONT_PATH=${latinFont}
          export TG_CJK_FONT_PATH=${cjkFont}
        '';
      };

      packages.${system}.default = pkgs.writeShellApplication {
        name = "tg-sticker";
        runtimeInputs = [ python ];
        text = ''
          export TG_FONT_PATH=''${TG_FONT_PATH:-${latinFont}}
          export TG_CJK_FONT_PATH=''${TG_CJK_FONT_PATH:-${cjkFont}}
          exec ${python}/bin/python ${./tgsticker.py} "$@"
        '';
      };
    };
}
