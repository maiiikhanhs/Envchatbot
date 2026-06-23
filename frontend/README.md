# EnvChat Frontend

Frontend là giao diện web của hệ thống EnvChat, được xây dựng để người dùng đăng nhập, đặt câu hỏi, gửi file tài liệu, xem lịch sử hội thoại và gửi phản hồi cho hệ thống.

## Công nghệ sử dụng

- Next.js 15 với App Router.
- React 19.
- TypeScript.
- CSS Modules cho styling theo từng component.
- Fetch API để giao tiếp với backend FastAPI.

## Chức năng chính

- Đăng ký và đăng nhập người dùng.
- Gửi câu hỏi dạng text-only.
- Gửi câu hỏi kèm file `.pdf` hoặc `.docx`.
- Hiển thị câu trả lời, trạng thái xử lý và nhãn router.
- Quản lý lịch sử hội thoại theo người dùng.
- Gửi báo cáo lỗi, góp ý hoặc đề xuất chức năng.

## Kết nối backend

Frontend gọi backend qua biến môi trường:

```text
NEXT_PUBLIC_API_URL=http://localhost:8080
```

Nếu không khai báo biến này, ứng dụng mặc định gọi backend tại `http://localhost:8080`.

## Chạy frontend

Cài thư viện:

```powershell
npm install
```

Chạy môi trường phát triển:

```powershell
npm run dev
```

Mở ứng dụng tại:

```text
http://localhost:3000
```

Build kiểm tra production:

```powershell
npm run build
```

## Ghi chú khi đưa lên Git

Không commit các file/thư mục sinh ra trong quá trình chạy hoặc build như `node_modules/`, `.next/`, `.env.local`, log và cache. Các nội dung này đã được loại trừ bằng `.gitignore` ở thư mục gốc.
