"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import styles from "../login/page.module.css";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim() || !confirmPassword.trim()) {
      setError("Vui lòng nhập đầy đủ thông tin");
      return;
    }

    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }

    setIsSubmitting(true);

    const res = await register(username.trim(), password);
    if (res.success) {
      router.push("/");
    } else {
      setError(res.message);
    }
    
    setIsSubmitting(false);
  };

  return (
    <div className={styles.splitContainer}>
      {/* ── Left: Form ── */}
      <div className={styles.formPanel}>
        <div className={styles.formInner}>
          {/* Brand */}
          <div className={styles.brand}>
            <div className={styles.brandIcon}>🌿</div>
            <span className={styles.brandName}>EnvChat</span>
          </div>

          {/* Heading */}
          <h1 className={styles.heading}>Tạo tài khoản mới</h1>
          <p className={styles.subheading}>
            Bắt đầu hành trình cùng hệ thống quan trắc môi trường thông minh
          </p>

          {/* Form */}
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="reg-username">
                Tên đăng nhập
              </label>
              <div className={styles.inputWrapper}>
                <input
                  id="reg-username"
                  className={styles.input}
                  type="text"
                  placeholder="Chọn tên đăng nhập"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                />
                <span className={styles.inputIcon}>👤</span>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="reg-password">
                Mật khẩu
              </label>
              <div className={styles.inputWrapper}>
                <input
                  id="reg-password"
                  className={styles.input}
                  type="password"
                  placeholder="Ít nhất 6 ký tự"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <span className={styles.inputIcon}>🔒</span>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="reg-confirm">
                Xác nhận mật khẩu
              </label>
              <div className={styles.inputWrapper}>
                <input
                  id="reg-confirm"
                  className={styles.input}
                  type="password"
                  placeholder="Nhập lại mật khẩu"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <span className={styles.inputIcon}>🔑</span>
              </div>
            </div>

            {error && <div className={styles.error}>{error}</div>}

            <button
              className={styles.submitBtn}
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Đang xử lý..." : "Tạo tài khoản"}
            </button>
          </form>

          {/* Hint */}
          <div className={styles.hint}>
            Đã có tài khoản?
            <Link href="/login" className={styles.hintLink}>
              Đăng nhập ngay
            </Link>
          </div>
        </div>
      </div>

      {/* ── Right: Image ── */}
      <div className={styles.imagePanel}>
        <img
          src="/bg_forest.png"
          alt="Tán rừng xanh mướt"
          className={styles.bgImage}
        />
        <div className={styles.imageOverlay} />
        <div className={styles.imageContent}>
          <p className={styles.imageQuote}>
            &ldquo;Mỗi hành động nhỏ hôm nay, tạo nên thay đổi lớn cho ngày mai.&rdquo;
          </p>
          <span className={styles.imageCaption}>EnvChat — Quan trắc môi trường thông minh</span>
        </div>
      </div>
    </div>
  );
}
