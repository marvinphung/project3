export const clubs = [
  { id: 'arsenal', name: 'Arsenal', league: 'Premier League', country: 'Anh', articles: 24, crest: '⚽', color: '#EF0107' },
  { id: 'man-utd', name: 'Manchester United', league: 'Premier League', country: 'Anh', articles: 18, crest: '🔴', color: '#DA291C' },
  { id: 'liverpool', name: 'Liverpool', league: 'Premier League', country: 'Anh', articles: 21, crest: '🔴', color: '#C8102E' },
  { id: 'man-city', name: 'Manchester City', league: 'Premier League', country: 'Anh', articles: 19, crest: '🔵', color: '#6CABDD' },
  { id: 'real-madrid', name: 'Real Madrid', league: 'La Liga', country: 'Tây Ban Nha', articles: 31, crest: '⚪', color: '#FEBE10' },
  { id: 'barcelona', name: 'Barcelona', league: 'La Liga', country: 'Tây Ban Nha', articles: 27, crest: '🔵', color: '#A50044' },
  { id: 'bayern', name: 'Bayern Munich', league: 'Bundesliga', country: 'Đức', articles: 16, crest: '🔴', color: '#DC052D' },
  { id: 'psg', name: 'Paris Saint-Germain', league: 'Ligue 1', country: 'Pháp', articles: 22, crest: '🔵', color: '#003370' },
]

export const players = [
  { id: 'mbappe', name: 'Kylian Mbappé', club: 'Real Madrid', position: 'Tiền đạo', articles: 28, img: 'https://images.unsplash.com/photo-1543326727-cf6c39e8f84c?w=200&h=200&fit=crop&auto=format' },
  { id: 'haaland', name: 'Erling Haaland', club: 'Manchester City', position: 'Tiền đạo', articles: 22, img: 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=200&h=200&fit=crop&auto=format' },
  { id: 'bellingham', name: 'Jude Bellingham', club: 'Real Madrid', position: 'Tiền vệ', articles: 19, img: 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=200&h=200&fit=crop&auto=format' },
  { id: 'saka', name: 'Bukayo Saka', club: 'Arsenal', position: 'Tiền vệ', articles: 17, img: 'https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=200&h=200&fit=crop&auto=format' },
  { id: 'vinicius', name: 'Vinícius Júnior', club: 'Real Madrid', position: 'Tiền đạo', articles: 25, img: 'https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=200&h=200&fit=crop&auto=format' },
  { id: 'yamal', name: 'Lamine Yamal', club: 'Barcelona', position: 'Tiền vệ', articles: 20, img: 'https://images.unsplash.com/photo-1566577739112-5180d4bf9390?w=200&h=200&fit=crop&auto=format' },
]

export const coaches = [
  { id: 'guardiola', name: 'Pep Guardiola', club: 'Manchester City', articles: 15, img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop&auto=format' },
  { id: 'arteta', name: 'Mikel Arteta', club: 'Arsenal', articles: 18, img: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&h=200&fit=crop&auto=format' },
  { id: 'slot', name: 'Arne Slot', club: 'Liverpool', articles: 12, img: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&h=200&fit=crop&auto=format' },
  { id: 'flick', name: 'Hansi Flick', club: 'Barcelona', articles: 14, img: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&h=200&fit=crop&auto=format' },
  { id: 'enrique', name: 'Luis Enrique', club: 'Paris Saint-Germain', articles: 11, img: 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=200&h=200&fit=crop&auto=format' },
  { id: 'alonso', name: 'Xabi Alonso', club: 'Bayer Leverkusen', articles: 13, img: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200&h=200&fit=crop&auto=format' },
]

export type Article = {
  id: string
  headline: string
  summary: string
  time: string
  sources: number
  status?: 'multi' | 'official' | 'updating'
  entities: { type: 'club' | 'player' | 'coach'; id: string; name: string }[]
  img: string
  body?: string[]
}

export const articles: Article[] = [
  {
    id: 'arsenal-transfer-1',
    headline: 'Arsenal tăng tốc đàm phán trong thương vụ chiêu mộ tiền đạo trẻ',
    summary: 'Nhiều nguồn cho biết Arsenal đã đạt tiến triển trong đàm phán với cầu thủ, nhưng hai câu lạc bộ vẫn chưa thống nhất mức phí chuyển nhượng.',
    time: '20 phút trước',
    sources: 4,
    status: 'multi',
    entities: [
      { type: 'club', id: 'arsenal', name: 'Arsenal' },
      { type: 'coach', id: 'arteta', name: 'Mikel Arteta' },
      { type: 'player', id: 'saka', name: 'Bukayo Saka' },
    ],
    img: 'https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=800&h=450&fit=crop&auto=format',
    body: [
      'Arsenal đang đẩy mạnh các cuộc đàm phán với đại diện của tiền đạo trẻ mà họ nhắm tới trong kỳ chuyển nhượng hè này. Theo thông tin từ nhiều nguồn uy tín, câu lạc bộ London đã có những tiến triển đáng kể trong việc thỏa thuận các điều khoản cá nhân với cầu thủ.',
      'Tuy nhiên, trở ngại lớn nhất vẫn là mức phí chuyển nhượng. Câu lạc bộ chủ quản hiện tại yêu cầu một khoản phí lên đến 80 triệu euro, trong khi Arsenal chỉ sẵn sàng trả tối đa 65 triệu euro. Hai bên hiện đang tiếp tục thương lượng.',
      'HLV Mikel Arteta đã xác nhận rằng đội bóng đang tìm kiếm sự tăng cường trong mùa hè này, nhưng từ chối tiết lộ cụ thể về tên cầu thủ hay câu lạc bộ liên quan.',
      'Thương vụ này dự kiến sẽ ngã ngũ trong vòng hai tuần tới khi cửa sổ chuyển nhượng sắp đóng lại. Arsenal cần ít nhất một tiền đạo mới để cạnh tranh ở Premier League và Champions League mùa tới.',
    ],
  },
  {
    id: 'man-utd-injury',
    headline: 'Manchester United cập nhật tình trạng chấn thương của tiền vệ trụ cột',
    summary: 'Câu lạc bộ xác nhận tiền vệ trụ cột sẽ vắng mặt từ bốn đến sáu tuần sau chấn thương trong buổi tập.',
    time: '1 giờ trước',
    sources: 3,
    entities: [
      { type: 'club', id: 'man-utd', name: 'Manchester United' },
    ],
    img: 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'real-madrid-renewal',
    headline: 'Real Madrid xác nhận gia hạn hợp đồng với một cầu thủ trẻ đầy triển vọng',
    summary: 'Hợp đồng mới kéo dài đến năm 2029 với mức lương được cải thiện đáng kể.',
    time: '2 giờ trước',
    sources: 2,
    status: 'official',
    entities: [
      { type: 'club', id: 'real-madrid', name: 'Real Madrid' },
      { type: 'player', id: 'bellingham', name: 'Jude Bellingham' },
    ],
    img: 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'guardiola-presser',
    headline: 'Pep Guardiola lên tiếng về kế hoạch nhân sự mùa giải mới',
    summary: 'HLV người Tây Ban Nha nói rõ quan điểm về việc giữ chân các cầu thủ chủ chốt.',
    time: '3 giờ trước',
    sources: 5,
    entities: [
      { type: 'coach', id: 'guardiola', name: 'Pep Guardiola' },
      { type: 'club', id: 'man-city', name: 'Manchester City' },
    ],
    img: 'https://images.unsplash.com/photo-1560272564-c83b66b1ad12?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'liverpool-tactics',
    headline: 'Liverpool chuẩn bị thay đổi hệ thống thi đấu trong trận sắp tới',
    summary: 'HLV Arne Slot được cho là sẽ chuyển sang sơ đồ 4-3-3 thay vì 4-2-3-1 quen thuộc.',
    time: '4 giờ trước',
    sources: 2,
    status: 'updating',
    entities: [
      { type: 'club', id: 'liverpool', name: 'Liverpool' },
      { type: 'coach', id: 'slot', name: 'Arne Slot' },
    ],
    img: 'https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'barcelona-tour',
    headline: 'Barcelona công bố danh sách cầu thủ tham dự chuyến du đấu hè',
    summary: 'Có 28 cầu thủ trong danh sách, trong đó có nhiều gương mặt trẻ từ đội dự bị.',
    time: '5 giờ trước',
    sources: 3,
    entities: [
      { type: 'club', id: 'barcelona', name: 'Barcelona' },
      { type: 'player', id: 'yamal', name: 'Lamine Yamal' },
      { type: 'coach', id: 'flick', name: 'Hansi Flick' },
    ],
    img: 'https://images.unsplash.com/photo-1459865264687-595d652de67e?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'bayern-scouting',
    headline: 'Bayern Munich theo dõi một hậu vệ tài năng tại Premier League',
    summary: 'Nhà vô địch Bundesliga đang tìm kiếm sự bổ sung ở vị trí hậu vệ trái.',
    time: '6 giờ trước',
    sources: 2,
    entities: [
      { type: 'club', id: 'bayern', name: 'Bayern Munich' },
    ],
    img: 'https://images.unsplash.com/photo-1515703407324-5f753afd8be8?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
  {
    id: 'mbappe-goals',
    headline: 'Kylian Mbappé chia sẻ về mục tiêu đầy tham vọng trong mùa giải mới',
    summary: 'Tiền đạo người Pháp muốn giành danh hiệu Quả bóng vàng đầu tiên trong sự nghiệp.',
    time: '7 giờ trước',
    sources: 4,
    entities: [
      { type: 'player', id: 'mbappe', name: 'Kylian Mbappé' },
      { type: 'club', id: 'real-madrid', name: 'Real Madrid' },
    ],
    img: 'https://images.unsplash.com/photo-1543326727-cf6c39e8f84c?w=800&h=450&fit=crop&auto=format',
    body: [],
  },
]

export const timeline = [
  { time: '10:00', event: 'Arsenal bắt đầu liên hệ với đại diện cầu thủ.', sources: 2 },
  { time: '14:30', event: 'Các điều khoản cá nhân được cho là đã thống nhất.', sources: 3, current: false },
  { time: '18:00', event: 'Đề nghị đầu tiên chưa được câu lạc bộ chủ quản chấp nhận.', sources: 4 },
  { time: '20:15', event: 'Hai bên tiếp tục đàm phán, dự kiến quyết định trong 48 giờ.', sources: 5, current: true },
]

export const sources = [
  { id: 1, name: 'BBC Sport', title: 'Arsenal in advanced talks for striker transfer', time: '18 phút trước', url: '#' },
  { id: 2, name: 'Sky Sports', title: 'Gunners accelerate move for top target this summer', time: '45 phút trước', url: '#' },
  { id: 3, name: 'The Athletic', title: 'Arsenal transfer: fee dispute remains key obstacle', time: '1 giờ trước', url: '#' },
  { id: 4, name: 'Fabrizio Romano', title: 'Arsenal working to agree full package, talks ongoing', time: '2 giờ trước', url: '#' },
]
