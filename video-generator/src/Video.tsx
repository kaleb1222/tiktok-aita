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
      </div>
    </AbsoluteFill>
  );
};

// ─── Root composition ─────────────────────────────────────────────────────────

// TikTok monetization requires videos >= 60s.
const MIN_FRAMES = 60 * FPS;

export const Main: React.FC<MainProps> = ({ scriptData, part }) => {
  const mid = Math.ceil(scriptData.script.length / 2);
  const scriptSlice = !part
    ? scriptData.script
    : part === 1
    ? scriptData.script.slice(0, mid)
    : scriptData.script.slice(mid);

  const segments = [scriptData.title, ...scriptSlice];
  const lastIdx = segments.length - 1;

  // Build sequence timing — each phrase gets its audio duration + 15-frame breathing room
  let offset = 0;
  const items = segments.map((seg, i) => {
    const durationFrames = Math.ceil(seg.duration * FPS) + 2;
    const from = offset;
    offset += durationFrames;
    const audioSrc =
      i === 0 ? staticFile('sounds/title.mp3') : staticFile(`sounds/${seg.audio_file}`);
    return { seg, from, durationFrames, audioSrc, isTitle: i === 0 };
  });

  // Pad the tail with a follow/CTA card so every video is at least 60s.
  const contentEnd = offset;
  const totalFrames = Math.max(contentEnd, MIN_FRAMES);
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

      {/* Story segments */}
      {items.map(({ seg, from, durationFrames, audioSrc, isTitle }, i) => (
        <Sequence key={i} from={from} durationInFrames={durationFrames} name={isTitle ? 'Title' : `Phrase ${i}`}>
          <ContentSequence
            segment={seg}
            isTitle={isTitle}
            audioSrc={audioSrc}
            durationFrames={durationFrames}
            ctaText={!isTitle && i === lastIdx && part === 1 ? '👀 Watch Part 2!' : undefined}
            showPart2Badge={isTitle && part === 2}
          />
        </Sequence>
      ))}

      {/* Outro pad — keeps every render >= 60s (mostly relevant for short stories) */}
      {outroFrames > 0 && (
        <Sequence from={contentEnd} durationInFrames={outroFrames} name="Outro">
          <Outro />
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

// Part2 is a throwaway stub (the CI workflow file can't be changed by this
// token's scope, so it still renders a "Part2"). Keep it tiny; the downloader
// discards it and keeps the full Part1 render.
async function calculateMetadataStub() {
  return {
    durationInFrames: 30,
    fps: FPS,
    width: WIDTH,
    height: HEIGHT,
    props: { ...PLACEHOLDER } as MainProps,
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
      {/* Part1/Part2 kept for the (unchangeable) CI workflow, but both now
          render the single full >=60s video so every upload is monetizable. */}
      <Composition
        id="Part1"
        component={Main}
        calculateMetadata={calculateMetadataFull}
        defaultProps={{ ...PLACEHOLDER }}
        durationInFrames={MIN_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      <Composition
        id="Part2"
        component={Main}
        calculateMetadata={calculateMetadataStub}
        defaultProps={{ ...PLACEHOLDER }}
        durationInFrames={30}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    </>
  );
};
