Design a complete responsive web application named **FootballPulse**, an automated football news intelligence platform.

All visible interface text must be written in **Vietnamese**.

The design must be:

* Simple and easy to understand.
* Clean and easy to scan.
* Modern but not overly decorative.
* Suitable for a real football news website.
* Focused on news reading, search, entities, editorial review, and source transparency.
* Responsive for desktop and mobile.
* Built with reusable Figma components, Auto Layout, design tokens, and consistent spacing.

Do not design FootballPulse as:

* A betting website.
* A live-score application.
* A fantasy football application.
* A complex analytics dashboard.
* A social network.
* A website filled with too many colors, badges, charts, or navigation items.

The public website should feel like a modern online football newspaper. The intelligence features should appear subtly through source count, related entities, story timeline, and source references.

# 1. Core product concept

FootballPulse automatically collects football news from multiple sources, identifies related players, coaches, and clubs, groups articles about the same event, generates a summarized article, and allows an editor to review and publish it.

The public user does not need to understand technical concepts such as Kafka, AI workers, source articles, or story clustering.

The public user should simply see:

* Clear football news.
* Related players, coaches, and clubs.
* The number of sources used.
* A timeline for developing stories.
* Original source references.

# 2. Main public navigation

The desktop header must contain exactly these primary navigation items:

```text
FootballPulse | Tin mới | Cầu thủ | CLB | HLV | Search
```

Do not add “Chuyển nhượng” to the primary navigation.

Do not add live scores, fixtures, standings, videos, betting, shop, or community.

Header structure:

* FootballPulse logo on the left.
* Navigation links in the center.
* Large and clearly visible search field on the right.
* Search placeholder:

```text
Tìm tin, cầu thủ, CLB hoặc HLV...
```

The search function is important because only famous players, coaches, and clubs are displayed in featured lists. Less popular entities are mainly discovered through search.

The header should remain simple and use only one row.

Mobile header:

* Menu icon.
* FootballPulse logo.
* Search icon.

Mobile drawer:

* Tin mới.
* Cầu thủ.
* CLB.
* HLV.

# 3. Visual style

Use a minimal editorial visual style.

Recommended palette:

```text
Page background: #F7F8FA
Card background: #FFFFFF
Primary text: #111827
Secondary text: #6B7280
Border: #E5E7EB
Header background: #FFFFFF
Primary accent: #78A83D
Dark accent: #1E293B
Success or official status: #2E7D32
Warning or reported status: #B7791F
```

Use the green accent sparingly for:

* Logo mark.
* Active navigation item.
* Primary buttons.
* Links.
* Small section markers.
* Selected filters.

Do not fill large areas with green.

Avoid strong gradients.

Avoid neon colors.

Avoid glassmorphism.

Avoid excessive shadows.

Cards should primarily use:

* White background.
* Thin gray border.
* Small or no shadow.
* Border radius around 8–12 pixels.

Typography:

* Use Inter or another clean sans-serif.
* Large headlines must be bold and readable.
* Body text must have comfortable line height.
* Avoid compressed typography.
* Desktop article body width should remain readable, around 680–760 pixels.

Recommended sizes:

```text
Hero headline: 36–44px
Page title: 30–36px
Section heading: 22–26px
Card headline: 17–21px
Body: 16–18px
Metadata: 13–14px
```

Use an 8-pixel spacing system.

Use a maximum desktop content width around 1200–1280 pixels.

# 4. Reusable components

Create reusable Figma components for:

## Header

Variants:

* Desktop.
* Mobile.
* Search active.
* Logged-in admin.

## News cards

Create three sizes.

### Large news card

Contains:

* Large 16:9 image.
* Headline.
* Short summary.
* Publication time.
* Source count.
* Up to three related entity chips.

### Medium news card

Contains:

* 16:9 thumbnail.
* Headline limited to three lines.
* Time and source count.
* Up to two entity chips.

### Compact news row

Contains:

* Small thumbnail.
* Headline.
* Time.
* Optional source count.

## Entity chip

An entity chip represents a related player, club, or coach.

Examples:

```text
Arsenal
Bukayo Saka
Mikel Arteta
```

Entity chip contents:

* Small avatar or club crest.
* Entity name.
* Same base style for players, clubs, and coaches.

Do not use a different strong color for each entity type.

A news card should display a maximum of three entity chips.

When more entities exist, display:

```text
+2
```

## Entity card

Variants:

* Player.
* Club.
* Coach.

Contains:

* Avatar or simple crest.
* Name.
* Entity type.
* Current club when relevant.
* Number of recent articles.

## Metadata row

Example:

```text
20 phút trước · Tổng hợp từ 4 nguồn
```

Keep metadata concise.

## Status badge

Use status badges only when useful:

* Tin được đưa bởi nhiều nguồn.
* Chính thức.
* Đang cập nhật.

Avoid exposing technical enum names such as `MULTI_SOURCE` or `OFFICIAL`.

Use Vietnamese text:

```text
Nhiều nguồn xác nhận
Chính thức
Đang cập nhật
```

## Buttons

Variants:

* Primary.
* Secondary.
* Text.
* Destructive.
* Disabled.
* Loading.

## Search result item

Variants:

* News.
* Player.
* Club.
* Coach.

## Timeline item

Contains:

* Time.
* Short event description.
* Source count or source name.
* Current step indicator.

## Source reference item

Contains:

* Source name.
* Original article title.
* Publication time.
* External-link icon.

# 5. Mock content

Use realistic Vietnamese football news mock data.

The content does not need to represent current real-world facts. It is interface demonstration data.

Featured clubs:

* Arsenal.
* Manchester United.
* Liverpool.
* Manchester City.
* Real Madrid.
* Barcelona.
* Bayern Munich.
* Paris Saint-Germain.

Featured players:

* Kylian Mbappé.
* Erling Haaland.
* Jude Bellingham.
* Bukayo Saka.
* Vinícius Júnior.
* Lamine Yamal.

Featured coaches:

* Pep Guardiola.
* Mikel Arteta.
* Arne Slot.
* Hansi Flick.
* Luis Enrique.
* Xabi Alonso.

Use generic editorial football photos and editable placeholder club crests. Do not depend on exact copyrighted logos.

Example primary story:

```text
Arsenal tăng tốc đàm phán trong thương vụ chiêu mộ tiền đạo trẻ
```

Summary:

```text
Nhiều nguồn cho biết Arsenal đã đạt tiến triển trong đàm phán với cầu thủ, nhưng hai câu lạc bộ vẫn chưa thống nhất mức phí chuyển nhượng.
```

Related entities:

* Arsenal.
* Cầu thủ mục tiêu.
* Mikel Arteta.
* Câu lạc bộ hiện tại của cầu thủ.

Metadata:

```text
20 phút trước · Tổng hợp từ 4 nguồn
```

Other mock headlines:

* Manchester United cập nhật tình trạng chấn thương của tiền vệ trụ cột.
* Real Madrid xác nhận gia hạn hợp đồng với một cầu thủ trẻ.
* Pep Guardiola lên tiếng về kế hoạch nhân sự mùa giải mới.
* Liverpool chuẩn bị thay đổi hệ thống thi đấu trong trận sắp tới.
* Barcelona công bố danh sách cầu thủ tham dự chuyến du đấu.
* Bayern Munich theo dõi một hậu vệ tại Premier League.
* Kylian Mbappé chia sẻ về mục tiêu trong mùa giải mới.
* HLV Mikel Arteta đánh giá màn trình diễn của các cầu thủ trẻ.

# 6. Required public screens

Create all of the following screens.

Organize them inside a Figma page named:

```text
01 — Public Website
```

## Screen P01 — Homepage desktop

Frame size around 1440px wide.

Structure:

### Header

* FootballPulse logo.
* Tin mới.
* Cầu thủ.
* CLB.
* HLV.
* Search field.

### Hero news area

Use a simple two-column layout.

Left side:

* One large featured article.
* Large image.
* Large headline.
* Two-line summary.
* Time and source count.
* Three related entity chips.

Right side:

* Three compact secondary articles.
* Thumbnail, headline, and metadata.
* Avoid too many details.

### Latest news section

Heading:

```text
Tin mới nhất
```

Display six to eight news rows.

Each row contains:

* Thumbnail.
* Headline.
* Short summary.
* Time and source count.
* Up to three related entity chips.

Use a simple main-column layout.

A small right sidebar may contain:

```text
Đang được quan tâm
```

Display a mixed list of famous players, clubs, and coaches.

Do not create separate homepage sections for players, clubs, and coaches.

### Load more

Use a clear button:

```text
Xem thêm tin
```

### Footer

Keep footer minimal:

* FootballPulse.
* Giới thiệu.
* Nguồn tin.
* Điều khoản.
* Liên hệ.
* Copyright placeholder.

## Screen P02 — Homepage mobile

Frame size around 390px wide.

Mobile order:

1. Mobile header.
2. Search button or expandable search field.
3. One featured article.
4. Secondary articles as compact rows.
5. Tin mới nhất.
6. Đang được quan tâm as horizontal scroll.
7. Xem thêm tin.
8. Footer.

Do not retain a desktop sidebar on mobile.

## Screen P03 — Latest news page

Page title:

```text
Tin mới
```

Include:

* Page description of one sentence.
* Search or filter bar.
* Filters:

```text
Tất cả
Mới nhất
Nhiều nguồn
Chính thức
```

Display a clean paginated list of news.

Desktop may use a main column and a small “Đang được quan tâm” sidebar.

Include pagination or a load-more button.

## Screen P04 — Players listing page

Page title:

```text
Cầu thủ
```

Include:

* Search field with placeholder:

```text
Tìm cầu thủ...
```

* Section:

```text
Cầu thủ nổi bật
```

Display six featured player cards.

* Section:

```text
Có tin gần đây
```

Display a simple grid or list of players with recent article count.

* Pagination.

Do not display hundreds of players at once.

## Screen P05 — Clubs listing page

Page title:

```text
Câu lạc bộ
```

Include:

* Search field:

```text
Tìm câu lạc bộ...
```

* Section:

```text
CLB nổi bật
```

Display eight featured club cards.

* Section:

```text
CLB có tin mới
```

Display a clean list or grid.

Club card:

* Simple crest.
* Club name.
* League or country.
* Number of recent articles.

## Screen P06 — Coaches listing page

Page title:

```text
Huấn luyện viên
```

Include:

* Search field:

```text
Tìm huấn luyện viên...
```

* Section:

```text
HLV nổi bật
```

* Section:

```text
Có tin gần đây
```

Use the same visual system as player cards.

## Screen P07 — Player detail page

Example entity:

```text
Bukayo Saka
```

Hero area:

* Player avatar.
* Name.
* Entity type:

```text
Cầu thủ
```

* Current club.
* Number of related articles.
* Optional short description.

Main content:

```text
Tin mới nhất về Bukayo Saka
```

Display article list.

Optional secondary section:

```text
Câu chuyện đang được cập nhật
```

Do not include statistics, goals, market value, biography tables, or performance charts.

## Screen P08 — Club detail page

Example:

```text
Arsenal
```

Hero area:

* Crest.
* Club name.
* League.
* Number of recent articles.

Main content:

```text
Tin mới nhất về Arsenal
```

Optional compact row:

```text
Được nhắc đến nhiều
```

This may display related players and the coach.

Do not create squad tables, standings, or match fixtures.

## Screen P09 — Coach detail page

Example:

```text
Mikel Arteta
```

Hero area:

* Portrait.
* Name.
* Entity type:

```text
Huấn luyện viên
```

* Current club.
* Related article count.

Main content:

```text
Tin mới nhất về Mikel Arteta
```

Use the same article list component as other entity pages.

## Screen P10 — Global search active state

Create a desktop state where the search field is active.

Query example:

```text
man
```

Display a dropdown or search panel grouped into:

```text
CLB
Cầu thủ
HLV
Tin tức
```

Example results:

* Manchester United.
* Manchester City.
* Manuel Ugarte.
* A coach result.
* Two related news articles.

Each result must clearly indicate its result type.

Include:

```text
Xem tất cả kết quả
```

## Screen P11 — Search results page

Example title:

```text
Kết quả tìm kiếm cho “arsenal”
```

Include a large search field.

Tabs:

```text
Tất cả
Tin tức
Cầu thủ
CLB
HLV
```

The “Tất cả” tab should show grouped results:

* Matching club.
* Matching players or coaches.
* Matching articles.

Create these states as component variants:

* Results available.
* No results.
* Loading.
* Search error.

No-results message:

```text
Không tìm thấy kết quả phù hợp
```

Supporting text:

```text
Thử kiểm tra lại từ khóa hoặc tìm bằng tên khác.
```

## Screen P12 — Article detail page desktop

Create a highly readable editorial article page.

Top area:

* Small category or news label.
* Headline.
* Two-to-three-line summary.
* Metadata:

```text
Cập nhật 20 phút trước · Tổng hợp từ 4 nguồn
```

* Large cover image.

Article body:

* Narrow readable content column.
* Several mock paragraphs.
* One subheading.
* Optional pull quote.
* Comfortable spacing.

Below article:

### Related entities

Heading:

```text
Liên quan
```

Display:

* Club.
* Player.
* Coach.

Use larger entity chips or compact cards.

### Story timeline

Heading:

```text
Diễn biến câu chuyện
```

Display a vertical timeline:

```text
10:00 — Arsenal bắt đầu liên hệ với đại diện cầu thủ.
14:30 — Các điều khoản cá nhân được cho là đã thống nhất.
18:00 — Đề nghị đầu tiên chưa được câu lạc bộ chủ quản chấp nhận.
20:15 — Hai bên tiếp tục đàm phán.
```

Allow the timeline to be collapsed or expanded.

### Sources

Heading:

```text
Nguồn tham khảo
```

Display four source reference items.

### Related news

Heading:

```text
Tin liên quan
```

Display three medium news cards.

## Screen P13 — Article detail page mobile

Create a responsive mobile version.

Requirements:

* Headline remains prominent.
* Metadata wraps naturally.
* Image uses full content width.
* Body text remains at least 16px.
* Related entities become horizontal chips.
* Timeline remains readable.
* Source list becomes stacked.
* No sticky sidebars.

## Screen P14 — Story detail page

This page represents a developing football event rather than one generated news article.

Example title:

```text
Arsenal theo đuổi tiền đạo trẻ trong kỳ chuyển nhượng
```

Show:

* Current status:

```text
Đang cập nhật
```

* Current confirmation:

```text
Nhiều nguồn đưa tin
```

* Number of source articles.
* Last update time.
* Related players, clubs, and coaches.
* Full vertical timeline.
* Latest generated article.
* Previous article updates.
* Source list.

The page must remain simple and editorial. Do not make it look like a technical event log.

## Screen P15 — Public empty, loading, error, and 404 states

Create reusable states for:

* News list loading skeleton.
* Entity list loading skeleton.
* Empty article list.
* API error.
* 404 page.

404 copy:

```text
Không tìm thấy trang
```

Button:

```text
Quay lại trang chủ
```

# 7. Required admin and editorial screens

Organize these in a Figma page named:

```text
02 — Admin Dashboard
```

The admin area may use a left sidebar, but it must remain clean and simple.

Admin navigation:

* Tổng quan.
* Nguồn tin.
* Bài nguồn.
* Story.
* Bản nháp.
* Đã xuất bản.
* Lỗi xử lý.

Use the same brand palette, but prioritize information clarity over decoration.

## Screen A01 — Admin login

Include:

* FootballPulse logo.
* Email.
* Password.
* Login button.
* Error state.
* Loading state.

Vietnamese labels:

```text
Đăng nhập quản trị
Email
Mật khẩu
Đăng nhập
```

## Screen A02 — Admin dashboard

Heading:

```text
Tổng quan hệ thống
```

Metric cards:

* Bài thu thập hôm nay.
* Story mới.
* Bản nháp cần duyệt.
* Bài đã xuất bản.
* Lỗi đang chờ xử lý.

Pipeline overview:

```text
Thu thập → Chuẩn hóa → Nhận diện → Nhóm story → Tạo bản nháp → Xuất bản
```

Show a small recent activity list.

Avoid complex charts. One simple bar chart or trend line is enough.

## Screen A03 — Source management

Heading:

```text
Nguồn tin
```

Table columns:

* Tên nguồn.
* Loại: RSS or HTML.
* Trạng thái.
* Lần crawl gần nhất.
* Số bài gần nhất.
* Tình trạng lỗi.
* Actions.

Actions:

* Bật or tắt.
* Chạy crawl.
* Chỉnh sửa.
* Xem lịch sử.

Include a clean “Thêm nguồn” modal.

## Screen A04 — Crawl and pipeline detail

Heading:

```text
Chi tiết đợt thu thập
```

Show:

* Batch ID.
* Start time.
* End time.
* Status.
* Sources completed.
* Sources failed.
* Total articles collected.

Source attempt list with states:

* Thành công.
* Đang chạy.
* Thử lại.
* Lỗi.
* Timeout.
* Bị giới hạn tần suất.

Use clear status chips but avoid excessive colors.

## Screen A05 — Source articles list

Heading:

```text
Bài viết nguồn
```

Table or list columns:

* Original title.
* Source.
* Published time.
* Processing status.
* Duplicate status.
* Detected entities.
* Assigned story.

Filters:

* Source.
* Status.
* Duplicate.
* Date.

Include row detail drawer.

## Screen A06 — Source article detail

Show:

* Original title.
* Original URL.
* Source.
* Parsed text preview.
* Canonical URL.
* Content hash.
* Duplicate relationships.
* Detected entities.
* Event category.
* Assigned story.
* Processing history.

Actions:

* Xử lý lại.
* Sửa thực thể.
* Chuyển sang story khác.

The interface must remain readable and not expose raw JSON by default.

## Screen A07 — Story management

Heading:

```text
Story
```

Display a list with:

* Working title.
* Number of source articles.
* Related entities.
* Confirmation level.
* Last update.
* Draft status.

Filters:

* Active.
* Official.
* Needs review.
* Possible duplicate.

## Screen A08 — Story detail and editor correction

Show:

* Story title.
* Status.
* Confirmation level.
* Related entities.
* Source articles.
* Timeline.
* Claims.
* Similar story warning.

Actions:

* Merge story.
* Move source article.
* Correct entity.
* Request draft generation.

Make the main content readable, not overly technical.

## Screen A09 — Draft review and article editor

This is the most important admin screen.

Layout:

Left main area:

* Editable headline.
* Editable summary.
* Editable article body.
* Cover image placeholder.
* Related entities.
* Timeline preview.

Right review panel:

* Supporting sources.
* Generated claims.
* Warning messages.
* Generation provider.
* Prompt version.
* Draft status.

Primary actions:

```text
Lưu bản nháp
Yêu cầu tạo lại
Phê duyệt
Từ chối
Xuất bản
```

Require confirmation modal before publishing.

Show a warning example:

```text
Một thông tin trong bài chưa có đủ nguồn tham khảo.
```

## Screen A10 — Published content list

Heading:

```text
Bài đã xuất bản
```

Columns:

* Headline.
* Publication time.
* Related story.
* Editor.
* Revision.
* Views placeholder.
* Actions.

Actions:

* Xem bài.
* Chỉnh sửa.
* Tạo bản cập nhật.
* Gỡ xuất bản.

## Screen A11 — Processing errors

Heading:

```text
Lỗi xử lý
```

Display:

* Failed item.
* Service or processing stage.
* Error category.
* Attempt count.
* Last attempt.
* Current status.

Actions:

* Xem chi tiết.
* Thử lại.
* Bỏ qua.
* Đánh dấu đã xử lý.

Create empty and error states.

# 8. Responsive behavior

Create desktop versions for all required screens.

Create mobile versions at minimum for:

* Homepage.
* Navigation.
* Search.
* Latest news.
* Article detail.
* Player or club detail.
* Admin draft review as a simplified responsive layout.

Rules:

* Use a 390px mobile frame.
* Tap targets must be at least 44px.
* Body text must not be smaller than 16px.
* Tables should transform into cards or horizontal-scroll containers.
* Sidebars move below the main content.
* Search should remain easy to access.
* Entity chips may horizontally scroll.
* Avoid hiding critical content on mobile.

# 9. Prototype interactions

Create clickable prototype connections for these main flows.

## Public flow

```text
Homepage
→ Open article
→ Open related player
→ Return to article
→ Open related club
```

## Search flow

```text
Click search
→ Enter query
→ View grouped suggestions
→ View all results
→ Open entity or article
```

## Entity discovery flow

```text
Players listing
→ Player detail
→ Related article
```

## Story flow

```text
Article detail
→ View full story timeline
→ Story detail
```

## Admin editorial flow

```text
Admin dashboard
→ Story requiring review
→ Generate or open draft
→ Edit
→ Approve
→ Confirm publish
→ View published article
```

## Error recovery flow

```text
Dashboard
→ Processing errors
→ Open failure
→ Retry
```

# 10. Usability requirements

The design must prioritize:

* Clear visual hierarchy.
* Short navigation paths.
* Familiar news-reading behavior.
* Search discoverability.
* Readable article typography.
* Consistent entity presentation.
* Clear editorial states.
* Clear source attribution.
* Clear empty and error states.
* Minimal cognitive load.

Avoid:

* More than one primary CTA in the same visual area.
* More than three entity chips on a news card.
* More than four primary navigation links.
* Large numbers of category badges.
* Dense technical tables on public pages.
* Multiple sidebars.
* Hidden search.
* Tiny metadata.
* Excessive dashboard cards.
* Overly rounded playful components.

# 11. Accessibility

Ensure:

* WCAG-friendly color contrast.
* Visible keyboard focus states.
* Text labels for icons.
* Images have placeholder alt-text annotations.
* Status is not communicated by color alone.
* Form fields have visible labels.
* Errors appear near the relevant field.
* Interactive elements have clear hover, focus, active, loading, and disabled states.

# 12. Figma organization

Create these Figma pages:

```text
00 — Design System
01 — Public Website
02 — Admin Dashboard
03 — Responsive Mobile
04 — Components and States
05 — Prototype Flows
```

Inside the design system include:

* Color tokens.
* Typography scale.
* Spacing scale.
* Grid.
* Buttons.
* Inputs.
* Search.
* Chips.
* Status badges.
* News cards.
* Entity cards.
* Timeline.
* Tables.
* Modals.
* Toasts.
* Skeleton loading states.
* Empty states.
* Error states.

Use Auto Layout for all major sections.

Use component variants instead of duplicating components.

Name layers and frames clearly.

Make all mock content easy to replace later.

# 13. Final result

Generate a complete, coherent FootballPulse interface with all screens listed above.

The final design should communicate:

```text
FootballPulse là một trang tin bóng đá đơn giản, dễ đọc và có nguồn rõ ràng.
```

The public website should primarily feel like a clean football newspaper.

The admin area should feel like a focused editorial workspace.

The result must be visually consistent, easy to use, easy to read, and realistic enough to be implemented later with Next.js and TypeScript.
