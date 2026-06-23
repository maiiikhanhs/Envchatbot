# EnvChat Backend

Backend là lớp API và xử lý nghiệp vụ của hệ thống EnvChat. Thành phần này nhận request từ frontend, xử lý câu hỏi hoặc file đính kèm, lưu dữ liệu vào MongoDB/ChromaDB và gọi ComfyUI để lấy câu trả lời cuối.

## Công nghệ sử dụng

- FastAPI và Uvicorn cho HTTP API.
- MongoDB và PyMongo để lưu người dùng, hội thoại, tin nhắn, tài liệu và phản hồi.
- ChromaDB client để lưu và truy vấn vector/chunk tài liệu.
- `pypdf` và `python-docx` để đọc file `.pdf` và `.docx`.
- ComfyUI để chạy workflow LLM cục bộ.
- pytest cho kiểm thử tự động.

## Cách hoạt động

- `text_only`: nhận câu hỏi, chuẩn hóa ngữ cảnh hội thoại, gọi workflow ComfyUI và trả về câu trả lời.
- `text_with_file`: nhận câu hỏi kèm file, trích xuất nội dung, chia chunk, tìm ngữ cảnh liên quan, refine context rồi gọi workflow ComfyUI.
- Backend lưu hội thoại, tin nhắn, tài liệu, chunk và báo cáo phản hồi để frontend có thể hiển thị lại lịch sử.
- Với ComfyUI, backend inject `question` và `context` vào workflow, poll history và đọc các node output như router/final answer.

## API chính

- `GET /api/health`: kiểm tra backend còn hoạt động.
- `POST /api/register`, `POST /api/login`: đăng ký và đăng nhập.
- `POST /api/chat`: gửi câu hỏi, có thể kèm file `.pdf` hoặc `.docx`.
- `GET /api/conversations`: lấy danh sách hội thoại.
- `GET /api/conversations/{conversation_id}/messages`: lấy tin nhắn của một hội thoại.
- `DELETE /api/conversations/{conversation_id}`: xóa hội thoại.
- `POST /api/reports`: gửi báo cáo lỗi, góp ý hoặc đề xuất chức năng.

## Cấu hình quan trọng

- `MONGODB_URI`: mặc định `mongodb://localhost:27019`.
- `CHROMA_HOST`: mặc định `localhost`.
- `CHROMA_PORT`: mặc định `8000`.
- `COMFYUI_BASE_URL`: mặc định `http://127.0.0.1:8188`.
- `COMFYUI_LLM_API_KEY`: API key được inject vào workflow ComfyUI lúc chạy.
- `COMFYUI_WORKFLOW_PATH`: mặc định trỏ tới `workflows/comfyui/EnvironmentChatbot.json` trong thư mục backend.
- `COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH`: mặc định trỏ tới `workflows/comfyui/Environment(1)Chatbot.json` trong thư mục backend.
- `NEXT_PUBLIC_API_URL`: cấu hình ở frontend để trỏ về backend, mặc định `http://localhost:8080`.

## Chạy backend

Cài thư viện:

```powershell
pip install -r requirements.txt
```

Chạy server:

```powershell
python -m uvicorn app.api:app --reload --host 0.0.0.0 --port 8080
```

Health check:

```text
http://localhost:8080/api/health
```

## Kiểm thử

```powershell
python -m pytest
```

Kết quả kiểm thử gần nhất: `116 passed, 1 skipped`.
