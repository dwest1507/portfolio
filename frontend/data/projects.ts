export interface Project {
  slug: string
  title: string
  shortDescription: string
  thumbnail: string
  tags: string[]
  liveUrl: string
  repoUrl: string
  featured: boolean
  year: number
}

export const projects: Project[] = [
  {
    slug: 'ai-music-gen',
    title: 'Generate Music with AI',
    shortDescription:
      'Full-stack app that generates original music from text prompts using LLMs and Modal for serverless GPU inference.',
    thumbnail: '/projects/ai-music-gen.png',
    tags: ['Next.js', 'TypeScript', 'FastAPI', 'Python', 'Modal', 'Groq', 'LLM'],
    liveUrl: 'https://ai-music-gen.vercel.app',
    repoUrl: 'https://github.com/davidawest/ai-music-gen',
    featured: true,
    year: 2025,
  },
  {
    slug: 'nietzsche-chat',
    title: 'Chat with Nietzsche',
    shortDescription:
      'Conversational AI that channels Nietzsche using RAG over his complete works for philosophically grounded responses.',
    thumbnail: '/projects/nietzsche-chat.png',
    tags: ['Streamlit', 'Python', 'Groq', 'LLM/RAG', 'LangChain', 'FAISS'],
    liveUrl: 'https://nietzsche-chat.streamlit.app',
    repoUrl: 'https://github.com/davidawest/nietzsche-chat',
    featured: true,
    year: 2024,
  },
  {
    slug: 'baby-names',
    title: 'Baby Name Popularity',
    shortDescription:
      'Interactive explorer for US baby name trends with ML-powered popularity forecasting using XGBoost.',
    thumbnail: '/projects/baby-names.png',
    tags: ['Streamlit', 'Python', 'Pandas', 'Scikit-Learn', 'XGBoost', 'Data Visualization'],
    liveUrl: 'https://baby-names.streamlit.app',
    repoUrl: 'https://github.com/davidawest/baby-names',
    featured: false,
    year: 2024,
  },
  {
    slug: 'diamonds-price',
    title: 'Diamonds: Predicting Price',
    shortDescription:
      'Regression analysis and ML modeling to predict diamond prices from physical attributes, with full EDA in R.',
    thumbnail: '/projects/diamonds-price.png',
    tags: ['R', 'Scikit-Learn', 'Jupyter', 'Data Science'],
    liveUrl: '/projects/diamonds-predicting-price.html',
    repoUrl: 'https://github.com/davidawest/diamonds-price',
    featured: false,
    year: 2023,
  },
]

export const allTags = [
  'All',
  ...Array.from(new Set(projects.flatMap((p) => p.tags))).sort(),
]
