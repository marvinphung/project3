import type { Article } from '../data/mock'
import type { PublicArticle } from './client'

const fallbackImage =
  'https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=800&h=450&fit=crop&auto=format'

export function toArticle(article: PublicArticle): Article {
  return {
    id: article.slug,
    headline: article.title_vi,
    summary: article.body_vi,
    time: new Date(article.published_at).toLocaleString('vi-VN'),
    sources: 1,
    entities: article.entities.map((entity) => ({
      type: entity.entity_type.toLowerCase() as 'club' | 'player' | 'coach',
      id: entity.slug,
      name: entity.name,
    })),
    img: fallbackImage,
  }
}
