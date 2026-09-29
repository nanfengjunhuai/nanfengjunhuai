# theme probe

Verification fixture — delete once the mechanism is settled.

Whether GitHub rewrites a **relative** path at page-render time differs between
`<img>` and `<picture><source>`, and that decides whether the images load at
all on a network where `raw.githubusercontent.com` is unreliable. The markdown
API proves the sanitizer keeps both forms; it does not prove the page rewrites
them, because rewriting happens later. Only a rendered page settles it.

## A: img + fragment, relative

<img src="assets/hero-dark.svg#gh-dark-mode-only" alt="A dark" width="100%">
<img src="assets/hero-light.svg#gh-light-mode-only" alt="A light" width="100%">

## B: picture + relative srcset

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img src="assets/hero-light.svg" alt="B" width="100%">
</picture>
