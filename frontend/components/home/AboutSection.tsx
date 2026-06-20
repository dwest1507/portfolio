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

export default function AboutSection() {
  return (
    <section id="about" className="relative z-10 border-t border-white/[0.06] py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <FadeIn className="mb-12">
          <p className="mb-2 font-mono text-[11px] tracking-widest text-[#0ea5e9]">About</p>
          <h2 className="text-4xl font-semibold tracking-tight text-[#ededef] md:text-5xl">
            Who I am
          </h2>
        </FadeIn>

        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          {/* Bio card */}
          <FadeIn delay={100}>
            <div className="rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.08] to-white/[0.02] p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_2px_20px_rgba(0,0,0,0.4)]">
              <p className="mb-5 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                Background
              </p>
              <div className="space-y-4">
                {BIO_LINES.map((line, i) => (
                  <p key={i} className="text-sm leading-relaxed text-[#8a8f98]">
                    {line}
                  </p>
                ))}
              </div>
              <div className="mt-6 border-t border-white/[0.06] pt-5">
                <a
                  href="https://www.linkedin.com/in/david-west-277509b1/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm text-[#8a8f98] transition-all duration-200 hover:border-white/[0.14] hover:text-[#ededef]"
                >
                  LinkedIn ↗
                </a>
              </div>
            </div>
          </FadeIn>

          {/* Skills */}
          <FadeIn delay={200}>
            <div className="space-y-6">
              <p className="font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                Capabilities
              </p>
              {Object.entries(SKILLS).map(([category, skills]) => (
                <div key={category}>
                  <div className="mb-3 flex items-center gap-3">
                    <span className="font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                      {category}
                    </span>
                    <span className="h-px flex-1 bg-white/[0.06]" />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full border border-white/[0.08] px-2.5 py-1 font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors duration-150 hover:border-white/[0.14] hover:text-[#ededef]"
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
