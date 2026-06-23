"use client";

import styles from "./WelcomeScreen.module.css";

const SUGGESTIONS = [
  { icon: "⚖️", text: "Nghị định 08/2022/NĐ-CP quy định thế nào về giấy phép môi trường?", color: "#8b5cf6" }, // Pháp lý
  { icon: "🧪", text: "QCVN 40:2011/BTNMT quy định ngưỡng xả thải thông số COD là bao nhiêu?", color: "#10b981" }, // Thông số
  { icon: "📝", text: "Quy trình quan trắc lấy mẫu mẫu nước thải định kỳ gồm những bước nào?", color: "#f59e0b" }, // Quy trình
  { icon: "📂", text: "Hồ sơ đề nghị cấp giấy phép môi trường và lập báo cáo cần tài liệu gì?", color: "#3b82f6" }, // Hồ sơ
  { icon: "⚙️", text: "Các bước hiệu chuẩn, bảo trì máy đo pH và DO cầm tay trước khi ra hiện trường?", color: "#64748b" }, // Vận hành
];

interface Props {
  userName?: string;
  onSuggestionClick: (text: string) => void;
}

export default function WelcomeScreen({ userName, onSuggestionClick }: Props) {
  return (
    <div className={styles.container}>
      <div className={styles.emoji}>👋</div>
      <h1 className={styles.title}>Xin chào, {userName || "Admin"}!</h1>
      <p className={styles.subtitle}>
        Hôm nay tôi có thể giúp gì cho bạn?
      </p>

      <div className={styles.suggestions}>
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            className={styles.card}
            style={{ borderLeftColor: s.color }}
            onClick={() => onSuggestionClick(s.text)}
            type="button"
          >
            <span className={styles.cardIcon}>{s.icon}</span>
            <span className={styles.cardText}>{s.text}</span>
            <span className={styles.cardArrow}>→</span>
          </button>
        ))}
      </div>
    </div>
  );
}
