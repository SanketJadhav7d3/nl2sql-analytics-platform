import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm text-ink-primary leading-relaxed [&>*+*]:mt-3">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h3 className="text-base font-semibold text-ink-primary" {...p} />,
          h2: (p) => <h3 className="text-base font-semibold text-ink-primary" {...p} />,
          h3: (p) => <h4 className="text-sm font-semibold text-ink-primary" {...p} />,
          p: (p) => <p className="text-ink-primary" {...p} />,
          strong: (p) => <strong className="font-semibold text-ink-primary" {...p} />,
          em: (p) => <em className="text-ink-secondary" {...p} />,
          ul: (p) => <ul className="list-disc pl-5 space-y-1 marker:text-accent" {...p} />,
          ol: (p) => <ol className="list-decimal pl-5 space-y-1 marker:text-accent" {...p} />,
          li: (p) => <li className="text-ink-primary" {...p} />,
          code: (p) => <code className="text-xs font-mono bg-white/5 border border-hairline rounded px-1 py-0.5 text-series-3" {...p} />,
          a: (p) => <a className="text-accent-glow underline underline-offset-2" target="_blank" rel="noreferrer" {...p} />,
          blockquote: (p) => <blockquote className="border-l-2 border-accent/40 pl-3 text-ink-secondary" {...p} />,
          hr: () => <hr className="border-hairline" />,
          table: (p) => (
            <div className="overflow-x-auto rounded-lg border border-hairline">
              <table className="w-full text-xs tabular" {...p} />
            </div>
          ),
          thead: (p) => <thead className="bg-white/[0.04]" {...p} />,
          tbody: (p) => <tbody {...p} />,
          tr: (p) => <tr className="border-b border-hairline last:border-0" {...p} />,
          th: (p) => <th className="text-left px-3 py-2 font-medium text-ink-secondary whitespace-nowrap" {...p} />,
          td: (p) => <td className="px-3 py-2 text-ink-primary whitespace-nowrap" {...p} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
