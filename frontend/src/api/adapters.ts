import type { Article, EntityKind, PublicEntity } from './models'
import type { PublicArticle } from './client'

const fallbackImage =
  'https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=800&h=450&fit=crop&auto=format'

export function toArticle(article: PublicArticle): Article {
  return {
    id: article.slug,
    headline: article.title_vi,
    summary: article.excerpt_vi ?? article.body_vi,
    time: new Date(article.published_at).toLocaleString('vi-VN'),
    sources: 1,
    entities: article.entities.map((entity) => ({
      type: entity.entity_type.toLowerCase() as EntityKind,
      id: entity.slug,
      name: entity.name,
    })),
    img: fallbackImage,
  }
}

export function entitiesFromArticles(articles: PublicArticle[], kind?: EntityKind): PublicEntity[] {
  const entities = new Map<string, PublicEntity>()
  for (const article of articles) {
    for (const entity of article.entities) {
      const type = entity.entity_type.toLowerCase() as EntityKind
      if (kind && type !== kind) continue
      const key = `${type}:${entity.slug}`
      const current = entities.get(key)
      entities.set(key, {
        type,
        id: entity.slug,
        name: entity.name,
        articleCount: (current?.articleCount ?? 0) + 1,
      })
    }
  }
  return [...entities.values()].sort((a, b) => b.articleCount - a.articleCount || a.name.localeCompare(b.name))
}
