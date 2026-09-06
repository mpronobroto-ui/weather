# Fix: "Quick Modules" button unreachable on mobile

## Bug
On phone-width screens, the "🧭 Quick Modules" button (and "Login" button)
were invisible/unreachable — not because of a `display:none`, but because
they were pushed physically off the right edge of the screen and clipped.

## Root cause
`.masthead-row` is a `display:flex` row with no wrapping, containing:
logo/brand → status chip → Quick Modules button → Login button.

The status chip (`.station-status`) has `white-space:nowrap`, so text like
"backend offline — set API endpoint" refuses to shrink or wrap. On a narrow
phone viewport this text alone can exceed the available width, shoving the
two buttons after it past the visible edge of the screen. Since `.app` has
`overflow:hidden`, that overflow is clipped rather than made scrollable —
the buttons exist in the DOM and still work, but there is no way to see or
tap them.

## Fix
Added a mobile media-query block (`max-width:900px`) that:
- Lets `.masthead-row` wrap onto two lines (`flex-wrap:wrap`)
- Lets the status chip take the full second line and truncate with an
  ellipsis instead of forcing a fixed nowrap width
- Reorders the row so brand + Login stay on line 1, and the status chip +
  Quick Modules button flow onto line 2

## Result
On mobile, the header now wraps to two rows so every control (status,
Quick Modules, Login) stays on-screen and tappable, instead of being
pushed off the right edge.
