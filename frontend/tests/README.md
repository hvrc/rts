# Browser checks

Three things that are cheap to get right by hand once and easy to break on the next
refactor, so they are measured rather than eyeballed:

    node tests/scroll.cjs    the newest message never lands behind the composer
    node tests/routes.cjs    URLs, invitation links, and the lights spelling out
    node tests/panels.cjs    the appearance panel, and the bars not cutting bubbles

They drive a real Chrome against a running dev server - `npm run dev` on :5174 and the
backend on :5001 - because all three are questions about rendered geometry and browser
history, and none of them can be answered by a renderer that only pretends to lay out.

`scroll.cjs` in particular measures the gap between the last bubble and the input bar
rather than the code that is meant to produce it, so it catches the bug however it is
caused. That mattered: the first fix for it was wrong in a way that reading the code
did not reveal.

They talk to a live model, so a full run takes a few minutes and costs tokens.
