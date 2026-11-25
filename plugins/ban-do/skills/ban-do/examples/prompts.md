# Prompt mẫu (example prompts)

Copy one into Claude Code after installing the skill. The first time, Claude checks what is installed and asks before
downloading the map data (about 18 MB, once). Results go to `ban-do/`; nothing you already have is overwritten.

## 1. Bắt đầu nhanh (one line)

> Làm clip bản đồ dọc: zoom từ châu Á vào Việt Nam, tô màu Việt Nam, ghim Hà Nội.

You get: `ban-do/viet-nam.mp4` (9:16, about 8 s, no sound) and `ban-do/viet-nam-khung.jpg` (six key frames to check).
Hoàng Sa, Trường Sa and Biển Đông are on the map by themselves.

## 2. Đề bài chi tiết (detailed brief)

> Làm clip bản đồ ngang 16:9, nền sáng, 7 giây. Mở đầu thấy cả Đông Á, rồi zoom vào Nhật Bản, làm tối các nước
> khác. Ghim Tokyo. Hiện số 14.125 đếm lên, dòng nhỏ bên dưới "hòn đảo (đếm lại năm 2023)", đặt bên trái.
> Tiêu đề trên cùng: "Nhật Bản có bao nhiêu hòn đảo?"

You get: the camera moves from East Asia to Japan, Japan in colour with the rest dimmed (`spotlight`), a pin on
Tokyo, the number counting up on the left, the title at the top.

## 3. Từng tính năng (one feature at a time)

- **Chỉ tô màu một nước:** "Tô đỏ nước Pháp trên bản đồ châu Âu, clip 5 giây."
- **Zoom vào một thành phố:** "Zoom từ Việt Nam vào Đà Nẵng, khung rộng khoảng 300 km, ghim Đà Nẵng."
- **Con số lớn:** "Thêm số 1.650 km ở giữa màn hình, sau giây thứ 3."
- **Đổi màu / nền:** "Làm lại với nền sáng, màu tô xanh dương."
- **Xem trước cho nhanh:** "Cho mình xem trước bản nhỏ rồi mới làm bản đầy đủ."
- **Sửa sau khi xem:** "Zoom chậm hơn một chút, và dời con số lên cao hơn."
