import FadeIn from '@/components/ui/FadeIn'

const BIO_LINES = [
  "I'm an AI Engineer with 5+ years building production ML systems and LLM-powered applications.",
  'My background spans the full AI stack — from RAG pipelines and fine-tuning to frontend interfaces that make AI accessible.',
  'Before pivoting to AI, I spent 8+ years in the defense industry, where precision, security, and reliability were non-negotiable.',
  'I bring that same rigor to every system I build.',
]

const SKILLS = {
  Languages: ['Python', 'TypeScript', 'JavaScript', 'R', 'SQL', 'Bash'],
  'AI / ML': ['LLMs', 'RAG', 'FAISS', 'Sentence Transformers', 'XGBoost', 'Scikit-Learn', 'PyTorch'],
  Frameworks: ['FastAPI', 'Next.js', 'React', 'LangChain', 'Streamlit'],
  'Cloud / Infra': ['AWS', 'Vercel', 'Railway', 'Modal', 'Docker'],
  APIs: ['Groq', 'OpenAI', 'Anthropic'],
}

const SKILL_VARIANTS: Record<string, string> = {
  Languages:
    'border-[#00ff88]/30 text-[#00ff88] bg-[#00ff88]/5',
  'AI / ML':
    'border-[#ff00ff]/30 text-[#ff00ff] bg-[#ff00ff]/5',
  Frameworks:
    'border-[#00d4ff]/30 text-[#00d4ff] bg-[#00d4ff]/5',
  'Cloud / Infra':
    'border-[#6b7280]/40 text-[#6b7280] bg-transparent',
  APIs:
    'border-[#ff9900]/30 text-[#ff9900] bg-[#ff9900]/5',
}

export default function AboutSection() {
  return (
    <section id="about" className="relative z-10 py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <FadeIn className="mb-12">
          <p className="mb-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#00ff88]">
            {'// 03. about'}
          </p>
          <h2 className="font-[family-name:var(--font-heading)] text-4xl font-bold uppercase tracking-wide text-[#e0e0e0] md:text-5xl">
            WHO I
            <br />
            <span className="text-[#00ff88]">AM_</span>
          </h2>
        </FadeIn>

        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          {/* Bio — terminal card */}
          <FadeIn delay={100}>
            <div className="clip-card relative border border-[#2a2a3a] bg-[#0a0a0f]">
              {/* Terminal header */}
              <div className="flex items-center gap-2 border-b border-[#2a2a3a] px-4 py-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-[#ff3366] opacity-80" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#ff9900] opacity-80" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#00ff88] opacity-80" />
                <span className="ml-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                  bio.md
                </span>
              </div>
              <div className="space-y-4 p-6 font-[family-name:var(--font-body)] text-sm leading-relaxed">
                {BIO_LINES.map((line, i) => (
                  <p key={i} className="text-[#e0e0e0]/80">
                    <span className="mr-2 text-[#00ff88]">&gt;</span>
                    {line}
                  </p>
                ))}
                <div className="mt-6 border-t border-[#2a2a3a] pt-4">
                  <a
                    href="https://www.linkedin.com/in/david-west-277509b1/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="clip-card-sm inline-flex items-center gap-2 border border-[#2a2a3a] px-4 py-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] transition-all duration-150 hover:border-[#00d4ff]/50 hover:text-[#00d4ff]"
                  >
                    LinkedIn ↗
                  </a>
                </div>
              </div>
            </div>
          </FadeIn>

          {/* Skills */}
          <FadeIn delay={200}>
            <div className="space-y-6">
              <p className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#6b7280]">
                {'// capabilities matrix'}
              </p>
              {Object.entries(SKILLS).map(([category, skills]) => (
                <div key={category}>
                  <div className="mb-2.5 flex items-center gap-3">
                    <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                      {category}
                    </span>
                    <span className="h-px flex-1 bg-[#2a2a3a]" />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill) => (
                      <span
                        key={skill}
                        className={`clip-card-sm border px-2.5 py-1 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.15em] ${SKILL_VARIANTS[category]}`}
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </FadeIn>
        </div>
      </div>
    </section>
  )
}
