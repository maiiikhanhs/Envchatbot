"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import styles from "./page.module.css";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("Vui lòng nhập đầy đủ thông tin");
      return;
    }

    setIsSubmitting(true);

    const res = await login(username.trim(), password);
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
          <h1 className={styles.heading}>Chào mừng trở lại</h1>
          <p className={styles.subheading}>
            Đăng nhập để tiếp tục với hệ thống quan trắc môi trường
          </p>

          {/* Form */}
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="login-username">
                Tên đăng nhập
              </label>
              <div className={styles.inputWrapper}>
                <input
                  id="login-username"
                  className={styles.input}
                  type="text"
                  placeholder="Nhập tên đăng nhập"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                />
                <span className={styles.inputIcon}>👤</span>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="login-password">
                Mật khẩu
              </label>
              <div className={styles.inputWrapper}>
                <input
                  id="login-password"
                  className={styles.input}
                  type="password"
                  placeholder="Nhập mật khẩu"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <span className={styles.inputIcon}>🔒</span>
              </div>
            </div>

            {error && <div className={styles.error}>{error}</div>}

            <button
              className={styles.submitBtn}
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Đang đăng nhập..." : "Đăng nhập"}
            </button>
          </form>

          {/* Hint */}
          <div className={styles.hint}>
            Chưa có tài khoản?
            <Link href="/register" className={styles.hintLink}>
              Tạo tài khoản mới
            </Link>
          </div>
        </div>
      </div>

      {/* ── Right: Image ── */}
      <div className={styles.imagePanel}>
        <img
          src="/bg_login_macro.png"
          alt="Cận cảnh thảm rêu và dương xỉ xanh mướt"
          className={styles.bgImage}
        />
        <div className={styles.imageOverlay} />
        <div className={styles.imageContent}>
          <p className={styles.imageQuote}>
            &ldquo;Bảo vệ môi trường là bảo vệ cuộc sống của chính chúng ta.&rdquo;
          </p>
          <span className={styles.imageCaption}>EnvChat — Quan trắc môi trường thông minh</span>
        </div>
      </div>
    </div>
  );
}
