# Looks

Each look is one CSS file that sets the same tokens on `[data-look="<id>"]`, plus optional decoration
for `#paper`. Scenes never use raw colours or fonts, only these tokens, so any video switches look by
changing the `look` variable (`vgt.py render --look …`), with no rebuild.

| id | Name | Fonts (OFL, in `fonts/`) |
|---|---|---|
| in-riso | In riso | Be Vietnam Pro |
| bang-phan | Bảng phấn | Pangolin (chalk edge from the `#chalk` SVG filter) |
| bao-giay | Báo giấy | Playfair Display + Be Vietnam Pro |
| ban-ve | Bản vẽ | Chakra Petch + Space Mono |
| poster | Poster | Anton + Be Vietnam Pro |

## Tokens

- Colours: `--paper` background, `--ink` text and outlines, `--hl` highlighted words (`--hl-bg` behind them),
  `--accent` main fill, `--soft` secondary fill, `--dot` halftone/pattern colour, `--c1`…`--c7` spectrum
  (red → violet), `--warm` / `--warm-ink` sunset fill / text, `--dusk` overlay gradient.
- Sentence type: `--say-font`, `--say-weight`, `--say-size`, `--say-lh`, `--say-tracking`, `--say-case`,
  `--say-shadow`, `--hl-shadow`.
- Labels: `--label-font`, `--label-weight`, `--label-size`, `--label-case`.

## Vietnamese rules for a new look

1. Run `python scripts/vgt_fonts.py yourfont.ttf`: every Vietnamese letter must be in the font, or the
   browser borrows one from another font and that letter looks wrong.
2. All-capitals looks need `--say-lh` of about **1.35-1.45**: capital letters carry their accents above the
   cap height, and a dot below (Ọ, Ạ) from the line above hits them otherwise. Lower-case looks are fine at 1.12-1.22.
3. Italic highlights need a little right margin (`margin-right: 0.12em`) or the slant touches the next word.
4. A highlight box (`--hl-bg`) needs top padding so stacked accents (Ầ, Ỗ) stay inside the box.
5. Check stills of the longest sentence in the new look before rendering (`vgt.py stills`).
