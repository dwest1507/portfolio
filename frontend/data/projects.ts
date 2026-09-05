export interface Project {
  slug: string
  title: string
  shortDescription: string
  thumbnail: string
  tags: string[]
  liveUrl: string
  /** Overrides the default "Live App" link label (e.g. for a non-app destination). */
  liveLabel?: string
  repoUrl: string
  featured: boolean
  year: number
}

export const projects: Project[] = [
  {
    slug: 'portfolio',
    title: 'This Portfolio',
    shortDescription:
      'The site you are on: a RAG chatbot answering recruiter questions, with an eval suite that scores retrieval on every commit, gates CI, and publishes its own results.',
    thumbnail: '/projects/portfolio.jpeg',
    tags: [
      'Next.js',
      'TypeScript',
      'FastAPI',
      'Python',
      'Groq',
      'RAG',
      'FAISS',
      'BM25',
      'Evals',
      'CI/CD',
    ],
    liveUrl: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md',
    liveLabel: 'Eval Method ↗',
    repoUrl: 'https://github.com/dwest1507/portfolio',
    featured: true,
    year: 2026,
  },
  {
    slug: 'ai-music-gen',
    title: 'Generate Music with AI',
    shortDescription:
      'Full-stack app that turns a text prompt into an original track, proxying to the ACE-Step model running on serverless GPUs.',
    thumbnail: '/projects/ai-music-gen3.png',
    tags: [
      'Next.js',
      'TypeScript',
      'FastAPI',
      'Python',
      'Modal',
      'GPU Inference',
      'Generative Audio',
    ],
    liveUrl: 'https://ai-music-gen.vercel.app',
    repoUrl: 'https://github.com/dwest1507/ai-music-gen',
    featured: true,
    year: 2026,
  },
  {
    slug: 'nietzsche-chat',
    title: 'Chat with Nietzsche',
    shortDescription:
      'Streaming RAG chatbot that answers in Nietzsche’s voice, grounded in hybrid search over his complete works with cited passages.',
    thumbnail: '/projects/nietzsche-chat4.png',
    tags: ['Next.js', 'TypeScript', 'FastAPI', 'Python', 'Groq', 'RAG', 'FAISS', 'BM25'],
    liveUrl: 'https://nietzsche-chat-one.vercel.app',
    repoUrl: 'https://github.com/dwest1507/nietzsche-chat',
    featured: true,
    year: 2025,
  },
  {
    slug: 'baby-names',
    title: 'Baby Names Explorer',
    shortDescription:
      'Explorer for 145 years of US baby name data, with ARIMA popularity forecasts and a chatbot that answers questions in plain English.',
    thumbnail: '/projects/baby-names3.png',
    tags: [
      'Next.js',
      'TypeScript',
      'FastAPI',
      'Python',
      'Groq',
      'SQLite',
      'Time Series',
      'Data Visualization',
    ],
    liveUrl: 'https://baby-names-app-zeta.vercel.app/',
    repoUrl: 'https://github.com/dwest1507/baby-names-app',
    featured: false,
    year: 2025,
  },
  {
    slug: 'diamonds-price',
    title: 'Diamonds: Predicting Price',
    shortDescription:
      'Regression and tree-based modeling to predict diamond prices from physical attributes, with a full EDA written end to end in R.',
    thumbnail: '/projects/diamonds-price3.png',
    tags: ['R', 'Tidyverse', 'Random Forest', 'Data Science'],
    liveUrl: '/projects/diamonds-predicting-price.html',
    repoUrl: 'https://github.com/dwest1507/diamonds',
    featured: false,
    year: 2020,
  },
]

export const allTags = ['All', ...Array.from(new Set(projects.flatMap((p) => p.tags))).sort()]
