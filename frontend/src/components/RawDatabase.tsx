import { useEffect, useState } from 'react';

/**
 * Every conversation ever recorded, dumped as-is.
 *
 * No interface. There was one - a list with export buttons - and it was the wrong
 * thing: this is a page you open to look at data, and a viewer built out of chat
 * bubbles is a worse reader than the browser's own JSON tree, which is in turn a worse
 * reader than `curl .../database | jq`. So the app gets out of the way and prints the
 * document.
 *
 * Which database follows from where the backend is running - SQLite on a laptop,
 * Firestore on Cloud Run - so this shows local runs locally and real ones in
 * production, with `store` in the payload saying which. That field matters: it is the
 * one thing you cannot tell by looking at the rows, and it decides whether what you
 * are reading is a benchmark you ran or something someone actually played.
 *
 * Rendered outside the chat window, not inside it. The window is a chat; this is a
 * file.
 */

interface RawDatabaseProps {
  api: string;
}

function RawDatabase({ api }: RawDatabaseProps) {
  const [text, setText] = useState('loading...');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.toString() ? `?${params}` : '';
    fetch(`${api}/database${query}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(d => setText(JSON.stringify(d, null, 2)))
      .catch(e => setText(e.message === '403'
        ? 'locked. add ?token=... to the url'
        : `could not read the database: ${e.message}`));
  }, [api]);

  return (
    <pre
      style={{
        /* Pinned to the viewport and scrolling itself, rather than growing and letting
           the page scroll. It cannot: index.css fixes html and body with overflow
           hidden so the chat window can never be scrolled off the screen, which is
           right for an app and leaves a document with nowhere to go. Taking the whole
           viewport back is simpler than unpicking that for one route. */
        position: 'fixed',
        inset: 0,
        margin: 0,
        padding: '16px',
        boxSizing: 'border-box',
        // Its own colours rather than the app's: the theme is built for glass over a
        // wallpaper, and this is a text file.
        background: '#111',
        color: '#d6d6d6',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: '12px',
        lineHeight: 1.5,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        // The shell fixes the viewport and hides overflow so the chat window can't be
        // scrolled off; a document has to be able to scroll.
        overflow: 'auto',
      }}
    >
      {text}
    </pre>
  );
}

export default RawDatabase;
