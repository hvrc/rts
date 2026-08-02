import { useCallback, useEffect, useRef, useState } from 'react';
import './rooms.css';
import { knownAs, savedName, type Member, type RoomMessage, type RoomState, type Rooms as RoomsApi } from '../lib/rooms';

/**
 * The lobby, built out of the chat's own parts.
 *
 * Rooms arrive as bubbles from the left and you answer in bubbles on the right, so
 * picking a room is the same gesture as playing a word - the list *is* a conversation,
 * and `r` swapping one for the other reads as the window turning round rather than as
 * a different screen. Everything here is `.rts-bubble`, which means the glass, the
 * accent and the theme all follow along without this file knowing they exist.
 *
 * Two ways in, and they ask for exactly what they need: a new room needs a name for
 * itself and a name for you, an existing one only needs yours.
 */

interface RoomsProps {
  api: RoomsApi;
  /** Somebody got in. The parent takes over from here. */
  onEnter: (room: RoomState, messages: RoomMessage[], you: Member) => void;
  reverse: boolean;
  /** Arrived by link: open this room's join form rather than the list. */
  joining?: string | null;
  /** The list is being shown, so the URL should say so. */
  onBrowse?: () => void;
}

type Mode =
  | { at: 'list' }
  | { at: 'new' }
  | { at: 'join'; room: RoomState }
  /** Following a link: we have a name but not the room behind it yet. */
  | { at: 'finding'; slug: string };

/** How often the list refreshes while you're looking at it. */
const POLL_MS = 4000;

function Rooms({ api, onEnter, reverse, joining, onBrowse }: RoomsProps) {
  const [rooms, setRooms] = useState<RoomState[]>([]);
  const [mode, setMode] = useState<Mode>(
    joining ? { at: 'finding', slug: joining } : { at: 'list' });
  const [who, setWho] = useState(savedName);
  const [roomName, setRoomName] = useState('');
  const [bot, setBot] = useState(true);
  const [timer, setTimer] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);

  // The lobby is the one place a poll is the right tool: you are not in any of these
  // rooms yet, so there is no event stream to be on, and opening one per listed room
  // to watch a number change would be absurd.
  useEffect(() => {
    let live = true;
    const pull = async () => {
      try {
        const { rooms: next } = await api.list();
        if (live) setRooms(next);
      } catch {
        /* the lobby going stale for four seconds is not worth an error state */
      }
    };
    pull();
    const every = window.setInterval(pull, POLL_MS);
    return () => { live = false; clearInterval(every); };
  }, [api]);

  useEffect(() => {
    if (mode.at !== 'list' && mode.at !== 'finding') field.current?.focus();
  }, [mode]);

  /* Turn a slug from the address bar into a room. Somebody arriving on a link has
     never seen the lobby and shouldn't have to: the only thing between them and the
     room is a name, so that is the only thing to ask for. */
  useEffect(() => {
    if (mode.at !== 'finding') return;
    let live = true;
    const slug = mode.slug;

    api.get(slug)
      .then(({ room }) => {
        if (!live) return null;

        // You have been in here before, so walk back in. Deliberately not "are you
        // currently a member": closing the tab reports you as gone, and a reload is
        // indistinguishable from that, so membership would make every refresh ask a
        // room you have been talking in for ten minutes who you are.
        const before = knownAs(slug);
        if (before) {
          return api.join(slug, before)
            .then(got => { if (live) onEnter(got.room, got.messages, got.you); });
        }
        setMode({ at: 'join', room });
        return null;
      })
      .catch(() => {
        if (!live) return;
        setError('that room has gone');
        setMode({ at: 'list' });
      });

    return () => { live = false; };
  }, [api, mode, onEnter]);

  /* Whenever the list is what's showing, the URL should be /rooms - including after
     backing out of a join form, so the address bar never claims you're somewhere you
     have just left. */
  useEffect(() => {
    if (mode.at === 'list') onBrowse?.();
  }, [mode.at, onBrowse]);

  const enter = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const name = who.trim();
    if (!name || busy) return;
    setBusy(true);
    setError(null);
    try {
      const got = mode.at === 'new'
        ? await api.create(roomName.trim() || 'room', name, { bot, timer, reverse })
        : mode.at === 'join'
          ? await api.join(mode.room.id, name)
          : null;
      if (got) onEnter(got.room, got.messages, got.you);
    } catch (err) {
      setError((err as Error).message === 'no such room'
        ? 'that room is gone'
        : "couldn't get in - try again");
      setBusy(false);
    }
  }, [api, bot, mode, onEnter, reverse, roomName, timer, who, busy]);

  const ask = (text: string) => (
    <div className="rts-msg is-bot">
      <div className="rts-msg-body"><div className="rts-bubble">{text}</div></div>
    </div>
  );

  if (mode.at === 'finding') {
    return <div className="rts-lobby">{ask(`looking for ${mode.slug}...`)}</div>;
  }

  if (mode.at !== 'list') {
    const fresh = mode.at === 'new';
    return (
      <form className="rts-lobby" onSubmit={enter}>
        {ask(fresh ? 'room name?' : `joining ${mode.room.name}`)}

        {fresh && (
          <div className="rts-msg is-user">
            <div className="rts-msg-body">
              <label className="rts-bubble is-user rts-field">
                <input
                  ref={field}
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  placeholder="room name"
                  maxLength={32}
                />
              </label>
            </div>
          </div>
        )}

        {ask('your name?')}

        <div className="rts-msg is-user">
          <div className="rts-msg-body">
            <label className="rts-bubble is-user rts-field">
              <input
                ref={fresh ? undefined : field}
                value={who}
                onChange={(e) => setWho(e.target.value)}
                placeholder="your name"
                maxLength={24}
              />
            </label>
          </div>
        </div>

        {/* Room settings, only when there's a room being made. Changing them later is
            done from inside, where everyone in the room can see it happen. */}
        {fresh && (
          <div className="rts-msg is-user">
            <div className="rts-msg-body rts-opts">
              <button type="button" onClick={() => setBot(b => !b)}
                      className={`rts-bubble is-user rts-opt${bot ? ' is-on' : ''}`}>
                {bot ? 'bot plays' : 'no bot'}
              </button>
              <button type="button" onClick={() => setTimer(t => !t)}
                      className={`rts-bubble is-user rts-opt${timer ? ' is-on' : ''}`}>
                {timer ? '20s' : 'no clock'}
              </button>
            </div>
          </div>
        )}

        {error && ask(error)}

        <div className="rts-msg is-user">
          <div className="rts-msg-body rts-opts">
            <button type="button" className="rts-bubble is-user rts-opt"
                    onClick={() => { setMode({ at: 'list' }); setError(null); }}>
              back
            </button>
            <button type="submit" className="rts-bubble is-user rts-opt is-go"
                    disabled={!who.trim() || busy}>
              {busy ? '...' : fresh ? 'create' : 'join'}
            </button>
          </div>
        </div>
      </form>
    );
  }

  return (
    <div className="rts-lobby">
      {/* A link to a room that has since been dropped lands here. Saying so matters:
          otherwise following an invitation and arriving at a list of other people's
          rooms looks like the link was never anything in particular. */}
      {error && ask(error)}
      {ask(rooms.length ? 'rooms' : 'no rooms yet. create one?')}

      <div className="rts-msg is-bot">
        <div className="rts-msg-body">
          <button className="rts-bubble rts-room is-new"
                  onClick={() => setMode({ at: 'new' })}>
            <span className="rts-room-name">+ new room</span>
          </button>
        </div>
      </div>

      {rooms.map((room) => (
        <div className="rts-msg is-bot" key={room.id}>
          <div className="rts-msg-body">
            <button className="rts-bubble rts-room"
                    onClick={() => setMode({ at: 'join', room })}>
              <span className="rts-room-name">{room.name}</span>
              <span className="rts-room-meta">
                {room.count === 0 ? 'empty'
                  : room.count === 1 ? '1 here'
                  : `${room.count} here`}
                {room.bot ? ' · bot' : ''}
                {room.timer ? ' · 20s' : ''}
              </span>
              {/* Who's actually in there. The list is a decision, and the useful half
                  of it is the names - a count tells you a room is busy, the names tell
                  you whether it's busy with anyone you know. */}
              {room.members.length > 0 && (
                <span className="rts-room-who">
                  {room.members.map(m => m.name).join(', ')}
                </span>
              )}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default Rooms;
