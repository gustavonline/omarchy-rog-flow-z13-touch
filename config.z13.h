#ifndef config_h_INCLUDED
#define config_h_INCLUDED

#define DEFAULT_FONT "Inter 19"
#define DEFAULT_ROUNDING 10

/* Catppuccin Macchiato defaults.  The launcher selects Latte or Macchiato
 * explicitly at runtime, so this is also a safe fallback. */
struct clr_scheme schemes[] = {
{
  .bg = {.bgra = {58, 39, 36, 255}},       /* #24273a base */
  .fg = {.bgra = {79, 58, 54, 255}},       /* #363a4f surface0 */
  .high = {.bgra = {100, 77, 73, 255}},    /* #494d64 surface1 */
  .swipe = {.bgra = {244, 173, 138, 255}}, /* #8aadf4 blue */
  .text = {.bgra = {245, 211, 202, 255}},  /* #cad3f5 text */
  .text_press = {.bgra = {245, 211, 202, 255}},
  .text_swipe = {.bgra = {58, 39, 36, 255}},
  .font = DEFAULT_FONT,
  .rounding = DEFAULT_ROUNDING,
},
{
  .bg = {.bgra = {58, 39, 36, 255}},
  .fg = {.bgra = {100, 77, 73, 255}},      /* surface1 */
  .high = {.bgra = {120, 96, 91, 255}},   /* #5b6078 surface2 */
  .swipe = {.bgra = {244, 173, 138, 255}},
  .text = {.bgra = {245, 211, 202, 255}},
  .text_press = {.bgra = {245, 211, 202, 255}},
  .text_swipe = {.bgra = {58, 39, 36, 255}},
  .font = DEFAULT_FONT,
  .rounding = DEFAULT_ROUNDING,
}
};

static enum layout_id layers[] = {
  Letters,
  Numbers,
  Symbols,
  Functions,
  NumLayouts
};

static enum layout_id landscape_layers[] = {
  Letters,
  Numbers,
  Symbols,
  Functions,
  NumLayouts
};

#endif
