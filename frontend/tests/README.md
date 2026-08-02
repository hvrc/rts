# Browser checks

Three things that are cheap to get right by hand once and easy to break on the next
refactor, so they are measured rather than eyeballed:

    node tests/scroll.cjs    the newest message never lands behind the composer
    node tests/routes.cjs    URLs, invitation links, and the lights spelling out
    node tests/panels.cjs    the appearance panel, and the bars not cutting bubbles
    node tests/chrome.cjs    --chrome-top tracks the header through every state

/database has no test: it fetches one document and prints it, and there is nothing
between those two steps worth pinning down.

They drive a real Chrome against a running dev server - `npm run dev` on :5174 and the
backend on :5001 - because all three are questions about rendered geometry and browser
history, and none of them can be answered by a renderer that only pretends to lay out.

`scroll.cjs` in particular measures the gap between the last bubble and the input bar
rather than the code that is meant to produce it, so it catches the bug however it is
caused. That mattered: the first fix for it was wrong in a way that reading the code
did not reveal.

`chrome.cjs` walks the combinations rather than checking one state, because the bug it
covers only appeared in a particular order: open the appearance panel, then open the
lobby, which removes the composer and used to take the whole measurement down with it.

Before deploying, run `npm run build`, not `vite build`. The two are not the same
check: the real build is `tsc -b && vite build`, and `tsc -b` applies
tsconfig.app.json - where `erasableSyntaxOnly` lives - while a bare `tsc --noEmit`
reads the root config and a bare `vite build` uses esbuild, which strips types without
looking at them. A constructor parameter property passed both of those and failed the
deploy.

They talk to a live model, so a full run takes a few minutes and costs tokens.
