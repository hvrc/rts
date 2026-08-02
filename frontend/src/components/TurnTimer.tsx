import { useEffect, useRef, useState } from 'react';
import './turnTimer.css';

/**
 * The seconds you have to answer, drawn as a draining arc.
 *
 * Driven by a deadline timestamp rather than a decrementing counter: a tab that gets
 * backgrounded has its timers throttled, and a counter would quietly run slow and hand
 * back seconds nobody was given. Comparing against a wall-clock deadline means the arc
 * is always showing the time that has actually passed.
 *
 * The arc is redrawn on an animation frame so it sweeps smoothly, and the parent is
 * told once, on the frame the deadline passes.
 */
const SIZE = 22;
const STROKE = 2.5;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** How long the arc takes to sweep back up when a new turn starts. */
const REFILL_MS = 450;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

interface TurnTimerProps {
  /** Wall-clock ms when the turn expires, or null when no clock is running. */
  deadline: number | null;
  /** Total length of a turn, so the arc knows what "full" is. */
  duration: number;
  onExpire: () => void;
}

function TurnTimer({ deadline, duration, onExpire }: TurnTimerProps) {
  const [fraction, setFraction] = useState(1);

  // What was on screen when the last turn ended. The refill sweeps up from here rather
  // than from empty, so handing the clock over reads as one continuous movement instead
  // of a snap to zero followed by a snap to full.
  const shown = useRef(1);
  shown.current = fraction;

  useEffect(() => {
    if (deadline === null) return;    // clock stopped: hold the arc where it is

    const from = shown.current;
    const startedAt = Date.now();
    let frame = 0;
    let fired = false;

    const tick = () => {
      const now = Date.now();
      const filling = now - startedAt;

      if (filling < REFILL_MS) {
        // Sweeping back up. The deadline is already running underneath this - the
        // refill is a few hundred milliseconds of a turn worth many seconds, and
        // pausing the clock to play an animation would be lying about the time left.
        setFraction(from + (1 - from) * easeOut(filling / REFILL_MS));
      } else {
        const left = deadline - now;
        setFraction(Math.max(0, Math.min(1, left / duration)));
        if (left <= 0) {
          if (!fired) {
            fired = true;      // the frame after expiry can still run; only fire once
            onExpire();
          }
          return;
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(frame);
  }, [deadline, duration, onExpire]);

  const seconds = Math.ceil((fraction * duration) / 1000);

  // White while there is time, amber as it gets tight, red at the end. Three states
  // rather than a continuous gradient: a colour that drifts imperceptibly reads as no
  // signal at all, whereas a change you notice is the whole point of a clock.
  const phase = fraction > 0.6 ? 'calm' : fraction > 0.3 ? 'warn' : 'urgent';

  return (
    <div
      className={`rts-timer is-${phase}${deadline === null ? ' is-idle' : ''}`}
      aria-label={deadline === null ? 'no timer running' : `${seconds} seconds left`}
      title={deadline === null ? '' : `${seconds}s`}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {/* The groove the arc drains out of. */}
        <circle
          className="rts-timer-track"
          cx={SIZE / 2} cy={SIZE / 2} r={RADIUS}
          fill="none" strokeWidth={STROKE}
        />
        {/* Rotated so it starts at twelve o'clock and unwinds clockwise, which is
            what a countdown reads as. */}
        <circle
          className="rts-timer-arc"
          cx={SIZE / 2} cy={SIZE / 2} r={RADIUS}
          fill="none" strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - fraction)}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </svg>
    </div>
  );
}

export default TurnTimer;
