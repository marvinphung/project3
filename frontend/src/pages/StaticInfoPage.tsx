import { Link } from 'react-router'

type StaticPageType = 'about' | 'sources' | 'terms' | 'contact'

const contentMap: Record<StaticPageType, { title: string; subtitle: string; content: string[] }> = {
  about: {
    title: 'Giới thiệu về FootballPulse',
    subtitle: 'Nền tảng tổng hợp tin tức và timeline bóng đá thông minh tự động.',
    content: [
      'FootballPulse là hệ thống phân tích và tổng hợp tin tức bóng đá chuyên sâu, ứng dụng AI để phân loại thực thể (CLB, Cầu thủ, Huấn luyện viên) và tạo ra dòng thời gian (timeline) sự kiện chính xác theo các khung giờ.',
      'Dữ liệu được cập nhật liên tục từ các nguồn báo chí uy tín hàng đầu trên toàn cầu.',
    ],
  },
  sources: {
    title: 'Nguồn tin thu thập',
    subtitle: 'Danh mục các cơ quan báo chí và kênh thể thao đối tác được tổng hợp.',
    content: [
      'FootballPulse tổng hợp tin tức tự động từ các nguồn tin thể thao uy tín bao gồm BBC Sport, The Guardian, Sky Sports, Reuters, ESPN và nhiều hãng tin chính thống khác.',
      'Mọi bài viết đều lưu trữ và dẫn link trực tiếp tới nguồn báo gốc nhằm đảm bảo bản quyền và tính minh bạch thông tin.',
    ],
  },
  terms: {
    title: 'Điều khoản sử dụng',
    subtitle: 'Quy định và chính sách sử dụng dịch vụ FootballPulse.',
    content: [
      'FootballPulse cung cấp dịch vụ tổng hợp tin tức bóng đá hoàn toàn phi thương mại và phục vụ mục đích thông tin cá nhân.',
      'Bản quyền bài viết gốc thuộc về các cơ quan xuất bản tương ứng. Chúng tôi trích dẫn tóm tắt và ghi nguồn rõ ràng cho từng nội dung.',
    ],
  },
  contact: {
    title: 'Liên hệ',
    subtitle: 'Kênh kết nối và phản hồi với đội ngũ phát triển FootballPulse.',
    content: [
      'Mọi đóng góp ý kiến, phản hồi về dữ liệu hoặc yêu cầu hợp tác xin vui lòng gửi về email: contact@footballpulse.local',
      'Đội ngũ phát triển luôn sẵn sàng lắng nghe để nâng cao chất lượng dịch vụ.',
    ],
  },
}

export default function StaticInfoPage({ type }: { type: StaticPageType }) {
  const page = contentMap[type]

  return (
    <main className="max-w-[800px] mx-auto px-4 sm:px-6 py-10">
      <nav className="mb-6 text-xs text-[#6B7280]">
        <Link to="/" className="hover:underline">Trang chủ</Link> / <span>{page.title}</span>
      </nav>
      <article className="rounded-2xl border border-[#E5E7EB] bg-white p-8 shadow-sm">
        <h1 className="text-3xl font-extrabold text-[#111827] mb-2">{page.title}</h1>
        <p className="text-sm text-[#6B7280] mb-6">{page.subtitle}</p>
        <hr className="border-gray-100 my-6" />
        <div className="space-y-4 text-[16px] leading-[1.8] text-[#374151]">
          {page.content.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      </article>
    </main>
  )
}
