export default function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* Base radial gradient — depth from top */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at top, #0a0a0f 0%, #050506 50%, #020203 100%)',
        }}
      />
      {/* Primary blob — top center, large indigo pool */}
      <div
        className="absolute -top-[200px] left-1/2 h-[900px] w-[1400px] -translate-x-1/2 rounded-full opacity-[0.18]"
        style={{
          background: '#0ea5e9',
          filter: 'blur(150px)',
          animation: 'float 10s ease-in-out infinite',
        }}
      />
      {/* Secondary blob — upper left, purple/pink */}
      <div
        className="absolute -left-[300px] top-[10%] h-[600px] w-[800px] rounded-full opacity-[0.10]"
        style={{
          background: 'linear-gradient(to bottom right, #7c3aed, #db2777)',
          filter: 'blur(120px)',
          animation: 'float-slow 8s ease-in-out infinite',
        }}
      />
      {/* Tertiary blob — right, indigo/blue */}
      <div
        className="absolute -right-[200px] top-[35%] h-[500px] w-[700px] rounded-full opacity-[0.10]"
        style={{
          background: 'linear-gradient(to bottom left, #0ea5e9, #2563eb)',
          filter: 'blur(100px)',
          animation: 'float 12s ease-in-out infinite reverse',
        }}
      />
      {/* Bottom accent — subtle glow at footer */}
      <div
        className="absolute bottom-0 left-1/2 h-[400px] w-[600px] -translate-x-1/2 rounded-full opacity-[0.08]"
        style={{
          background: '#0ea5e9',
          filter: 'blur(100px)',
          animation: 'float-slow 9s ease-in-out infinite 1s',
        }}
      />
    </div>
  )
}
