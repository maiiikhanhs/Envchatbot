"use client";

import type { ChatMessage, RouterLabel } from "@/types";
import RouterBadge from "./RouterBadge";
import styles from "./MessageBubble.module.css";

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`${styles.message} ${isUser ? styles.user : styles.assistant}`}
    >
      {!isUser && message.routerLabel && (
        <RouterBadge label={message.routerLabel as RouterLabel} variant="glow" />
      )}
      <div className={styles.bubble}>
        {isUser ? (
          <>
            <span>{message.content}</span>
            {message.fileName && (
              <div className={styles.fileChip}>📎 {message.fileName}</div>
            )}
          </>
        ) : (
          <>
            <div
              className={styles.markdownContent}
              dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
            />
            {message.sources && message.sources.length > 0 && (
              <div className={styles.sourcesContainer}>
                <div className={styles.sourcesTitle}>Nguồn tham khảo:</div>
                <div className={styles.sourceList}>
                  {message.sources
                    .filter((src, idx, arr) =>
                      arr.findIndex(s => s.source_file_name === src.source_file_name) === idx
                    )
                    .map((src, idx) => (
                      <div className={styles.sourceItem} key={src.chunk_id || idx} title={src.content}>
                        <span className={styles.sourceIndex}>[{idx + 1}]</span>
                        <span className={styles.sourceFile}>{src.source_file_name || "Tài liệu upload"}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────
 *  formatMarkdown – Simple & reliable
 *
 *  Logic: Split LLM text by "\n". Each line is checked:
 *    - "# "  → <h1>
 *    - "## " → <h2>
 *    - "### "→ <h3>
 *    - "1. " → <ol><li>
 *    - "- "  → <ul><li>
 *    - else  → <p>
 *  Bold (**text**) is handled inline.
 *  LLM's own newlines are the ONLY source of line breaks.
 * ──────────────────────────────────────────────────────────────── */
function fixLlmFormatting(text: string): string {
  let s = text || "";
  
  // 1. Missing space/newline for main uppercase headers: "định.4.TỔ CHỨC" -> "định.\n4. TỔ CHỨC"
  s = s.replace(/([.!?\s]|^)(\d+)\.([A-ZÀ-Ỹ]{2,})/g, "$1\n$2. $3");
  
  // 2. Mashed sub-bullets with dashes: "dựng.-1.2.Đối tượng" -> "dựng.\n- 1.2. Đối tượng"
  s = s.replace(/([.!?\s]|^)-(\d+(?:\.\d+)*)\.\s*([A-ZÀ-Ỹa-zà-ỹ])/g, "$1\n- $2. $3");
  
  // 3. Mashed sub-bullets preceded by words: "CHUNG -1.1. Phạm vi" -> "CHUNG\n- 1.1. Phạm vi"
  s = s.replace(/([A-ZÀ-Ỹa-zà-ỹ])\s+-(\d+(?:\.\d+)*)\.\s*/g, "$1\n- $2. ");
  
  // 4. Sentence end followed by dash: "câu. - Mục mới" -> "câu.\n- Mục mới"
  s = s.replace(/([.!?])\s*-\s+/g, "$1\n- ");
  
  // 5. Sentence end followed by bold: "câu.**Đậm**" -> "câu.\n**Đậm**"
  s = s.replace(/([.!?])\s*\*\*/g, "$1\n**");
  
  // 6. Sentence end followed by number: "câu. 1. Mục" -> "câu.\n1. Mục"
  s = s.replace(/([.!?])\s+(\d+\.\s+)/g, "$1\n$2");
  
  // 7. Sentence end followed by sub-number: "câu. 1.1. Mục" -> "câu.\n1.1. Mục"
  s = s.replace(/([.!?])\s+(\d+(?:\.\d+)+)\.\s*/g, "$1\n$2. ");

  // 8. LLMs often insert blank lines between markdown table rows, which breaks table parsing.
  s = s.replace(/(\|[^\n]*\|)\n\s*\n(?=\|)/g, "$1\n");

  return s;
}

function formatMarkdown(text: string): string {
  const preProcessed = fixLlmFormatting(text);
  const cleaned = sanitizeDisplayText(preProcessed)
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");

  const lines = cleaned.split("\n");
  const out: string[] = [];

  let inOl = false;
  let inUl = false;

  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const inlineFmt = (s: string) => {
    let h = esc(s);
    h = h.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    return h;
  };

  const closeOl = () => { if (inOl) { out.push("</ol>"); inOl = false; } };
  const closeUl = () => { if (inUl) { out.push("</ul>"); inUl = false; } };
  const closeLists = () => { closeUl(); closeOl(); };

  const isTableRow = (line: string) => {
    const trimmed = line.trim();
    return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.split("|").length >= 4;
  };
  const isSeparatorRow = (line: string) =>
    /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
  const tableCells = (line: string) => {
    const cells = line.trim().split("|");
    if (cells[0] === "") cells.shift();
    if (cells[cells.length - 1] === "") cells.pop();
    return cells.map(cell => cell.trim());
  };
  const nextNonEmptyIndex = (start: number) => {
    let index = start;
    while (index < lines.length && !lines[index].trim()) index += 1;
    return index;
  };
  const renderTable = (start: number) => {
    const separatorIndex = nextNonEmptyIndex(start + 1);
    if (!isTableRow(lines[start]) || separatorIndex >= lines.length || !isSeparatorRow(lines[separatorIndex])) {
      return null;
    }

    const header = tableCells(lines[start]);
    const rows: string[][] = [];
    let index = separatorIndex + 1;
    while (index < lines.length) {
      const trimmed = lines[index].trim();
      if (!trimmed) {
        const lookahead = nextNonEmptyIndex(index + 1);
        if (lookahead < lines.length && isTableRow(lines[lookahead])) {
          index = lookahead;
          continue;
        }
        break;
      }
      if (!isTableRow(trimmed) || isSeparatorRow(trimmed)) break;
      rows.push(tableCells(trimmed));
      index += 1;
    }

    if (!header.length || !rows.length) return null;

    const colCount = Math.max(header.length, ...rows.map(row => row.length));
    const normalize = (cells: string[]) =>
      Array.from({ length: colCount }, (_, cellIndex) => inlineFmt(cells[cellIndex] || ""));
    const thead = `<thead><tr>${normalize(header).map(cell => `<th>${cell}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${rows
      .map(row => `<tr>${normalize(row).map(cell => `<td>${cell}</td>`).join("")}</tr>`)
      .join("")}</tbody>`;
    return {
      html: `<div class="tableScroll"><table class="dataTable">${thead}${tbody}</table></div>`,
      nextIndex: index,
    };
  };

  for (let lineIndex = 0; lineIndex < lines.length;) {
    const raw = lines[lineIndex];
    const trimmed = raw.trim();

    // Empty line → close lists, skip (no extra spacing)
    if (!trimmed) {
      closeLists();
      lineIndex += 1;
      continue;
    }

    const table = renderTable(lineIndex);
    if (table) {
      closeLists();
      out.push(table.html);
      lineIndex = table.nextIndex;
      continue;
    }

    // Headings
    const h3 = trimmed.match(/^###\s+(.*)$/);
    if (h3) { closeLists(); out.push(`<h3>${inlineFmt(h3[1])}</h3>`); lineIndex += 1; continue; }

    const h2 = trimmed.match(/^##\s+(.*)$/);
    if (h2) { closeLists(); out.push(`<h2>${inlineFmt(h2[1])}</h2>`); lineIndex += 1; continue; }

    const h1 = trimmed.match(/^#\s+(.*)$/);
    if (h1) { closeLists(); out.push(`<h1>${inlineFmt(h1[1])}</h1>`); lineIndex += 1; continue; }

    // Ordered list: "1. text", "2. text"
    const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (olMatch) {
      closeUl();
      if (!inOl) { out.push("<ol>"); inOl = true; }
      out.push(`<li>${inlineFmt(olMatch[2])}</li>`);
      lineIndex += 1;
      continue;
    }

    // Bullet list: "- text", "• text", "* text"
    const ulMatch = trimmed.match(/^[-•*]\s+(.*)$/);
    if (ulMatch) {
      closeOl();
      if (!inUl) { out.push("<ul>"); inUl = true; }
      out.push(`<li>${inlineFmt(ulMatch[1])}</li>`);
      lineIndex += 1;
      continue;
    }

    // Plain text
    closeLists();
    out.push(`<p>${inlineFmt(trimmed)}</p>`);
    lineIndex += 1;
  }

  closeLists();
  return out.join("");
}

function normalizePlainDisplaySymbols(text: string): string {
  const normalizeSourceMarkers = (value: string) =>
    value
      .replace(/\[\s*FILE\s*_?\s*SOURCE\s*_?\s*(\d+)\s*\]/gi, (_match, index) => `[FILE_SOURCE_${index}]`)
      .replace(/\[\s*SOURCE\s*_?\s*(\d+)\s*\]/gi, (_match, index) => `[SOURCE_${index}]`);
  const joinPlainSubscript = (match: string, prefix: string, suffix: string) =>
    prefix.toUpperCase() === "SOURCE" ? match : `${prefix}${suffix}`;

  let s = String(text || "")
    .replace(/&micro;/gi, "µ")
    .replace(/&mu;/gi, "µ")
    .replace(/\\[()[\]]/g, "")
    .replace(/\$/g, "");

  s = normalizeSourceMarkers(s);

  let previous = "";
  while (previous !== s) {
    previous = s;
    s = s.replace(/\\(?:text|mathrm)\{([^{}]*)\}/g, "$1");
  }

  s = s
    .replace(/\\mu/g, "µ")
    .replace(/µ\s+g/g, "µg")
    .replace(/\b([A-Za-zÀ-Ỹà-ỹµ]+)_\{([^{}]+)\}/g, joinPlainSubscript)
    .replace(/\b([A-Za-zÀ-Ỹà-ỹµ]+)_([0-9]+(?:,[0-9]+)?)\b/g, joinPlainSubscript)
    .replace(/\bNm\^\{?3\}?/g, "Nm3")
    .replace(/\b([mc]?g\/Nm)\^\{?3\}?/g, (_match, unit) => `${unit}3`)
    .replace(/\{([^{}\n]+)\}/g, "$1")
    .replace(/\\(?=[A-Za-zÀ-Ỹà-ỹµ])/g, "")
    .replace(/\\+/g, "")
    .replace(/\s*\/\s*/g, "/")
    .replace(/\s+([,.;:!?])/g, "$1");

  return normalizeSourceMarkers(s);
}

/* Strip router labels and source tags from raw LLM output */
function sanitizeDisplayText(text: string): string {
  return normalizePlainDisplaySymbols(text)
    .replace(
      /^(?:\[\s*)?(PHAP_LY|PHAP_L|THONG_SO|THONG_S|QUY_TRINH|QUY_TRIN|HO_SO|HO_S|VAN_HANH|VAN_HAN|XA_GIAO|KHONG_LIEN_QUAN)(?:\s*\])?\s*/i,
      "",
    )
    .replace(
      /\n(?:\[\s*)?(PHAP_LY|PHAP_L|THONG_SO|THONG_S|QUY_TRINH|QUY_TRIN|HO_SO|HO_S|VAN_HANH|VAN_HAN|XA_GIAO|KHONG_LIEN_QUAN)(?:\s*\])?\s*/gi,
      "\n",
    )
    .replace(/\[(?:FILE_SOURCE|SOURCE)_\d+\]/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
