import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Composition,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

// Thick black text outline via stacked text-shadow
const OUTLINE =
  '-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000,' +
  ' 0 3px 0 #000, 0 -3px 0 #000, 3px 0 0 #000, -3px 0 0 #000';

type Segment = {
  text: string;
  duration: number;
  audio_file: string;
  emoji?: string;
};

type ScriptData = {
  title: Segment;
  script: Segment[];
  url: string;
  workdir: string;
};

export type MainProps = {
  scriptData: ScriptData;
  part?: 1 | 2;
};

// ─── Word-by-word pop-in animation ───────────────────────────────────────────

const WordAnimation: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const words = text.split(' ');

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '12px',
        padding: '0 60px',
      }}
    >
      {words.map((word, i) => {
        // Words slide up quickly but stay fully opaque — no fade from black
        // between phrases (each Sequence resets frame to 0, so a 0-opacity
        // start would flash dark at every phrase boundary).
        const start = i * 2;
        const y = interpolate(frame, [start, start + 4], [14, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <span
            key={i}
            style={{
              opacity: 1,
              transform: `translateY(${y}px)`,
              fontSize: 60,
              fontWeight: 900,
              color: '#FFD700',
              fontFamily: '"Arial Black", Arial, sans-serif',
              textShadow: OUTLINE,
              lineHeight: 1.35,
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// ─── Single story segment (title card or body phrase) ────────────────────────

const ContentSequence: React.FC<{
  segment: Segment;
  isTitle: boolean;
  audioSrc: string;
  durationFrames: number;
  ctaText?: string;
  showPart2Badge?: boolean;
}> = ({
  segment,
  isTitle,
  audioSrc,
  durationFrames,
  ctaText = '💬 Comment your verdict below',
  showPart2Badge = false,
}) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Audio src={audioSrc} />

      {/* "PART 2" badge above the main banner — only on Part 2 title card */}
      {showPart2Badge && (
        <div
          style={{
            position: 'absolute',
            top: 76,
            left: 0,
            right: 0,
            textAlign: 'center',
          }}
        >
          <span
            style={{
              fontSize: 36,
              fontWeight: 900,
              color: '#FF8C00',
              fontFamily: '"Arial Black", Arial, sans-serif',
              textShadow: '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000',
              letterSpacing: 3,
            }}
          >
            PART 2
          </span>
        </div>
      )}

      {/* "AM I THE A-HOLE?" banner on title card */}
      {isTitle && (
        <div
          style={{
            position: 'absolute',
            top: 140,
            left: 0,
            right: 0,
            textAlign: 'center',
            padding: '0 60px',
          }}
        >
          <span
            style={{
              fontSize: 44,
              fontWeight: 900,
              color: '#FF4444',
              fontFamily: '"Arial Black", Arial, sans-serif',
              textShadow: '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000',
              letterSpacing: 2,
            }}
          >
            AM I THE A-HOLE?
          </span>
        </div>
      )}

      <WordAnimation text={segment.text} />

      {/* CTA badge pinned to bottom on all non-title segments */}
      {!isTitle && (
        <div
          style={{
            position: 'absolute',
            bottom: 180,
            left: 0,
            right: 0,
            textAlign: 'center',
          }}
        >
          <span
            style={{
              fontSize: 30,
              fontWeight: 700,
              color: '#FFD700',
              fontFamily: 'Arial, sans-serif',
              textShadow: '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000',
              opacity: interpolate(frame, [0, 10], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              }),
            }}
          >
            {ctaText}
          </span>
        </div>
      )}

    </AbsoluteFill>
  );
};

// ─── Referral promo (shown on every end card) ────────────────────────────────

const PromoLine: React.FC = () => (
  <div
    style={{
      marginTop: 30,
      background: 'rgba(0,0,0,0.55)',
      border: '3px solid #FFD700',
      borderRadius: 14,
      padding: '14px 20px',
      display: 'inline-block',
    }}
  >
    <div
      style={{
        fontSize: 34,
        fontWeight: 900,
        color: '#FFD700',
        fontFamily: '"Arial Black", Arial, sans-serif',
        textShadow: OUTLINE,
        lineHeight: 1.25,
      }}
    >
      🎁 Code <span style={{ color: '#fff' }}>JTMOTJCJ</span> on Tilt Rips
    </div>
    <div
      style={{
        fontSize: 27,
        fontWeight: 700,
        color: '#fff',
        marginTop: 6,
        fontFamily: 'Arial, sans-serif',
        textShadow: OUTLINE,
      }}
    >
      Deposit $10 → FREE $10 pack
    </div>
  </div>
);

// ─── Outro / follow card (pads short stories up to the 60s minimum) ───────────

const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const pop = interpolate(frame, [0, 8], [0.9, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ textAlign: 'center', padding: '0 60px', transform: `scale(${pop})` }}>
        <div
          style={{
            fontSize: 64,
            fontWeight: 900,
            color: '#FFD700',
            fontFamily: '"Arial Black", Arial, sans-serif',
            textShadow: OUTLINE,
            lineHeight: 1.2,
          }}
        >
          👍 Follow for more
        </div>
        <div
          style={{
            fontSize: 42,
            fontWeight: 700,
            color: '#fff',
            marginTop: 22,
            fontFamily: 'Arial, sans-serif',
            textShadow: OUTLINE,
          }}
        >
          💬 Comment your verdict
        </div>
        <PromoLine />
      </div>
    </AbsoluteFill>
  );
};

// ─── "Continues in Part 2" end card (closes Part 1 of a split) ───────────────

const Part2Cue: React.FC = () => {
  const frame = useCurrentFrame();
  const pop = interpolate(frame, [0, 10], [0.85, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // gentle pulse so it reads as a call to action, not a static card
  const pulse = 1 + 0.04 * Math.sin(frame / 5);
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <AbsoluteFill style={{ backgroundColor: 'rgba(0,0,0,0.55)' }} />
      <div style={{ textAlign: 'center', padding: '0 50px', transform: `scale(${pop})` }}>
        <div
          style={{
            fontSize: 92,
            fontWeight: 900,
            color: '#fff',
            fontFamily: '"Arial Black", Arial, sans-serif',
            textShadow: OUTLINE,
            lineHeight: 1.05,
          }}
        >
          TO BE
          <br />
          CONTINUED
        </div>
        <div
          style={{
            display: 'inline-block',
            marginTop: 30,
            background: '#FF2D55',
            color: '#fff',
            fontSize: 62,
            fontWeight: 900,
            fontFamily: '"Arial Black", Arial, sans-serif',
            letterSpacing: 3,
            padding: '14px 40px',
            borderRadius: 18,
            border: '6px solid #000',
            transform: `scale(${pulse})`,
          }}
        >
          WATCH PART 2
        </div>
        <div
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: '#FFD700',
            marginTop: 26,
            fontFamily: 'Arial, sans-serif',
            textShadow: OUTLINE,
          }}
        >
          👉 On my profile now
        </div>
        <PromoLine />
      </div>
    </AbsoluteFill>
  );
};

// ─── Root composition ─────────────────────────────────────────────────────────

// TikTok monetization requires videos >= 60s.
const MIN_SEC = 60;
const MIN_FRAMES = MIN_SEC * FPS;
const PAD_FRAMES = 2; // breathing room appended to each phrase

const segSeconds = (seg: Segment) => seg.duration + PAD_FRAMES / FPS;
const sum = (a: number[]) => a.reduce((s, n) => s + n, 0);

// "Continues in Part 2" end card shown at the end of Part 1.
const CUE_SEC = 2.5;
const CUE_FRAMES = Math.round(CUE_SEC * FPS);

/**
 * Where part 2 starts, or null to keep the story whole.
 *
 * A story is only cut in half when BOTH halves still clear the 60s
 * monetization floor (each part replays the title card). That keeps long
 * stories watchable without making either part ineligible for Creator Rewards.
 * Of all legal cut points we take the one closest to the middle.
 */
export function splitIndex(data: ScriptData): number | null {
  const body = data.script;
  if (body.length < 2) return null;
  const titleSec = segSeconds(data.title);
  const bodySecs = body.map(segSeconds);
  const bodyTotal = sum(bodySecs);
  // Part 1 = title + first half + "continues in Part 2" cue.
  // Part 2 = second half ONLY (it does not re-read the title).
  // fast reject: even the best cut can't give two 60s parts
  if (titleSec + CUE_SEC + bodyTotal < MIN_SEC * 2) return null;

  const middle = bodyTotal / 2;
  let best: number | null = null;
  let bestDist = Infinity;
  let acc = 0;
  for (let i = 0; i < body.length - 1; i++) {
    acc += bodySecs[i];
    const cut = i + 1;
    const p1 = titleSec + acc + CUE_SEC;
    const p2 = bodyTotal - acc;
    if (p1 < MIN_SEC || p2 < MIN_SEC) continue;
    const dist = Math.abs(acc - middle);
    if (dist < bestDist) {
      bestDist = dist;
      best = cut;
    }
  }
  return best;
}

export const Main: React.FC<MainProps> = ({ scriptData, part }) => {
  const mid = splitIndex(scriptData);
  const isSplit = mid !== null;
  const scriptSlice = !part || !isSplit
    ? scriptData.script
    : part === 1
    ? scriptData.script.slice(0, mid as number)
    : scriptData.script.slice(mid as number);

  // Part 2 does NOT re-read the title — it drops straight back into the story
  // (the persistent PART 2 banner tells viewers where they are instead).
  const isPart2Split = isSplit && part === 2;
  const isPart1Split = isSplit && part === 1;
  const segments = isPart2Split ? scriptSlice : [scriptData.title, ...scriptSlice];
  const lastIdx = segments.length - 1;

  // Build sequence timing — each phrase gets its audio duration + breathing room
  let offset = 0;
  const items = segments.map((seg, i) => {
    const durationFrames = Math.ceil(seg.duration * FPS) + PAD_FRAMES;
    const from = offset;
    offset += durationFrames;
    const isTitle = !isPart2Split && i === 0;
    const audioSrc = isTitle
      ? staticFile('sounds/title.mp3')
      : staticFile(`sounds/${seg.audio_file}`);
    return { seg, from, durationFrames, audioSrc, isTitle };
  });

  // Tail card: Part 1 of a split ends on an explicit "continues in Part 2" cue;
  // everything else pads with the follow/CTA card. Either way >= 60s.
  const contentEnd = offset;
  const minTotal = isPart1Split ? contentEnd + CUE_FRAMES : contentEnd;
  const totalFrames = Math.max(minTotal, MIN_FRAMES);
  const outroFrames = totalFrames - contentEnd;

  return (
    <AbsoluteFill style={{ backgroundColor: '#000' }}>
      {/* Minecraft parkour — looping background, muted */}
      <OffthreadVideo
        src={staticFile('parkour.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        muted
        loop
      />

      {/* Subtle dark overlay so white text stays readable */}
      <AbsoluteFill style={{ backgroundColor: 'rgba(0,0,0,0.38)' }} />

      {/* PART 2 banner — on screen from frame 0 so whatever frame TikTok grabs
          for the thumbnail clearly reads PART 2 */}
      {part === 2 && isSplit && (
        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          <div style={{ position: 'absolute', top: 56, left: 0, right: 0, textAlign: 'center' }}>
            <span
              style={{
                display: 'inline-block',
                background: '#FF2D55',
                color: '#fff',
                fontSize: 54,
                fontWeight: 900,
                fontFamily: '"Arial Black", Arial, sans-serif',
                letterSpacing: 5,
                padding: '10px 34px',
                borderRadius: 14,
                border: '5px solid #000',
                textShadow: OUTLINE,
              }}
            >
              PART 2
            </span>
          </div>
        </AbsoluteFill>
      )}

      {/* Story segments */}
      {items.map(({ seg, from, durationFrames, audioSrc, isTitle }, i) => (
        <Sequence key={i} from={from} durationInFrames={durationFrames} name={isTitle ? 'Title' : `Phrase ${i}`}>
          <ContentSequence
            segment={seg}
            isTitle={isTitle}
            audioSrc={audioSrc}
            durationFrames={durationFrames}
            ctaText={
              !isTitle && i === lastIdx && part === 1 && isSplit
                ? '👀 Watch Part 2!'
                : undefined
            }
            showPart2Badge={false}
          />
        </Sequence>
      ))}

      {/* Tail card: explicit Part 2 hand-off on Part 1, otherwise the follow/CTA
          pad that keeps every render >= 60s */}
      {outroFrames > 0 && (
        <Sequence
          from={contentEnd}
          durationInFrames={outroFrames}
          name={isPart1Split ? 'Part2Cue' : 'Outro'}
        >
          {isPart1Split ? <Part2Cue /> : <Outro />}
        </Sequence>
      )}
    </AbsoluteFill>
  );
};

// ─── Remotion entry point ─────────────────────────────────────────────────────

// Single full-story video (no part split); enforces the 60s minimum.
async function calculateMetadataFull() {
  const response = await fetch(staticFile('script.json'));
  const data = (await response.json()) as ScriptData;
  const contentFrames = [data.title, ...data.script].reduce(
    (sum, seg) => sum + Math.ceil(seg.duration * FPS) + 2,
    0,
  );
  const totalFrames = Math.max(contentFrames, MIN_FRAMES);
  return {
    durationInFrames: totalFrames,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
    props: { scriptData: data } as MainProps,
  };
}

// Part1 / Part2 for stories long enough that BOTH halves clear 60s.
// When a story isn't long enough to split, Part1 renders the whole video and
// Part2 collapses to a 1-frame stub the workflow never renders / downloader drops.
function makeCalculateMetadataPart(part: 1 | 2) {
  return async () => {
    const response = await fetch(staticFile('script.json'));
    const data = (await response.json()) as ScriptData;
    const mid = splitIndex(data);
    const isSplit = mid !== null;

    if (part === 2 && !isSplit) {
      return {
        durationInFrames: 1,
        fps: FPS,
        width: WIDTH,
        height: HEIGHT,
        props: { scriptData: data, part } as MainProps,
      };
    }

    const slice = !isSplit
      ? data.script
      : part === 1
      ? data.script.slice(0, mid as number)
      : data.script.slice(mid as number);

    // Part 2 of a split skips the title; Part 1 gains the "continues" cue card.
    const segs = isSplit && part === 2 ? slice : [data.title, ...slice];
    const contentFrames = segs.reduce(
      (s, seg) => s + Math.ceil(seg.duration * FPS) + PAD_FRAMES,
      0,
    );
    const withCue =
      isSplit && part === 1 ? contentFrames + CUE_FRAMES : contentFrames;
    return {
      durationInFrames: Math.max(withCue, MIN_FRAMES),
      fps: FPS,
      width: WIDTH,
      height: HEIGHT,
      props: { scriptData: data, part } as MainProps,
    };
  };
}

const PLACEHOLDER: MainProps = {
  scriptData: {
    title: {
      text: 'Put script.json in video-generator/public/ to preview',
      duration: 3,
      audio_file: 'title.mp3',
    },
    script: [],
    url: '',
    workdir: '',
  },
};

export const RemotionVideo: React.FC = () => {
  return (
    <>
      <Composition
        id="Full"
        component={Main}
        calculateMetadata={calculateMetadataFull}
        defaultProps={{ ...PLACEHOLDER }}
        durationInFrames={MIN_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      {/* Part1/Part2 — a real split only when both halves clear 60s, otherwise
          Part1 is the whole (monetizable) video and Part2 is a dropped stub. */}
      <Composition
        id="Part1"
        component={Main}
        calculateMetadata={makeCalculateMetadataPart(1)}
        defaultProps={{ ...PLACEHOLDER, part: 1 as const }}
        durationInFrames={MIN_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      <Composition
        id="Part2"
        component={Main}
        calculateMetadata={makeCalculateMetadataPart(2)}
        defaultProps={{ ...PLACEHOLDER, part: 2 as const }}
        durationInFrames={MIN_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    </>
  );
};
