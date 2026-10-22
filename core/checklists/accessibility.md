# Accessibility

Load for any change to a user interface. Covers WCAG 2.2 AA essentials; it is not a full audit.

## Keyboard
- [ ] Every interactive element can be reached and operated with the keyboard alone.
- [ ] Tab order follows the visual and reading order.
- [ ] No keyboard trap; dialogs and menus close with Escape.
- [ ] Custom widgets implement the expected keys (arrows in menus, tabs, listboxes).

## Focus
- [ ] Focus is always visible, with sufficient contrast.
- [ ] Focused elements are not hidden behind sticky headers, footers or overlays.
- [ ] Opening a dialog moves focus into it; closing returns focus to the trigger.
- [ ] Route changes and dynamic content move focus or announce the change.

## Labels and names
- [ ] Every input has a visible label tied to it programmatically.
- [ ] Icon-only buttons and links have an accessible name.
- [ ] Link and button text says what it does without surrounding context.
- [ ] Images have meaningful alt text, or empty alt when decorative.

## Contrast and sizing
- [ ] Text contrast is at least 4.5:1 (3:1 for large text); UI component and focus contrast at least 3:1.
- [ ] Information is not conveyed by colour alone.
- [ ] Content reflows at 320 CSS px width and 200% zoom without loss or two-way scrolling.
- [ ] Pointer targets are at least 24 by 24 CSS px or adequately spaced.

## Semantics
- [ ] Native elements are used before ARIA (`button`, `a`, `label`, `table`).
- [ ] Headings form a logical outline; landmarks mark main regions.
- [ ] ARIA roles, states and properties are valid and kept in sync with the UI.

## Motion and timing
- [ ] Animations respect `prefers-reduced-motion`.
- [ ] Nothing flashes more than three times per second.
- [ ] Auto-moving content can be paused; time limits can be extended.

## Errors and forms
- [ ] Errors are described in text, next to the field, and announced to assistive technology.
- [ ] Required fields and formats are stated before submission.

## Verification
- [ ] An automated checker ran on changed screens with zero new violations, and the command is recorded.
- [ ] Changed flows were completed once with the keyboard only.
