"use client";

import { motion, type Variants } from "motion/react";
import type { ReactNode } from "react";

const EASE = [0.16, 1, 0.3, 1] as const;

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}

/** Fade + rise on mount. Precision-tier default for content blocks. */
export function Reveal({ children, className, delay = 0, y = 12 }: RevealProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

const container: Variants = {
  hidden: {},
  show: (gap: number) => ({
    transition: { staggerChildren: gap, delayChildren: 0.04 },
  }),
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

interface StaggerProps {
  children: ReactNode;
  className?: string;
  gap?: number;
}

/** Staggered reveal container — pair with StaggerItem for grids/lists. */
export function Stagger({ children, className, gap = 0.06 }: StaggerProps) {
  return (
    <motion.div
      className={className}
      variants={container}
      custom={gap}
      initial="hidden"
      animate="show"
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={item}>
      {children}
    </motion.div>
  );
}
