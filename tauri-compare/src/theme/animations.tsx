import React, { type CSSProperties } from 'react';
import { motion } from 'framer-motion';

// ─── HoverPress: Physical "press down" on hover (y: 3px) ─────────────────
// Matches Flutter HoverPress with pressDepth=3, enter 350ms, exit 180ms

interface HoverPressProps {
  children: React.ReactNode;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
  pressDepth?: number;
}

export function HoverPress({ children, style, className, onClick, pressDepth = 3 }: HoverPressProps) {
  return (
    <motion.div
      whileHover={{ y: pressDepth }}
      transition={{ type: 'spring', damping: 12, stiffness: 300 }}
      style={style}
      className={className}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );
}

// ─── BouncyPress: Tap scale with spring bounce-back ──────────────────────
// Matches Flutter BouncyPress with scaleDown=0.97

interface BouncyPressProps {
  children: React.ReactNode;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
  scaleDown?: number;
  disabled?: boolean;
}

export function BouncyPress({ children, style, className, onClick, scaleDown = 0.95, disabled }: BouncyPressProps) {
  return (
    <motion.div
      whileTap={disabled ? undefined : { scale: scaleDown }}
      transition={{ type: 'spring', damping: 12, stiffness: 300 }}
      style={{ ...style, cursor: disabled ? 'default' : style?.cursor ?? 'pointer' }}
      className={className}
      onClick={disabled ? undefined : onClick}
    >
      {children}
    </motion.div>
  );
}

// ─── HoverPress + BouncyPress combined ───────────────────────────────────

interface PressableProps {
  children: React.ReactNode;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
  pressDepth?: number;
  scaleDown?: number;
  disabled?: boolean;
}

export function Pressable({ children, style, className, onClick, pressDepth = 3, scaleDown = 0.95, disabled }: PressableProps) {
  return (
    <motion.div
      whileHover={{ y: pressDepth }}
      whileTap={disabled ? undefined : { scale: scaleDown }}
      transition={{ type: 'spring', damping: 12, stiffness: 300 }}
      style={style}
      className={className}
      onClick={disabled ? undefined : onClick}
    >
      {children}
    </motion.div>
  );
}

// ─── StaggeredFadeIn: List item stagger animation ────────────────────────
// Matches Flutter StaggeredFadeIn: 60ms delay, 400ms duration, 12px translate

interface StaggeredFadeInProps {
  children: React.ReactNode;
  index: number;
  delayStep?: number;
  duration?: number;
  yOffset?: number;
  style?: CSSProperties;
}

export function StaggeredFadeIn({ children, index, delayStep = 0.06, duration = 0.4, yOffset = 12, style }: StaggeredFadeInProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: yOffset }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration,
        delay: index * delayStep,
        ease: [0, 0, 0.2, 1],
      }}
      style={style}
    >
      {children}
    </motion.div>
  );
}

// ─── Re-export motion for convenience ────────────────────────────────────
export { motion, AnimatePresence } from 'framer-motion';
