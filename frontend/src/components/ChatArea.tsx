"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/types";
import MessageBubble from "./MessageBubble";
import LoadingDots from "./LoadingDots";
import WelcomeScreen from "./WelcomeScreen";
import WeatherWidget from "./WeatherWidget";
import styles from "./ChatArea.module.css";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  onSuggestionClick: (text: string) => void;
  userName?: string;
}

export default function ChatArea({
  messages,
  isLoading,
  onSuggestionClick,
  userName,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className={styles.chatArea}>
      <WeatherWidget />

      {/* Floating decorative blobs */}
      <div className={styles.bgDecorations}>
        <div className={`${styles.bgDeco} ${styles.bgDeco1}`} />
        <div className={`${styles.bgDeco} ${styles.bgDeco2}`} />
        <div className={`${styles.bgDeco} ${styles.bgDeco3}`} />
        <div className={`${styles.bgDeco} ${styles.bgDeco4}`} />
        <div className={`${styles.bgDeco} ${styles.bgDeco5}`} />
      </div>

      {/* Watermark — visible when chatting */}
      {messages.length > 0 && (
        <div className={styles.watermark}>
          <div className={styles.watermarkIcon}>🌿</div>
          <div className={styles.watermarkText}>EnvChat</div>
        </div>
      )}

      <div className={styles.container}>
        {messages.length === 0 && !isLoading ? (
          <WelcomeScreen userName={userName} onSuggestionClick={onSuggestionClick} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div className={styles.loadingWrapper}>
                <LoadingDots />
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
