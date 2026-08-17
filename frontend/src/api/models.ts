export type EntityKind = 'club' | 'player' | 'coach'

export type Article = {
  id: string
  headline: string
  summary: string
  time: string
  sources: number
  status?: 'multi' | 'official' | 'updating'
  entities: { type: EntityKind; id: string; name: string }[]
  img: string
  body?: string[]
}

export type PublicEntity = Article['entities'][number] & { articleCount: number }
