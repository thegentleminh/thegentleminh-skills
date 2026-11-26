# Example prompts (copy, paste, change the topic)

## One-line starter
> Làm cho mình một video Short "Ở thế giới này, nước lã quý hơn sữa".

What you get: the connection check, the setup questions (first run only), 3-4 premise and title options to pick from, then a full script for your approval.

## Detailed brief
> Làm một Short 2 phút: "Ở thị trấn này, ai càng ngủ nhiều càng giàu". Người kể là một bé trai 9 tuổi, gia đình nghèo vì ba bị mất ngủ. Có một nhà hàng xóm ngủ suốt ngày nên giàu nhất phố. Kết thúc có twist, gọi lại câu ba hay nói ở đầu video. Nhìn kiểu trưa nắng, giọng miền Nam. Mình sẽ tự thu giọng.

What you get: a script in story shape A with a family motto and a callback, written for a Southern voice, plus the list of lines that might sound stiff.

## Per step
- **Script only:** "Chỉ viết kịch bản và 4 tiêu đề, chưa dựng gì trong Studio." -> script.md + titles.
- **Narration sheet:** "Làm bảng thu giọng cho kịch bản đã duyệt, mình dùng TTSMaker." -> narration/sheet.md with one numbered line per file, plus warnings (years, digits, long lines, weekly characters).
- **Check the lines:** "Mình bỏ file giọng vào narration/in rồi, kiểm tra giúp." -> each flagged line in plain words; then the cleaned, joined narration.wav with its length.
- **Shot plan:** "Lên shot plan cho kịch bản đã duyệt." -> shotplan.json + a table you can read (shot, size, move, angle, what's in it).
- **Build one place:** "Dựng cảnh căn nhà của gia đình nhân vật chính, rồi chụp 3 góc máy cho mình xem." -> the set in your place + 3 stills.
- **Cast:** "Tạo nhân vật: bé trai kể chuyện, ba, hàng xóm giàu. Cho mình xem ảnh cả ba đứng cạnh nhau." -> rigs + a lineup still.
- **Test one take:** "Quay thử take A (shot 1-12) và ghép lại cho mình xem." -> raw/takeA.mp4 + work/render_silent.mp4 for those shots.
- **Edit:** "Ghép phụ đề, nhạc và hiệu ứng âm thanh, xuất bản cuối." -> out/final.mp4 + the check report.
- **Connection:** "kiểm tra kết nối" -> one line for Roblox Studio, one for StoryKit Pass.

## Revision notes (say what's wrong, the skill fixes only that)
- "Shot 7 cái bồn cầu quay ngược rồi." -> turns the prop, re-records only that take.
- "Thằng bé đi nhanh hơn nữa, như đang vội." -> faster walk matched to the step rate, longer path, same take only.
- "Ông ba phải to hơn thằng con." -> rescales the father, re-plants his feet, re-records his shots.
- "Phụ đề chữ 'bồn cầu' bị tách hai dòng." -> keeps that pair together, re-runs only the edit.
- "Câu 12 đọc sai chữ 'quý', mình thu lại rồi." -> checks the new take, re-joins the narration, re-times the shots.
- "Nhạc to quá đoạn giữa." -> lowers the bed there, re-runs the edit and the voice-gap check.
