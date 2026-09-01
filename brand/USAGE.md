# Dev-Strom brand assets

A copper spark at the centre, six steel nodes radiating out. One stack goes in,
several ideas come out — the mark says what the product does. The `</>` glyph
from the reference sketch was dropped: it's redundant on GitHub, it's the most
overused symbol in developer branding, and it was the first thing to break at
small sizes.

## Two cuts of the mark

The full mark carries the nodes. Below about 24px the steel dots merge into
noise, so `favicon.ico` ships a separate 16px drawing: the copper spark alone,
scaled up to fill the tile. Don't regenerate the 16px entry by downscaling
`favicon.svg` — you'll get mush.

| File | Use |
| --- | --- |
| `logo-mark.svg` / `.png` | Mark alone, transparent. |
| `logo-mark-tile.svg` | Mark on the ink tile. |
| `logo-lockup-dark.svg` / `.png` | Mark + wordmark, dark backgrounds. |
| `logo-lockup-light.svg` / `.png` | Mark + wordmark, light backgrounds. |
| `banner.png` (1280×320) | Top of the README. |
| `og-image.png` (1200×630) | Open Graph, Twitter card, Slack and LinkedIn unfurls. |
| `favicon.svg` | Modern browsers. |
| `favicons/favicon.ico` | 16 / 32 / 48 bundle. Serve from site root. |
| `favicons/apple-touch-icon.png` | 180×180, full-bleed; iOS adds its own rounding. |
| `favicons/icon-192.png`, `icon-512.png` | PWA and Android. |
| `favicons/icon-maskable-512.png` | Adaptive icon, art inside the 80% safe zone. |
| `site.webmanifest` | Manifest referencing the above. |

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| Ink | `#1A1512` | Base surface, tile background |
| Umber | `#4A3B31` | Raised surfaces, borders, background texture |
| Copper | `#E2703A` | The spark, primary accent, one CTA per screen |
| Steel | `#9BB0C1` | Nodes, secondary text, code and metadata |
| Bone | `#F5EFE8` | Primary text on ink |

Copper is warm and steel is cool, which is what keeps the spark reading as the
hero — if you tint the nodes copper too, the whole mark flattens into a
snowflake and the hierarchy disappears. Keep copper rare. Type is Space Grotesk;
the wordmark is already outlined, so no font ships with the SVGs.

## Wiring it up

Drop this folder in at the repo root as `brand/`, then copy `favicons/`,
`favicon.svg` and `site.webmanifest` into whatever directory serves static files
(`web/public/` for the React UI).

**README**

```html
<p align="center">
  <img src="brand/banner.png" alt="Dev-Strom" width="100%">
</p>
```

**HTML head**

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/favicons/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#1A1512">

<meta property="og:title" content="Dev-Strom">
<meta property="og:description" content="You've learned the stack. Now build something with it.">
<meta property="og:image" content="https://your-domain/og-image.png">
<meta name="twitter:card" content="summary_large_image">
```

**Streamlit** (`ui/Home.py`)

```python
from PIL import Image

st.set_page_config(
    page_title="Dev-Strom",
    page_icon=Image.open("brand/favicons/favicon-48x48.png"),
    layout="wide",
)
st.image("brand/banner.png", use_container_width=True)
```

**FastAPI** (`app/api.py`)

```python
from fastapi.staticfiles import StaticFiles
api.mount("/brand", StaticFiles(directory="brand"), name="brand")
```

For the repo card, upload `og-image.png` under Settings → General → Social
preview. GitHub reads only that upload and ignores `og:image` on repo pages.
