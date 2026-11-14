# Prompt mẫu (example prompts)

Copy one into Claude Code after installing the skill. The first time, Claude asks the setup questions
(platform, font, colour, how much you may cover the text, how text comes in, outline, accent, sounds)
and remembers your answers. Every effect works on your own clip; your original file is never changed.

## 1. Bắt đầu nhanh (one line)

> Làm chữ "THÀNH CÔNG" sau lưng mình trong clip raw/clip.mp4.

You get: 4 stills with a readability check ("first and last letters of every word visible"), then the
full clip with the big text behind your head, inside TikTok's safe area.

## 2. Đề bài chi tiết (detailed brief)

> Clip raw/phong-van.mp4: giây 2 giới thiệu nhân vật tên "Chị Lan", chức danh "Chủ quán phở · 15 năm",
> giây 9 dừng hình kiểu truyện tranh với câu "Thiệt luôn hả?!", giây 14 chụp ảnh dừng hình. Có tiếng động.

You get: one render with a character intro (background goes dark, you pop forward with an outline, a name
card slides in), a comic freeze with a speech box and a photo snap, each pausing the video with its own
generated sound.

## 3. Từng tính năng (one feature at a time)

- **Chữ sau lưng, kiểu trend:** "Chữ 'ĐÀ LẠT' sau lưng mình, cho đầu che nhiều như trend, chữ vàng, hiện từng
  chữ cái." → `cover: bold`, yellow, letter-by-letter.
- **Giới thiệu nhân vật:** "Giây 3 giới thiệu mình: tên 'Minh', dòng dưới 'Thợ chụp ảnh cưới'."
- **Dừng hình chụp ảnh:** "Lúc mình nhảy lên ở giây 6, dừng hình kiểu chụp ảnh." → the sharpest frame near 6 s.
- **Phân thân (một lần quay):** "Clip raw/di-bo.mp4 mình đi ngang qua: để lại bóng mình mỗi 0,8 giây rồi mờ dần."
- **Hai vai (hai lần quay):** "Mình quay 2 lần cùng chỗ (raw/vai-a.mp4, raw/vai-b.mp4), ghép thành 2 người nói
  chuyện với nhau." → overlay or split; a tripod is needed.
- **So sánh:** "Cho mình xem các kiểu chữ để so sánh." → a labelled side-by-side on your own clip.
- **Làm lại cài đặt:** "Làm lại phần cài đặt."

## 4. Sửa theo ghi chú (revision notes)

> Chữ to hơn chút, dời lên trên, dừng hình lâu hơn 1 giây, bỏ tiếng chụp ảnh.

You get: only those changes, new stills to check, then a new render. The previous render is kept.
