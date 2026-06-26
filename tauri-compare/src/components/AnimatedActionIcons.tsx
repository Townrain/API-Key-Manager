import { motion } from 'framer-motion';

const spring = { type: 'spring' as const, damping: 10, stiffness: 200 };
const springFast = { type: 'spring' as const, damping: 10, stiffness: 250 };

// ─── Upload (Import) — card pops up, arrow shoots up ────────────────────
export function UploadIcon({ color, hovered }: { color: string; hovered: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Base bar */}
      <motion.rect
        x="2" y="13" width="14" height="2" rx="1"
        fill={color}
        animate={{ opacity: hovered ? 0.85 : 0.6 }}
        transition={spring}
      />
      {/* Card / document */}
      <motion.rect
        x="5" y="7" width="8" height="5" rx="1.5"
        stroke={color} strokeWidth="1.5" fill="none"
        animate={{ y: hovered ? 3.5 : 0 }}
        transition={spring}
      />
      {/* Arrow shaft */}
      <motion.line
        x1="9" y1="11.5" x2="9" y2="4"
        stroke={color} strokeWidth="1.5" strokeLinecap="round"
        animate={{ y: hovered ? -1.5 : 0 }}
        transition={springFast}
      />
      {/* Arrow head */}
      <motion.path
        d="M6 6.5L9 3.5L12 6.5"
        stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
        fill="none"
        animate={{ y: hovered ? -2 : 0 }}
        transition={springFast}
      />
    </svg>
  );
}

// ─── Shield (Check All) — scale pulse + checkmark draws in ──────────────
export function ShieldIcon({ color, hovered }: { color: string; hovered: boolean }) {
  return (
    <motion.div
      animate={{ scale: hovered ? 1.15 : 1 }}
      transition={spring}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18 }}
    >
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        {/* Shield outline */}
        <path
          d="M9 2L3 5V8.5C3 12.09 5.56 15.41 9 16.35C12.44 15.41 15 12.09 15 8.5V5L9 2Z"
          stroke={color} strokeWidth="1.5" strokeLinejoin="round" fill="none"
        />
        {/* Checkmark — appears on hover */}
        <motion.path
          d="M6 9.5L8 11.5L12 7"
          stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
          fill="none"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: hovered ? 1 : 0,
            opacity: hovered ? 1 : 0,
          }}
          transition={{
            pathLength: { duration: 0.4, ease: [0.34, 1.56, 0.64, 1] },
            opacity: { duration: 0.15 },
          }}
        />
      </svg>
    </motion.div>
  );
}

// ─── Rocket (Test All) — launches up + exhaust flames ────────────────────
export function RocketIcon({ color, hovered }: { color: string; hovered: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Rocket body — launches up on hover */}
      <motion.g
        animate={{ y: hovered ? -2 : 0 }}
        transition={spring}
      >
        {/* Body */}
        <path
          d="M9 2C9 2 5.5 5.5 5.5 10L7 12H11L12.5 10C12.5 5.5 9 2 9 2Z"
          stroke={color} strokeWidth="1.3" strokeLinejoin="round" fill="none"
        />
        {/* Window */}
        <circle cx="9" cy="7.5" r="1.3" stroke={color} strokeWidth="1" fill="none" />
        {/* Nose tip */}
        <circle cx="9" cy="4" r="0.5" fill={color} />
      </motion.g>

      {/* Exhaust flames — fade in on hover */}
      <motion.g
        animate={{ opacity: hovered ? 1 : 0 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
      >
        {/* Center flame */}
        <motion.path
          d="M8 12.5Q9 15.5 10 12.5"
          stroke={color} strokeWidth="1" strokeLinecap="round" fill="none"
          animate={{ scaleY: hovered ? 1.2 : 0.6 }}
          style={{ transformOrigin: '9px 12px' }}
          transition={springFast}
        />
        {/* Left spark */}
        <motion.circle
          cx="7" cy="14" r="0.6" fill={color}
          animate={{ y: hovered ? 0.5 : 0, opacity: hovered ? 0.7 : 0 }}
          transition={springFast}
        />
        {/* Right spark */}
        <motion.circle
          cx="11" cy="14" r="0.6" fill={color}
          animate={{ y: hovered ? 0.5 : 0, opacity: hovered ? 0.7 : 0 }}
          transition={springFast}
        />
      </motion.g>
    </svg>
  );
}

// ─── Download (Export) — arrow drops, container opens ────────────────────
export function DownloadIcon({ color, hovered }: { color: string; hovered: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Base bar */}
      <motion.rect
        x="2" y="14" width="14" height="2" rx="1"
        fill={color}
        animate={{ opacity: hovered ? 0.85 : 0.6 }}
        transition={spring}
      />
      {/* Container / tray */}
      <motion.rect
        x="5" y="9" width="8" height="4" rx="1.5"
        stroke={color} strokeWidth="1.5" fill="none"
        animate={{ scaleY: hovered ? 1.15 : 1 }}
        style={{ transformOrigin: 'center bottom' }}
        transition={spring}
      />
      {/* Arrow shaft — drops down */}
      <motion.line
        x1="9" y1="4" x2="9" y2="10.5"
        stroke={color} strokeWidth="1.5" strokeLinecap="round"
        animate={{ y: hovered ? 2 : 0 }}
        transition={springFast}
      />
      {/* Arrow head — drops down */}
      <motion.path
        d="M6 8L9 11L12 8"
        stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
        fill="none"
        animate={{ y: hovered ? 2.5 : 0 }}
        transition={springFast}
      />
    </svg>
  );
}

// ─── Trash (Clear) — lid lifts up from left side ────────────────────────
export function TrashIcon({ color, hovered }: { color: string; hovered: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      {/* Hinge (right end of lid — stays in place) */}
      <line x1="11" y1="5" x2="14" y2="5" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      {/* Lid left end — lifts up (y: 5 → 2.5) */}
      <motion.line
        x1="4" x2="11"
        stroke={color} strokeWidth="1.5" strokeLinecap="round"
        animate={{ y1: hovered ? 2.5 : 5, y2: hovered ? 4 : 5 }}
        transition={spring}
      />
      {/* Handle — lifts up with lid */}
      <motion.line
        x1="7" x2="11"
        stroke={color} strokeWidth="1.2" strokeLinecap="round"
        animate={{ y1: hovered ? 0.5 : 3, y2: hovered ? 2 : 3 }}
        transition={spring}
      />
      {/* Bin body */}
      <path
        d="M5.5 5H12.5L11.5 15.5H6.5L5.5 5Z"
        stroke={color} strokeWidth="1.3" strokeLinejoin="round" fill="none"
      />
      {/* Center line */}
      <line x1="8" y1="7.5" x2="8" y2="13" stroke={color} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
      {/* Side line */}
      <line x1="10" y1="7.5" x2="10" y2="13" stroke={color} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}
