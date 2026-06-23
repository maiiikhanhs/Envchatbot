"use client";

import type { RouterLabel } from "@/types";
import styles from "./RouterBadge.module.css";

const LABEL_MAP: Record<string, { icon: string; text: string; className: string }> = {
  PHAP_LY: { icon: "⚖️", text: "Pháp lý", className: styles.phapLy },
  THONG_SO: { icon: "📊", text: "Thông số", className: styles.thongSo },
  QUY_TRINH: { icon: "🔬", text: "Quy trình", className: styles.quyTrinh },
  HO_SO: { icon: "📋", text: "Hồ sơ", className: styles.hoSo },
  VAN_HANH: { icon: "🔧", text: "Vận hành", className: styles.vanHanh },
};

type BadgeVariant = 'soft' | 'outline' | 'solid' | 'glow' | 'tech';

const VARIANT_MAP: Record<BadgeVariant, string> = {
  soft: styles.variantSoft,
  outline: styles.variantOutline,
  solid: styles.variantSolid,
  glow: styles.variantGlow,
  tech: styles.variantTech,
};

interface Props {
  label: RouterLabel;
  variant?: BadgeVariant;
}

export default function RouterBadge({ label, variant = 'glow' }: Props) {
  const info = LABEL_MAP[label];
  if (!info) return null;

  const variantClass = VARIANT_MAP[variant] || VARIANT_MAP.glow;

  return (
    <span className={`${styles.badge} ${info.className} ${variantClass}`}>
      {info.icon} {info.text}
    </span>
  );
}
