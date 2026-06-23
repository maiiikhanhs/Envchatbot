# EnvChat - Chatbot quan trắc môi trường

EnvChat là hệ thống chatbot hỗ trợ hỏi đáp và phân tích tài liệu trong lĩnh vực quan trắc môi trường. Hệ thống gồm giao diện web, API xử lý nghiệp vụ, cơ sở dữ liệu lưu hội thoại/tài liệu và workflow ComfyUI/LLM chạy cục bộ.

## Kiến trúc tổng quan

```text
Frontend Next.js
  -> Backend FastAPI
  -> MongoDB + ChromaDB
  -> ComfyUI / LLM workflow
```

- `frontend/`: giao diện chat, đăng nhập, lịch sử hội thoại, upload file và gửi phản hồi.
- `backend/`: API FastAPI, xử lý câu hỏi, đọc file, chunking, retrieval, lưu dữ liệu, gọi ComfyUI và chứa workflow JSON.
- `docker-compose.yml`: khởi động MongoDB và ChromaDB.
- `START_ALL.ps1`: script hỗ trợ chạy nhanh hệ thống trên Windows.

## Công nghệ chính

- Frontend: Next.js 15, React 19, TypeScript, CSS Modules.
- Backend: FastAPI, Uvicorn, PyMongo, ChromaDB client, pypdf, python-docx.
- Database/vector store: MongoDB, ChromaDB.
- LLM workflow: ComfyUI chạy cục bộ.

## Yêu cầu cài đặt

- Python 3.12+
- Node.js và npm
- Docker Desktop
- ComfyUI chạy tại `http://127.0.0.1:8188` nếu sử dụng luồng trả lời bằng LLM workflow
- API key LLM đặt qua biến môi trường `COMFYUI_LLM_API_KEY` khi chạy ComfyUI workflow

## Cài đặt và vận hành

Khởi động MongoDB và ChromaDB:

```powershell
docker compose up -d
```

Cài và chạy backend:

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.api:app --reload --host 0.0.0.0 --port 8080
```

Cài và chạy frontend:

```powershell
cd frontend
npm install
npm run dev
```

Truy cập ứng dụng:

```text
Frontend: http://localhost:3000
Backend health check: http://localhost:8080/api/health
```

## Kiểm thử

Backend:

```powershell
cd backend
python -m pytest
```

Frontend:

```powershell
cd frontend
npm run build
```

## Ghi chú khi nộp Git

Các thư mục/file runtime hoặc dữ liệu sinh ra không được đưa lên Git: `ComfyUI_windows_portable/`, `node_modules/`, `.next/`, `.env.local`, `backend/chroma_data/`, `backend/uploads/`, log và cache build. Chỉ commit workflow JSON đã làm sạch trong `backend/workflows/comfyui/`; không commit API key thật.
