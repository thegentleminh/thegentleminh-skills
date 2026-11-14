# Prompt mẫu (example prompts)

Copy one into Claude Code after installing the skill. The first time, Claude asks the setup questions
(shape, style, camera move, how hard cuts hit, title font, how to fit photos) and remembers your answers.
Your photos and music are never changed; every video is a new file.

## 1. Bắt đầu nhanh (one line)

> Làm video từ ảnh trong thư mục anh/da-lat với bài nhac/vui.mp3.

You get: stills of the first shots, then a 9:16 video where the photos change on the song's beat, with faces kept
in frame and the music levelled for TikTok.

## 2. Đề bài chi tiết (detailed brief)

> Làm video kỷ niệm đám cưới 60 giây từ thư mục anh-cuoi, kiểu album nhẹ nhàng, khung 16:9 cho YouTube,
> nhạc nhac/piano.mp3 từ giây 12, tiêu đề "Lan & Huy · 2026", mỗi ảnh có chú thích theo tên địa điểm.

You get: a gentle album where each photo pushes slowly toward the faces, crossfades land on the music's beats, the
title stays off faces, and each photo has a one-line caption.

## 3. Từng tính năng (one feature at a time)

- **3D chiều sâu:** "Làm 8 ảnh phong cảnh này thành video 3D chiều sâu, dọc cho TikTok." → near things move more than
  far things (slower to render).
- **Kiểu mẫu nhanh:** "Ảnh đổi mỗi nhịp, giật mạnh kiểu glitch." → `beats_per_photo: 1`, hits `manh`.
- **Khung vuông:** "Làm bản vuông 1:1 để đăng Facebook." → same photos, 1:1.
- **Giữ nguyên ảnh:** "Đừng cắt ảnh nào, giữ cả ảnh với nền mờ." → `fit: blur`.
- **So sánh:** "Cho mình xem các kiểu chuyển động để so sánh." → your own photos in every camera move, side by side.
- **Làm lại cài đặt:** "Làm lại phần cài đặt."

## 4. Sửa theo ghi chú (revision notes)

> Đổi ảnh chậm lại (4 nhịp một ảnh), bỏ hiệu ứng rung, tiêu đề màu vàng, bỏ ảnh số 5.

You get: only those changes, new stills to check, then a new render. The previous render is kept.
