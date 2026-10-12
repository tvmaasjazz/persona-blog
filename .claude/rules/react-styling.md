---
paths:
  - "frontend/**/*.tsx"
  - "frontend/**/*.css"
  - "frontend/components.json"
---

# Frontend styling

The look follows substack.com: dark surfaces, a system sans-serif for the UI, a
serif for reading, rounded solid buttons. Purple replaces Substack's orange. Values
were measured from substack.com and live as design tokens in `src/index.css`.

## Tokens only

Components style with semantic Tailwind classes that read tokens: `bg-card`,
`text-muted-foreground`, `border-border`, `rounded-lg`. Never:

- a raw palette color: `bg-zinc-900`, `text-violet-400`
- an arbitrary color value: `bg-[#1b1c1d]`, `style={{ color: '#fff' }}`
- a `dark:` variant

The app is dark only. The token values live under `.dark` in `src/index.css`, and
`index.html` sets `class="dark"` on `<html>`. Light mode, when it comes, is a `:root`
block with the same variable names plus a script that toggles the class. Tokens are
what make that a CSS-only change, so a component that bypasses them is a bug.

`src/components/ui/` is exempt. shadcn generates `dark:` variants there, and they
always apply because the app is always dark.

A new color need is a new token, not a one-off class. Add the variable under `.dark`
and map it in `@theme inline`, then use the class.

| Token (class suffix)   | Use                                                          |
| ---------------------- | ------------------------------------------------------------ |
| `background`           | The page                                                     |
| `foreground`           | Body text                                                    |
| `card`                 | Raised surfaces: sidebar cards, post cards                   |
| `popover`              | Dialogs, menus, dropdowns                                    |
| `primary`              | Filled purple: the main action on a screen. Text on it is `primary-foreground` |
| `primary-text`         | Purple text or icons on a dark surface: links, "Subscribe"   |
| `secondary`            | The grey button beside a primary one                         |
| `muted-foreground`     | Secondary text: timestamps, captions, placeholders           |
| `accent`               | Hover background for nav items and ghost buttons             |
| `border`, `input`      | Dividers and control borders                                 |
| `ring`                 | Focus rings                                                  |
| `destructive`          | Delete and error states                                      |

Purple text is always `text-primary-text`, never `text-primary`. The fill purple is
only 4:1 against the background, which fails WCAG AA for body text.

## Shape and type

| Element                    | Classes                                              |
| -------------------------- | ---------------------------------------------------- |
| Button                     | `<Button>`: 40px tall, `rounded-lg` (8px), 15px semibold |
| Input, nav item            | `rounded-xl` (12px). Nav items are 48px tall         |
| Card, dialog               | `rounded-2xl` (16px), `border`, `bg-card` or `bg-popover` |
| Card or dialog title       | `text-xl font-extrabold`                             |
| UI text                    | `font-sans`, the default                             |
| Post body text             | `font-serif`                                         |

`font-serif` is Spectral with a Georgia fallback. Spectral isn't loaded yet. Loading
it (a Google Fonts link or a `@fontsource` package) is decided when post pages land.

## Layout

Substack's columns, from the left:

- **Nav rail**: 200px wide, pinned to the left edge of the window and full height,
  with icon plus label items and the primary "Create" button under the nav
- **Main column**: about 600px wide, centred in the space right of the nav rail.
  When the right sidebar shows, the two are centred together
- **Right sidebar**: only on a page that has something for it, never an empty
  column. `AppLayout` shows one when signed out, holding the sign-in card (about
  370px). A page with its own sidebar, like a persona and their posts, sets
  `hasSidebar` on its route (`react-structure.md` › Routing); the main column widens
  to 960px and the page lays out a 600px column beside a 320px sidebar

Below `lg` a right sidebar drops out, or, when its content matters, like a persona's
posts, moves into the main column under the page's header. Below `md` the nav rail
collapses to icons.

## Components

Add shadcn components with the CLI from `frontend/`:

```bash
npx shadcn@latest add dialog
```

Read the generated file before using it. Files in `components/ui/` are generated and
treated as vendored: don't reorganize, split, or trim them, and don't rewrite their
class strings for readability. A long string there is upstream's, not ours, and the
file stays regenerable by the CLI. `dropdown-menu.tsx` is the example: its density is
Radix's runtime behaviour expressed as data-attribute classes.

Edit only a variant you're deliberately changing. `button.tsx` is the example there:
Substack's sizes and a `link` variant that uses `primary-text`. Change the variant in
the file rather than overriding it with `className` at every call site. A `className`
passed at the call site is for layout (`w-full`, margins), not for restyling.

`alert-dialog.tsx` is edited the same way: its content takes the dialog shape from
Shape and type (`rounded-2xl`, `bg-popover`), and its title takes the dialog title
style (`text-xl font-extrabold`).

`sonner.tsx` is edited for a different reason. shadcn's version reads the theme from
`next-themes`, which the app doesn't use. It pins `theme="dark"` instead. When light
mode lands, replace the pinned value with one read from the class toggle.

Re-running `npx shadcn@latest add` for an edited file overwrites the edit. When
another component pulls one in as a dependency, the CLI asks before overwriting:
answer no.

Build app components from `components/ui/` parts. Don't use a raw `<button>` or
`<input>` where a shadcn one exists.

## Icons

`lucide-react` only, at `size-5` in nav and `size-4` inside buttons, which is the
Button's default. An icon next to a text label is decorative and takes `aria-hidden`.
An icon-only button needs an `aria-label`.
